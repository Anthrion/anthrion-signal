"""Spanish co-official languages (Catalan/Valencian `ca`, Galician `gl`) and new Spanish (`es`) aliases.

Positive controls come from real PLACSP/TED wording (Catalan councils and hospitals, Xunta/AMTEGA style);
negative controls cover the ambiguous uses the gated phrases share with human services, equipment upkeep and
training courses.
"""
import pytest

from anthrion_signal.discovery import prefilter
from anthrion_signal.spain_notices import relevant_placsp_record
from anthrion_signal.vocabulary import collection_match


def classify(signal, config, title, description="", cpv=()):
    signal.title, signal.description, signal.cpv_codes = title, description, list(cpv)
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"], {})
    return signal


def admitted(signal):
    return signal.prefilter_score >= 12 and not signal.exclusion_reasons


@pytest.mark.parametrize("title", [
    "Servei d'un agent d'intel·ligència artificial per a la consulta d'atenció primària",
    "Servei d'un agent d'intel•ligència artificial per a la consulta d'atenció primària",
    "Servei d'un agent d'intel.ligència artificial per a la consulta d'atenció primària",
    "Servei d'un agent d'intelligència artificial per a la consulta d'atenció primària",
    "Contratación do servizo de intelixencia artificial para a atención á cidadanía",
])
def test_catalan_and_galician_ai_spellings_tag_ai_without_cpv(signal, config, title):
    classify(signal, config, title, "Implantació, parametrització i manteniment en mode SaaS.")
    assert "ai" in signal.matched_capabilities
    assert admitted(signal)
    assert signal.delivery_priority == "ai"


@pytest.mark.parametrize("title,cpv,family", [
    ("Programari del gestor d'expedients administratius i electrònics", ["48000000"], "service"),
    ("Subministrament i serveis per a la implantació i manteniment d'una solució de software de gestió d'expedients",
     ["48000000"], "service"),
    ("Servei de manteniment evolutiu de l'aplicació de gestió de la docència", ["72267000"], "managed"),
    ("Servei de manteniment correctiu i evolutiu del sistema informàtic integral de farmàcia", ["72267000"], "managed"),
    ("El desenvolupament d'una aplicació informàtica per a la gestió de la documentació de les sessions", ["72000000"],
     "transformation"),
    ("Servizo de mantemento evolutivo do sistema de xestión de residencias universitarias", ["72267000"], "managed"),
    ("Servicio de desarrollo y mantenimiento de una solución de automatización robótica de procesos (RPA)",
     ["72000000"], "automation"),
    ("Servicio de analítica de datos de la Oficina del Dato", ["72300000"], "analytics"),
    ("Contratación del servicio de soporte y mantenimiento de la aplicación de gestión de ayudas", ["72267000"],
     "managed"),
])
def test_real_native_software_wording_gets_a_family(signal, config, title, cpv, family):
    classify(signal, config, title, "", cpv)
    assert family in signal.matched_capabilities
    assert admitted(signal)
    assert signal.delivery_priority in ("platform", "ai")


@pytest.mark.parametrize("title,description,cpv,family", [
    # The buyer's existing file system named in a human service contract.
    ("Oficina tècnica per al desplegament del programa de benestar", "El personal treballarà amb el gestor "
     "d'expedients de l'Ajuntament.", ["79342000"], "service"),
    # Evolutive maintenance of physical equipment.
    ("Manteniment correctiu i evolutiu dels equips de climatització", "Revisió de les màquines.", ["39717200"], "managed"),
    ("Servizo de mantemento evolutivo dos equipos de climatización", "Revisión das máquinas.", ["39717200"], "managed"),
    # Industrial robotics, and course topics.
    ("Suministro de una célula de automatización robótica de procesos de soldadura", "Suministro de robots industriales.",
     ["42600000"], "automation"),
    ("Formación en analítica de datos para empleados municipales", "Curso de 30 horas.", ["80500000"], "analytics"),
    ("Curso de procesamiento del lenguaje natural para el personal", "Formación presencial de 20 horas.", ["80500000"],
     "genai"),
])
def test_gated_phrases_need_software_context(signal, config, title, description, cpv, family):
    classify(signal, config, title, description, cpv)
    assert family not in signal.matched_capabilities
    assert not admitted(signal)


@pytest.mark.parametrize("phrase", [
    "intel·ligència artificial", "gestió d'expedients", "plataforma d'administració electrònica",
    "intelixencia artificial", "xestión de expedientes", "automatización robótica de procesos",
])
def test_co_official_and_new_spanish_phrases_feed_ted_and_placsp_collection(config, phrase):
    assert collection_match(phrase, config["search_terms"])
    assert relevant_placsp_record({"state": "PUB", "title": phrase}, config["search_terms"])
