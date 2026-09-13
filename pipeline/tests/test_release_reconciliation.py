import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def reconcile_script():
    path = Path(__file__).resolve().parents[2] / "scripts/reconcile_release_data.py"
    spec = importlib.util.spec_from_file_location("release_reconciliation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_deadline_repair_and_newer_collection_both_survive(reconcile_script, signal):
    base = signal.model_dump()
    local = {**base, "deadline_at": "2026-08-01T12:00:00Z"}
    remote = {**base, "last_seen_at": "2026-09-13T12:00:00Z"}
    result = reconcile_script.merge_record(base, local, remote)
    assert result["deadline_at"] == local["deadline_at"]
    assert result["last_seen_at"] == remote["last_seen_at"]
    assert result["id"] == signal.id
    assert result["title"] == signal.title


def test_unexpected_conflicting_source_facts_stop_release(reconcile_script, signal):
    base = signal.model_dump()
    with pytest.raises(ValueError, match="Conflicting source facts"):
        reconcile_script.merge_record(base, {**base, "title": "Local correction"}, {**base, "title": "Remote correction"})


def test_explicit_current_ids_do_not_restore_archive_only_records(reconcile_script, signal):
    record = signal.model_dump()
    archived = {**record, "id": "archived-only"}
    result = reconcile_script.merge_maps({}, {record["id"]: record, archived["id"]: archived}, {}, {record["id"]})
    assert list(result) == [record["id"]]
