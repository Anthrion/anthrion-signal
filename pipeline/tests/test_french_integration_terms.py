"""French interoperability and social-welfare wording.

The cases reproduce real notices: a Belgian data-centre cabling framework (TED 610948-2026), ADEME's integrated
training-management system (TED 419444-2026) and CPAS d'Evere's social-welfare software (TED 649572-2026).
"""
from anthrion_signal.discovery import prefilter

CABLING = (
    "Accord-cadre pour la fourniture, l'installation, la connexion et les tests du câblage du data center, des PDU et "
    "des accessoires associés",
    "Le futur accord-cadre doit permettre au pouvoir adjudicateur de répondre rapidement et de manière techniquement "
    "maîtrisée : • des modifications et des extensions de l'infrastructure du datacenter existante, tout en maintenant "
    "la compatibilité et l'interopérabilité avec l'infrastructure existante. Cela doit prendre en compte, entre autres "
    ": • interopérabilité avec les panneaux de brassage, cassettes, connecteurs et accessoires existants ;",
    ["50312300"])
TRAINING_SYSTEM = (
    "Système intégré de gestion de la formation externe ADEME",
    "L’ADEME souhaite disposer d’une solution intégrée pour la gestion complète de ses formations multimodales, "
    "incluant une vitrine ADEME Académie, la gestion administrative, le pilotage logistique, la diffusion des "
    "formations en ligne, ainsi que l’interopérabilité avec les outils institutionnels.",
    ["79990000"])
SOCIAL_WELFARE_SOFTWARE = (
    "Acquisition d’un nouveau logiciel de gestion de l’action sociale et implémentation des services relatifs à son "
    "utilisation",
    "Le présent marché est un marché public de services portant sur l’acquisition d’un logiciel de gestion de l’action "
    "sociale et sur l’implémentation des services relatifs à son utilisation.",
    ["72260000"])


def classify(signal, config, title, description, cpv):
    signal.title, signal.description, signal.cpv_codes = title, description, cpv
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal


def admitted(signal, config):
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    return signal.prefilter_score >= threshold and not signal.exclusion_reasons


def test_equipment_interoperability_is_not_integration_work(signal, config):
    assert not admitted(classify(signal, config, *CABLING), config)


def test_interoperability_with_the_buyers_tools_is_integration_work(signal, config):
    result = classify(signal, config, *TRAINING_SYSTEM)
    assert admitted(result, config) and "integration" in result.matched_capabilities


def test_social_welfare_case_software_is_platform_work(signal, config):
    assert classify(signal, config, *SOCIAL_WELFARE_SOFTWARE).delivery_priority == "platform"
