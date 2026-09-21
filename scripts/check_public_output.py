"""Validate every public manifest dependency, source passage and URL."""
import json
import re
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from anthrion_signal.models import Dataset, Signal
from anthrion_signal.discovery import is_public_award
from anthrion_signal.public_context import PUBLIC_EXCLUDE
from anthrion_signal.public_feed import search_text
from anthrion_signal.utils import clean, digest

PATHS = re.compile(r"(?:awards|current)/[A-Z]+-[a-f0-9]{16}\.json|records/[A-Za-z0-9_-]{1,100}-[a-f0-9]{16}\.json|buyers/buyer_[a-f0-9]{20}-[a-f0-9]{16}\.json")
SECRETS = re.compile(r"AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9_]{20,}|-----BEGIN .*PRIVATE KEY-----")


def public_links(value, key=""):
    if isinstance(value, dict):
        for field, item in value.items():
            public_links(item, field)
    elif isinstance(value, list):
        for item in value:
            public_links(item, key)
    elif isinstance(value, str) and value and (key.endswith("url") or key in {"source_urls", "website"}):
        if key == "url" and PATHS.fullmatch(value):
            return
        try:
            parsed = urlparse(value)
            if parsed.scheme in {"https", "http"} and parsed.netloc and not parsed.username and not parsed.password:
                return
        except ValueError:
            pass
        raise ValueError("Unsafe link detected in public output")


def evidence_checked(item, translation):
    signal = Signal.model_validate(item)
    if PUBLIC_EXCLUDE.intersection(item):
        raise ValueError("Retired model analysis detected in public output")
    evidenced = set()
    for evidence in signal.capability_evidence:
        field = evidence.get("field")
        if field not in {"title", "description"} or evidence.get("source_hash") != digest([signal.title, signal.description]):
            raise ValueError("Capability evidence has an invalid source field/hash")
        original = getattr(signal, field)
        reference = original
        if evidence.get("basis") == "english_translation":
            if not translation or translation.get("source_hash") != digest([signal.title, signal.description]):
                raise ValueError("Capability evidence relies on a missing/stale translation")
            reference = translation.get(field, "")
            if evidence.get("original_quote") != original:
                raise ValueError("Translated evidence lost its original field")
        quote = evidence.get("quote", "")
        if not quote or clean(unescape(quote), limit=None) not in clean(unescape(reference), limit=None):
            raise ValueError("Capability passage cannot be traced to its source")
        if evidence.get("source_url") not in signal.source_urls + [signal.primary_source_url]:
            raise ValueError("Capability evidence points outside its notice provenance")
        evidenced.add(evidence.get("capability"))
    if set(signal.matched_capabilities) - evidenced:
        raise ValueError("Displayed capability has no public source evidence")
    for requirement in signal.participation_requirements:
        if requirement.get("status") != "needs_checking" or requirement.get("company_evidence") is not None:
            raise ValueError("Public source facts cannot assert private company qualification")
        quote = requirement.get("source_quote", "")
        if not quote or clean(quote, limit=None) not in clean(signal.description + " " + (signal.eligibility_text or ""), limit=None):
            raise ValueError("Participation requirement cannot be traced to its source")
        if requirement.get("translated_quote") and (not translation or
                requirement.get("source_hash") != digest([signal.title, signal.description]) or
                requirement["translated_quote"] not in translation.get("description", "")):
            raise ValueError("Participation requirement relies on a missing/stale translation")
    for document in signal.documents:
        if document.content_hash and not re.fullmatch(r"[a-f0-9]{64}", document.content_hash):
            raise ValueError("Document hash is invalid")
        if document.pages and not (document.content_hash and document.retrieved_at and document.reuse_basis):
            raise ValueError("Document excerpts lack retrieval or reuse evidence")
    for deadline in signal.deadlines:
        if deadline.precision != "instant" and deadline.instant is not None:
            raise ValueError("Untimed deadline acquired an invented exact instant")
    return signal


