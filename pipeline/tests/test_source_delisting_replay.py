"""Source-confirmed disappearance also constrains previously rejected notice replay."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from anthrion_signal import cli
from anthrion_signal.collectors import Collection, RawRecord
from anthrion_signal.dedupe import merge
from anthrion_signal.discovery import discovery_signature
from anthrion_signal.discovery_retention import retain_rejected
from anthrion_signal.models import Dataset
from anthrion_signal.utils import atomic_json

from test_record_inclusions import classified, configured, inclusion, write_ledger
from test_restoration_fixes import RESCORE, public as public_fixture, threshold as threshold_fixture, write_canonical
from test_sam_opportunities import normalise as sam_notice
from test_canada_buys import normalise as canada_notice, row as canada_row, source as canada_source, CLOSING

public, threshold = public_fixture, threshold_fixture


@pytest.mark.parametrize("source_id", ["sam", "canada_buys"])
@pytest.mark.parametrize("operation", ["rescore", "export"])
def test_rejected_reviewed_notice_does_not_reopen_after_confirmed_delisting(
        tmp_path, config, now, public, threshold, monkeypatch, source_id, operation):
    if source_id == "sam":
        rejected = sam_notice(config, now, ResponseDeadLine="2099-10-01", Title="Supplier engagement",
                              Description="The authority needs assistance with its engagement programme.")
        state = {"sam": {"removed_ids": ["a" * 32], "removed_at": {"a" * 32: now.isoformat()}}}
    else:
        rejected = canada_notice(config, now, canada_row(**{CLOSING: "2099-10-01", "title-titre-eng": "Supplier engagement",
            "tenderDescription-descriptionAppelOffres-eng": "The authority needs assistance with its engagement programme."}))
        state = {"canada_buys": {"feeds": {"open": {"removed": ["tender:cb-100-123"],
                 "removed_at": {"tender:cb-100-123": now.isoformat()}}}}}
    rejected = classified(rejected, config)
    assert rejected.prefilter_score < threshold
    write_canonical(tmp_path, public)
    retain_rejected(tmp_path, [rejected], now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    atomic_json(tmp_path / "data/source_state.json", state)
    previous = Dataset(generated_at=now.isoformat(), data_updated_at=now.isoformat(), profile_version="1",
        scoring_version="none", run={"discovery_signature": discovery_signature(configured(config)(tmp_path))},
        sources=[], capabilities=[], markets={}, evidence_catalog={}, signals=[public])
    atomic_json(tmp_path / "data/current.json", previous.model_dump())
    write_ledger(tmp_path, inclusion(rejected, priority="other"))
    result = cli.run(tmp_path, SimpleNamespace(**RESCORE, no_export=True)) if operation == "rescore" else cli.export(tmp_path)
    assert {s.id for s in result.signals} == {public.id}


@pytest.mark.parametrize("source", ["sam", "canada_buys"])
def test_projection_preserves_terminal_status_and_newer_explicit_reopening(config, now, source):
    if source == "sam":
        from anthrion_signal.sam_opportunities import removed_sam_records as removed
        notice = sam_notice(config, now)
        state = {"removed_ids": ["a" * 32], "removed_at": {"a" * 32: now.isoformat()}}
    else:
        from anthrion_signal.canada_buys import removed_canada_records as removed
        notice = canada_notice(config, now)
        state = {"feeds": {"open": {"removed": ["tender:cb-100-123"],
                                  "removed_at": {"tender:cb-100-123": now.isoformat()}}}}
    for status in ("cancelled", "withdrawn", "closed", "awarded", "expired", "complete"):
        assert not removed([notice.model_copy(update={"status": status})], state, now.isoformat())
    newer = notice.model_copy(update={"updated_at": (now + timedelta(days=1)).isoformat()})
    assert not removed([newer], state, (now + timedelta(days=2)).isoformat())


@pytest.mark.parametrize("changes,normalized,projected", [
    ({}, "unknown", "not_listed"),
    ({"Type": "New upstream category"}, "unverified", "not_listed"),
    ({"Active": "No"}, "closed", "closed"),
])
def test_sam_listing_states_keep_their_lifecycle_when_projected(config, now, changes, normalized, projected):
    notice = sam_notice(config, now, **changes)
    assert notice.status == normalized
    state = {"sam": {"removed_ids": ["a" * 32], "removed_at": {"a" * 32: now.isoformat()}}}
    result = cli.project_source_removals([notice], state, now.isoformat())
    assert result[0].status == projected


@pytest.mark.parametrize("proof", ["fresh", "stale", "absent"])
def test_canada_resumed_open_snapshot_can_relist_unchanged_notice(config, now, monkeypatch, proof):
    from anthrion_signal.canada_buys import removed_canada_records
    notice = canada_notice(config, now)
    closed = removed_canada_records([notice], {"feeds": {"open": {"removed": ["tender:cb-100-123"]}}}, now.isoformat())[0]
    later = now + timedelta(days=1)
    checked_at = (later if proof != "stale" else now).isoformat()
    open_state = {"etag": '"same-resumable-version"', "checked_at": checked_at,
                  "hashes": {"tender:cb-100-123": "hash"} if proof != "absent" else {}}
    # The full snapshot already cleared the tombstone on the first bounded batch;
    # this row is emitted on a later batch with the same ETag.
    previous_state = {"canada_buys": {"feeds": {"open": {"etag": open_state["etag"], "pending": 1}}}}
    raw = RawRecord({"_kind": "tender", **canada_row()}, canada_source(config), later.isoformat(), "canada_buys")
    result = Collection(records=[raw], state={"feeds": {"open": open_state}})
    monkeypatch.setattr(cli, "collect_with_backfill", lambda *args: result)
    monkeypatch.setattr(cli, "hydrate_sparse", lambda *args: None)
    monkeypatch.setattr(cli, "Http", lambda *args: SimpleNamespace(close=lambda: None))
    _, incoming, _, health, _ = cli._collect(canada_source(config), previous_state, later, config, [closed])
    assert health.status == "healthy"
    reopened, _ = merge(closed, incoming[0])
    assert reopened.status == ("active" if proof == "fresh" else "not_listed")
    assert reopened.published_at == notice.published_at
