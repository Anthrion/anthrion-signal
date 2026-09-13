import importlib.util
import json
from pathlib import Path

import pytest

from anthrion_signal.utils import digest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("audit_discovery", ROOT / "scripts/audit_discovery.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def snapshot(path, rows, translations):
    data = {"generated_at": "2026-09-13T14:07:52Z", "run": {"content_digest": "audit-fixture"},
            "signals": [row.model_dump() for row in rows], "translations": translations}
    path.write_text(json.dumps(data), encoding="utf-8")


def test_audit_compares_copies_without_changing_source_records(tmp_path, signal):
    customer = signal.model_copy(deep=True, update={
        "id": "customer", "title": "Asiakastietojarjestelma", "description": "Asiakastietojarjestelma",
        "matched_capabilities": [], "prefilter_matches": ["Relevant CPV classification"],
    })
    licence = customer.model_copy(deep=True, update={"id": "licence", "title": "Lizenzen"})
    path = tmp_path / "snapshot.json"
    translations = {
        customer.id: {"source_hash": digest([customer.title, customer.description]),
                      "title": "Customer information system", "description": "Implement a new customer information system."},
        licence.id: {"source_hash": digest([licence.title, licence.description]),
                     "title": "Microsoft software licences", "description": "Supply Microsoft software licences."},
    }
    snapshot(path, [customer, licence], translations)
    before = path.read_bytes()
    result = audit.inspect_dataset(ROOT, path, [customer.id, licence.id])
    assert path.read_bytes() == before
    assert customer.matched_capabilities == licence.matched_capabilities == []
    assert result["untagged"] == 2
    assert result["new_english_matches"] == 1
    assert result["new_english_context_only_matches"] == 0
    assert result["records_reviewed"][0]["english_test_capabilities"] == ["crm"]
    assert result["records_reviewed"][1]["source_capabilities"] == []


def test_audit_does_not_use_stale_translations(tmp_path, signal):
    path = tmp_path / "snapshot.json"
    snapshot(path, [signal], {signal.id: {"source_hash": "old", "title": "Old CRM title", "description": "Old"}})
    result = audit.inspect_dataset(ROOT, path)
    assert result["english_overlays_tested"] == 0
    assert result["stale_overlays_skipped"] == [signal.id]
    assert result["new_english_matches"] == 0


def test_audit_refuses_ambiguous_duplicate_ids(tmp_path, signal):
    path = tmp_path / "snapshot.json"
    snapshot(path, [signal, signal], {})
    with pytest.raises(ValueError, match="Duplicate signal IDs"):
        audit.inspect_dataset(ROOT, path)
