"""Norwegian and Danish case processing is also bought as human casework, like English "case handling"."""
import pytest

from anthrion_signal.discovery import prefilter


def classify(signal, config, title, description, cpv):
    signal.title, signal.description, signal.cpv_codes = title, description, cpv
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal.prefilter_score >= config["capabilities"]["discovery"]["minimum_candidate_score"] \
        and not signal.exclusion_reasons


@pytest.mark.parametrize("title, description", [
    ("Konsulenttjenester til saksbehandling av byggesøknader",
     "Kommunen skal inngå rammeavtale med konsulenter som kan bistå med saksbehandling av byggesaker."),
    ("Innleige av personell til sakshandsaming",
     "Kommunen treng mellombels hjelp til sakshandsaming av byggjesaker."),
    ("Konsulentbistand til sagsbehandling",
     "Kommunen ønsker bistand til sagsbehandling af byggesager i en travl periode."),
])
def test_human_casework_is_not_case_management(signal, config, title, description):
    assert not classify(signal, config, title, description, ["71000000"])


@pytest.mark.parametrize("title, description, cpv", [
    ("Anskaffelse av saksbehandlingssystem", "Kommunen skal anskaffe et nytt saksbehandlingssystem for byggesaker.",
     ["71000000"]),
    ("Saksbehandling av byggesøknader", "Kommunen skal anskaffe en løsning for saksbehandling i sitt fagsystem.",
     ["71000000"]),
    ("Sagsbehandling", "Kommunen ønsker en løsning til sagsbehandling af byggesager.", ["72000000"]),
])
def test_case_processing_software_stays_visible(signal, config, title, description, cpv):
    assert classify(signal, config, title, description, cpv)
