"""A bidder's cyber-certification condition is eligibility, not purchased IT scope."""
from anthrion_signal.discovery import prefilter

CLAUSE = ("• Cyber Security: If you handle patient or personal data, or provide any IT systems, services, or devices "
          "you will need to have a Cyber Security Essentials Plus Certificate.")


def classify(signal, config, title, description, cpv):
    signal.title, signal.description, signal.cpv_codes = title, description, cpv
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal


def test_certification_condition_alone_does_not_admit_an_equipment_framework(signal, config):
    # Reproduces NHS Supply Chain equipment frameworks admitted only by this condition.
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    description = (f"{CLAUSE} Lot 1: Dental Consumables & Appliances. This Lot provides dental consumables and "
                   "appliance-based solutions for routine and specialist dental care.")
    assert classify(signal, config, "Dental Equipment, Consumables & Solutions", description,
                    ["33130000"]).prefilter_score < threshold
    classify(signal, config, "Dental Equipment, Consumables & Solutions",
             description + " Separately implement a Salesforce CRM platform with API integration and customer casework.",
             ["33130000"])
    assert signal.prefilter_score >= threshold and not signal.exclusion_reasons


def test_lot_text_directly_after_the_condition_stays_matchable(signal, config):
    description = (CLAUSE[:-1] + " Lot 1: Remote monitoring platform with CRM integration and patient portal")
    classify(signal, config, "Technology enabled care", description, [])
    assert signal.prefilter_score >= config["capabilities"]["discovery"]["minimum_candidate_score"]
    assert not signal.exclusion_reasons and signal.description == description
