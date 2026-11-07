"""Immutable current indexes and record details, published before their manifest."""
import gzip
import json
import re
from collections import defaultdict

from .markets import MARKETS
from .public_context import public_signal
from .public_compression import decoded_limit
from .utils import atomic_bytes, digest


def atomic_public_json(path, payload):
    # Identical source facts and content hashes, without indentation repeated in
    # every immutable public shard. Canonical storage retains its existing format.
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if path.suffix == ".gz":
        name = path.relative_to(path.parents[1]).as_posix()
        if len(body) > decoded_limit(path.name if path.name in {"current.json.gz", "manifest.json.gz"} else name):
            raise ValueError("Public JSON exceeds its decoded size limit")
        body = gzip.compress(body, compresslevel=6, mtime=0)
    atomic_bytes(path, body)

DETAIL_FIELDS = {"description", "documents", "changes", "capability_evidence", "eligibility_text",
                 "buyer_history", "procedure_history", "participation_requirements", "delivery_role", "lots",
                 "contacts", "buyer_name_conflicts", "reviewed_guidance"}


def ranking_evidence(item):
    """Compact, deduplicated facts from the same validated evidence as full details.

    No score, extra source text or private company facts enter the index. Original
    and translated passages describing the same capability contribute only once.
    """
    fields = ("capability", "strength", "field", "context")
    rows = {tuple(e.get(key, "") for key in fields) for e in item.get("capability_evidence", [])}
    return [dict(zip(fields, row)) for row in sorted(rows)]


def bucket_files(root, kind, entries, target_bytes=512 * 1024):
    """Stream small, immutable detail bundles with bounded memory and downloads."""
    field = "buyers" if kind == "buyers" else "records"
    buffers, parts, references = {}, defaultdict(int), {}

    def flush(prefix):
        items, _ = buffers.pop(prefix)
        body = (b'{"' + field.encode() + b'":{' + b','.join(
            json.dumps(key).encode() + b':' + value for key, value in sorted(items)) + b'},"schema_version":"1.0"}')
        if len(body) > decoded_limit(kind + "/bucket.json.gz"):
            raise ValueError("A public detail exceeds the bounded download size")
        payload = json.loads(body)
        relative = f"{kind}/bucket-{prefix}-{parts[prefix]:03d}-{digest(payload)[:16]}.json.gz"
        parts[prefix] += 1
        atomic_bytes(root / "app/public/data" / relative, gzip.compress(body, compresslevel=6, mtime=0))
        references.update({key: relative for key, _ in items})

    for key, payload in entries:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", key) or key in references:
            raise ValueError("Invalid or duplicate public detail identity")
        prefix = digest(key)[:2]
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        size = len(json.dumps(key).encode()) + len(body) + 2
        if prefix in buffers and buffers[prefix][1] + size + 64 > target_bytes:
            flush(prefix)
        items, total = buffers.setdefault(prefix, ([], 0))
        if any(ident == key for ident, _ in items):
            raise ValueError("Duplicate public detail identity")
        items.append((key, body))
        buffers[prefix] = items, total + size
    for prefix in sorted(buffers):
        flush(prefix)
    return references


def buyer_files(root, signals):
    representatives = {}
    for signal in signals:
        if signal.buyer_id and signal.buyer_history:
            representatives.setdefault(signal.buyer_id, signal)
    def entries():
        for ident, signal in sorted(representatives.items()):
            yield ident, {"schema_version": "1.0", "buyer_id": ident, "buyer_name": signal.buyer_name,
                          "identity_basis": signal.buyer_identity_basis, "records": signal.buyer_history}
    paths = bucket_files(root, "buyers", entries())
    return {ident: {"url": path, "count": len(representatives[ident].buyer_history),
                    "identity_basis": representatives[ident].buyer_identity_basis} for ident, path in paths.items()}


def record_files(root, signals, translations, buyer_refs, award_ids=()):
    def entries():
        for signal in sorted(signals, key=lambda item: item.id):
            if signal.buyer_id in buyer_refs:
                signal.buyer_history_ref = buyer_refs[signal.buyer_id]
            translation = translations.get(signal.id)
            payload = {"signal": public_signal(signal, translation)}
            if translation:
                payload["translation"] = translation.model_dump() if hasattr(translation, "model_dump") else translation
            yield signal.id, payload
    paths = bucket_files(root, "records", entries())
    return {signal.id: {"url": paths[signal.id], "markets": [market for market, countries in MARKETS.items()
                if set(countries).intersection(signal.countries)],
                "view": "awards" if signal.id in award_ids else "opportunities"} for signal in signals}


