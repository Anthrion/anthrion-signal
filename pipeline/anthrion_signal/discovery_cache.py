"""Discardable source-classification cache; lifecycle is always evaluated afresh."""
import gzip
import json
from copy import deepcopy

from .discovery import discovery_signature, prefilter
from .models import Signal
from .notice_dates import digital_deadline
from .record_reviews import apply_inclusions, load_inclusions
from .utils import atomic_bytes, digest, read_json

FIELDS = ("prefilter_score", "prefilter_matches", "discovery_families", "delivery_priority",
          "matched_capabilities", "discovery_version", "exclusion_reasons", "capability_evidence",
          "scope_evidence", "categories")


class DiscoverySignatures:
    """Prove catalogue-only compatibility without weakening the policy signature.

    The classifier does not read search_terms.markets. Every other policy value
    and every engine file still participates in the unchanged full signature.
    Saved catalogues are candidates, never a trusted compatibility flag.
    """

    def __init__(self, config, previous_markets=None, transitions=None):
        self.config = config
        self.signature = discovery_signature(config)
        self._catalogues, self._verified = {}, {}
        self._add(previous_markets)
        # A small bridge survives ingest --no-export replacing current.json
        # before the independently generated award cache has been migrated.
        for entry in transitions[-3:] if isinstance(transitions, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("signature"), str):
                candidate = self._add(entry.get("markets"), entry["signature"])
                if candidate and candidate != self.signature:
                    self._verified[candidate] = self._catalogues[candidate]

    def _add(self, markets, expected_signature=None):
        if not isinstance(markets, dict) or any(
                not isinstance(key, str) or not isinstance(value, dict)
                or not isinstance(value.get("name"), str) or not isinstance(value.get("enabled"), bool)
                for key, value in markets.items()):
            return None
        try:
            # Reject malformed cache metadata rather than stringify arbitrary
            # objects through digest's permissive source-evidence fallback.
            json.dumps(markets, allow_nan=False)
        except (TypeError, ValueError):
            return None
        if markets == self.config["search_terms"]["markets"]:
            return self.signature if expected_signature in (None, self.signature) else None
        for signature, catalogue in self._catalogues.items():
            if catalogue == markets:
                return signature if expected_signature in (None, signature) else None
        signature = discovery_signature({**self.config, "search_terms": {
            **self.config["search_terms"], "markets": markets}})
        if expected_signature not in (None, signature):
            return None
        self._catalogues[signature] = deepcopy(markets)
        return signature

    def accepts(self, signature, markets=None):
        if not isinstance(signature, str):
            return False
        if signature == self.signature:
            return True
        self._add(markets)
        if signature not in self._catalogues:
            return False
        self._verified[signature] = self._catalogues[signature]
        return True

    def transitions(self):
        return [{"signature": signature, "markets": deepcopy(markets)}
                for signature, markets in list(self._verified.items())[-3:]]


def read_discovery_state(root):
    try:
        state = read_json(root / "data/discovery/state.json", {})
    except (OSError, ValueError, EOFError):
        return {}
    return state if isinstance(state, dict) else {}


def discovery_cache_signatures(root, config, previous_markets=None):
    return DiscoverySignatures(config, previous_markets, read_discovery_state(root).get("market_catalogues"))


class ClassificationCache:
    def __init__(self, root, config, *, previous_markets=None, signatures=None):
        self.config = config
        self.path = root / "data/discovery/current_classification.json.gz"
        self.signatures = signatures or discovery_cache_signatures(root, config, previous_markets)
        self.signature = self.signatures.signature
        # Restorations are applied after every lookup and never cached: removing
        # or staling one restores the classifier's own decision.
        self.inclusions, self.stale_inclusions, self.matched_inclusions = load_inclusions(root), set(), set()
        try:
            previous = json.loads(gzip.decompress(self.path.read_bytes()))
        except (OSError, ValueError, EOFError):
            previous = {}
        compatible = isinstance(previous, dict) and self.signatures.accepts(previous.get("signature"), previous.get("markets"))
        records = previous.get("records", {}) if compatible else {}
        self.records = records if isinstance(records, dict) else {}
        # Migrate the signature/catalogue even when every record is a cache hit.
        self.dirty = bool(compatible and (previous.get("signature") != self.signature
                          or previous.get("markets") != config["search_terms"]["markets"]))

    def classify(self, signals, translations=None):
        translations = translations or {}
        grouped, pending = {}, []
        for signal in signals:
            translated = translations.get(signal.id)
            if translated is not None and not isinstance(translated, dict):
                translated = translated.model_dump()
            key = digest([signal.title, signal.description, signal.buyer_name, signal.cpv_codes,
                          signal.source, signal.notice_type, signal.signal_type, translated])
            grouped.setdefault(key, []).append(signal)
        for key, group in grouped.items():
            values = self.records.pop(key, None)
            if isinstance(values, dict) and set(values) == set(FIELDS):
                try:
                    validated = Signal.model_validate({**group[0].model_dump(), **values})
                    self.records[key] = {field: getattr(validated, field) for field in FIELDS}
                    continue
                except ValueError:
                    pass
            pending.append(group[0])
        prefilter(pending, self.config["company_profile"], self.config["search_terms"], self.config["capabilities"], translations)
        pending_ids = {id(signal) for signal in pending}
        for key, group in grouped.items():
            if id(group[0]) in pending_ids:
                self.records[key] = {field: getattr(group[0], field) for field in FIELDS}
                self.dirty = True
            values = self.records[key]
            for signal in group:
                for field, value in values.items():
                    # Pydantic outputs are JSON-compatible scalars/lists/dicts;
                    # copy nested evidence so later enrichment cannot mutate cache.
                    setattr(signal, field, json.loads(json.dumps(value)))
                if signal.source == "digital_outcomes":
                    deadline = digital_deadline(signal.description)
                    if deadline:
                        signal.deadline_at, signal.response_deadlines = deadline, [deadline]
        if self.inclusions:
            matched, stale = apply_inclusions(signals, self.inclusions,
                                              self.config["capabilities"]["discovery"]["minimum_candidate_score"])
            # A later classification of the same notice supersedes an earlier outcome.
            self.stale_inclusions = (self.stale_inclusions - matched) | stale
            self.matched_inclusions |= matched
        return len(pending)

    def save(self):
        if not self.dirty:
            return
        # This is a performance cache, not record retention. Eviction recomputes
        # scope next time; original and rejected source evidence is untouched.
        recent = dict(list(self.records.items())[-50000:])
        body = json.dumps({"signature": self.signature, "markets": self.config["search_terms"]["markets"],
                           "records": recent}, ensure_ascii=False, sort_keys=True).encode()
        atomic_bytes(self.path, gzip.compress(body, compresslevel=6, mtime=0))
