import importlib.util
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

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


def test_new_legacy_value_cannot_keep_an_older_typed_amount(reconcile_script, signal):
    local = signal.model_dump()
    base = {**local, "amount": None}
    remote = {**base, "value_max": local["value_max"] + 1000, "last_seen_at": "2026-09-19T05:00:00Z"}
    with pytest.raises(ValueError, match="amount disagrees with numeric values"):
        reconcile_script.merge_record(base, local, remote)


def test_explicit_current_ids_do_not_restore_archive_only_records(reconcile_script, signal):
    record = signal.model_dump()
    archived = {**record, "id": "archived-only"}
    result = reconcile_script.merge_maps({}, {record["id"]: record, archived["id"]: archived}, {}, {record["id"]})
    assert list(result) == [record["id"]]


def test_explicit_empty_current_ids_do_not_restore_archives(reconcile_script, signal):
    record = signal.model_dump()
    assert reconcile_script.merge_maps({}, {record["id"]: record}, {}, set()) == {}


def test_record_moved_to_archive_uses_canonical_base_and_compact_output(reconcile_script, signal, tmp_path, monkeypatch):
    base = signal.model_dump(mode="json")
    base["buyer_identity_basis"] = "unknown"
    local = {**base, "buyer_identity_basis": "identifier"}
    remote = {**base, "last_seen_at": "2026-09-19T05:00:00Z"}
    current = {**base, "id": "still-current", "contacts": [], "buyer_history": []}
    archive = "data/archive/2026-09.jsonl.gz"

    def rows(*items):
        return ("\n".join(json.dumps(item) for item in items) + "\n").encode()

    seed = json.dumps({"sources": []}).encode()
    blobs = {("base", "data/signals.jsonl"): rows(base, current),
             ("remote", "data/signals.jsonl"): rows(current),
             ("remote", archive): gzip.compress(rows(remote)),
             ("remote", "data/current.json"): seed}
    for path, body in {archive: gzip.compress(rows(local)), "data/signals.jsonl": rows(current),
                       "data/current.json": seed, "data/source_state.json": b"{}", "data/history.jsonl": b""}.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)

    def fake_git(command, **kwargs):
        operation = command[1]
        return {"merge-base": b"base", "diff": archive.encode(),
                "ls-tree": archive.encode(), "rev-parse": b"remote-sha"}[operation]

    def fake_show(command, **kwargs):
        ref, path = command[2].split(":", 1)
        body = blobs.get((ref, path))
        return SimpleNamespace(stdout=body or b"", returncode=0 if body is not None else 1)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reconcile_script.subprocess, "check_output", fake_git)
    monkeypatch.setattr(reconcile_script.subprocess, "run", fake_show)
    monkeypatch.setattr("sys.argv", ["reconcile_release_data.py", "--remote", "remote", "--apply"])
    reconcile_script.main()

    merged = json.loads(gzip.decompress((tmp_path / archive).read_bytes()))
    assert merged["buyer_identity_basis"] == "identifier"
    assert merged["last_seen_at"] == remote["last_seen_at"]
    assert merged["title"] == base["title"]
    persisted = json.loads((tmp_path / "data/signals.jsonl").read_bytes())
    assert persisted["id"] == "still-current"
    assert "contacts" not in persisted and "buyer_history" not in persisted
    assert persisted["amount"] == current["amount"]
