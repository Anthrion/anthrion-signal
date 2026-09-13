import copy
from datetime import timedelta

import pytest

from anthrion_signal.discovery import prefilter
from anthrion_signal.german_notices import collect_german_notices, relevant_release
from anthrion_signal.spain_notices import relevant_placsp_record
from anthrion_signal.utils import digest
from anthrion_signal.vocabulary import collection_match


def classify(signal, config, title, description="", cpv=None, translations=None):
    signal.title, signal.description, signal.cpv_codes = title, description, cpv or []
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"], translations)
    return signal


@pytest.mark.parametrize("title,description,required", [
    ("Upgrade of citizen service 1555", "Αναβάθμιση πολυκαναλικού συστήματος εξυπηρέτησης πολιτών, διαχείρισης αιτημάτων και τεχνητής νοημοσύνης.", {"contact_centre", "service", "ai"}),
    ("Asiakastietojärjestelmä SaaS-palveluna", "Hankitaan asiakastietojärjestelmän toteutus.", {"crm"}),
    ("Social Housing Allocation System", "Supplier to implement a new housing allocation system.", {"service", "industry"}),
    ("Artificial Intelligence (AI)-Powered Pre-Plan Check (AIP-PPC) Assistant", "", {"ai"}),
    ("HRIS platform", "Employee Self Service and Manager Self Service. People Analytics.", {"portals", "analytics"}),
    ("Financial Benchmarking & Insights Tool Continuous Improvement", "Maintain and develop our Financial Benchmarking & Insights Tool.", {"analytics"}),
    ("Student admission applications", "Application maintenance and upgrades. End-user helpdesk is not included.", {"managed"}),
    ("Citizen services", "Implement Salesforce Public Sector Solutions with OmniStudio Document Generation.", {"salesforce", "service", "industry", "workflow"}),
    ("Software procurement", "Lot 1: Servers. Lot 2: Customer portal and AI assistant implementation.", {"portals", "ai"}),
    ("Database delivery", "An off-the-shelf database is required as a central communication hub for staff and community coalitions.", {"relationships"}),
])
def test_positive_controls_without_cpv(signal, config, title, description, required):
    classify(signal, config, title, description)
    assert required <= set(signal.matched_capabilities)
    assert signal.prefilter_score >= 12
    assert not signal.exclusion_reasons
    assert set(signal.matched_capabilities) == {e["capability"] for e in signal.capability_evidence}


@pytest.mark.parametrize("title,description,forbidden", [
    ("Software licensing", "Supply Microsoft software licences, including Power BI.", {"external_integration", "analytics"}),
    ("Team equipment", "Supply computer systems to volunteer teams.", {"external_integration"}),
    ("Backup appliance", "Storage software with compression and deduplication.", {"data"}),
    ("Fornitura", "Il sistema fornisce servizi ai cittadini.", {"ai"}),
    ("Apex building systems", "Lightning protection systems and Apex maintenance services.", {"salesforce"}),
    ("Public sector consultancy", "Public sector strategy and a Government Cloud presentation.", {"salesforce", "industry"}),
    ("Knowledge platform", "An application maintenance service; end-user helpdesk is not included.", {"contact_centre"}),
    ("Research grant", "The applicant must be a permanent resident. Data archiving and database management are required.", {"relationships"}),
    ("Research equipment", "Computer system for running AI applications. Computing system for training Large Language Models.", {"ai", "genai"}),
    ("Tender", "Submit your bid through our customer portal. Check the portal for further updates.", {"portals"}),
    ("Future engagement", "Preliminary market engagement on a procurement pipeline.", {"pipeline"}),
])
def test_incidental_words_do_not_assign_capabilities(signal, config, title, description, forbidden):
    classify(signal, config, title, description, ["48000000"])
    assert not forbidden.intersection(signal.matched_capabilities)


def test_mechanical_interface_coordination_is_not_software_integration(signal, config):
    classify(signal, config, "BEW-Transformationsplan Wärmenetz", "Generalkoordination und Schnittstellenmanagement für Tiefengeothermie.", ["71300000"])
    assert "integration" not in signal.matched_capabilities
    assert signal.prefilter_score < 12


