"""Canonical compaction preserves source facts across old and new write paths."""
import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from anthrion_signal import cli
from anthrion_signal.canonical import canonical_signal_json
from anthrion_signal.models import Signal, SourceHealth
from anthrion_signal.normalise import material_payload, set_hashes
from anthrion_signal.public_context import public_signal
from anthrion_signal.utils import jsonl_lines


DEFAULT_ENRICHMENT = {
    "buyer_id": None, "buyer_identity_basis": "unknown", "agency_name": None,
    "department_name": None, "contacts": [], "buyer_name_conflicts": [], "source_language": "und",
    "procedure_id": None, "procedure_identifiers": [], "lots": [], "lot_award_baseline": {},
    "procedure_history": [], "buyer_history": [], "buyer_history_ref": None, "award_date": None,
    "winners": [], "amount": None, "deadlines": [], "delivery_role": {}, "participation_requirements": [],
}


def reconciliation_script():
    path = Path(__file__).resolve().parents[2] / "scripts/reconcile_release_data.py"
    spec = importlib.util.spec_from_file_location("reconcile_release_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_equivalent(signal):
    before = signal.model_dump()
    compact = canonical_signal_json(signal)
    restored = Signal.model_validate_json(compact)
    assert signal.model_dump() == before  # Serialization does not mutate the source model.
    assert restored.model_dump() == before
    assert material_payload(restored) == material_payload(signal)
    assert set_hashes(restored.model_copy(deep=True)).content_hash == set_hashes(signal.model_copy(deep=True)).content_hash
    assert public_signal(restored.model_copy(deep=True)) == public_signal(signal.model_copy(deep=True))
    return json.loads(compact)


def test_only_new_top_level_defaults_are_omitted_and_explicit_defaults_match(signal):
    full = {**signal.model_dump(), **DEFAULT_ENRICHMENT}
    legacy = {key: value for key, value in full.items() if key not in DEFAULT_ENRICHMENT}
    explicit = Signal.model_validate(full)
    implicit = Signal.model_validate(legacy)
    assert explicit.model_fields_set != implicit.model_fields_set
    assert canonical_signal_json(explicit) == canonical_signal_json(implicit)
    payload = assert_equivalent(explicit)
    assert set(payload) == set(full) - set(DEFAULT_ENRICHMENT)
    assert payload == legacy
    assert payload["documents"] == full["documents"]
    assert payload["documents"][0]["status"] == "linked"
    assert payload["documents"][0]["pages"] == []
    assert payload["documents"][0]["content_hash"] is None


def test_every_populated_enrichment_fact_and_nested_document_survives(signal):
    url = signal.primary_source_url
    facts = {
        "buyer_id": "buyer-1", "buyer_identity_basis": "identifier", "agency_name": "Agency",
        "department_name": "Digital", "contacts": [{"name": "Public contact", "source_url": url}],
        "buyer_name_conflicts": ["Earlier source name"], "source_language": "de",
        "procedure_id": "procedure-1", "procedure_identifiers": ["published-procedure"],
        "lots": [{"id": "1", "source_url": url, "value_min": 0, "value_max": 0}],
        "lot_award_baseline": {"1": "active"},
        "procedure_history": [{"source_url": url, "status": "active"}],
        "buyer_history": [{"source_url": url, "supplier": "Example Ltd"}],
        "buyer_history_ref": {"url": "buyers/buyer-1.json", "count": 1},
        "award_date": "2026-09-08", "winners": [{"name": "Example Ltd", "source_url": url}],
        "amount": {"kind": "award", "minimum": 0, "maximum": 0, "currency": "GBP",
                   "source_label": "Award value", "source_url": url},
        "deadlines": [{"kind": "tender", "date": "2026-10-01", "precision": "date",
                       "source_text": "1 October", "source_url": url}],
        "delivery_role": {"kind": "advertised_component"},
        "participation_requirements": [{"requirement": "Register on the portal", "source_url": url}],
    }
    enriched = Signal.model_validate({**signal.model_dump(), **facts})
    enriched.documents[0].status = "cached"
    enriched.documents[0].content_hash = "document-hash"
    enriched.documents[0].pages = [{"page": 1, "text": "Original source evidence."}]
    payload = assert_equivalent(enriched)
    assert set(DEFAULT_ENRICHMENT).issubset(payload)
    assert payload["amount"]["maximum"] == 0
    assert payload["lots"][0]["value_min"] == 0
    assert payload["documents"] == enriched.model_dump()["documents"]


@pytest.mark.parametrize("local_change", [False, True])
def test_compact_local_and_full_remote_reconcile_without_false_fact_changes(signal, local_change):
    script = reconciliation_script()
    base = Signal.model_validate({**signal.model_dump(), **DEFAULT_ENRICHMENT})
    remote = base.model_copy(deep=True)
    remote.description += " The published scope also includes data migration."
    remote.last_seen_at = "2026-09-10T12:00:00Z"
    remote.contacts = [{"name": "New published contact", "source_url": remote.primary_source_url}]
    set_hashes(remote)
    local = base.model_copy(deep=True)
    if local_change:
        local.agency_name = "New published agency"
        set_hashes(local)
    full_base = script.records((base.model_dump_json() + "\n").encode())[base.id]
    compact_local = script.records((canonical_signal_json(local) + "\n").encode())[base.id]
    full_remote = script.records((remote.model_dump_json() + "\n").encode())[base.id]
    assert compact_local == local.model_dump(mode="json")
    merged = Signal.model_validate(script.merge_record(full_base, compact_local, full_remote))
    expected = remote.model_copy(deep=True)
    expected.agency_name = local.agency_name
    set_hashes(expected)
    assert merged.model_dump() == expected.model_dump()
    assert merged.content_hash == expected.content_hash


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
@pytest.mark.parametrize("compressed", [False, True])
def test_compact_unicode_rows_restore_defaults_in_release_reconciliation(signal, separator, compressed):
    signal = Signal.model_validate({**signal.model_dump(), **DEFAULT_ENRICHMENT})
    signal.incumbent_supplier = f"Source supplier{separator}Original name"
    body = (canonical_signal_json(signal) + "\r\n\r\n").encode("utf-8")
    if compressed:
        body = gzip.compress(body)
    restored = reconciliation_script().records(body, compressed=compressed)[signal.id]
    assert restored == signal.model_dump(mode="json")


def test_reconciliation_does_not_skip_a_truncated_canonical_row():
    with pytest.raises(ValueError, match="Invalid JSON"):
        reconciliation_script().records(b'{"id":"unfinished\n')


def test_ingest_export_rescore_use_compact_canonical_without_changing_public_facts(
    tmp_path, signal, source, config, monkeypatch,
):
    health = SourceHealth(id=source["id"], name=source["name"], website=source["website"], enabled=True, status="healthy")
    monkeypatch.setattr(cli, "load_config", lambda root: config)
    monkeypatch.setattr(cli, "_collect", lambda *args: (source["id"], [signal], {}, health, 1))
    monkeypatch.setattr(cli, "enrich_documents", lambda *args, **kwargs: None)
    args = SimpleNamespace(command="ingest", days=None, max_pages=None, max_ai=0, no_ai=True, sources=source["id"])
    initial = cli.run(tmp_path, args)
    before = {s.id: public_signal(s.model_copy(deep=True)) for s in initial.signals}
    args.command = "rescore"
    repeated = cli.run(tmp_path, args)
    after = {s.id: public_signal(s.model_copy(deep=True)) for s in repeated.signals}
    assert after == before
    rows = list(jsonl_lines((tmp_path / "data/signals.jsonl").read_text(encoding="utf-8")))
    assert len(rows) == 1
    assert "agency_name" not in json.loads(rows[0])
    assert "documents" in json.loads(rows[0])
    restored = Signal.model_validate_json(rows[0])
    assert restored.content_hash == repeated.signals[0].content_hash
    assert (tmp_path / "app/public/data/manifest.json").exists()
