"""Compact rejected versions losslessly; separately prune proven unused history.

Both commands default to a dry run. Publication runs them only after a validated
public export; a retained receipt records counts, integrity proof and recovery SHA.
"""
import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from anthrion_signal.config import load_config
from anthrion_signal.discovery import discovery_signature
from anthrion_signal.rejected_compaction import migrate, safe_path
from anthrion_signal.rejected_pruning import POLICY, apply_pruning, plan_pruning, recoverable_candidates
from anthrion_signal.rejected_store import current_paths, current_rows, directory, migrated, stamp
from anthrion_signal.utils import atomic_json, digest, parse_date, read_json


def heads(root):
    result = {}
    for path in current_paths(root):
        for row in current_rows(path):
            key = stamp(row)
            if row["id"] not in result or key >= result[row["id"]][0]:
                result[row["id"]] = (key, digest(row))
    return {sid: value[1] for sid, value in result.items()}


def maintain(root, command, *, apply=False, daily=False, at=None, recovery_commit=None):
    now = at or datetime.now(UTC)
    receipt = root / "data/retention" / f"rejected-{command}.json"
    if command == "compact":
        before = heads(root) if apply and any(directory(root).glob("*.jsonl.gz")) else None
        result = migrate(root, apply=apply)
        if result["applied"]:
            if heads(root) != before:
                raise ValueError("Compaction changed the selected current version")
            result["current_heads_sha256"] = digest(before)
    else:
        if not migrated(root):
            if not current_paths(root):
                return {"skipped": "No rejected notices to prune", "applied": False}
            raise ValueError("Compact rejected notices before planning inactive pruning")
        config = load_config(root)
        signature = {"policy": POLICY, "discovery": discovery_signature(config), "day": now.date().isoformat()}
        if daily and read_json(receipt, {}).get("signature") == signature:
            return {"skipped": "Inactive pruning already checked today", "applied": False}
        manifest = read_json(root / "app/public/data/manifest.json", {})
        candidates, fingerprints = plan_pruning(root, manifest, now, config)
        candidates = recoverable_candidates(root, recovery_commit, candidates)
        result = {"signature": signature, "candidate_records": len(candidates), "removed_bytes": 0,
                  "records": list(candidates.values()), "applied": apply}
        if apply:
            before = heads(root)
            # Write the full recovery inventory before any deletion, including
            # the immutable Git revision containing the original retained rows.
            inventory = receipt.with_name(f"rejected-prune-{now:%Y%m%dT%H%M%S%fZ}.json")
            if candidates:
                atomic_json(safe_path(root, inventory),
                            {**result, "applied": False, "at": now.isoformat(), "recovery_commit": recovery_commit})
            result["removed_bytes"] = apply_pruning(root, candidates, fingerprints)
            expected = {sid: key for sid, key in before.items() if sid not in candidates}
            if heads(root) != expected:
                raise ValueError("Pruning changed a retained notice or removed an unplanned ID")
            result["retained_heads_sha256"] = digest(expected)
    result.update({"at": now.isoformat(), "recovery_commit": recovery_commit})
    if result["applied"]:
        atomic_json(safe_path(root, receipt), result)
        if command == "prune":
            # Keep completed removal inventories append-only, so a later empty
            # daily check cannot replace the recovery evidence for deleted IDs.
            if candidates:
                atomic_json(safe_path(root, inventory), result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("compact", "prune"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--daily", action="store_true")
    parser.add_argument("--at", help="Fixed ISO timestamp for comparable audits")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    recovery = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    result = maintain(root, args.command, apply=args.apply, daily=args.daily,
                      at=parse_date(args.at) if args.at else None, recovery_commit=recovery)
    if args.output:
        atomic_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