@pytest.mark.parametrize("title,description,excluded", [
    ("Purchase and delivery of 2 brand-new servers", "Server hardware only.", True),
    ("Supply of Microsoft software licences", "M365, SQL Server and Power BI subscription quantities.", True),
    ("Supply of equipment", "Computing system for training Large Language Models. Laptops and computers.", True),
    ("IT infrastructure services", "Technical operational support.", False),
    ("Software Assurance Reviews", "Independent software engineering quality and maintainability reviews.", False),
    ("Servers and CRM", "Lot 1: New servers. Lot 2: A customer relationship management platform.", False),
    ("Unknown software notice", "Further information is in the tender documents.", False),
    ("Supply of equipment for a secure application roll-out", "Details in procurement documents.", False),
])
def test_narrow_supply_exclusions_preserve_mixed_and_sparse_notices(signal, config, title, description, excluded):
    classify(signal, config, title, description, ["48000000"])
    assert bool(signal.exclusion_reasons) is excluded


@pytest.mark.parametrize("language", ["de", "it", "es", "sv", "fi", "no", "da", "el", "is"])
def test_native_families_feed_collection_and_tagging_with_english_always_available(signal, config, language):
    pack = config["discovery_languages"][language]
    assert len(pack) >= 20
    for family, phrases in pack.items():
        phrase = phrases[0]
        classify(signal, config, phrase, "Software implementation.", ["48000000"])
        assert family in signal.matched_capabilities, (language, family, phrase)
        if family != "staffing":
            assert collection_match(phrase, config["search_terms"])
    classify(signal, config, "Salesforce CRM with an AI assistant", "", [])
    assert {"salesforce", "crm", "ai"} <= set(signal.matched_capabilities)
    assert signal.delivery_priority == "platform"


def test_exact_hash_translation_augments_evidence_without_changing_source_or_identity(signal, config):
    original = signal.model_copy(deep=True)
    original.title, original.description = "Asiakastiedot", "Lyhyt kuvaus."
    before = original.model_dump()
    overlay = {original.id: {"source_hash": digest([original.title, original.description]),
        "title": "Customer information system", "description": "Implement a customer information system."}}
    prefilter([original], config["company_profile"], config["search_terms"], config["capabilities"], overlay)
    assert "crm" in original.matched_capabilities
    assert all(e["basis"] == "english_translation" for e in original.capability_evidence)
    for key in ("id", "title", "description", "content_hash", "first_seen_at", "raw_source_hash"):
        assert getattr(original, key) == before[key]
    stale = copy.deepcopy(overlay)
    stale[original.id]["source_hash"] = "stale"
    prefilter([original], config["company_profile"], config["search_terms"], config["capabilities"], stale)
    assert "crm" not in original.matched_capabilities


def test_national_collector_gates_share_the_expanded_terms(config):
    assert relevant_release({"tender": {"title": "OmniStudio"}}, config["search_terms"], set())
    assert relevant_release({"tender": {"title": "Fördermittelmanagementsystem"}}, config["search_terms"], set())
    assert relevant_placsp_record({"state": "OPEN", "title": "plataforma de gestión de campañas"}, config["search_terms"])
    assert not collection_match("public sector Teams AI data", config["search_terms"])


def test_german_vocabulary_replays_recent_days_once_without_losing_old_pending(config, now):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "germany")
    older = (now - timedelta(days=30)).date().isoformat()
    state = {"scheduled_through": (now - timedelta(days=1)).date().isoformat(), "pending_days": [older]}
    settings = {**config["runtime"], "max_pages": 0}
    result = collect_german_notices(source, state, now, None, settings, config["search_terms"])
    assert older in result.state["pending_days"]
    assert len(result.state["pending_days"]) == settings["lookback_days"] + 1
    assert state["pending_days"] == [older]
    result.state["pending_days"] = []
    second = collect_german_notices(source, result.state, now, None, settings, config["search_terms"])
    assert second.state["pending_days"] == []
