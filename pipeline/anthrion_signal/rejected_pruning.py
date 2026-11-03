"""Conservative removal of unused, old, explicitly non-technical notices.

Awards and uncertain scope are never candidates. Every stored version must pass;
canonical records, research pages, translations and procurement relatives win.
"""
import gzip
import io
import json
import re
import subprocess
from datetime import timedelta

from .discovery import lifecycle, prefilter
from .models import Signal
from .rejected_compaction import file_hash, safe_path
from .rejected_store import directory, encode_bucket, read_bucket, unpack_versions
from .translation import field_key
from .utils import atomic_bytes, digest, parse_date, read_json, retained_path

POLICY = "unused-physical-inactive-1"
INACTIVE = {"EXPIRED", "CLOSED", "CANCELLED", "WITHDRAWN"}
# Positive non-technical CPV evidence, rather than absence of a technology match.
PHYSICAL_CPV = ("03", "15", "18", "19", "44", "45")
REASONS = {
    "Physical goods or works without a stated technology-services scope.",
    "Non-technology service delivery without a stated software, AI or systems scope.",
    "Building renovation without a separately stated business-application or AI delivery scope.",
    "Construction, building control or physical maintenance without a separately stated business-application, Salesforce or AI delivery scope.",
    "Physical construction, refurbishment, engineering or ecological works without a separately stated business-application, Salesforce or AI delivery scope.",
}
# These are preservation hints only. False positives keep extra history.
RENEWAL = re.compile(r"renew|extend|extension|option|reprocure|re-procure|retender|re-tender|"
                     r"verläng|verlaeng|erneuer|reconduc|renouvel|prolong|prorog|rinnovo|"
                     r"renova|verleng|förläng|forlæng|forleng|uusimi|jatko|επέκτα|ανανέω", re.I)
TECHNOLOGY = re.compile(r"salesforce|mulesoft|agentforce|software|logiciel|crm\b|saas\b|"
                         r"digital|digitale|informatics|informatique|ai\b|artificial intelligence|"
                         r"machine learning|künstliche intelligenz|dynamics|servicenow", re.I)


def identity_keys(row):
    # Deliberately ignore lot suffixes: a cancellation on a different lot is
    # still a reason to retain the whole procurement's evidence.
    return {"id:" + row["id"], *(
        prefix + str(value) for prefix, values in (
            ("ocid:", [row.get("ocid")]), ("procedure:", [row.get("procedure_id")]),
            ("reference:", row.get("procedure_identifiers", []) + row.get("external_ids", [])),
            ("url:", row.get("source_urls", []) + [row.get("primary_source_url")]),
            ("id:", [row.get("related_signal_id")]),
        ) for value in values if value)}


def protected_records(root, manifest):
    if not isinstance(manifest.get("current_feed", {}).get("records"), dict):
        raise ValueError("A validated public record manifest is required before pruning")
    ids = set(manifest["current_feed"]["records"])
    ids.update(row["id"] for row in read_json(root / "config/record_reviews.json", {}).get("records", []))
    ids.update(read_json(root / "data/translation/translations.en.json", {}).get("signals", {}))
    # Reviewed translations use a separate ledger; keep every mentioned ID even
    # if its translated passage is currently absent from the display overlay.
    reviewed = (root / "config/reviewed_translations.json")
    if reviewed.exists():
        ids.update(re.findall(r"sig_[a-zA-Z0-9_]+", reviewed.read_text(encoding="utf-8")))
    keys = set()
    canonical = retained_path(root / "data/signals.jsonl")
    for path in [canonical, *sorted((root / "data/archive").glob("*.jsonl.gz"))]:
        if not path.exists():
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    ids.add(row["id"])
                    keys.update(identity_keys(row))
    return ids, keys


def disposable(signal, now, cached_fields, *, days=180, document_urls=()):
    if (lifecycle(signal, now)[0] not in INACTIVE or signal.signal_type in {"AWARD", "RENEWAL_SIGNAL"}
            or signal.prefilter_score != 0 or not REASONS.intersection(signal.exclusion_reasons)
            or not signal.cpv_codes or not all(code.startswith(PHYSICAL_CPV) for code in signal.cpv_codes)):
        return False
    if any((signal.matched_capabilities, signal.capability_evidence, signal.scope_evidence,
            signal.analysis, signal.reviewed_guidance, signal.prefilter_matches, signal.framework,
            signal.contract_start, signal.contract_end, signal.extension_end, signal.winners,
            signal.award_date, signal.award_statuses, signal.incumbent_supplier,
            signal.related_signal_id, signal.renewal_basis, signal.procedure_history, signal.buyer_history)):
        return False
    if (any(d.url in document_urls or d.status != "linked" or d.content_hash or d.pages or d.previous_revisions
            for d in signal.documents)
            or any(field_key(text) in cached_fields for text in (signal.title, signal.description))):
        return False
    dates = [signal.updated_at, signal.published_at, signal.deadline_at, *signal.response_deadlines,
             *(lot.deadline_at for lot in signal.lots), *(d.instant or d.date for d in signal.deadlines)]
    try:
        dated = [parse_date(value) for value in dates if value]
        if not dated or any(d is None for d in dated) or max(dated) >= now - timedelta(days=days):
            return False
    except (ValueError, TypeError):
        return False
    text = " ".join([signal.title, signal.description, signal.eligibility_text or "",
                     *(lot.title + " " + lot.description for lot in signal.lots)])
    return not (RENEWAL.search(text) or TECHNOLOGY.search(text))


