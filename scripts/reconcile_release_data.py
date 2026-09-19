"""Merge scheduled collection data with local source corrections before a release.

Reads Git objects without changing refs or checking out files. Unexpected material
conflicts fail closed; the caller still needs to regenerate/validate public output.
"""

import argparse
import gzip
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from anthrion_signal.canonical import canonical_signal_json
from anthrion_signal.dedupe import exact_keys
from anthrion_signal.models import Signal
from anthrion_signal.normalise import set_hashes
from anthrion_signal.utils import atomic_bytes, atomic_json, jsonl_lines


def unique(values):
    return list({json.dumps(value, sort_keys=True): value for value in values}.values())


def merge_record(base, local, remote):
    if local is None:
        return remote
    if remote is None:
        return local
    base = base or {}
    if local == remote or remote == base:
        return local
    if local == base:
        return remote
    result = {}
    for key in local.keys() | remote.keys():
        old, left, right = base.get(key), local.get(key), remote.get(key)
        if left == old:
            result[key] = right
        elif right == old or left == right:
            result[key] = left
        elif key == "first_seen_at":
            result[key] = min(left, right)
        elif key in ("last_seen_at", "last_material_update"):
            result[key] = max(left, right)
        elif key in ("provenance", "changes", "external_ids", "source_urls"):
            result[key] = unique((left or []) + (right or []))
        elif key in ("raw_source_hash", "content_hash", "material_change_hash", "fingerprint"):
            result[key] = right if remote["last_seen_at"] >= local["last_seen_at"] else left
        else:
            raise ValueError(f"Conflicting source facts for {local['id']}: {key}")
    signal = Signal.model_validate(result)
    if signal.amount and (signal.amount.minimum is not None or signal.amount.maximum is not None):
        if (signal.amount.minimum, signal.amount.maximum, signal.amount.currency) != (
                signal.value_min, signal.value_max, signal.currency):
            raise ValueError(f"Conflicting source facts for {signal.id}: amount disagrees with numeric values")
    return set_hashes(signal).model_dump()


def merge_maps(base, local, remote, keys=None):
    return {key: merge_record(base.get(key), local.get(key), remote.get(key))
            for key in sorted(keys if keys is not None else (local.keys() | remote.keys()))}


def records(body, compressed=False):
    if not body:
        return {}
    text = gzip.decompress(body).decode() if compressed else body.decode()
    # Compare source facts, not whether a canonical writer included empty defaults.
    return {record.id: record.model_dump(mode="json") for line in jsonl_lines(text)
            for record in [Signal.model_validate_json(line)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="origin/main")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()

    def git(*command):
        return subprocess.check_output(["git", *command], cwd=root)

    base_ref = git("merge-base", "HEAD", args.remote).decode().strip()
    changed = git("diff", "--name-only", base_ref, args.remote).decode().splitlines()
    if any(not path.startswith("data/") for path in changed):
        raise SystemExit("Remote code changed; merge it separately before reconciling generated data")

    def blob(ref, path):
        result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, capture_output=True)
        return result.stdout if result.returncode == 0 else b""

    def local_blob(path):
        target = root / path
        return target.read_bytes() if target.exists() else b""

    def json_blob(ref, path):
        return json.loads(blob(ref, path) or b"{}")

    archive_paths = {path.as_posix().removeprefix(root.as_posix() + "/")
                     for path in (root / "data/archive").glob("*.jsonl.gz")}
    archive_paths.update(git("ls-tree", "-r", "--name-only", args.remote, "data/archive").decode().splitlines())
    archive_versions, base_all, local_all, remote_all = {}, {}, {}, {}
    for path in sorted(archive_paths):
        old = records(blob(base_ref, path), True)
        left = records(local_blob(path), True)
        right = records(blob(args.remote, path), True)
        base_all.update(old)
        local_all.update(left)
        remote_all.update(right)
        archive_versions[path] = (left, right)
    old_current = records(blob(base_ref, "data/signals.jsonl"))
    local_current = records(local_blob("data/signals.jsonl"))
    remote_current = records(blob(args.remote, "data/signals.jsonl"))
    base_all.update(old_current)
    local_all.update(local_current)
    remote_all.update(remote_current)
    # Retention can move the same base record into an archive on both branches.
    # Its source ancestor is still the canonical base row, not an absent row in
    # that month's old partition.
    archives = {path: merge_maps(base_all, left, right)
                for path, (left, right) in archive_versions.items()}
    merged = merge_maps(base_all, local_all, remote_all, local_current.keys() | remote_current.keys())

    old_state = json_blob(base_ref, "data/source_state.json")
    left_state = json.loads(local_blob("data/source_state.json"))
    right_state = json_blob(args.remote, "data/source_state.json")
    state = {}
    for source in left_state.keys() | right_state.keys():
        left, right, old = left_state.get(source, {}), right_state.get(source, {}), old_state.get(source, {})
        if left == old:
            state[source] = right
        elif right == old or not right:
            state[source] = left
        else:
            # Keep the newer retrieval checkpoint as a coherent object, including its pagination cursor.
            state[source] = {**{k: v for k, v in left.items() if k not in old}, **right}

    current = json_blob(args.remote, "data/current.json")
    health = {s["id"]: s for s in current["sources"]}
    for item in json.loads(local_blob("data/current.json"))["sources"]:
        if item["id"] not in health or (item.get("last_attempt") or "") > (health[item["id"]].get("last_attempt") or ""):
            health[item["id"]] = item
    current["sources"] = list(health.values())
    history = unique([json.loads(line) for body in (blob(args.remote, "data/history.jsonl"), local_blob("data/history.jsonl"))
                      for line in jsonl_lines(body.decode())])
    print(json.dumps({"base": base_ref, "remote": git("rev-parse", args.remote).decode().strip(),
                      "local_current": len(local_current), "remote_current": len(remote_current),
                      "merged_candidates": len(merged), "archive_partitions": len(archives),
                      "remote_changed_paths": changed}, indent=2))
    if not args.apply:
        return
    backup = root / "artifacts/pre-release-data" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    for path in {"data/signals.jsonl", "data/current.json", "data/source_state.json", "data/history.jsonl",
                 "data/archive_index.json", *archive_paths}:
        body = local_blob(path)
        if body:
            atomic_bytes(backup / path, body)
    index = {}
    for path, items in archives.items():
        if items != records(local_blob(path), True):
            body = "\n".join(canonical_signal_json(Signal.model_validate(items[key])) for key in sorted(items)) + "\n"
            atomic_bytes(root / path, gzip.compress(body.encode(), mtime=0))
        month = Path(path).name[:7]
        for item in items.values():
            for key in exact_keys(Signal.model_validate(item)):
                index[key] = {"id": item["id"], "month": month}
    atomic_json(root / "data/archive_index.json", index)
    atomic_bytes(root / "data/signals.jsonl", ("\n".join(canonical_signal_json(Signal.model_validate(value))
                                                       for value in merged.values()) + "\n").encode())
    atomic_json(root / "data/source_state.json", state)
    atomic_json(root / "data/current.json", current)
    atomic_bytes(root / "data/history.jsonl", ("\n".join(json.dumps(value) for value in sorted(history, key=lambda x: x["at"])) + "\n").encode())
    for path in ("data/publication_state.json", "data/verification_state.json"):
        body = blob(args.remote, path)
        if body:
            atomic_bytes(root / path, body)
    atomic_json(backup / "merge.json", {"base": base_ref, "remote": args.remote,
                                       "remote_commit": git("rev-parse", args.remote).decode().strip()})


if __name__ == "__main__":
    main()
