"""German specialist-system and programme words need technical context, as their English counterparts do.

The cases reproduce real notices: TED 755724-2025 and 423763-2026 (collected by the new lanes)
and three retained German notices.
"""
import pytest

from anthrion_signal.discovery import prefilter

LETTER_PRINTING = (
    "Druck, Kuvertierung und Versand von Schreiben aus Fachverfahren",
    "Das Bundesamt für Justiz beabsichtigt, den Druck, die Kuvertierung und den Postversand von Schreiben in "
    "Ordnungsgeld-, Beitreibungs- und EU-Vollstreckungshilfeverfahren sowie für das Verbandsklageregister in vier "
    "Losen im Offenen Verfahren zu vergeben. Gegenstand des Vergabeverfahrens ist unter anderem auch die Erstellung "
    "und die konkrete Beschreibung der Schnittstellen für alle Fachverfahren.",
    ["79800000", "79820000"])
TREE_INSPECTION = (
    "Rahmenvertrag Baumkontrollen",
    "Die ausgeschriebenen Baumkontrollen dienen dem Ziel, der Verkehrssicherungspflicht nachzukommen, "
    "Fehlentwicklungen zu korrigieren und Gefahren abzuwehren. Der AG behält sich das Recht vor, die Fachanwendung "
    "Archikart zur Verwaltung des Baumkatasters gegen eine andere Fachanwendung auszutauschen.",
    ["71630000", "77211500"])
MUSIC_SCHOOL_PROCEDURE = (
    "Markterkundung zur Vorbereitung eines IT-Fachverfahrens für die Berliner Musikschulen",
    "Die Auftraggeberin beabsichtigt, ein neues IT-Fachverfahren für die Verwaltung der Berliner Musikschulen im "
    "Betriebsmodell Software-as-a-Service im Verhandlungsverfahren auszuschreiben. Der Ausschreibungsgegenstand "
    "umfasst neben dem reinen Betrieb einschl. Wartung und Support auch ein jährliches Kontingent an Personentagen "
    "zur Weiterentwicklung sowie ein vorgeschaltetes Transition-Projekt zur Ablösung der Bestandssoftware.",
    ["72260000"])
DOCUMENT_MANAGEMENT = (
    "Einführung zentrales DMS",
    "Hereon beabsichtigt die Einführung einer unternehmensweiten Dokumentenmanagement-Plattform (DMS), um die "
    "Verwaltung, Bearbeitung und Bereitstellung geschäftsrelevanter Informationen nachhaltig zu modernisieren und zu "
    "vereinheitlichen.",
    ["50000000"])
SURVEY_TOPIC = (
    "Hauptstudie DiGeVe - Datenerhebung & Auswertung",
    "Die Initiative D21 e.V. ist ein überparteiliches, gemeinnütziges Netzwerk aus Wirtschaft, Politik, Wissenschaft "
    "und Zivilgesellschaft. Diese Studien liefern eine fundierte Datenbasis für eine digitale Transformation, die "
    "Chancengerechtigkeit und gesellschaftlichen Fortschritt fördert. Gegenstand der Ausschreibung ist die "
    "Durchführung, Auswertung und Dokumentation von zwei bevölkerungsrepräsentativen Befragungen.",
    ["79311000", "79311200", "79311300", "79320000"])


def classify(signal, config, title, description, cpv):
    signal.title, signal.description, signal.cpv_codes = title, description, cpv
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal


def admitted(signal, config):
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    return signal.prefilter_score >= threshold and not signal.exclusion_reasons


@pytest.mark.parametrize("notice", [LETTER_PRINTING, TREE_INSPECTION], ids=["letter printing", "tree inspection"])
def test_buyer_system_named_in_a_physical_service_is_not_platform_work(signal, config, notice):
    assert not admitted(classify(signal, config, *notice), config)


def test_specialist_procedure_procurement_is_platform_work(signal, config):
    result = classify(signal, config, *MUSIC_SCHOOL_PROCEDURE)
    assert admitted(result, config) and result.delivery_priority == "platform"


def test_document_management_introduction_is_recovered(signal, config):
    assert admitted(classify(signal, config, *DOCUMENT_MANAGEMENT), config)


def test_digital_transformation_as_a_survey_topic_is_not_platform_priority(signal, config):
    assert classify(signal, config, *SURVEY_TOPIC).delivery_priority != "platform"