def plan_pruning(root, manifest, now, config):
    protected, kept_keys = protected_records(root, manifest)
    fields = set(read_json(root / "data/translation/cache.json", {}).get("fields", {}))
    document_urls = set(read_json(root / "data/documents/index.json", {}))
    candidates, candidate_keys, fingerprints = {}, {}, {}
    for path in sorted((directory(root) / "compact").glob("*.jsonl.gz")):
        fingerprints[path] = file_hash(safe_path(root, path))
        for identifier, envelope in read_bucket(path).items():
            versions = list(unpack_versions(envelope))
            keys = set().union(*(identity_keys(row) for row in versions))
            eligible = identifier not in protected
            signals = []
            if eligible:
                signals = [Signal.model_validate(row) for row in versions]
                eligible = all(disposable(s, now, fields, document_urls=document_urls) for s in signals)
            if eligible:
                # Re-evaluate the small candidate set using today's discovery
                # rules; stale historic exclusions cannot authorize deletion.
                prefilter(signals, config["company_profile"], config["search_terms"], config["capabilities"], {})
                eligible = all(disposable(s, now, fields, document_urls=document_urls) for s in signals)
            if eligible:
                candidates[identifier] = {"id": identifier, "title": envelope["current"]["title"],
                                          "url": envelope["current"]["primary_source_url"],
                                          "bucket": path.name, "hashes": sorted(digest(row) for row in versions),
                                          "reason": "Every version is old, inactive and explicitly physical/non-technical; no retained dependency."}
                candidate_keys[identifier] = keys
            else:
                kept_keys.update(keys)
    # Preserve transitive procurement relatives, including closure/update rows.
    while blocked := [sid for sid in candidates if candidate_keys[sid].intersection(kept_keys)]:
        for sid in blocked:
            kept_keys.update(candidate_keys[sid])
            del candidates[sid]
    return candidates, fingerprints


def apply_pruning(root, candidates, fingerprints):
    if (sorted(fingerprints) != sorted((directory(root) / "compact").glob("*.jsonl.gz"))
            or any(file_hash(safe_path(root, p)) != value for p, value in fingerprints.items())):
        raise ValueError("Rejected inputs changed after the pruning plan")
    removed_bytes = 0
    for name in sorted({row["bucket"] for row in candidates.values()}):
        path = safe_path(root, directory(root) / "compact" / name)
        rows = read_bucket(path)
        before = path.stat().st_size
        for sid in [sid for sid in rows if sid in candidates]:
            del rows[sid]
        body = encode_bucket(rows)
        atomic_bytes(path, body)
        if path.read_bytes() != body:
            raise ValueError("Pruned bucket write did not round-trip")
        removed_bytes += before - len(body)
    return removed_bytes


def recoverable_candidates(root, commit, candidates):
    """Never delete a new, uncommitted observation without a recovery copy.

    A scheduled run can collect old notices for the first time. Only versions
    already present in the recorded Git revision qualify for physical removal.
    """
    if not candidates:
        return {}
    paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", commit, "--", "data/discovery/rejected"], cwd=root,
        text=True).splitlines()
    missing = {sid: set(row["hashes"]) for sid, row in candidates.items()}
    buckets = {row["bucket"] for row in candidates.values()}
    for path in paths:
        if not path.endswith(".jsonl.gz") or ("/compact/" in path and path.rsplit("/", 1)[-1] not in buckets):
            continue
        body = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)
        with gzip.open(io.BytesIO(body), "rt", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                entry = json.loads(line)
                identifier = entry["current"]["id"] if "/compact/" in path else entry["id"]
                if identifier in missing:
                    rows = unpack_versions(entry) if "/compact/" in path else [entry]
                    missing[identifier].difference_update(digest(row) for row in rows)
    return {sid: row for sid, row in candidates.items() if not missing[sid]}
