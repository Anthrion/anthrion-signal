"""Contact mailboxes, engineering standards and paper applications are not purchased software scope."""
import pytest

from anthrion_signal.discovery import prefilter


def classify(signal, config, title, description, cpv=()):
    signal.title, signal.description, signal.cpv_codes = title, description, list(cpv)
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal


# Each case reproduces a retained notice that was admitted only by the masked text.
@pytest.mark.parametrize("title,description,cpv", [
    ("DfT - Supply of Overseas E SIMS",
     "DfT are seeking a supplier capable of providing eSIM solutions for data roaming for business travellers. "
     "Please email DDaT.CRM@dft.gov.uk to request the EOI documentation quoting reference number TRGA3399.",
     ["64212000"]),
    ("API 653 Fuel Tank Repairs and Maintenance - Eielson AFB, Alaska",
     "The intent is to procure construction services to provide repair and maintenance of five vertical "
     "aboveground storage tanks at Eielson AFB, AK.", []),
    ("Insurance Services excluding Property Insurance",
     "The Council is seeking to procure its suite of insurance requirements. Please register ahead of publishing "
     "date on Registering with a Supplier Portal.", ["66516400"]),
    ("Planning Application Support",
     "Direct award of a framework call off contract to a previously used supplier to provide planning application "
     "support linked to the Student and Staff accommodation.", ["71240000"]),
    ("Direct Award for the Provision of Da Vinci Funding Application Support",
     "Direct Award for the Provision of Da Vinci Funding Application Support.", ["79400000"]),
])
def test_contact_standard_registration_and_paper_application_text_is_not_scope(signal, config, title, description, cpv):
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    assert classify(signal, config, title, description, cpv).prefilter_score < threshold
    classify(signal, config, title, description
             + " Separately implement a Salesforce CRM platform with API integration and customer casework.", cpv)
    assert signal.prefilter_score >= threshold
    assert "salesforce" in signal.matched_capabilities and not signal.exclusion_reasons


@pytest.mark.parametrize("description", [
    "Implement a CRM for resident enquiries. Contact crm.team@council.gov.uk with any questions.",
    "Deliver API integration between the case management system and the finance application.",
    "Implement a new supplier portal so that businesses can register and track their invoices.",
    "Provide licensing application support and maintenance for the council's licensing system.",
    "Provide application support for the planning system used by the development management team.",
])
def test_real_delivery_beside_masked_text_stays_visible(signal, config, description):
    classify(signal, config, "Service requirement", description)
    assert signal.prefilter_score >= config["capabilities"]["discovery"]["minimum_candidate_score"]
    assert not signal.exclusion_reasons
    assert signal.description == description
    assert all(item["quote"] in getattr(signal, item["field"]) for item in signal.capability_evidence)
