"""Restore one sparse merged amount from an explicitly selected retained TED notice.

Offline and dry-run by default. No source requests, classification changes or bulk
record rewrites are made. Run after any data replay and before final rescore/export.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from anthrion_signal.canonical import canonical_signal_json
from anthrion_signal.collectors import RawRecord
from anthrion_signal.models import Signal
from anthrion_signal.normalise import normalise_ted, set_hashes
from anthrion_signal.utils import atomic_bytes, atomic_json


def prepare_repair(canonical_body, retained_body, signal_id, notice_number):
    rows = canonical_body.splitlines(keepends=True)
    matches = [(i, Signal.model_validate_json(row)) for i, row in enumerate(rows)
               if row.strip() and json.loads(row).get("id") == signal_id]
    if len(matches) != 1:
        raise ValueError("Canonical signal must occur exactly once")
    index, current = matches[0]
    retained = json.loads(gzip.decompress(retained_body))
    records = [record for record in retained if record.get("source", {}).get("id") == "ted"
               and record.get("data", {}).get("publication-number") == notice_number]
    if len(records) != 1:
        raise ValueError("Retained official TED notice must occur exactly once")
    restored = normalise_ted(RawRecord(**records[0]))
    if current.source != "ted" or restored is None or restored.primary_source_url not in current.source_urls:
        raise ValueError("Retained notice is not an established source of this signal")
    if "ted:" + notice_number not in current.external_ids:
        raise ValueError("Retained notice reference is absent from the signal")
    expected = restored.amount
    if expected is None or (expected.minimum is None and expected.maximum is None):
        raise ValueError("Retained notice contains no proved amount")
    if (current.value_min, current.value_max, current.currency) != (expected.minimum, expected.maximum, expected.currency):
        raise ValueError("Retained amount does not match the surviving numeric facts")
    if current.amount and current.amount != expected and current.amount.kind != "unknown" and (
            current.amount.minimum is not None or current.amount.maximum is not None):
        raise ValueError("A different populated amount cannot be replaced by this repair")
    repaired = current.model_copy(deep=True)
    repaired.amount = expected.model_copy(deep=True)
    proof = restored.provenance[0]
    existing = [p for p in repaired.provenance if p.url == proof.url]
    if any(p.raw_hash != proof.raw_hash for p in existing):
        raise ValueError("Retained notice conflicts with existing raw provenance")
    if not existing:
        repaired.provenance.append(proof)
    set_hashes(repaired)
    before, after = current.model_dump(), repaired.model_dump()
    changed = [field for field in before if before[field] != after[field]]
    if set(changed) - {"amount", "provenance", "content_hash", "material_change_hash"}:
        raise ValueError("Repair changed unrelated source facts or fingerprint")
    newline = b"\r\n" if rows[index].endswith(b"\r\n") else b"\n" if rows[index].endswith(b"\n") else b""
    rows[index] = canonical_signal_json(repaired).encode("utf-8") + newline
    body = b"".join(rows)
    receipt = {"signal_id": signal_id, "notice_number": notice_number, "changed_fields": changed,
        "retained_snapshot_sha256": hashlib.sha256(retained_body).hexdigest(),
        "source_proof": proof.model_dump(), "old_amount": before["amount"], "new_amount": after["amount"],
        "old_hashes": {key: before[key] for key in ("raw_source_hash", "content_hash", "material_change_hash", "fingerprint")},
        "new_hashes": {key: after[key] for key in ("raw_source_hash", "content_hash", "material_change_hash", "fingerprint")},
        "canonical_before_sha256": hashlib.sha256(canonical_body).hexdigest(),
        "canonical_after_sha256": hashlib.sha256(body).hexdigest()}
    return body, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=Path("data/signals.jsonl"))
    parser.add_argument("--retained", type=Path, required=True)
    parser.add_argument("--signal-id", required=True)
    parser.add_argument("--notice-number", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    original = args.canonical.read_bytes()
    body, receipt = prepare_repair(original, args.retained.read_bytes(), args.signal_id, args.notice_number)
    receipt["applied"] = args.apply
    if args.apply:
        if args.canonical.read_bytes() != original:
            raise ValueError("Canonical data changed while preparing repair")
        atomic_bytes(args.canonical, body)
    atomic_json(args.receipt, receipt)
    print(json.dumps({"signal_id": args.signal_id, "applied": args.apply, "changed_fields": receipt["changed_fields"]}))


if __name__ == "__main__":
    main()