def check_public_output(path, inventory_path=None):
    raw = json.loads(path.read_text(encoding="utf-8"))
    data = Dataset.model_validate(raw)
    loaded = {}

    def check_page(page):
        if SECRETS.search(json.dumps(page, ensure_ascii=False)):
            raise ValueError("Credential-shaped material detected in public output")
        public_links(page)

    def load(relative):
        if not PATHS.fullmatch(relative):
            raise ValueError("Unsafe public data path")
        if relative not in loaded:
            page = json.loads((path.parent / relative).read_text(encoding="utf-8"))
            if page.get("schema_version") != "1.0" or not relative.endswith(digest(page)[:16] + ".json"):
                raise ValueError("Public content hash/schema mismatch")
            check_page(page)
            loaded[relative] = page
        return loaded[relative]

    check_page(raw)
    for signal in raw["signals"]:
        evidence_checked(signal, raw.get("translations", {}).get(signal["id"]))
    award_ids = set()
    for manifest in data.award_history.values():
        page = load(manifest["url"])
        if len(page["signals"]) != manifest["count"]:
            raise ValueError("Award history manifest count mismatch")
        for item in page["signals"]:
            signal = evidence_checked(item, page.get("translations", {}).get(item["id"]))
            if not is_public_award(signal, datetime.now(UTC)):
                raise ValueError("Non-awarded record detected in award history")
            award_ids.add(signal.id)
    if data.current_feed:
        if data.current_feed.get("version") != "1.0":
            raise ValueError("Unknown current-feed manifest version")
        root_manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
        if root_manifest.get("signals") or root_manifest.get("current_feed") != data.current_feed:
            raise ValueError("Initial manifest and legacy dataset disagree")
        check_page(root_manifest)
        details = {}
        history_ids = set()
        public_ids = {s.id for s in data.signals}
        anchor_ids = public_ids | award_ids
        for ident, pointer in data.current_feed["records"].items():
            page = load(pointer["url"])
            if page["signal"]["id"] != ident:
                raise ValueError("Record detail identity mismatch")
            signal = evidence_checked(page["signal"], page.get("translation"))
            if pointer.get("view") not in {"opportunities", "awards", "history", None}:
                raise ValueError("Unknown record detail view")
            expected_view = "opportunities" if ident in public_ids else "awards" if ident in award_ids else "history"
            if pointer.get("view") not in {expected_view, None}:
                raise ValueError("Record detail view does not match its published role")
            if ident in anchor_ids:
                history_ids.update(event["signal_id"] for event in signal.procedure_history + signal.buyer_history if event.get("signal_id"))
            if signal.buyer_history_ref:
                reference = signal.buyer_history_ref
                buyer = load(reference["url"])
                if buyer["buyer_id"] != signal.buyer_id or len(buyer["records"]) != reference["count"]:
                    raise ValueError("Buyer history identity/count mismatch")
                if ident in anchor_ids:
                    history_ids.update(event["signal_id"] for event in buyer["records"])
            details[ident] = (signal, page.get("translation"))
        context_ids = {ident for ident, pointer in data.current_feed["records"].items() if pointer.get("view") == "history"}
        if set(details) != public_ids | award_ids | context_ids or context_ids - history_ids or context_ids & (public_ids | award_ids):
            raise ValueError("Detail manifest is missing public records or includes unlinked history")
        for market, pointer in data.current_feed["markets"].items():
            page = load(pointer["url"])
            if len(page["signals"]) != pointer["count"]:
                raise ValueError("Current index manifest count mismatch")
            if len({s["id"] for s in page["signals"]}) != len(page["signals"]):
                raise ValueError("Duplicate current index identity")
            for item in page["signals"]:
                if item["id"] not in public_ids:
                    raise ValueError("Current index contains an unavailable record")
                signal, translation = details[item["id"]]
                if item.get("search_text") != search_text(signal, translation):
                    raise ValueError("Current index lost complete source/English search text")
                if market not in data.current_feed["records"][signal.id]["markets"]:
                    raise ValueError("Current index market membership mismatch")
    if inventory_path:
        # Export retains old content-addressed files for readers already in flight.
        # Cache only the validated graph, never unrelated or obsolete files.
        files = ["current.json", *loaded]
        if data.current_feed:
            files.append("manifest.json")
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(json.dumps(sorted(files)) + "\n", encoding="utf-8")
    return len(data.signals), len(award_ids), len(loaded)


if __name__ == "__main__":
    try:
        current, awards, pages = check_public_output(Path("app/public/data/current.json"), Path("tmp/public-data-files.json"))
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from None
    print(f"Public output checked: {current} current records, {awards} awards and {pages} hashed data files; evidence and links verified.")
