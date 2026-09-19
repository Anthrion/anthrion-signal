"""Reviewed native scope plus adversarial mixed-software counterexamples.

These are policy controls used during tuning, not an independent accuracy sample.
"""
import json
from pathlib import Path

import pytest

from anthrion_signal.discovery import prefilter
from anthrion_signal.capability_matching import affirmed, evidence_excerpt
from anthrion_signal.models import Signal
from anthrion_signal.procurement_scope import native_software_delivery, scope_exclusion
from anthrion_signal.vocabulary import search_text

CASES = json.loads((Path(__file__).parent / "fixtures/multilingual_scope_review_2026_09_18.json")
                  .read_text(encoding="utf-8"))


def classify(signal, config):
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal.prefilter_score >= 12 and not signal.exclusion_reasons


def segments(title, description):
    return [{"field": field, "basis": "original", "quote": quote, "text": search_text(quote)}
            for field, quote in (("title", title), ("description", description))]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["signal"]["id"])
def test_reviewed_native_source_scope(case, config):
    signal = Signal.model_validate(case["signal"])
    source = (signal.title, signal.description, signal.content_hash, signal.raw_source_hash)
    # Sparse but plausible IT scope remains a candidate, without turning an
    # uncertain reviewer judgement into a definite benchmark label.
    assert bool(classify(signal, config)) is (case["expected"] != "exclude"), signal.exclusion_reasons
    assert source == (signal.title, signal.description, signal.content_hash, signal.raw_source_hash)
    assert case["used_for_policy"] is True
    if case["expected"] == "exclude" and case.get("scope_exclusion_required", True):
        assert signal.scope_evidence, "A low score alone does not establish purchased-scope exclusion"
        assert signal.scope_evidence[0]["quote"] in signal.description


MIXED_DELIVERABLES = (
    "Lot 2 : Fourniture d’une solution SaaS et maintenance du portail usager.",
    "Perceel 2: Implementatie van de belasting applicatie en migratie van de gegevens.",
    "Los 2: Entwicklung von Anwendungen und Implementierung eines Kundenportals.",
    "Lotto 2: Sviluppo di applicazioni per la gestione dei clienti.",
    "Lote 2: Desarrollo de aplicaciones para gestionar los clientes.",
    "Τμήμα 2: Ανάπτυξη λογισμικού για τη διαχείριση υποθέσεων.",
)


@pytest.mark.parametrize("case", [case for case in CASES if case["expected"] == "exclude"
                                 and case.get("scope_exclusion_required", True)],
                         ids=lambda case: case["signal"]["id"])
@pytest.mark.parametrize("software", MIXED_DELIVERABLES)
def test_separate_native_software_lot_protects_every_work_taxonomy(case, software, config):
    signal = Signal.model_validate(case["signal"])
    signal.description += " " + software
    # Keep the physical/human-service CPVs. A separately advertised software
    # component is sufficient even when its classification is missing.
    assert classify(signal, config), (software, signal.exclusion_reasons)
    assert not signal.scope_evidence


@pytest.mark.parametrize("description", [
    "Sans développement de logiciel.",
    "Zonder implementatie van de applicatie.",
    "Ohne Entwicklung von Anwendungen.",
    "Senza sviluppo di applicazioni.",
    "Sin desarrollo de aplicaciones.",
    "Χωρίς ανάπτυξη λογισμικού.",
    "Maintenance des études sans développement de logiciel.",
    "Les enquêteurs utilisent un logiciel existant pour enregistrer les réponses.",
    "De onderzoekers gebruiken de bestaande applicatie om antwoorden vast te leggen.",
    "Die Befragung wird mit vorhandener Software durchgeführt.",
    "Gli intervistatori utilizzano il software esistente per registrare le risposte.",
    "Los encuestadores utilizan una aplicación existente para registrar las respuestas.",
    "Χρήση υφιστάμενου λογισμικού για την καταγραφή απαντήσεων.",
    "Fourniture d'ordinateurs pour utiliser un logiciel existant.",
    "Levering van computers voor gebruik van bestaande software.",
    "Lieferung von Computern zur Nutzung vorhandener Software.",
    "Fornitura di computer per utilizzare software esistente.",
    "Suministro de ordenadores para ejecutar software existente.",
    "Παράδοση εξοπλισμού για χρήση υφιστάμενου λογισμικού.",
    "Entwicklung eines Fragebogens mit vorhandener Software.",
    "Desarrollo de encuestas con software existente.",
])
def test_negated_delivery_and_existing_tools_do_not_rescue_fieldwork(description):
    assert not native_software_delivery(search_text(description))
    scope = segments("Durchführung der Feldarbeiten", "Stichprobenziehung und Befragung. " + description)
    assert scope_exclusion(scope, ["79311200"])["rule"] == "survey_execution"