def record_file(root, signal, translation=None, view="opportunities", buyer_refs=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", signal.id):
        raise ValueError("Unsafe public record identifier")
    if signal.buyer_id and signal.buyer_history:
        if buyer_refs is not None and signal.buyer_id in buyer_refs:
            signal.buyer_history_ref = buyer_refs[signal.buyer_id]
        else:
            buyer = {"schema_version": "1.0", "buyer_id": signal.buyer_id, "buyer_name": signal.buyer_name,
                     "identity_basis": signal.buyer_identity_basis, "records": signal.buyer_history}
            relative = f"buyers/{signal.buyer_id}-{digest(buyer)[:16]}.json.gz"
            atomic_public_json(root / "app/public/data" / relative, buyer)
            signal.buyer_history_ref = {"url": relative, "count": len(signal.buyer_history),
                                        "identity_basis": signal.buyer_identity_basis}
            if buyer_refs is not None:
                buyer_refs[signal.buyer_id] = signal.buyer_history_ref
    item = public_signal(signal, translation)
    payload = {"schema_version": "1.0", "signal": item}
    if translation:
        payload["translation"] = translation.model_dump() if hasattr(translation, "model_dump") else translation
    relative = f"records/{signal.id}-{digest(payload)[:16]}.json.gz"
    atomic_public_json(root / "app/public/data" / relative, payload)
    return item, {"url": relative, "markets": [market for market, countries in MARKETS.items()
                                               if set(countries).intersection(signal.countries)], "view": view}


def history_files(root, signals, translations, buyer_refs, max_bytes=8 * 1024 * 1024):
    """Small stable buckets preserve full history with bounded download/decode costs."""
    groups = defaultdict(list)
    for signal in signals:
        groups[digest(signal.id)[:3]].append(signal)
    manifest = {}

    def write(prefix, records):
        details = {}
        for signal in records:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", signal.id):
                raise ValueError("Unsafe historical record identifier")
            translation = translations.get(signal.id)
            detail = signal.model_copy(update={"buyer_history": [], "procedure_history": [],
                "buyer_history_ref": buyer_refs.get(signal.buyer_id)})
            details[signal.id] = {"signal": public_signal(detail, translation)}
            if translation:
                details[signal.id]["translation"] = translation.model_dump() if hasattr(translation, "model_dump") else translation
        payload = {"schema_version": "1.0", "records": details}
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(body) > max_bytes:
            if len(records) == 1 or len(prefix) >= 64:
                raise ValueError("A historical notice exceeds the bounded detail download size")
            children = defaultdict(list)
            for signal in records:
                children[digest(signal.id)[:len(prefix) + 1]].append(signal)
            for child, values in sorted(children.items()):
                write(child, values)
            return
        relative = f"history/{prefix}-{digest(payload)[:16]}.json.gz"
        atomic_bytes(root / "app/public/data" / relative, gzip.compress(body, compresslevel=6, mtime=0))
        for signal in records:
            manifest[signal.id] = {"url": relative, "view": "history", "markets": [market for market, countries in MARKETS.items()
                if set(countries).intersection(signal.countries)]}

    for prefix, records in sorted(groups.items()):
        write(prefix, records)
    return manifest


def search_text(signal, translation):
    translated = translation.model_dump() if hasattr(translation, "model_dump") else translation or {}
    if translated.get("source_hash") != digest([signal.title, signal.description]):
        translated = {}
    return "\n".join(str(value) for value in [signal.title, signal.description, signal.buyer_name or "",
        signal.incumbent_supplier or "", signal.id, signal.ocid or "", *signal.external_ids,
        *signal.cpv_codes, *signal.categories, *signal.regions, *signal.countries,
        translated.get("title", ""), translated.get("description", ""), translated.get("buyer_name", "")] if value)


def export_current(root, dataset, award_records=None):
    records, summaries, translations = dict(award_records or {}), {}, {}
    missing = [signal for signal in dataset.signals if signal.id not in records]
    records.update(record_files(root, missing, dataset.translations, buyer_files(root, missing)))
    for signal in dataset.signals:
        translation = dataset.translations.get(signal.id)
        item = public_signal(signal, translation)
        summary = {key: value for key, value in item.items() if key not in DETAIL_FIELDS}
        summary["description"] = ""
        summary["documents"] = []
        summary["changes"] = []
        summary["ranking_evidence"] = ranking_evidence(item)
        summary["search_text"] = search_text(signal, translation)
        summary["is_summary"] = True
        summaries[signal.id] = summary
        if translation:
            translations[signal.id] = {**translation.model_dump(), "description": ""}
    manifest = {"version": "1.0", "markets": {}, "records": records}
    for market, countries in MARKETS.items():
        selected = [summaries[s.id] for s in dataset.signals if set(countries).intersection(s.countries)]
        ids = {s["id"] for s in selected}
        payload = {"schema_version": "1.0", "signals": selected,
                   "translations": {key: value for key, value in translations.items() if key in ids}}
        relative = f"current/{market}-{digest(payload)[:16]}.json.gz"
        atomic_public_json(root / "app/public/data" / relative, payload)
        manifest["markets"][market] = {"url": relative, "count": len(selected)}
    # No shards are deleted during generation: a failed/parallel reader of the
    # previous manifest must retain all of its content-addressed dependencies.
    return manifest
