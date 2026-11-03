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


@pytest.mark.parametrize(("quote", "context"), [
    ("Offer robust integration with existing systems using standards-based APIs.", "delivery"),
    ("Support integration and collaboration • Seamlessly integrate with existing systems.", "delivery"),
    ("It will also integrate with tools we already use.", "delivery"),
    ("Our existing system supports integration with other software.", "existing_system"),
    ("The existing system does not support integration.", "existing_system"),
    ("The existing CRM was developed to support integration with the finance system.", "existing_system"),
    ("The buyer currently uses its integration platform to provide seamless integration with the existing CRM.", "existing_system"),
    ("The existing system was developed in 2018.", "existing_system"),
])
def test_existing_system_context_preserves_commissioned_integration(signal, quote, context):
    signal.description = quote
    signal.matched_capabilities = ["integration"]
    signal.capability_evidence = [{"capability": "integration", "phrase": "integration", "strength": "needs",
        "field": "description", "basis": "original", "quote": quote}]
    result = public_signal(signal)
    assert result["capability_evidence"][0]["context"] == context
    evidence_checked(result, None)


@pytest.mark.parametrize(("phrase", "quote", "strength", "context"), [
    ("data cloud", "Technical assurance across architecture, integration, data, cloud/SaaS lock-in and security.", "contextual", "delivery"),
    ("data cloud", "Implement Data Cloud.", "explicit", "delivery"),
    ("data cloud", "Implement Data-Cloud.", "explicit", "delivery"),
    ("data cloud", "Review data, cloud services; implement Data Cloud.", "explicit", "delivery"),
    ("education cloud", "Digital Reading Education Cloud-based Software Solution", "contextual", "uncertain"),
    ("education cloud", "Education Cloud implementation", "explicit", "delivery"),
    ("education cloud", "Salesforce Education Cloud-based implementation", "explicit", "delivery"),
    ("salesforce", "Salesforce LogIT, Change IT decommission Security Operations Centre (SOC) Integration", "explicit", "existing_system"),
    ("salesforce", "Implement Salesforce and decommission legacy CRM.", "explicit", "delivery"),
    ("salesforce", "Migrate from Dynamics to Salesforce and decommission the old system.", "explicit", "delivery"),
    ("salesforce", "Salesforce implementation will decommission old tools.", "explicit", "delivery"),
    ("salesforce", "Integrate with Salesforce and decommission old interfaces.", "explicit", "delivery"),
    ("salesforce", "Maintain Salesforce during decommissioning of the old tools.", "explicit", "delivery"),
    ("salesforce", "Replace the old CRM with Salesforce and decommission the old tools.", "explicit", "delivery"),
    ("salesforce", "Salesforce will replace the old CRM, which will be decommissioned.", "explicit", "delivery"),
    ("salesforce", "The supplier must not deliver hardware and must implement Salesforce.", "explicit", "delivery"),
])
def test_named_product_evidence_requires_the_product_and_its_actual_role(signal, phrase, quote, strength, context):
    signal.description = quote
    signal.matched_capabilities = ["salesforce"]
    signal.capability_evidence = [{"capability": "salesforce", "phrase": phrase, "strength": "explicit",
        "field": "description", "basis": "original", "quote": quote}]
    result = public_signal(signal)
    assert result["id"] == signal.id
    assert result["matched_capabilities"] == signal.matched_capabilities
    assert result["capability_evidence"][0]["quote"] == quote
    assert result["capability_evidence"][0]["strength"] == strength
    assert result["capability_evidence"][0]["context"] == context
    evidence_checked(result, None)


@pytest.mark.parametrize(("quote", "strength", "context"), [
    ("It must not deliver technology, configure platforms, act as a systems integrator, or become part of the delivery supply chain.", "contextual", "uncertain"),
    ("The supplier will act as a systems integrator to implement the platform.", "needs", "delivery"),
    ("The supplier must not deliver hardware, but must act as a systems integrator to implement the CRM.", "needs", "delivery"),
    ("The supplier must not configure a systems integrator portal; the systems integrator must implement Salesforce.", "needs", "delivery"),
    ("The supplier must not deliver hardware and will act as a systems integrator to implement the CRM.", "needs", "delivery"),
])
def test_prohibited_delivery_does_not_rank_as_a_commissioned_implementation(signal, quote, strength, context):
    signal.description = quote
    signal.matched_capabilities = ["staffing"]
    signal.capability_evidence = [{"capability": "staffing", "phrase": "systems integrator", "strength": "needs",
        "field": "description", "basis": "original", "quote": quote}]
    result = public_signal(signal)
    assert result["matched_capabilities"] == signal.matched_capabilities
    assert result["capability_evidence"][0]["strength"] == strength
    assert result["capability_evidence"][0]["context"] == context
    evidence_checked(result, None)
