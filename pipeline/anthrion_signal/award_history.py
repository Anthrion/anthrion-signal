"""Replayable, market-partitioned historical awards with cached relevance decisions.

The cache is derived and dispensable. Original notices stay in the canonical,
archive and rejection stores. No translation/model requests are made here.
"""
import gzip
import json
import re

from .discovery import discovery_signature, is_public_award, lifecycle, prefilter, ranking_key
from .discovery_retention import read_rejected
from .models import Signal
from .translation import available_translations
from .utils import atomic_bytes, atomic_json, digest, parse_date

MARKETS = {"GB": ["GB"], "US": ["US"], "IT": ["IT"], "NORDICS": ["SE", "FI", "DK", "NO", "IS"],
           "DE": ["DE"], "ES": ["ES"], "GR": ["GR"]}
DECISION_FIELDS = ("prefilter_score", "prefilter_matches", "discovery_families", "delivery_priority",
                   "matched_capabilities", "discovery_version", "exclusion_reasons", "capability_evidence", "scope_evidence", "categories")
PUBLIC_EXCLUDE = {"analysis", "analysis_cache_key", "ai_status", "ai_model", "ai_scored_at", "fit_score",
                  "confidence_score", "known_weight", "score_components", "score_explanation", "recommendation",
                  "prefilter_score", "capability_evidence", "scope_evidence"}


def retained_history(root, canonical):
    # Canonical records are reconciled versions and override old archived copies,
    # including cancellations that supersede a former award.
    latest = {s.id: s for s in read_rejected(root)}
    for path in sorted((root / "data/archive").glob("*.jsonl.gz")):
        for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines():
            if line:
                signal = Signal.model_validate_json(line)
                previous = latest.get(signal.id)
                if previous is None or parse_date(signal.updated_at or signal.last_seen_at) >= parse_date(previous.updated_at or previous.last_seen_at):
                    latest[signal.id] = signal
    latest.update({s.id: s for s in canonical})
    return list(latest.values())


def export_awards(root, canonical, config, now):
    candidates = [s for s in retained_history(root, canonical) if is_public_award(s.model_copy(update={"exclusion_reasons": []}), now)]
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
    manifest = {}
    for market, countries in MARKETS.items():
        records = [s for s in awards if set(countries).intersection(s.countries)]
        ids = {s.id for s in records}
        payload = {"schema_version": "1.0", "signals": [s.model_dump(exclude=PUBLIC_EXCLUDE) for s in records],
                   "translations": {sid: value for sid, value in translations.items() if sid in ids}}
        relative = f"awards/{market}-{digest(payload)[:16]}.json"
        atomic_json(root / "app/public/data" / relative, payload)
        manifest[market] = {"url": relative, "count": len(records)}
    # Remove only our obsolete generated shards, never the retained source stores.
    current_paths = {item["url"] for item in manifest.values()}
    for path in (root / "app/public/data/awards").glob("*.json"):
        if f"awards/{path.name}" not in current_paths and re.fullmatch(r"(?:" + "|".join(MARKETS) + r")-[a-f0-9]{16}\.json", path.name):
            path.unlink()
    return manifest
