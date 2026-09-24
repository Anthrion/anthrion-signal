import gzip
import json
from copy import deepcopy
from datetime import timedelta

import pytest

from anthrion_signal.discovery_retention import read_rejected, retain_rejected
from anthrion_signal.rejected_compaction import migrate
from anthrion_signal.rejected_store import (bucket_id, directory, jsonl_rows, pack_versions,
                                           read_bucket, unpack_versions)
from anthrion_signal.utils import digest


def write_versions(root, name, rows):
    path = directory(root) / f"{name}.jsonl.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n").encode()))


def stored_versions(root, identifier):
    path = directory(root) / "compact" / f"{bucket_id(identifier)}.jsonl.gz"
    envelope = next(row for row in jsonl_rows(path) if row["current"]["id"] == identifier)
    return list(unpack_versions(envelope))


def test_field_history_round_trips_removed_fields_unicode_and_json_number_types(signal):
    original = signal.model_dump(mode="json", exclude_defaults=True)
    original["description"] = "Full scope\u2028with a paragraph\u0085and an amendment"
    original["value_max"] = 1
    original["documents"] = [{"url": "https://example.gov/a", "arbitrary": [True, {"number": 1}]}]
    changed = deepcopy(original)
    changed["description"] += " — revised"
    changed["value_max"] = 1.0
    changed["documents"][0]["arbitrary"] = [1, {"number": 1.0}]
    changed.pop("deadline_at")
    changed["extension_end"] = "2028-01-01"
    packed = pack_versions([original, changed])
    assert list(unpack_versions(packed)) == [original, changed]
    assert {digest(v) for v in unpack_versions(packed)} == {digest(original), digest(changed)}
    assert "deadline_at" in packed["previous"][0]["restore"]
    assert "extension_end" in packed["previous"][0]["remove"]


def test_migration_preserves_latest_precedence_and_every_distinct_version(tmp_path, signal, now):
    first = signal.model_dump(mode="json", exclude_defaults=True)
    cancelled = {**first, "status": "cancelled", "description": first["description"] + " Cancelled.",
                 "updated_at": (now + timedelta(days=4)).isoformat()}
    older = {**first, "updated_at": (now - timedelta(days=2)).isoformat(), "title": "Earlier source release"}
    write_versions(tmp_path, "2026-09-01", [first, cancelled])
    write_versions(tmp_path, "2026-09-02", [older, cancelled])
    before = [s.model_dump() for s in read_rejected(tmp_path)]
    dry = migrate(tmp_path)
    assert not dry["applied"]
    assert len(list(directory(tmp_path).glob("*.jsonl.gz"))) == 2
    result = migrate(tmp_path, apply=True)
    assert result["current_records"] == 1
    assert result["identical_rows_removed"] == 1
    assert [s.model_dump() for s in read_rejected(tmp_path)] == before
    assert {digest(v) for v in stored_versions(tmp_path, signal.id)} == {digest(v) for v in [first, cancelled, older]}
    assert not list(directory(tmp_path).glob("*.jsonl.gz"))
    assert migrate(tmp_path, apply=True)["already_compact"]


def test_updates_write_one_current_record_and_preserve_older_revisions(tmp_path, signal, now):
    signal.prefilter_score = 0
    retain_rejected(tmp_path, [signal], now, 12)
    migrate(tmp_path, apply=True)
    cancelled = signal.model_copy(update={"status": "cancelled", "updated_at": (now + timedelta(days=2)).isoformat()})
    delayed_old = signal.model_copy(update={"description": "Older full description", "updated_at": (now - timedelta(days=2)).isoformat()})
    retain_rejected(tmp_path, [cancelled, delayed_old], now + timedelta(days=3), 12)
    assert read_rejected(tmp_path)[0].model_dump() == cancelled.model_dump()
    versions = stored_versions(tmp_path, signal.id)
    assert len(versions) == 3
    assert {digest(v) for v in versions} == {digest(s.model_dump(mode="json", exclude_defaults=True))
                                           for s in [signal, cancelled, delayed_old]}
    retain_rejected(tmp_path, [cancelled], now + timedelta(days=4), 12)
    assert len(stored_versions(tmp_path, signal.id)) == 3
    assert not list(directory(tmp_path).glob("*.jsonl.gz"))


def test_tied_dates_keep_the_last_observation_even_when_it_is_a_repeat(signal):
    first = signal.model_dump(mode="json", exclude_defaults=True)
    second = {**first, "status": "cancelled"}
    assert pack_versions([first, second, first])["current"] == first
    assert pack_versions([first, second])["current"] == second


