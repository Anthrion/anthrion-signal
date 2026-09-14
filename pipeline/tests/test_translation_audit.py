import importlib.util
from pathlib import Path

from anthrion_signal.translation import VERSION
from anthrion_signal.utils import digest

spec = importlib.util.spec_from_file_location(
    "audit_translations", Path(__file__).resolve().parents[2] / "scripts/audit_translations.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def test_audit_distinguishes_notice_coverage_from_optional_buyer_renderings():
    first = {"id": "one", "title": "Manutenzione del sistema", "description": "Durata: 60 mesi.",
             "buyer_name": "Fondimpresa", "countries": ["IT"]}
    second = {**first, "id": "two"}
    entry = {"version": VERSION, "source_hash": digest([first["title"], first["description"]]),
             "title": "System maintenance", "description": "Duration: 60 months."}
    audit = audit_module.audit_dataset({"signals": [first, second], "translations": {"one": entry}})
    assert audit["complete_records"] == 1
    assert audit["by_country"]["IT"] == {"records": 2, "complete": 1}
    assert audit["outstanding_records"][0]["id"] == "two"
    assert audit["outstanding_records"][0]["problems"] == ["missing_pair"]


def test_audit_detects_changed_numbers_even_when_translation_is_english():
    record = {"id": "one", "title": "Contract", "description": "The contract lasts 60 months.",
              "countries": ["GB"]}
    entry = {"version": VERSION, "source_hash": digest([record["title"], record["description"]]),
             "title": record["title"], "description": "The contract lasts 50 months."}
    audit = audit_module.audit_dataset({"signals": [record], "translations": {"one": entry}})
    assert audit["complete_records"] == 0
    assert audit["outstanding_records"][0]["problems"] == ["description:failed_validation"]


def test_audit_rejects_stale_or_encoded_output():
    record = {"id": "one", "title": "The buyer's contract", "description": "", "countries": ["GB"]}
    entry = {"version": VERSION, "source_hash": "old", "title": "The buyer&#8217;s contract", "description": ""}
    audit = audit_module.audit_dataset({"signals": [record], "translations": {"one": entry}})
    assert audit["outstanding_records"][0]["problems"] == ["stale_source", "title:encoded_characters"]
