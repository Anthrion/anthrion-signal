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
    ("Planung, Errichtung und Betrieb eines Gigabit-Netzes", "Netzbetreiber für den Breitbandausbau.", True),
    ("Hyrda fiberförbindelser och tjänster", "Hyrda förbindelser för nätverket.", True),
    ("Broadband network construction", "Construct the network. Lot 2: Implement a customer portal and CRM.", False),
    ("Broadband network AI assistant", "Develop an AI assistant for field staff.", False),
    ("Broadband network", "Scope not yet published.", False),
    ("SUMINISTRO DE LICENCIAS Y SOPORTE PARA DOS FIREWALLS PALOALTO", "Renovación de licencias de cortafuegos.", True),
    ("Erweiterung und Sanierung der Aventinus-Grundschule", "Kernsanierung in zwei Bauabschnitten.", True),
    ("School refurbishment and software", "Lot 2: Implement a student admissions system.", False),
])
def test_narrow_supply_exclusions_preserve_mixed_and_sparse_notices(signal, config, title, description, excluded):
    classify(signal, config, title, description, ["48000000"])
    assert bool(signal.exclusion_reasons) is excluded


@pytest.mark.parametrize("description,required", [
    ("Submission of a pre-proposal/pre-application is required and must be submitted through the electronic Biomedical Research Application Portal (eBRAP).", set()),
    ("EDGE was developed to streamline the application and grants management process by implementing a single platform with higher data quality.", set()),
    ("Funding for full Investigational New Drug (IND) application development and clinical trials.", set()),
    ("The R33 phase supports prototype development, large trial testing and data integration.", set()),
    ("Coordinating cross-project data integration, analysis, and visualization.", set()),
    ("Develop a software platform for data integration across clinical databases.", {"integration"}),
    ("Develop software for Investigational New Drug application development and tracking.", {"transformation"}),
    ("Develop a new application portal for applicants to submit proposals.", {"portals"}),
    ("EDGE was developed to streamline the application and grants management process by implementing a single platform with higher data quality. This funding develops a new patient CRM and AI assistant.", {"crm", "ai"}),
])
def test_funding_scope_excludes_administration_and_paper_applications_but_keeps_software(signal, config, description, required):
    signal.signal_type = "FUNDING"
    classify(signal, config, "Funding opportunity", description)
    assert required <= set(signal.matched_capabilities)
    if not required:
        assert not signal.matched_capabilities
        assert signal.prefilter_score < 12
    else:
        assert signal.prefilter_score >= 12
        assert not signal.exclusion_reasons


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


@pytest.mark.parametrize("title", [
    "GARA APERTA AI SENSI DELL'ART.71 DEL D.LGS. 36/2023 PER UNA PIATTAFORMA SOFTWARE",
    "AVVISO DI CONSULTAZIONE PRELIMINARE DEL MERCATO AI FINI DELL'AFFIDAMENTO DI UN SISTEMA",
])
def test_italian_preposition_is_not_the_ai_acronym(signal, config, title):
    """Case cannot separate an acronym from prose when every word is capitalised."""
    classify(signal, config, title, "Piattaforma software per la gestione delle segnalazioni.")
    assert "ai" not in signal.matched_capabilities
    assert signal.delivery_priority != "ai"


def test_all_capitals_ai_scope_is_still_matched(signal, config):
    classify(signal, config, "SUPPLY OF AN AI CHATBOT", "IMPLEMENTATION OF A VIRTUAL ASSISTANT FOR CITIZENS.")
    assert "ai" in signal.matched_capabilities


def test_mixed_case_ai_acronym_is_unaffected(signal, config):
    classify(signal, config, "Procurement of an AI platform",
             "The authority requires an AI platform to triage enquiries.")
    assert "ai" in signal.matched_capabilities


def test_research_funding_ai_topic_does_not_claim_an_ai_delivery_tier(signal, config):
    """A programme studying AI is a lead; it is not a buyer implementing AI."""
    signal.signal_type = "FUNDING"
    classify(signal, config, "Unlocking Dataset Value for AI-Enabled Scientific Discovery",
             "This programme funds research using artificial intelligence for scientific discovery.")
    assert signal.delivery_priority != "ai"
    assert "ai" not in signal.matched_capabilities


def test_funding_for_an_actual_ai_implementation_is_retained(signal, config):
    signal.signal_type = "FUNDING"
    classify(signal, config, "Grant for an AI assistant",
             "Funding to procure and implement an artificial intelligence chatbot for residents.")
    assert "ai" in signal.matched_capabilities


@pytest.mark.parametrize("cpv", ["79310000", "79410000", "75120000", "75130000"])
def test_non_technology_classifications_do_not_grant_relevance(signal, config, cpv):
    """These prefixes corroborate procurement_scope exclusions; they cannot also admit."""
    classify(signal, config, "Employee Assistance Programme", "Counselling and wellbeing support for staff.", [cpv])
    assert signal.prefilter_score < 12


def corroboration_policy(config):
    policy = copy.deepcopy(config["capabilities"])
    policy["discovery"]["cpv_requires_corroboration"] = True
    return policy


def test_cpv_alone_admits_a_notice_while_the_policy_is_off(signal, config):
    classify(signal, config, "Beschaffung von Gartenmoebeln", "Lieferung von Sitzbaenken.", ["72000000"])
    assert signal.prefilter_score == 12


@pytest.mark.parametrize("title,description", [
    ("Beschaffung von Gartenmoebeln", "Lieferung von Sitzbaenken fuer den Stadtpark."),
    ("Standard Eurobarometer Surveys", "Fieldwork and reporting for public opinion surveys."),
])
def test_cpv_alone_does_not_admit_under_the_corroboration_policy(signal, config, title, description):
    signal.title, signal.description, signal.cpv_codes = title, description, ["72000000"]
    prefilter([signal], config["company_profile"], config["search_terms"], corroboration_policy(config))
    assert signal.prefilter_score == 0


@pytest.mark.parametrize("title,description", [
    ("Anskaffelse", "Development of a new software platform for the municipality."),
    ("Kulttuuriperintojarjestelma", "Procurement of a collection management information system."),
    ("Radiology information system", "Supply and maintenance of the radiology information system."),
])
def test_corroboration_policy_keeps_stated_delivery_scope(signal, config, title, description):
    signal.title, signal.description, signal.cpv_codes = title, description, ["72000000"]
    prefilter([signal], config["company_profile"], config["search_terms"], corroboration_policy(config))
    assert signal.prefilter_score >= 12


def test_corroboration_policy_never_suppresses_capability_evidence(signal, config):
    signal.title, signal.description, signal.cpv_codes = (
        "CRM replacement", "Replace the legacy customer relationship management system.", ["72000000"])
    prefilter([signal], config["company_profile"], config["search_terms"], corroboration_policy(config))
    assert "crm" in signal.matched_capabilities
    assert signal.prefilter_score >= 12
