"""Verified, restartable migration of duplicate full rows to reversible changes."""
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from .models import Signal
from .rejected_store import (FORMAT, bucket_id, current_paths, directory, encode_bucket, jsonl_rows,
                             pack_versions, unpack_versions)
from .utils import atomic_bytes, atomic_json, digest


def safe_path(root, path):
    workspace, resolved = Path(root).resolve(), path.resolve()
    if path.is_symlink() or resolved == workspace or not resolved.is_relative_to(workspace):
        raise ValueError("Retention path escapes the workspace")
    return path


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def migrate(root, *, apply=False):
    root = Path(root)
    base = directory(root)
    legacy = sorted(base.glob("*.jsonl.gz"))
    compact = sorted((base / "compact").glob("*.jsonl.gz"))
    if not legacy:
        return {"legacy_rows": 0, "already_compact": bool(compact), "applied": False}
    sources = current_paths(root)
    fingerprints = {path: file_hash(safe_path(root, path)) for path in compact + legacy}
    temp_root = safe_path(root, root / "tmp")
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rejected-compaction-", dir=temp_root) as temporary:
        staging = safe_path(root, Path(temporary))
        handles = {}
        input_rows = 0
        try:
            for path in sources:
                for entry in jsonl_rows(path):
                    rows = unpack_versions(entry) if path in compact else [entry]
                    for row in rows:
                        # Validate before any source-file mutation. Spooling
                        # bounds memory by one bucket, not the whole archive.
                        Signal.model_validate(row)
                        bucket = bucket_id(row["id"])
                        if bucket not in handles:
                            handles[bucket] = (staging / f"{bucket}.jsonl").open("w", encoding="utf-8", newline="\n")
                        handles[bucket].write(json.dumps(row, ensure_ascii=False) + "\n")
                        input_rows += 1
        finally:
            for handle in handles.values():
                handle.close()
        heads = versions = output_bytes = 0
        for bucket in sorted(handles):
            grouped = defaultdict(list)
            with (staging / f"{bucket}.jsonl").open(encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    grouped[row["id"]].append(row)
            envelopes = {}
            for identifier, rows in grouped.items():
                envelope = pack_versions(rows)
                expected = {digest(row) for row in rows}
                restored = {digest(row) for row in unpack_versions(envelope)}
                if expected != restored:
                    raise ValueError("Compaction did not preserve every distinct source version")
                envelopes[identifier] = envelope
                heads += 1
                versions += len(expected)
            body = encode_bucket(envelopes)
            (staging / f"{bucket}.jsonl.gz").write_bytes(body)
            output_bytes += len(body)
        result = {"legacy_rows": input_rows, "current_records": heads,
                  "distinct_versions": versions, "historical_patches": versions - heads,
                  "identical_rows_removed": input_rows - versions,
                  "before_bytes": sum(path.stat().st_size for path in sources),
                  "after_bytes": output_bytes, "buckets": len(handles), "applied": apply}
        if apply:
            if (list(fingerprints) != sorted((base / "compact").glob("*.jsonl.gz")) + sorted(base.glob("*.jsonl.gz"))
                    or any(file_hash(safe_path(root, path)) != value for path, value in fingerprints.items())):
                raise ValueError("Retained inputs changed during compaction; retry without modifying them")
            # Each bucket is self-contained and atomic. Original files remain
            # until all replacements are written and independently verified.
            for bucket in sorted(handles):
                target = safe_path(root, base / "compact" / f"{bucket}.jsonl.gz")
                body = (staging / f"{bucket}.jsonl.gz").read_bytes()
                atomic_bytes(target, body)
                if target.read_bytes() != body:
                    raise ValueError("Compacted bucket write did not round-trip")
            # Publish the completed migration before deleting originals. If a
            # process stops mid-cleanup, consumed old files cannot override the
            # new head at a tied publication timestamp when reading/restarting.
            atomic_json(safe_path(root, base / "format.json"),
                        {**FORMAT, "migrated_files": {p.name: fingerprints[p] for p in legacy}})
            for path in legacy:
                safe_path(root, path).unlink()
        return result
