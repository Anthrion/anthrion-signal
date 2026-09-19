"""Losslessly migrate large retained snapshots before Git publication.

Public assets are exported separately. This never changes record content, source
checkpoints or history, and requires no provider calls or Git LFS subscription.
"""
from pathlib import Path

from anthrion_signal.utils import atomic_retained_bytes, read_retained_bytes, retained_path

SNAPSHOTS = ("signals.jsonl", "current.json", "source_state.json")


def compress(root):
    for name in SNAPSHOTS:
        path = root / "data" / name
        actual = retained_path(path)
        if not actual.exists() or actual.suffix == ".gz":
            continue
        body = read_retained_bytes(path)
        atomic_retained_bytes(path, body)
        if read_retained_bytes(path) != body:
            raise ValueError(f"Retained snapshot verification failed: {name}")
        print(f"{name}: {len(body):,} bytes retained in {retained_path(path).stat().st_size:,} bytes")


if __name__ == "__main__":
    compress(Path.cwd())
