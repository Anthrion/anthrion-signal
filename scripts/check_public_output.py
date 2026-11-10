"""Validate every public manifest dependency, source passage and URL."""
import json
import re
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from anthrion_signal.models import Dataset, Signal
from anthrion_signal.discovery import is_public_award
from anthrion_signal.markets import MARKETS
from anthrion_signal.public_context import PUBLIC_EXCLUDE
from anthrion_signal.public_feed import current_summary, ranking_evidence, search_text
from anthrion_signal.public_compression import decode_public_bytes
from anthrion_signal.public_snapshot import PATHS, read_public_shard
from anthrion_signal.record_reviews import GUIDANCE_COUNTRIES, validate_guidance
from anthrion_signal.utils import clean, digest, retained_path

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
    if signal.reviewed_guidance:
        validate_guidance(signal, signal.reviewed_guidance)
        if not GUIDANCE_COUNTRIES.intersection(signal.countries) or signal.signal_type in {"AWARD", "RENEWAL_SIGNAL"} or signal.exclusion_reasons:
            raise ValueError("Guidance is only published for reviewed opportunities in supported countries")
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
    path = retained_path(path)
    manifest_only = path.name == "manifest.json"
    raw = json.loads(decode_public_bytes(path.read_bytes(), path.name))
    data = Dataset.model_validate(raw)
    loaded = {}
    if manifest_only and (data.signals or data.translations or not data.current_feed):
        raise ValueError("Expected a bootstrap manifest with separate current records")

    def check_page(page):
        if SECRETS.search(json.dumps(page, ensure_ascii=False)):
            raise ValueError("Credential-shaped material detected in public output")
        public_links(page)

    def load(relative):
        if relative not in loaded:
            page = read_public_shard(path.parent, relative)
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
            translation = page.get("translations", {}).get(item["id"])
            if item.get("is_summary") is True:
                pointer = data.current_feed.get("records", {}).get(item["id"])
                if not pointer or pointer.get("view") != "awards":
                    raise ValueError("Award index has no complete record")
                detail = load(pointer["url"])
                detail = detail["records"][item["id"]] if "records" in detail else detail
                if item != {**detail["signal"], "procedure_history": [], "is_summary": True} or translation != detail.get("translation"):
                    raise ValueError("Award index differs from its full source/translation pair")
                item = {key: value for key, value in item.items() if key != "is_summary"}
            signal = evidence_checked(item, translation)
            if not is_public_award(signal, datetime.now(UTC)):
                raise ValueError("Non-awarded record detected in award history")
            award_ids.add(signal.id)
    public_ids = {s.id for s in data.signals}
    if data.current_feed:
        if data.current_feed.get("version") != "1.0":
            raise ValueError("Unknown current-feed manifest version")
        root_manifest = raw if manifest_only else json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
        if root_manifest.get("signals") or root_manifest.get("current_feed") != data.current_feed:
            raise ValueError("Initial manifest and legacy dataset disagree")
        if not manifest_only:
            check_page(root_manifest)
        compressed_manifest = path.parent / "manifest.json.gz"
        if manifest_only and not compressed_manifest.exists():
            raise ValueError("Compressed bootstrap manifest is missing")
        if compressed_manifest.exists() and json.loads(decode_public_bytes(
                compressed_manifest.read_bytes(), compressed_manifest.name)) != root_manifest:
            raise ValueError("Compressed and plain root manifests disagree")
        details = {}
        history_ids = set()
        if manifest_only:
            public_ids = {ident for ident, pointer in data.current_feed["records"].items()
                          if pointer.get("view") == "opportunities"}
            if type(data.run.get("public_signals")) is not int or len(public_ids) != data.run["public_signals"]:
                raise ValueError("Current record count does not match the public manifest")
        anchor_ids = public_ids | award_ids
        bucket_ids = {}
        buyer_bucket_ids = {}
        for ident, pointer in data.current_feed["records"].items():
            page = load(pointer["url"])
            if "records" in page:
                if (pointer["url"].startswith("history/") and pointer.get("view") != "history"
                        or not isinstance(page["records"], dict) or ident not in page["records"]):
                    raise ValueError("Historical bucket does not match the requested record")
                bucket_ids.setdefault(pointer["url"], set()).add(ident)
                page = page["records"][ident]
            if page["signal"]["id"] != ident:
                raise ValueError("Record detail identity mismatch")
            signal = evidence_checked(page["signal"], page.get("translation"))
            if pointer.get("view") not in {"opportunities", "awards", "history", None}:
                raise ValueError("Unknown record detail view")
            expected_view = "opportunities" if ident in public_ids else "awards" if ident in award_ids else "history"
            if pointer.get("view") not in ({expected_view} if manifest_only else {expected_view, None}):
                raise ValueError("Record detail view does not match its published role")
            if manifest_only and ident in anchor_ids and not pointer["url"].startswith("records/"):
                raise ValueError("Public detail path does not match its published role")
            if ident in anchor_ids:
                history_ids.update(event["signal_id"] for event in signal.procedure_history + signal.buyer_history if event.get("signal_id"))
            if signal.buyer_history_ref:
                reference = signal.buyer_history_ref
                buyer = load(reference["url"])
                if "buyers" in buyer:
                    buyer_bucket_ids.setdefault(reference["url"], set()).add(signal.buyer_id)
                    buyer = buyer["buyers"][signal.buyer_id]
                if buyer["buyer_id"] != signal.buyer_id or len(buyer["records"]) != reference["count"]:
                    raise ValueError("Buyer history identity/count mismatch")
                if ident in anchor_ids:
                    history_ids.update(event["signal_id"] for event in buyer["records"])
            details[ident] = (signal, page.get("translation"), page["signal"])
        context_ids = {ident for ident, pointer in data.current_feed["records"].items() if pointer.get("view") == "history"}
        if (set(details) != public_ids | award_ids | context_ids or context_ids - history_ids
                or context_ids & (public_ids | award_ids) or public_ids & award_ids):
            raise ValueError("Detail manifest is missing public records or includes unlinked history")
        for relative, identifiers in bucket_ids.items():
            if set(loaded[relative]["records"]) != identifiers:
                raise ValueError("Historical bucket includes records outside its manifest")
        for relative, identifiers in buyer_bucket_ids.items():
            if set(loaded[relative]["buyers"]) != identifiers:
                raise ValueError("Buyer bucket includes identities outside its manifest")
        current_markets = data.current_feed["markets"]
        expected_markets = {market: set() for market in MARKETS}
        if manifest_only:
            if set(current_markets) != set(MARKETS):
                raise ValueError("Current indexes do not cover the configured markets")
            for ident in public_ids:
                signal = details[ident][0]
                memberships = {market for market, countries in MARKETS.items()
                               if set(countries).intersection(signal.countries)}
                if not memberships or set(data.current_feed["records"][ident]["markets"]) != memberships:
                    raise ValueError("Current detail market membership mismatch")
                for market in memberships:
                    expected_markets[market].add(ident)
        for market, pointer in current_markets.items():
            page = load(pointer["url"])
            if len(page["signals"]) != pointer["count"]:
                raise ValueError("Current index manifest count mismatch")
            index_ids = {s["id"] for s in page["signals"]}
            if len(index_ids) != len(page["signals"]):
                raise ValueError("Duplicate current index identity")
            if manifest_only and (not pointer["url"].startswith(f"current/{market}-")
                                  or index_ids != expected_markets[market]):
                raise ValueError("Current index membership does not match its record details")
            expected_translations = {}
            for item in page["signals"]:
                if item["id"] not in public_ids:
                    raise ValueError("Current index contains an unavailable record")
                signal, translation, detail = details[item["id"]]
                if item.get("search_text") != search_text(signal, translation):
                    raise ValueError("Current index lost complete source/English search text")
                if "ranking_evidence" in item and item["ranking_evidence"] != ranking_evidence(
                        {"capability_evidence": signal.capability_evidence}):
                    raise ValueError("Current index ranking evidence differs from its validated detail")
                if market not in data.current_feed["records"][signal.id]["markets"]:
                    raise ValueError("Current index market membership mismatch")
                if manifest_only:
                    if item != current_summary(detail, signal, translation):
                        raise ValueError("Current index differs from its full record")
                    if translation:
                        expected_translations[signal.id] = {**translation, "description": ""}
            if manifest_only and page.get("translations", {}) != expected_translations:
                raise ValueError("Current index translations differ from their full records")
    if inventory_path:
        # Export retains old content-addressed files for readers already in flight.
        # Cache only the validated graph, never unrelated or obsolete files.
        files = {path.name, *loaded}
        if data.current_feed:
            files.add("manifest.json")
            if (path.parent / "manifest.json.gz").exists():
                files.add("manifest.json.gz")
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(json.dumps(sorted(files)) + "\n", encoding="utf-8")
    return len(public_ids), len(award_ids), len(loaded)


if __name__ == "__main__":
    try:
        current, awards, pages = check_public_output(Path("app/public/data/manifest.json"), Path("tmp/public-data-files.json"))
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from None
    print(f"Public output checked: {current} current records, {awards} awards and {pages} hashed data files; evidence and links verified.")
