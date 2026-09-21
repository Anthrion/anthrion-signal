"""Immutable current indexes and record details, published before their manifest."""
import gzip
import json
import re
from collections import defaultdict

from .markets import MARKETS
from .public_context import public_signal
from .utils import atomic_bytes, digest


def atomic_public_json(path, payload):
    # Identical source facts and content hashes, without indentation repeated in
    # every immutable public shard. Canonical storage retains its existing format.
    atomic_bytes(path, json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))

DETAIL_FIELDS = {"description", "documents", "changes", "capability_evidence", "eligibility_text",
                 "buyer_history", "procedure_history", "participation_requirements", "delivery_role", "lots",
                 "contacts", "buyer_name_conflicts"}


def record_file(root, signal, translation=None, view="opportunities", buyer_refs=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", signal.id):
        raise ValueError("Unsafe public record identifier")
    if signal.buyer_id and signal.buyer_history:
        if buyer_refs is not None and signal.buyer_id in buyer_refs:
            signal.buyer_history_ref = buyer_refs[signal.buyer_id]
        else:
            buyer = {"schema_version": "1.0", "buyer_id": signal.buyer_id, "buyer_name": signal.buyer_name,
                     "identity_basis": signal.buyer_identity_basis, "records": signal.buyer_history}
            relative = f"buyers/{signal.buyer_id}-{digest(buyer)[:16]}.json"
            atomic_public_json(root / "app/public/data" / relative, buyer)
            signal.buyer_history_ref = {"url": relative, "count": len(signal.buyer_history),
                                        "identity_basis": signal.buyer_identity_basis}
            if buyer_refs is not None:
                buyer_refs[signal.buyer_id] = signal.buyer_history_ref
    item = public_signal(signal, translation)
    payload = {"schema_version": "1.0", "signal": item}
    if translation:
        payload["translation"] = translation.model_dump() if hasattr(translation, "model_dump") else translation
    relative = f"records/{signal.id}-{digest(payload)[:16]}.json"
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
    buyer_refs = {}
    for signal in dataset.signals:
        translation = dataset.translations.get(signal.id)
        item, records[signal.id] = record_file(root, signal, translation, buyer_refs=buyer_refs)
        summary = {key: value for key, value in item.items() if key not in DETAIL_FIELDS}
        summary["description"] = ""
        summary["documents"] = []
        summary["changes"] = []
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
        relative = f"current/{market}-{digest(payload)[:16]}.json"
        atomic_public_json(root / "app/public/data" / relative, payload)
        manifest["markets"][market] = {"url": relative, "count": len(selected)}
    # No shards are deleted during generation: a failed/parallel reader of the
    # previous manifest must retain all of its content-addressed dependencies.
    return manifest
