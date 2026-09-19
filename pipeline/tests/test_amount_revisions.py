"""Sparse source updates cannot mix financial values with unrelated metadata."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from anthrion_signal import cli
from anthrion_signal.collectors import RawRecord
from anthrion_signal.dedupe import merge
from anthrion_signal.models import Amount, Signal, SourceHealth
from anthrion_signal.normalise import material_payload, normalise_ocds, normalise_ted, set_hashes
from anthrion_signal.public_context import backfill_retained_facts, public_signal
from anthrion_signal.utils import digest, jsonl_lines


@pytest.mark.parametrize("currency_only", [False, True])
def test_sparse_award_preserves_proved_amount_and_its_source(release, source, now, currency_only):
    release["id"], release["tag"] = "award-1", ["award"]
    release["tender"].pop("value")
    release["tender"]["documents"] = []
    release["awards"] = [{"id": "a1", "status": "active", "value": {"amount": 15000, "currency": "GBP"}}]
    original = normalise_ocds(RawRecord(deepcopy(release), source, now.isoformat()))
    release["id"], release["date"] = "award-2", now.isoformat()
    release["awards"][0]["value"] = {"currency": "EUR"} if currency_only else {}
    sparse = normalise_ocds(RawRecord(release, source, now.isoformat()))
    assert sparse.amount.kind == "unknown" and sparse.amount.maximum is None

    result, _ = merge(original, sparse)
    assert result.primary_source_url == sparse.primary_source_url != original.primary_source_url
    assert result.amount == original.amount
    assert result.amount.kind == "award" and result.amount.source_url == original.primary_source_url
    assert (result.value_min, result.value_max, result.currency) == (None, 15000, "GBP")


@pytest.mark.parametrize(("minimum", "maximum", "currency"), [
    (None, 0, "USD"), (5000, None, "EUR"), (5000, 12500, "EUR"), (None, 16000, None),
])
def test_published_replacement_amount_changes_bounds_and_currency_together(signal, release, source, now, minimum, maximum, currency):
    release["id"], release["date"] = "updated-value", now.isoformat()
    release["tender"]["documents"] = []
    release["tender"]["value"] = {"amount": maximum, "currency": currency} if maximum is not None else {}
    release["tender"]["minValue"] = {"amount": minimum, "currency": currency} if minimum is not None else {}
    update = normalise_ocds(RawRecord(release, source, now.isoformat()))
    result, changed = merge(signal, update)
    assert changed and result.amount == update.amount
    assert result.amount.kind == "estimated_contract"
    assert (result.value_min, result.value_max, result.currency) == (minimum, maximum, currency)
    assert result.amount.source_url == update.primary_source_url


def test_unproved_sparse_legacy_amount_is_kept_without_an_invented_meaning(signal):
    signal.amount = Amount(kind="award", source_label="awards[].value", source_url=signal.primary_source_url)
    result = public_signal(signal)
    assert result["amount"]["kind"] == "unknown"
    assert result["amount"]["maximum"] == result["value_max"] == 250000
    assert result["amount"]["currency"] == "GBP"


@pytest.mark.parametrize(("minimum", "maximum", "currency"), [(None, 0, "USD"), (5000, None, "EUR"), (None, 16000, None)])
def test_legacy_replayed_price_does_not_inherit_an_older_amount_type(signal, minimum, maximum, currency):
    signal.signal_type = "AWARD"
    signal.amount.kind = "award"
    incoming = signal.model_copy(update={"amount": None, "value_min": minimum, "value_max": maximum,
        "currency": currency, "updated_at": "2026-09-10T12:00:00Z",
        "primary_source_url": "https://example.gov/notices/amendment"}, deep=True)

    result, changed = merge(signal, incoming)

    assert changed
    assert (result.value_min, result.value_max, result.currency) == (minimum, maximum, currency)
    assert (result.amount.minimum, result.amount.maximum, result.amount.currency) == (minimum, maximum, currency)
    assert result.amount.kind == "unknown"
    assert result.amount.source_url == incoming.primary_source_url
    assert incoming.amount is None


def test_legacy_currency_only_replay_does_not_change_units_of_retained_price(signal):
    incoming = signal.model_copy(update={"amount": None, "value_min": None, "value_max": None,
        "currency": "EUR", "updated_at": "2026-09-10T12:00:00Z"}, deep=True)

    result, _ = merge(signal, incoming)

    assert result.amount == signal.amount
    assert (result.value_min, result.value_max, result.currency) == (signal.value_min, signal.value_max, signal.currency)


def test_legacy_replay_with_unchanged_price_preserves_proved_meaning_and_source(signal):
    signal.signal_type = "AWARD"
    signal.amount.kind = "award"
    incoming = signal.model_copy(update={"amount": None, "updated_at": "2026-09-10T12:00:00Z",
        "primary_source_url": "https://example.gov/notices/amendment"}, deep=True)

    result, _ = merge(signal, incoming)

    assert result.amount == signal.amount
    assert result.amount.kind == "award"
    assert result.primary_source_url == incoming.primary_source_url != result.amount.source_url


def test_ted_sparse_revision_preserves_amount_and_distinct_notice_provenance(config, now):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "ted")
    raw = {"publication-number": "694369-2023", "title-proc": {"eng": "CRM implementation"},
           "form-type": "competition", "publication-date": "2023-11-15Z",
           "estimated-value-proc": "8264463", "estimated-value-cur-proc": "EUR"}
    original = normalise_ted(RawRecord(deepcopy(raw), source, now.isoformat(), "ted"))
    raw.update({"publication-number": "731503-2024", "publication-date": "2024-11-29+01:00",
                "estimated-value-proc": None, "estimated-value-cur-proc": None})
    sparse = normalise_ted(RawRecord(raw, source, now.isoformat(), "ted"))
    assert sparse.amount.kind == "unknown"
    result, _ = merge(original, sparse)
    assert result.amount == original.amount
    assert result.amount.source_url.endswith("694369-2023")
    assert [p.release_id for p in result.provenance] == ["694369-2023", "731503-2024"]
    assert len({p.raw_hash for p in result.provenance}) == 2

    # Retained legacy records used an empty release ID for both TED revisions.
    original.provenance[0].release_id = sparse.provenance[0].release_id = ""
    legacy, _ = merge(original, sparse)
    assert {p.url for p in legacy.provenance} == {original.primary_source_url, sparse.primary_source_url}


def test_backfill_refreshes_enrichment_hash_without_changing_source_text_or_raw_hash(signal):
    signal.amount, signal.deadlines = None, []
    set_hashes(signal)
    before = signal.model_dump()
    backfill_retained_facts([signal], {})
    assert signal.content_hash == signal.material_change_hash == digest(material_payload(signal))
    assert signal.content_hash != before["content_hash"]
    for field in ("raw_source_hash", "title", "description", "source_urls", "primary_source_url", "provenance", "published_at", "updated_at", "fingerprint"):
        assert signal.model_dump()[field] == before[field]
    material_hash = signal.content_hash
    backfill_retained_facts([signal], {})
    assert signal.content_hash == material_hash


def test_cached_source_corrections_recompute_hash_and_preserve_original_text(signal):
    signal.source, signal.external_ids = "grants", ["grants:123"]
    cached = {"id": "123", "title": "Newer cached title", "agencyDetails": {"agencyCode": "DOE", "agencyName": "Department of Energy"},
        "facts": {"awardFloor": 5000, "awardCeiling": 10000, "responseDateStr": "2026-12-01-00-00-00",
                  "agencyContactName": "Public grant contact", "synopsisDesc": "Newer cached description"}}
    source_evidence = (signal.title, signal.description, signal.raw_source_hash, signal.provenance)
    old_hash = signal.content_hash
    backfill_retained_facts([signal], {"grants": {"detail_cache": {"123": {"record": cached}}}})
    assert signal.buyer_name == "Department of Energy" and signal.contacts[0]["name"] == "Public grant contact"
    assert signal.deadline_at == "2026-12-01" and signal.amount.maximum == 10000
    assert (signal.value_min, signal.value_max, signal.currency) == (5000, 10000, "USD")
    assert (signal.title, signal.description, signal.raw_source_hash, signal.provenance) == source_evidence
    assert signal.content_hash != old_hash
    assert signal.content_hash == signal.material_change_hash == digest(material_payload(signal))


def test_ingest_persists_partial_lot_outcome_hash_without_response_deadlines(tmp_path, release, source, config, now, monkeypatch):
    release["tender"].pop("tenderPeriod")
    release["tender"]["lots"] = [{"id": "1", "title": "CRM implementation", "status": "active"},
                                 {"id": "2", "title": "CRM integration", "status": "active"}]
    original = normalise_ocds(RawRecord(deepcopy(release), source, now.isoformat()))
    (tmp_path / "data").mkdir()
    (tmp_path / "data/signals.jsonl").write_text(original.model_dump_json() + "\n", encoding="utf-8")
    release["id"], release["tag"], release["date"] = "partial-award", ["award"], now.isoformat()
    release["awards"] = [{"id": "a1", "status": "active", "relatedLots": ["1"],
                          "value": {"amount": 15000, "currency": "GBP"}, "suppliers": [{"name": "CRM supplier"}]}]
    award = normalise_ocds(RawRecord(release, source, now.isoformat()), original)
    health = SourceHealth(id=source["id"], name=source["name"], website=source["website"], enabled=True, status="healthy")
    monkeypatch.setattr(cli, "load_config", lambda root: config)
    monkeypatch.setattr(cli, "_collect", lambda *args: (source["id"], [award], {}, health, 1))
    monkeypatch.setattr(cli, "enrich_documents", lambda *args, **kwargs: None)
    args = SimpleNamespace(command="ingest", days=None, max_pages=None, max_ai=0, no_ai=True, sources=source["id"])
    cli.run(tmp_path, args)
    rows = [Signal.model_validate_json(line) for line in jsonl_lines((tmp_path / "data/signals.jsonl").read_text(encoding="utf-8"))]
    stored = next(s for s in rows if s.id == original.id)
    assert not stored.response_deadlines
    assert [(lot.id, lot.status) for lot in stored.lots] == [("1", "awarded"), ("2", "active")]
    assert stored.status == "active" and stored.raw_source_hash == original.raw_source_hash
    assert stored.content_hash == stored.material_change_hash == digest(material_payload(stored))
    assert stored.content_hash != original.content_hash
