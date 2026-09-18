"""Compressed, replayable rejected notices; no public-feed or model calls here."""
import gzip
from pathlib import Path

from .models import Signal
from .utils import atomic_bytes, jsonl_lines, parse_date


def read_rejected(root):
    latest = {}
    for path in sorted((Path(root) / "data/discovery/rejected").glob("*.jsonl.gz")):
        for line in jsonl_lines(gzip.decompress(path.read_bytes()).decode("utf-8")):
            if not line.strip():
                continue
            signal = Signal.model_validate_json(line)
            previous = latest.get(signal.id)
            stamp = parse_date(signal.updated_at or signal.last_seen_at)
            prior = parse_date(previous.updated_at or previous.last_seen_at) if previous else None
            if previous is None or stamp >= prior:
                latest[signal.id] = signal
    return list(latest.values())


def retain_rejected(root, signals, now, threshold):
    """Deduplicate this day's rejected source versions; older dates stay replayable.

    Normalized source text, dates, URLs, decision version and reasons are retained.
    exclude_defaults keeps storage compact without truncating procurement scope.
    No age/size cap silently deletes rejection evidence.
    """
    rejected = [s for s in signals if s.prefilter_score < threshold or s.exclusion_reasons]
    if not rejected:
        return 0
    path = Path(root) / "data/discovery/rejected" / f"{now:%Y-%m-%d}.jsonl.gz"
    records = {}
    if path.exists():
        for line in jsonl_lines(gzip.decompress(path.read_bytes()).decode("utf-8")):
            if line.strip():
                s = Signal.model_validate_json(line)
                records[(s.id, s.content_hash)] = s
    for signal in rejected:
        records[(signal.id, signal.content_hash)] = signal
    body = "\n".join(records[key].model_dump_json(exclude_defaults=True) for key in sorted(records)) + "\n"
    atomic_bytes(path, gzip.compress(body.encode("utf-8"), mtime=0))
    return len(rejected)
