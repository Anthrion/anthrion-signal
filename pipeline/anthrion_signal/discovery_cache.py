"""Discardable source-classification cache; lifecycle is always evaluated afresh."""
import gzip
import json

from .discovery import discovery_signature, prefilter
from .models import Signal
from .notice_dates import digital_deadline
from .utils import atomic_bytes, digest

FIELDS = ("prefilter_score", "prefilter_matches", "discovery_families", "delivery_priority",
          "matched_capabilities", "discovery_version", "exclusion_reasons", "capability_evidence",
          "scope_evidence", "categories")


class ClassificationCache:
    def __init__(self, root, config):
        self.config = config
        self.path = root / "data/discovery/current_classification.json.gz"
        self.signature = discovery_signature(config)
        try:
            previous = json.loads(gzip.decompress(self.path.read_bytes()))
        except (OSError, ValueError, EOFError):
            previous = {}
        records = previous.get("records", {}) if isinstance(previous, dict) and previous.get("signature") == self.signature else {}
        self.records = records if isinstance(records, dict) else {}
        self.dirty = False

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
        return len(pending)

    def save(self):
        if not self.dirty:
            return
        # This is a performance cache, not record retention. Eviction recomputes
        # scope next time; original and rejected source evidence is untouched.
        recent = dict(list(self.records.items())[-50000:])
        body = json.dumps({"signature": self.signature, "records": recent}, ensure_ascii=False, sort_keys=True).encode()
        atomic_bytes(self.path, gzip.compress(body, compresslevel=6, mtime=0))
