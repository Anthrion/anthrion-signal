import copy
import gzip
import json

from anthrion_signal import discovery_cache
from anthrion_signal.discovery import lifecycle, prefilter
from anthrion_signal.utils import digest


def test_cache_matches_fresh_classification_and_never_caches_lifecycle(tmp_path, signal, config, now, monkeypatch):
    cache = discovery_cache.ClassificationCache(tmp_path, config)
    expected = signal.model_copy(deep=True)
    prefilter([expected], config["company_profile"], config["search_terms"], config["capabilities"])
    assert cache.classify([signal]) == 1
    for field in discovery_cache.FIELDS:
        assert getattr(signal, field) == getattr(expected, field)
    cache.save()
    fresh = discovery_cache.ClassificationCache(tmp_path, config)
    def no_misses(signals, *args):
        assert not signals
    monkeypatch.setattr(discovery_cache, "prefilter", no_misses)
    signal.deadline_at = "2001-01-01"
    signal.response_deadlines = []
    signal.deadlines = []  # Exercise a legacy deadline without newer source facts.
    assert fresh.classify([signal]) == 0
    assert lifecycle(signal, now)[0] == "EXPIRED"
    signal.status = "cancelled"
    assert fresh.classify([signal]) == 0
    assert lifecycle(signal, now)[0] == "CANCELLED"


def test_scope_translation_and_policy_changes_invalidate_and_duplicates_share_work(tmp_path, signal, config):
    cache = discovery_cache.ClassificationCache(tmp_path, config)
    duplicate = signal.model_copy(deep=True)
    assert cache.classify([signal, duplicate]) == 1
    duplicate.capability_evidence.clear()
    assert signal.capability_evidence
    cache.save()
    for field, changed in [("description", "Supply printed journals only."), ("title", "Revised scope"),
                           ("buyer_name", "New buyer"), ("cpv_codes", ["45000000"]),
                           ("source", "sam"), ("notice_type", "RFI"), ("signal_type", "FUNDING")]:
        candidate = signal.model_copy(deep=True, update={field: changed})
        assert cache.classify([candidate]) == 1
        assert cache.classify([candidate]) == 0
    overlay = {signal.id: {"source_hash": digest([signal.title, signal.description]),
                          "title": "Salesforce CRM", "description": "Implement Salesforce CRM software."}}
    assert cache.classify([signal], overlay) == 1
    assert cache.classify([signal], overlay) == 0
    policy = copy.deepcopy(config)
    policy["capabilities"]["version"] += "-changed"
    assert discovery_cache.ClassificationCache(tmp_path, policy).classify([signal]) == 1


def test_missing_corrupt_or_malformed_cache_recomputes_without_discarding_records(tmp_path, signal, config):
    cache = discovery_cache.ClassificationCache(tmp_path, config)
    assert cache.classify([signal]) == 1
    cache.save()
    for content in (b"bad gzip", gzip.compress(b"[]"), gzip.compress(b'{"records":[]}')):
        cache.path.write_bytes(content)
        assert discovery_cache.ClassificationCache(tmp_path, config).classify([signal]) == 1
    cache.save()
    values = json.loads(gzip.decompress(cache.path.read_bytes()))
    key = next(iter(values["records"]))
    values["records"][key]["delivery_priority"] = "invalid"
    cache.path.write_bytes(gzip.compress(json.dumps(values).encode()))
    assert discovery_cache.ClassificationCache(tmp_path, config).classify([signal]) == 1


def test_digital_outcomes_deadline_repair_also_runs_on_a_cache_hit(tmp_path, signal, config):
    signal.source = "digital_outcomes"
    signal.description += " Closing date for applications: 1 December 2026 at 12:00pm."
    cache = discovery_cache.ClassificationCache(tmp_path, config)
    cache.classify([signal])
    repaired = signal.deadline_at
    signal.deadline_at, signal.response_deadlines = None, []
    assert cache.classify([signal]) == 0
    assert signal.deadline_at == repaired
