"""Preserve native delivery wording and mixed lots without promoting incidental uses."""
import pytest

from anthrion_signal.discovery import prefilter
from anthrion_signal.vocabulary import collection_match


def classify(signal, config, title, description, cpv=()):
    signal.title, signal.description, signal.cpv_codes = title, description, list(cpv)
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal


def admitted(signal, config):
    return (signal.prefilter_score >= config["capabilities"]["discovery"]["minimum_candidate_score"]
            and not signal.exclusion_reasons)


@pytest.mark.parametrize("title,description,family", [
    ("Interopérabilité des applications métiers",
     "Le prestataire doit réaliser les échanges entre nos logiciels de formation et de facturation.", "integration"),
    ("Interopérabilité entre les plateformes",
     "Conception et mise en place des échanges de données entre nos logiciels.", "integration"),
    ("Interopérabilité des applications métiers pour le réseau ferroviaire",
     "Développement des interfaces entre les logiciels de gestion.", "integration"),
    ("Solutions de Contrôles / Gestion des Risques et de la Conformité (GRC)",
     "Intégration et interopérabilité (Intégration au SI, APIs et connecteurs, Imports de données, "
     "Réversibilité, Automatisation / IA pour optimisation des fonctionnalités).", "integration"),
    ("Espace de travail numérique",
     "Création d'un intranet collaboratif avec gestion des contenus et des accès.", "collaboration"),
    ("Digitale werkplek",
     "Ontwerp en bouw van een intranet met samenwerking, kennisdeling en publicatie van bedrijfsinformatie.", "collaboration"),
    ("Digitale werkplek", "Levering van laptops. Bouw van een intranet voor de medewerkers.", "collaboration"),
    ("Procesautomatisering voor het beheer van gemalen",
     "Bouw van een platform voor werkorders, klantmeldingen en het plannen van onderhoud.", "workflow"),
    ("Implantación de sede electrónica",
     "Contratación para el diseño y puesta en marcha del acceso telemático de los ciudadanos.", "portals"),
    ("Implementación de procesamiento del lenguaje natural",
     "Clasificación de las consultas de la ciudadanía y extracción de entidades de documentos.", "genai"),
    ("Servicios de apoyo técnico para modelado de procesos para la transformación digital",
     "Apoyo técnico para modelado de procesos para la transformación digital.", "transformation"),
    ("Manutenzione evolutiva delle applicazioni",
     "Servizi per i sistemi informativi e le applicazioni aziendali.", "managed"),
    ("Ανάπτυξη εφαρμογής διαχείρισης παραπόνων",
     "Υλοποίηση νέας πλατφόρμας για τα αιτήματα των πολιτών.", "service"),
])
def test_native_business_delivery_survives_without_software_cpv(signal, config, title, description, family):
    result = classify(signal, config, title, description)
    assert admitted(result, config)
    assert family in result.matched_capabilities


@pytest.mark.parametrize("title,description,cpv", [
    ("Certification de l'interopérabilité ferroviaire",
     "Contrôle de la compatibilité des matériels roulants et des rails.", ["71300000"]),
    ("Espace de travail numérique",
     "Fourniture des ordinateurs portables et des écrans pour les agents.", ["30213100"]),
    ("Digitale werkplek",
     "Levering van laptops, beeldschermen en dockingstations voor medewerkers.", ["30213100"]),
    ("Digitale werkplek",
     "Levering van laptops. Geen bouw van een intranet.", ["30213100"]),
    ("Manutenzione evolutiva degli impianti di climatizzazione",
     "Revisione e sostituzione di pompe e tubazioni.", ["39717200"]),
    ("Υπηρεσίες διαχείρισης παραπόνων",
     "Στελέχωση γραφείου με υπαλλήλους για τηλεφωνική εξυπηρέτηση πολιτών.", ["79620000"]),
    ("Compra de materiales", "Las ofertas se presentan a través de la sede electrónica.", ["44100000"]),
    ("Curso de implementación de procesamiento del lenguaje natural",
     "Formación presencial de veinte horas.", ["80500000"]),
])
def test_equipment_human_service_and_procedural_mentions_do_not_become_software(signal, config, title, description, cpv):
    assert not admitted(classify(signal, config, title, description, cpv), config)


def test_industrial_automation_does_not_gain_a_business_workflow_tag_from_it_cpv(signal, config):
    result = classify(signal, config, "Procesautomatisering van gemalen",
                      "Onderhoud van PLC besturing en elektrotechnische installaties.", ["72212140"])
    assert "workflow" not in result.matched_capabilities


@pytest.mark.parametrize("phrase", ["interopérabilité", "espace de travail numérique", "digitale werkplek", "klantmanagement"])
def test_restored_aliases_still_drive_collection(config, phrase):
    assert collection_match(phrase, config["search_terms"])
