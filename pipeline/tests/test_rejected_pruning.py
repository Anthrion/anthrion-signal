import gzip
import json
from datetime import timedelta

import pytest

from anthrion_signal.discovery_retention import read_rejected
from anthrion_signal.rejected_pruning import (REASONS, apply_pruning, disposable, plan_pruning,
                                             recoverable_candidates)
from anthrion_signal.rejected_store import directory, upsert
from anthrion_signal.translation import field_key
from anthrion_signal.utils import atomic_json


@pytest.fixture
def physical(signal, now):
    return signal.model_copy(update={
        "title": "Road resurfacing works", "description": "Construction of a footpath and resurfacing of the access road.",
        "status": "closed", "published_at": (now - timedelta(days=500)).isoformat(),
        "updated_at": (now - timedelta(days=400)).isoformat(), "deadline_at": (now - timedelta(days=390)).isoformat(),
        "cpv_codes": ["45233140"], "exclusion_reasons": sorted(REASONS)[:1], "prefilter_score": 0,
        "prefilter_matches": [], "matched_capabilities": [], "capability_evidence": [], "scope_evidence": [],
        "deadlines": [], "response_deadlines": [], "framework": None, "source_language": "en",
    })


@pytest.mark.parametrize("change", [
    {"status": "awarded"}, {"signal_type": "RENEWAL_SIGNAL"}, {"status": "postponed"},
    {"status": "unknown", "deadline_at": None}, {"contract_end": "2028-01-01"},
    {"extension_end": "2028-01-01"}, {"related_signal_id": "sig_useful"},
    {"winners": [{"name": "Supplier"}]}, {"prefilter_score": 1}, {"cpv_codes": ["45233140", "72200000"]},
    {"exclusion_reasons": []}, {"description": "Works with an option to extend for a year."},
    {"description": "Bauarbeiten mit Verlängerung."}, {"description": "Travaux avec reconduction."},
    {"description": "Construction with a separately supplied Salesforce system."},
    {"deadline_at": "2028-01-01"}, {"updated_at": "2026-09-01"},
])
def test_useful_or_uncertain_history_is_not_disposable(physical, now, change):
    assert disposable(physical, now, set())
    assert not disposable(physical.model_copy(update=change), now, set())


def test_translated_and_document_enriched_records_are_preserved(physical, now):
    assert not disposable(physical, now, {field_key(physical.description)})
    assert not disposable(physical, now, set(), document_urls={physical.documents[0].url})
    enriched = physical.model_copy(deep=True)
    enriched.documents[0].status = "cached"
    enriched.documents[0].pages = [{"page": 1, "text": "A retained source attachment"}]
    assert not disposable(enriched, now, set())


def unrelated(signal, suffix, **changes):
    return signal.model_copy(update={"id": "sig_" + suffix, "ocid": "ocds_" + suffix,
        "primary_source_url": "https://example.gov/" + suffix, "source_urls": ["https://example.gov/" + suffix],
        "external_ids": [suffix], "procedure_id": None, "procedure_identifiers": [], **changes})


def test_prune_preserves_public_canonical_reviews_and_linked_closures(tmp_path, physical, now, config):
    removable = unrelated(physical, "unused")
    public = unrelated(physical, "public")
    canonical = unrelated(physical, "canonical")
    reviewed = unrelated(physical, "reviewed")
    closure = unrelated(physical, "closure", ocid="shared")
    valuable = unrelated(physical, "valuable", ocid="shared", prefilter_score=15)
    changed_scope = unrelated(physical, "changed")
    earlier_relevant = changed_scope.model_copy(update={"description": "Salesforce delivery", "prefilter_score": 15,
        "updated_at": (now - timedelta(days=450)).isoformat()})
    upsert(tmp_path, [removable, public, canonical, reviewed, closure, valuable, earlier_relevant, changed_scope])
    path = tmp_path / "data/signals.jsonl"
    path.write_text(canonical.model_dump_json() + "\n")
    atomic_json(tmp_path / "config/record_reviews.json", {"records": [{"id": reviewed.id}]})
    manifest = {"current_feed": {"records": {public.id: {}}}}
    candidates, fingerprints = plan_pruning(tmp_path, manifest, now, config)
    assert set(candidates) == {removable.id}
    before = {s.id: s.model_dump() for s in read_rejected(tmp_path)}
    assert apply_pruning(tmp_path, candidates, fingerprints) > 0
    after = {s.id: s.model_dump() for s in read_rejected(tmp_path)}
    assert after == {sid: row for sid, row in before.items() if sid != removable.id}


def test_missing_manifest_or_concurrent_update_cannot_prune(tmp_path, physical, now, config):
    upsert(tmp_path, [physical])
    with pytest.raises(ValueError, match="manifest"):
        plan_pruning(tmp_path, {}, now, config)
    candidates, fingerprints = plan_pruning(tmp_path, {"current_feed": {"records": {}}}, now, config)
    assert candidates
    upsert(tmp_path, [physical.model_copy(update={"title": "CRM implementation"})])
    with pytest.raises(ValueError, match="changed after"):
        apply_pruning(tmp_path, candidates, fingerprints)
    assert read_rejected(tmp_path)[0].title == "CRM implementation"


def test_deletion_requires_every_version_in_recovery_commit(tmp_path, physical, monkeypatch):
    from anthrion_signal import rejected_pruning
    from anthrion_signal.utils import digest
    row = physical.model_dump(mode="json", exclude_defaults=True)
    changed = {**row, "last_seen_at": "2026-09-24T12:00:00Z"}
    candidates = {physical.id: {"hashes": [digest(row), digest(changed)], "bucket": "ab.jsonl.gz"}}
    path = directory(tmp_path) / "2026-09-23.jsonl.gz"
    legacy = gzip.compress((json.dumps(row) + "\n").encode())
    def git(command, **kwargs):
        return str(path.relative_to(tmp_path)).replace("\\", "/") + "\n" if command[1] == "ls-tree" else legacy
    monkeypatch.setattr(rejected_pruning.subprocess, "check_output", git)
    assert recoverable_candidates(tmp_path, "recovery-sha", candidates) == {}
    candidates[physical.id]["hashes"] = [digest(row)]
    assert recoverable_candidates(tmp_path, "recovery-sha", candidates) == candidates
