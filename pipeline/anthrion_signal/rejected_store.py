"""One current rejected notice plus reversible field changes, in bounded buckets.

The current row is unchanged. Reverse patches contain the old values of changed
fields, including observation metadata, so every distinct prior row is recoverable.
Nothing depends on a classification/content hash omitting some source fields.
"""
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .utils import atomic_bytes, digest, parse_date, read_json

FORMAT = {"version": 2, "buckets": 256}
MAX_BYTES = 90 * 1024 * 1024


def directory(root):
    return Path(root) / "data/discovery/rejected"


def migrated(root):
    marker = read_json(directory(root) / "format.json", {})
    return all(marker.get(key) == value for key, value in FORMAT.items())


def bucket_id(identifier):
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:2]


def stamp(row):
    return parse_date(row.get("updated_at") or row.get("last_seen_at")) or datetime.min.replace(tzinfo=UTC)


def jsonl_rows(path):
    # A literal LF separates JSONL rows; Unicode paragraph/line separators can
    # occur inside a source string and must not be treated as record boundaries.
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def same_value(left, right):
    # Python considers True == 1 and 1 == 1.0. Their original JSON differs and
    # must round-trip through the historical hash unchanged, including in lists.
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_value(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_value(a, b) for a, b in zip(left, right))
    return left == right


def pack_versions(rows):
    versions = {}
    for row in rows:
        key = digest(row)
        # A repeated row can be the last observation at a tied publisher date.
        versions.pop(key, None)
        versions[key] = row
    if not versions:
        raise ValueError("A versioned notice needs a current record")
    if len({row["id"] for row in versions.values()}) != 1:
        raise ValueError("Cannot combine different notice IDs")
    ordered = list(versions.items())
    current_hash, current = max(enumerate(ordered), key=lambda p: (stamp(p[1][1]), p[0]))[1]
    patches = []
    for key, prior in ordered:
        if key == current_hash:
            continue
        patches.append({"hash": key,
                        "restore": {field: value for field, value in prior.items()
                                    if field not in current or not same_value(value, current[field])},
                        "remove": sorted(set(current) - set(prior))})
    return {"version": 1, "hash": current_hash, "current": current, "previous": patches}


def unpack_versions(envelope):
    if set(envelope) - {"rolling_hash"} != {"version", "hash", "current", "previous"} or envelope["version"] != 1:
        raise ValueError("Unknown rejected-notice version format")
    current = envelope["current"]
    if not isinstance(current, dict) or digest(current) != envelope["hash"]:
        raise ValueError("Rejected current-record integrity check failed")
    seen = {envelope["hash"]}
    for patch in envelope["previous"]:
        if set(patch) != {"hash", "restore", "remove"}:
            raise ValueError("Invalid rejected-notice change")
        prior = dict(current)
        for field in patch["remove"]:
            if field not in prior or field in patch["restore"]:
                raise ValueError("Invalid removed field in rejected-notice change")
            del prior[field]
        prior.update(patch["restore"])
        if (prior.get("id") != current.get("id") or digest(prior) != patch["hash"]
                or patch["hash"] in seen):
            raise ValueError("Rejected historical-record integrity check failed")
        seen.add(patch["hash"])
        yield prior
    if "rolling_hash" in envelope and envelope["rolling_hash"] not in seen:
        raise ValueError("Invalid rolling observation in rejected-notice history")
    yield current


def current_rows(path):
    for row in jsonl_rows(path):
        if path.parent.name == "compact":
            if row.get("version") != 1 or digest(row.get("current")) != row.get("hash"):
                raise ValueError("Rejected current-record integrity check failed")
            row = row["current"]
        yield row


def current_paths(root):
    # Legacy files can coexist during migration. Their later observations retain
    # the existing timestamp/tie precedence; compacted history is not replayed.
    base = directory(root)
    consumed = read_json(base / "format.json", {}).get("migrated_files", {})
    legacy = []
    for path in sorted(base.glob("*.jsonl.gz")):
        if path.name in consumed:
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() == consumed[path.name]:
                    continue
        legacy.append(path)
    return sorted((base / "compact").glob("*.jsonl.gz")) + legacy


def read_bucket(path):
    envelopes = {}
    for entry in jsonl_rows(path):
        identifier = entry["current"]["id"]
        if (identifier in envelopes or bucket_id(identifier) != path.name.split(".")[0]
                or entry.get("version") != 1 or digest(entry["current"]) != entry.get("hash")):
            raise ValueError("Rejected bucket identity or integrity check failed")
        envelopes[identifier] = entry
    return envelopes


def encode_bucket(envelopes):
    body = "".join(json.dumps(envelopes[key], ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")) + "\n" for key in sorted(envelopes)).encode()
    compressed = gzip.compress(body, compresslevel=9, mtime=0)
    if len(compressed) >= MAX_BYTES:
        raise ValueError("Rejected history bucket needs finer partitioning before publication")
    return compressed


def observation_facts(row):
    """All source/decision fields; only collector observation clocks excluded."""
    value = {key: item for key, item in row.items() if key not in {"first_seen_at", "last_seen_at"}}
    value["provenance"] = [{key: item for key, item in entry.items() if key != "retrieved_at"}
                           for entry in row.get("provenance", [])]
    return digest(value)


def repeated_observation(prior, incoming):
    before, after = parse_date(prior.get("last_seen_at")), parse_date(incoming.get("last_seen_at"))
    return (before is not None and after is not None
            and before.astimezone(UTC).date() == after.astimezone(UTC).date()
            and observation_facts(prior) == observation_facts(incoming))


def upsert(root, signals):
    grouped = {}
    for signal in signals:
        row = signal.model_dump(mode="json", exclude_defaults=True)
        grouped.setdefault(bucket_id(signal.id), []).append(row)
    for bucket, rows in grouped.items():
        path = directory(root) / "compact" / f"{bucket}.jsonl.gz"
        envelopes = read_bucket(path) if path.exists() else {}
        before = path.read_bytes() if path.exists() else None
        for row in rows:
            previous = envelopes.get(row["id"])
            versions = list(unpack_versions(previous)) if previous else []
            incoming_hash = digest(row)
            existing_hashes = {digest(prior) for prior in versions}
            # Like the legacy daily writer, keep the latest same-day observation
            # of identical facts. The marker is only set by this writer: migration
            # never marks old source rows as replaceable. Unlike content_hash,
            # this comparison covers every non-observation field.
            rolling = previous.get("rolling_hash") if previous else None
            versions = [prior for prior in versions if not (
                digest(prior) == rolling and repeated_observation(prior, row))]
            envelopes[row["id"]] = pack_versions([*versions, row])
            if incoming_hash not in existing_hashes or incoming_hash == rolling:
                envelopes[row["id"]]["rolling_hash"] = incoming_hash
        body = encode_bucket(envelopes)
        if body != before:
            atomic_bytes(path, body)