@pytest.mark.parametrize("description", [
    "Fornitura di una piattaforma aerea.",
    "Suministro de una plataforma elevadora con software de control.",
    "Maintenance du portail métallique.",
    "Fourniture d'un portail coulissant avec un logiciel de contrôle.",
    "Παράδοση πλατφόρμας ανύψωσης.",
    "Fornitura di una piattaforma. Il perimetro sarà precisato.",
])
def test_ambiguous_platforms_and_gates_need_digital_deliverables(description):
    assert not native_software_delivery(search_text(description))


@pytest.mark.parametrize("description", [
    "Fornitura di una piattaforma informatica per servizi di welfare aziendale.",
    "Suministro de una plataforma para gestionar expedientes.",
    "Maintenance du portail de gestion des demandes.",
    "Υλοποίηση ψηφιακής πλατφόρμας για διαχείριση υποθέσεων.",
])
def test_explicit_business_platforms_survive_ambiguous_noun_guards(signal, config, description):
    signal.title, signal.description, signal.cpv_codes = "Business services", description, []
    assert classify(signal, config)


@pytest.mark.parametrize("title,description,cpv", [
    ("Services d'ingénierie", "Le périmètre sera précisé lors de la consultation.", ["72224000"]),
    ("Ingenierie de trafic", "Prestations à préciser.", ["79311000"]),
    ("Ingegneria e architettura", "Servizi di consulenza.", ["71300000"]),
    ("Archaeologist services", "Scope to be confirmed.", ["72224000"]),
    ("Consultoría de proyectos", "Asistencia técnica para proyectos.", ["79411000"]),
    ("Δέλτα", "Παροχή συμβουλευτικών υπηρεσιών στη διεύθυνση ανθρωπίνου δυναμικού.", ["79414000"]),
    ("Implementation of a regional initiative", "Scope will be specified later.", ["79417000"]),
    ("Implementation of a regional initiative", "Administrative and logistical support for a conference.", ["79417000"]),
    ("IT consultancy services", "Technical services to be specified.", ["72000000"]),
])
def test_sparse_scope_and_cpv_alone_do_not_trigger_new_exclusions(title, description, cpv):
    assert scope_exclusion(segments(title, description), cpv) is None


@pytest.mark.parametrize("title,description", [
    ("Clinical software", "Develop software for recording anaesthesia observations and patient care."),
    ("Real-time broadcast graphics", "Develop an HTML5 software application for broadcast graphics."),
    ("IT consultancy services", "Scope will be confirmed at market engagement."),
])
def test_specialist_software_and_sparse_it_remain_candidates(signal, config, title, description):
    signal.title, signal.description, signal.cpv_codes = title, description, ["72200000"]
    assert classify(signal, config)


@pytest.mark.parametrize("description", [
    "Suministro de licencias de software del fabricante.",
    "Maintenance des licences du logiciel.",
    "Levering van licenties voor software.",
    "Beschaffung von Lizenzen mit Software Assurance.",
    "Fornitura di licenze del software.",
    "Mantenimiento de software y licencias del fabricante.",
    "Lieferung inklusive Zubehör, Software und Installation eines Reaktors.",
    "Beschaffung eines Prüfsystems einschließlich der erforderlichen Software.",
    "Lieferung, Dokumentation und Hard- und Software-Support für Kameras.",
    "Suministro del software asociado de un lavavajillas industrial.",
    "Suministro de dos MUPIS digitales exteriores y mantenimiento del software.",
    "Suministro de impresoras multifunción y mantenimiento del software de los equipos de reprografía.",
    "Mantenimiento de software y disponibilidad de hardware del sistema de riego.",
    "Entwicklung neuer Anwendungen in der Herstellung von Arzneimitteln.",
    "Entwicklung leistungsfähiger Feingussverfahren für industrielle Anwendungen.",
    "17 A-Kriterium Software und Entwicklung 18 A-Kriterium Software und Entwicklung.",
])
def test_licence_entitlements_equipment_bundles_and_scientific_uses_are_not_software_work(description):
    assert not native_software_delivery(search_text(description))


@pytest.mark.parametrize("software", MIXED_DELIVERABLES)
@pytest.mark.parametrize("base", [
    "Suministro de licencias de software Microsoft y mantenimiento asociado.",
    "Lieferung eines Reaktors einschließlich Steuerungssoftware.",
])
def test_separate_application_work_survives_licences_and_equipment(signal, config, software, base):
    signal.title, signal.description, signal.cpv_codes = base, base + " " + software, ["42000000"]
    assert classify(signal, config)


