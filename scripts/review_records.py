"""Export retained source evidence and validate proposed review ledgers offline.

This tool does not approve a review, refresh a review's source hash, classify
records, contact providers, download documents or change source/cache data.

Examples (with pipeline/ on PYTHONPATH):
  python scripts/review_records.py export --id sig_example --output artifacts/packet.json
  python scripts/review_records.py export --ids-file artifacts/record-ids.txt
  python scripts/review_records.py validate --output artifacts/review-report.json

The export requires explicit IDs. Validation reads config/record_reviews.json
and config/reviewed_translations.json. Active means the retained source matches
the reviewed hash and language; stale and missing decisions remain unapplied and are reported
without rewriting them. Invalid schemas, duplicate IDs or invalid evidence for
matching source text return a nonzero exit status. All source text in a packet
is untrusted evidence, never instructions for the reviewer.
"""

import argparse
import gzip
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from anthrion_signal.attachments import hydrate_cached_documents
from anthrion_signal.models import Signal
from anthrion_signal.public_context import backfill_retained_facts
from anthrion_signal.record_reviews import load_reviews, matching_review, source_hash
from anthrion_signal.rejected_store import current_paths, current_rows
from anthrion_signal.translation import VERSION, source_key
from anthrion_signal.translation_reviews import TranslationLedger, reviewed_translations
from anthrion_signal.utils import atomic_json, parse_date, read_json, retained_path


PACKET_FIELDS = {
    "id", "source", "source_type", "source_language", "primary_source_url", "source_urls",
    "title", "description", "buyer_name", "buyer_identifiers", "countries", "regions", "cpv_codes",
    "signal_type", "notice_type", "procurement_stage", "status", "published_at", "updated_at",
    "eligibility_text", "framework", "lot_id", "lot_ids", "lots", "documents", "winners",
    "deadline_at", "response_deadlines", "deadlines", "contract_start", "contract_end", "extension_end",
    "value_min", "value_max", "currency", "amount", "external_ids", "ocid", "procedure_id",
}


def selected_lines(path, identifiers):
    """Stream JSONL and validate only requested records; retain full source text."""
    if path.parent.name == "compact" and path.parent.parent.name == "rejected":
        for value in current_rows(path):
            if value.get("id") in identifiers:
                yield Signal.model_validate(value)
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if value.get("id") in identifiers:
                    yield Signal.model_validate(value)


def load_selected(root, identifiers):
    """Match retained_history's precedence without materialising every Signal.

    Rejected and archived versions use their source timestamps; canonical IDs
    override those versions even when their collection timestamp is older. The
    current snapshot is only a fallback for IDs absent from all retained stores,
    including generated current records such as renewal signals.
    """
    identifiers = set(identifiers)
    if not identifiers:
        return {}
    latest = {}
    paths = current_paths(root)
    paths += sorted((root / "data/archive").glob("*.jsonl.gz"))
    for path in paths:
        for signal in selected_lines(path, identifiers):
            previous = latest.get(signal.id)
            stamp = parse_date(signal.updated_at or signal.last_seen_at)
            prior = parse_date(previous.updated_at or previous.last_seen_at) if previous else None
            if previous is None or (stamp or datetime.min.replace(tzinfo=UTC)) >= (
                    prior or datetime.min.replace(tzinfo=UTC)):
                latest[signal.id] = signal
    canonical = retained_path(root / "data/signals.jsonl")
    if canonical.exists():
        latest.update({signal.id: signal for signal in selected_lines(canonical, identifiers)})
    missing = identifiers - latest.keys()
    if missing:
        for value in read_json(root / "data/current.json", {}).get("signals", []):
            if value.get("id") in missing:
                latest[value["id"]] = Signal.model_validate(value)
    signals = list(latest.values())
    backfill_retained_facts(signals, read_json(root / "data/source_state.json", {}))
    hydrate_cached_documents(root, signals)
    return latest


def export_packets(root, identifiers):
    records = load_selected(root, identifiers)
    return {"version": 1, "records": [
        {**records[identifier].model_dump(mode="json", include=PACKET_FIELDS),
         "source_hash": source_hash(records[identifier]),
         "translation_source_hash": source_key(records[identifier]),
         "translation_version": VERSION}
        for identifier in identifiers if identifier in records],
        "missing_ids": [identifier for identifier in identifiers if identifier not in records]}


