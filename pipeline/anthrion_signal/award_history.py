"""Replayable, market-partitioned historical awards with cached relevance decisions.

The cache is derived and dispensable. Original notices stay in the canonical,
archive and rejection stores. No translation/model requests are made here.
"""
import gzip
import json

from .attachments import hydrate_cached_documents
from .discovery import discovery_signature, is_public_award, lifecycle, prefilter, ranking_key
from .discovery_retention import read_rejected
from .models import Signal
from .markets import MARKETS
from .public_context import attach_history, backfill_retained_facts, enrich_signal, public_signal
from .public_feed import atomic_public_json, history_files, record_file
from .record_reviews import apply_reviews, load_reviews
from .translation import available_translations
from .utils import atomic_bytes, digest, jsonl_lines, parse_date, read_json

DECISION_FIELDS = ("prefilter_score", "prefilter_matches", "discovery_families", "delivery_priority",
                   "matched_capabilities", "discovery_version", "exclusion_reasons", "capability_evidence", "scope_evidence", "categories")


def retained_history(root, canonical):
    # Canonical records are reconciled versions and override old archived copies,
    # including cancellations that supersede a former award.
    latest = {s.id: s for s in read_rejected(root)}
    for path in sorted((root / "data/archive").glob("*.jsonl.gz")):
        for line in jsonl_lines(gzip.decompress(path.read_bytes()).decode("utf-8")):
            if line:
                signal = Signal.model_validate_json(line)
                previous = latest.get(signal.id)
                if previous is None or parse_date(signal.updated_at or signal.last_seen_at) >= parse_date(previous.updated_at or previous.last_seen_at):
                    latest[signal.id] = signal
    latest.update({s.id: s for s in canonical})
    return list(latest.values())


def prepare_awards(root, canonical, config, now):
    """Select the same relevant, retained awards for publication and translation."""
    history = retained_history(root, canonical)
    backfill_retained_facts(history, read_json(root / "data/source_state.json", {}))
    reviews = load_reviews(root)
    # Use the same document facts as current-record decisions without hydrating
    # tens of thousands of unrelated history rows or changing canonical objects.
    history = [s.model_copy() if s.id in reviews else s for s in history]
    reviewed = [s for s in history if s.id in reviews]
    if reviewed:
        hydrate_cached_documents(root, reviewed)
    history = apply_reviews(history, reviews, now=now, guidance=False)
    candidates = [s for s in history if is_public_award(s.model_copy(update={"exclusion_reasons": []}), now)]
    translations = available_translations(root, candidates)
    path = root / "data/discovery/award_classification.json.gz"
    try:
        cache = json.loads(gzip.decompress(path.read_bytes()))
    except (OSError, ValueError, EOFError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    signature = discovery_signature(config)
    old = cache.get("records", {}) if cache.get("signature") == signature else {}
    if not isinstance(old, dict):
        old = {}
    decisions, pending = {}, []
    for signal in candidates:
        key = digest([signal.title, signal.description, signal.buyer_name, signal.cpv_codes,
                      signal.source, signal.notice_type, signal.signal_type, translations.get(signal.id)])
        decision = old.get(signal.id, {})
        values = decision.get("values") if isinstance(decision, dict) else None
        valid = isinstance(values, dict) and set(values) == set(DECISION_FIELDS) and decision.get("key") == key
        if valid:
            try:
                validated = Signal.model_validate({**signal.model_dump(), **values})
                values = {field: getattr(validated, field) for field in DECISION_FIELDS}
            except ValueError:
                valid = False
        if valid:
            for field, value in values.items():
                setattr(signal, field, value)
        else:
            pending.append(signal)
        decisions[signal.id] = {"key": key}
    for start in range(0, len(pending), 1000):
        prefilter(pending[start:start + 1000], config["company_profile"], config["search_terms"], config["capabilities"], translations)
        print(f"Classified {min(start + 1000, len(pending))}/{len(pending)} historical award notices", flush=True)
    for signal in candidates:
        decisions[signal.id]["values"] = {field: getattr(signal, field) for field in DECISION_FIELDS}
        signal.lifecycle_state, signal.lifecycle_reason = lifecycle(signal, now)
    new_cache = {"signature": signature, "records": decisions}
    if cache != new_cache:
        atomic_bytes(path, gzip.compress(json.dumps(new_cache, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    awards = sorted((s for s in candidates if is_public_award(s, now) and s.prefilter_score >= threshold), key=lambda s: ranking_key(s, now))
    return awards, history, translations


def export_awards(root, canonical, config, now, record_manifest=None, context_signals=None):
    awards, history, translations = prepare_awards(root, canonical, config, now)
    public_records = awards + (context_signals or [])
    for signal in history + public_records:
        enrich_signal(signal)
    buyer_ids = {s.buyer_id for s in public_records if s.buyer_id}
    procedure_ids = {s.procedure_id for s in public_records if s.procedure_id}
    context = [s for s in history if s.buyer_id in buyer_ids or s.procedure_id in procedure_ids]
    context_translations = available_translations(root, context)
    context_translations.update(translations)
    attach_history(awards, history, context_translations)
    history_ids = {s.id for s in history}
    attach_history([s for s in canonical if s.id in history_ids] + (context_signals or []), history, context_translations)
    if record_manifest is not None:
        buyer_refs = {}
        award_ids = {s.id for s in awards}
        for signal in public_records:
            _, record_manifest[signal.id] = record_file(root, signal, context_translations.get(signal.id),
                "awards" if signal.id in award_ids else "opportunities", buyer_refs)
        # Linked history retains complete text without thousands of additional
        # uncompressed files or recursively repeated buyer/procedure histories.
        record_manifest.update(history_files(root, [s for s in context if s.id not in record_manifest],
            context_translations, buyer_refs))
    manifest = {}
    for market, countries in MARKETS.items():
        records = [s for s in awards if set(countries).intersection(s.countries)]
        ids = {s.id for s in records}
        payload = {"schema_version": "1.0", "signals": [public_signal(s, translations.get(s.id)) for s in records],
                   "translations": {sid: value for sid, value in translations.items() if sid in ids}}
        relative = f"awards/{market}-{digest(payload)[:16]}.json"
        atomic_public_json(root / "app/public/data" / relative, payload)
        manifest[market] = {"url": relative, "count": len(records)}
    # Old manifests must remain readable until the new root manifest is published.
    return manifest
