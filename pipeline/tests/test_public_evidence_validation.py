"""Evidence membership checks must retain complete source and translated fields."""
import runpy
from pathlib import Path

import pytest

from anthrion_signal.public_context import public_signal
from anthrion_signal.utils import digest

evidence_checked = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/check_public_output.py"))["evidence_checked"]


@pytest.mark.parametrize("translated", [False, True])
def test_valid_evidence_after_24000_characters_survives_publication(signal, translated):
    quote = "Implement a CRM system."
    full_text = "Neutral context. " * 1600 + quote
    signal.description, signal.eligibility_text = ("Alkuperäinen kuvaus." if translated else full_text), None
    source_hash = digest([signal.title, signal.description])
    translation = {"source_hash": source_hash, "description": full_text} if translated else None
    signal.matched_capabilities = ["crm"]
    signal.capability_evidence = [{"capability": "crm", "field": "description", "phrase": "CRM", "strength": "needs",
                                   "basis": "english_translation" if translated else "original", "quote": quote}]
    result = public_signal(signal, translation)
    assert result["matched_capabilities"] == ["crm"]
    assert result["capability_evidence"][0]["quote"] == quote
    assert result["capability_evidence"][0]["source_hash"] == source_hash
    assert result["description"] == signal.description
    evidence_checked(result, translation)
    if translated:
        assert result["capability_evidence"][0]["original_quote"] == signal.description
        stale = {**translation, "source_hash": "stale"}
        assert not public_signal(signal, stale)["matched_capabilities"]
        with pytest.raises(ValueError, match="missing/stale translation"):
            evidence_checked(result, stale)


def test_long_quote_cannot_hide_an_invented_suffix_after_shared_prefix(signal):
    signal.description, signal.eligibility_text = "Neutral context. " * 1600, None
    signal.matched_capabilities = ["crm"]
    signal.capability_evidence = [{"capability": "crm", "field": "description", "basis": "original",
                                   "quote": signal.description + "Invented CRM requirement."}]
    assert not public_signal(signal)["matched_capabilities"]
    forged = public_signal(signal)
    forged["capability_evidence"] = [{**signal.capability_evidence[0],
        "source_hash": digest([signal.title, signal.description]), "source_url": signal.primary_source_url}]
    with pytest.raises(ValueError, match="cannot be traced"):
        evidence_checked(forged, None)


def test_participation_field_remains_traceable_after_a_long_description(signal):
    signal.description = "Neutral context. " * 1600
    signal.eligibility_text = "The supplier must have mandatory certification."
    signal.capability_evidence, signal.matched_capabilities = [], []
    result = public_signal(signal)
    assert result["participation_requirements"][0]["source_quote"] == signal.eligibility_text
    evidence_checked(result, None)
