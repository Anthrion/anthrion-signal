from anthrion_signal.markets import CARIBBEAN_COUNTRIES, MARKETS
from anthrion_signal.collectors import COLLECTORS
from anthrion_signal.normalise import NORMALISERS
from anthrion_signal.discovery import prefilter
import pytest


def test_caribbean_sources_have_complete_dispatch_and_market_partitions(config):
    assert "CARIBBEAN" not in CARIBBEAN_COUNTRIES
    assert "CARIBBEANREGIONAL" in CARIBBEAN_COUNTRIES
    sources = [s for s in config["sources"]["sources"] if s.get("enabled")
               and set(s.get("countries", [s.get("country")])) & set(CARIBBEAN_COUNTRIES)]
    assert len(sources) >= 4
    for source in sources:
        assert source["collector"] in COLLECTORS
        assert source["collector"] in NORMALISERS
        for country in source.get("countries", [source["country"]]):
            assert country in MARKETS["CARIBBEAN"]
            assert config["search_terms"]["markets"][country]["enabled"]


@pytest.mark.parametrize("country,language,description", [
    ("DO", "es", "Implementación de un sistema de gestión documental y automatización de procesos."),
    ("HT", "fr", "Développement d'un portail citoyen avec gestion des dossiers et intégration des applications."),
    ("SR", "en", "Implement a customer relationship management platform with workflow automation."),
    ("SR", "nl", "Ontwikkeling van een klantenportaal met zaakgericht werken en API-koppelingen."),
    ("GP", "en", "Implement a CRM platform and customer portal with systems integration."),
])
def test_caribbean_scope_is_discovered_in_notice_language_not_country_language(
    signal, config, country, language, description
):
    signal.title, signal.description = "Digital services procurement", description
    signal.countries, signal.source_language, signal.cpv_codes = [country], language, []
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    assert signal.prefilter_score >= 25
    assert signal.discovery_families
    assert not signal.exclusion_reasons