def test_bad_history_fails_without_rewriting_or_removing_inputs(tmp_path, signal, now):
    retain_rejected(tmp_path, [signal], now, 12)
    migrate(tmp_path, apply=True)
    path = directory(tmp_path) / "compact" / f"{bucket_id(signal.id)}.jsonl.gz"
    row = next(jsonl_rows(path))
    row["previous"] = [{"hash": "bad", "restore": {"description": "Changed"}, "remove": []}]
    body = gzip.compress((json.dumps(row) + "\n").encode())
    path.write_bytes(body)
    with pytest.raises(ValueError, match="integrity"):
        retain_rejected(tmp_path, [signal], now, 12)
    assert path.read_bytes() == body


def test_interrupted_cleanup_does_not_restore_an_older_tied_version(tmp_path, signal, monkeypatch):
    from pathlib import Path
    first = signal.model_dump(mode="json", exclude_defaults=True)
    later = {**first, "status": "cancelled"}
    write_versions(tmp_path, "2026-09-01", [first])
    write_versions(tmp_path, "2026-09-02", [later])
    unlink = Path.unlink
    def interrupted(path, *args, **kwargs):
        if path.name == "2026-09-01.jsonl.gz":
            raise OSError("Interrupted after writing migration marker")
        return unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", interrupted)
        with pytest.raises(OSError, match="Interrupted"):
            migrate(tmp_path, apply=True)
    assert read_rejected(tmp_path)[0].status == "cancelled"
    migrate(tmp_path, apply=True)
    assert read_rejected(tmp_path)[0].status == "cancelled"
    assert len(stored_versions(tmp_path, signal.id)) == 2


def test_duplicate_bucket_ids_and_changed_inputs_fail_closed(tmp_path, signal, monkeypatch):
    from anthrion_signal import rejected_compaction
    row = signal.model_dump(mode="json", exclude_defaults=True)
    write_versions(tmp_path, "2026-09-01", [row])
    original = directory(tmp_path) / "2026-09-01.jsonl.gz"
    before = original.read_bytes()
    actual_hash = rejected_compaction.file_hash
    calls = 0
    def modified(path):
        nonlocal calls
        calls += 1
        return actual_hash(path) if calls == 1 else "concurrent writer changed input"
    with monkeypatch.context() as patch:
        patch.setattr(rejected_compaction, "file_hash", modified)
        with pytest.raises(ValueError, match="changed during"):
            migrate(tmp_path, apply=True)
    assert original.read_bytes() == before
    assert not (directory(tmp_path) / "format.json").exists()
    path = directory(tmp_path) / "compact" / f"{bucket_id(signal.id)}.jsonl.gz"
    path.parent.mkdir()
    envelope = json.dumps(pack_versions([row]))
    path.write_bytes(gzip.compress((envelope + "\n" + envelope + "\n").encode()))
    with pytest.raises(ValueError, match="identity"):
        read_bucket(path)


def test_same_day_observation_refreshes_do_not_inflate_history(tmp_path, signal, now):
    from anthrion_signal.rejected_store import upsert
    original = signal.model_dump(mode="json", exclude_defaults=True)
    write_versions(tmp_path, "2026-09-09", [original])
    migrate(tmp_path, apply=True)
    upsert(tmp_path, [signal])  # An identical replay must not mark a migrated row replaceable.
    for hour in range(1, 8):
        observed = signal.model_copy(deep=True)
        observed.first_seen_at = observed.last_seen_at = (now + timedelta(hours=hour)).isoformat()
        observed.provenance[0].retrieved_at = observed.last_seen_at
        upsert(tmp_path, [observed])
    versions = stored_versions(tmp_path, signal.id)
    assert len(versions) == 2  # Original migrated row plus latest daily observation.
    assert digest(original) in {digest(v) for v in versions}
    assert read_rejected(tmp_path)[0].last_seen_at == observed.last_seen_at
    # Even facts omitted by the old content_hash must start a separate version.
    observed.buyer_identifiers = ["new-published-buyer-id"]
    upsert(tmp_path, [observed])
    assert len(stored_versions(tmp_path, signal.id)) == 3
    observed.last_seen_at = (now + timedelta(days=1)).isoformat()
    upsert(tmp_path, [observed])
    assert len(stored_versions(tmp_path, signal.id)) == 4