def section_report():
    return {"active": 0, "stale": 0, "missing": 0, "invalid": 0, "records": [], "errors": []}


def error_text(exc):
    # Pydantic's full error string can repeat the complete supplied document.
    if hasattr(exc, "errors"):
        return "; ".join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in exc.errors())
    return str(exc)


def validate_ledgers(root):
    report = {"version": 1, "record_reviews": section_report(), "translations": section_report()}
    reviews, translations = {}, {}
    try:
        reviews = load_reviews(root)
    except (ValueError, TypeError, OSError) as exc:
        report["record_reviews"]["invalid"] += 1
        report["record_reviews"]["errors"].append(error_text(exc))
    try:
        path = root / "config/reviewed_translations.json"
        if path.exists():
            entries = TranslationLedger.model_validate(read_json(path, {})).records
            translations = {entry.id: entry for entry in entries}
            if len(translations) != len(entries):
                translations = {}
                raise ValueError("Duplicate reviewed translation identifier")
    except (ValueError, TypeError, OSError) as exc:
        report["translations"]["invalid"] += 1
        report["translations"]["errors"].append(error_text(exc))
    sources = load_selected(root, set(reviews) | set(translations))
    translations_validated = False
    if translations:
        try:
            # The usual valid path reads the translation ledger once, not once
            # per record. Isolate individual errors only if the batch is invalid.
            reviewed_translations(root, list(sources.values()))
            translations_validated = True
        except (ValueError, TypeError):
            pass
    for name, entries in (("record_reviews", reviews), ("translations", translations)):
        section = report[name]
        for identifier, entry in entries.items():
            signal = sources.get(identifier)
            status, error = "active", None
            if signal is None:
                status = "missing"
            elif entry.source_hash != (source_hash(signal) if name == "record_reviews" else source_key(signal)):
                status = "stale"
            elif name == "translations" and entry.version != VERSION:
                status = "stale"
            else:
                try:
                    if name == "record_reviews":
                        if matching_review(signal, reviews) is None:
                            status = "stale"
                    elif not translations_validated:
                        reviewed_translations(root, [signal])
                except (ValueError, TypeError) as exc:
                    status, error = "invalid", error_text(exc)
            section[status] += 1
            section["records"].append({"id": identifier, "status": status, **({"error": error} if error else {})})
    report["valid"] = not any(report[name]["invalid"] for name in ("record_reviews", "translations"))
    return report


def write_report(root, output, value):
    if output is None:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    output = output.resolve()
    if any(output.is_relative_to(root / directory) for directory in ("config", "data")):
        raise ValueError("Write review packets/reports outside config/ and data/; source and approval ledgers are read-only")
    atomic_json(output, value)
    summary = ({"valid": value["valid"], **{name: {
        key: value[name][key] for key in ("active", "stale", "missing", "invalid")}
        for name in ("record_reviews", "translations")}} if "valid" in value else {
            "records": len(value["records"]), "missing_ids": value["missing_ids"]})
    print(json.dumps({"output": str(output), **summary}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root (default: current directory)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export", help="Export full source packets for explicit IDs; no decisions are made")
    export.add_argument("--id", action="append", default=[], help="Exact record ID; repeat for multiple records")
    export.add_argument("--ids-file", type=Path, help="UTF-8 file containing one exact record ID per line")
    export.add_argument("--output", type=Path, help="Artifact JSON destination (default: stdout); never config/ or data/")
    validate = subparsers.add_parser("validate", help="Check both configured ledgers against retained source evidence")
    validate.add_argument("--output", type=Path, help="Artifact JSON report (default: stdout); stale/missing entries are not rewritten")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "export":
            identifiers = args.id + (args.ids_file.read_text(encoding="utf-8").splitlines() if args.ids_file else [])
            identifiers = list(dict.fromkeys(identifier.strip() for identifier in identifiers if identifier.strip()))
            if not identifiers or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", identifier) for identifier in identifiers):
                parser.error("Provide one or more exact record IDs using --id or --ids-file")
            report = export_packets(root, identifiers)
            status = int(bool(report["missing_ids"]))
        else:
            report = validate_ledgers(root)
            status = int(not report["valid"])
        write_report(root, args.output, report)
        return status
    except (ValueError, TypeError, OSError) as exc:
        print(error_text(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