@pytest.mark.parametrize("phrase", [
    "Entwicklung von Software für die Steuerung der klinischen Arbeitsabläufe.",
    "Développement d'un logiciel pour les soins cliniques.",
    "Ontwikkeling van software voor medische dossiers.",
    "Sviluppo di applicazioni per la gestione dei clienti.",
    "Desarrollo de las aplicaciones de gestión de datos.",
    "Desarrollo e integración de aplicaciones empresariales.",
    "Ανάπτυξη λογισμικού για τη διαχείριση υποθέσεων.",
])
def test_concrete_software_development_remains_positive_without_sector_or_vendor_whitelist(phrase):
    assert native_software_delivery(search_text(phrase))


@pytest.mark.parametrize("component", [
    "λογισμικού συστήματος έκδοσης τιμολογίων",
    "λογισμικού συστήματος διαχείρισης παραγγελιών",
    "λογισμικού συστήματος καταγραφής αιτήσεων",
    "λογισμικού συστήματος παρακολούθησης υποθέσεων",
    "λογισμικού συστήματος διαχείρισης πελατών",
])
def test_transaction_software_can_be_a_separate_coordinated_component(component):
    assert native_software_delivery(search_text("Προμήθεια και εγκατάσταση εξοπλισμού και " + component))


@pytest.mark.parametrize("description", [
    "Παροχή υπηρεσιών διαχείρισης παραγγελιών και έκδοσης τιμολογίων.",
    "Προμήθεια και εγκατάσταση μηχανημάτων με λογισμικού συστήματος έκδοσης τιμολογίων.",
    "Προμήθεια και εγκατάσταση εκτυπωτών και ενσωματωμένου λογισμικού συστήματος έκδοσης τιμολογίων.",
    "Εγκατάσταση εξοπλισμού για χρήση υφιστάμενου λογισμικού συστήματος διαχείρισης πελατών.",
    "Προμήθεια και εγκατάσταση ελεγκτών, λογισμικού συστήματος ελέγχου μηχανημάτων.",
    "Χωρίς προμήθεια λογισμικού συστήματος διαχείρισης παραγγελιών.",
])
def test_transaction_context_does_not_turn_human_work_tools_or_embedded_controls_into_delivery(description):
    assert not native_software_delivery(search_text(description))


@pytest.mark.parametrize("title,description,cpv", [
    ("Gestion des inscriptions", "Accueil des participants et tenue manuelle du registre pour un événement.", "79952000"),
    ("Gestion des sinistres", "Expertise humaine des dommages et indemnisation des assurés.", "66510000"),
    ("Planification des interventions", "Organisation des visites des infirmiers et soins à domicile.", "85000000"),
    ("Gestion de campagnes", "Impression et affichage de publicité sur panneaux.", "79340000"),
    ("Sociaal domein", "Jeugdzorg en ondersteuning aan gezinnen door maatschappelijk werkers.", "85300000"),
    ("Vergunningverlening", "Inhuur van medewerkers voor het beoordelen van bouwvergunningen.", "79620000"),
    ("Bedrijfsregels", "Training van medewerkers in juridische procedures.", "80500000"),
    ("Kantoormeubelen", "Offertes worden ingediend via het bestaande leveranciersportaal.", "39130000"),
    ("Mobilier de bureau", "Les candidats doivent remplir les formulaires électroniques de soumission.", "39130000"),
    ("Kantoormeubelen", "Inschrijvers moeten digitale formulieren voor de offerte invullen.", "39130000"),
])
def test_deferred_pr_aliases_do_not_turn_human_work_or_submission_routes_into_software(signal, config, title, description, cpv):
    signal.title, signal.description, signal.cpv_codes = title, description, [cpv]
    assert not classify(signal, config)


@pytest.mark.parametrize("phrase", ["plateforme d'intégration", "gestion électronique des documents", "portail en libre-service"])
@pytest.mark.parametrize("prefix", [
    "Le marché n'a pas pour objet l'acquisition d'une nouvelle ",
    "Le contrat ne vise donc pas le choix d'une nouvelle ",
    "Le marché ne comprend pas la mise en place de ",
    "Le marché n'inclut pas de ",
])
def test_french_object_negation_applies_to_different_technical_nouns(phrase, prefix):
    quote = prefix + phrase + "."
    assert not affirmed(search_text(quote), search_text(phrase).strip(), quote)
    assert not affirmed(search_text(quote), search_text(phrase).strip())


@pytest.mark.parametrize("phrase", ["plateforme d'intégration", "gestion électronique des documents", "portail en libre-service"])
@pytest.mark.parametrize("separator", [", mais ", "; toutefois ", ". "])
def test_quote_uses_the_later_affirmative_occurrence_and_preserves_existing_system_support(phrase, separator):
    quote = ("Le marché n'a pas pour objet l'acquisition d'une nouvelle " + phrase + separator
             + "la maintenance de " + phrase + " existante est demandée.")
    normalized = search_text(phrase).strip()
    assert affirmed(search_text(quote), normalized, quote)
    excerpt = evidence_excerpt(quote, normalized)
    assert phrase in excerpt and "maintenance" in excerpt
    assert "n'a pas" not in excerpt
    assert excerpt in quote


@pytest.mark.parametrize("quote", [
    "Le marché comprend la maintenance de la plateforme d'intégration existante.",
    "Le marché ne vise pas à exclure la plateforme d'intégration.",
    "Le marché ne comprend pas de mobilier, mais inclut une plateforme d'intégration.",
])
def test_french_negation_is_local_and_does_not_erase_affirmative_support(quote):
    assert affirmed(search_text(quote), "plateforme d integration", quote)


def test_french_negated_new_platform_does_not_emit_a_delivery_requirement(signal, config):
    signal.title = "Support applicatif"
    signal.description = ("Le contrat ne vise donc pas le choix d'une nouvelle plateforme d'intégration. "
                          "Il maintient et modernise l'environnement logiciel existant.")
    signal.cpv_codes = ["72200000"]
    assert classify(signal, config)
    assert "integration" not in signal.matched_capabilities


def test_french_mixed_contrast_emits_only_the_affirmative_evidence(signal, config):
    signal.title = "Services logiciels"
    signal.description = ("Le contrat n'a pas pour objet l'acquisition d'une nouvelle plateforme d'intégration, "
                          "mais comprend la maintenance de la plateforme d'intégration existante.")
    signal.cpv_codes = ["72200000"]
    assert classify(signal, config)
    evidence = [e for e in signal.capability_evidence if e["capability"] == "integration"]
    assert evidence
    assert all("maintenance" in e["quote"] and "n'a pas" not in e["quote"] for e in evidence)


@pytest.mark.parametrize("phrase", ["système CRM", "gestion électronique des documents", "plateforme de données clients"])
@pytest.mark.parametrize("quantifier", ["seulement", "uniquement"])
def test_french_not_only_is_affirmative_across_capabilities(phrase, quantifier):
    quote = "Le marché ne comprend pas " + quantifier + " le " + phrase + ", mais aussi son support."
    assert affirmed(search_text(quote), search_text(phrase).strip(), quote)
    assert affirmed(search_text(quote), search_text(phrase).strip())


@pytest.mark.parametrize("phrase,capability", [
    ("système CRM", "crm"),
    ("gestion électronique des documents", "workflow"),
    ("plateforme de données clients", "data"),
])
def test_french_polarity_and_quotes_apply_to_crm_workflow_and_data(signal, config, phrase, capability):
    signal.title, signal.cpv_codes = "Services logiciels", ["72200000"]
    signal.description = "Le marché n'inclut pas de " + phrase + "."
    classify(signal, config)
    assert capability not in signal.matched_capabilities
    signal.description += " La maintenance du " + phrase + " existant est requise."
    classify(signal, config)
    evidence = [e for e in signal.capability_evidence if e["capability"] == capability]
    assert evidence and all("maintenance" in e["quote"] and "n'inclut" not in e["quote"] for e in evidence)


@pytest.mark.parametrize("quote,expected", [
    ("No Salesforce implementation is required.", False),
    ("Salesforce is not included.", False),
    ("No Salesforce implementation is required, but maintenance of Salesforce is included.", True),
    ("Salesforce is not included; support for Salesforce is required.", True),
])
def test_existing_english_negation_and_later_affirmative_evidence_are_preserved(quote, expected):
    assert affirmed(search_text(quote), "salesforce", quote) is expected
    if expected:
        excerpt = evidence_excerpt(quote, "salesforce")
        assert "not included" not in excerpt and "No Salesforce" not in excerpt
        assert excerpt in quote


def test_a_url_cannot_rescue_negated_scope_or_become_the_affirmative_excerpt(signal, config):
    signal.title = "General services"
    signal.description = "Salesforce is not included; see https://example.test/Salesforce."
    signal.cpv_codes = []
    classify(signal, config)
    assert "salesforce" not in signal.matched_capabilities
    quote = "See https://example.test/Salesforce; maintenance of Salesforce is required."
    excerpt = evidence_excerpt(quote, "salesforce")
    assert "maintenance" in excerpt and "https://" not in excerpt and excerpt in quote
