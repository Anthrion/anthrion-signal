import pytest

from anthrion_signal.discovery import prefilter

DOS_PAGE = ("Home Digital Outcomes opportunities Procurement details {buyer} {title} Single stage Call-off procedure "
            "1. Project name {project} 2. Summary of work {summary} 3. Latest start date 2026-12-25 "
            "4. Expected contract length 2 Years 0 months")


def admitted(signal, config):
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal.prefilter_score >= 12 and not signal.exclusion_reasons


@pytest.mark.parametrize("summary,accepted", [
    ("MoJ requires a managed service provider to provide flexible multidisciplinary digital capability to support "
     "the Digital Modernisation Programme.", True),
    ("DCMS is seeking bids for a combined Discovery/Alpha programme in respect of the design of a digital service.", True),
    ("test", False),
    ("This is a test", False),
    ("n m", False),
    ("https://uat-contractawardservice-ui.crowncommercial.gov.uk/project/48216/event/ocds-pfhb7i-49612/overview", False),
    ("UKHSA is seeking a participant recruitment supplier to recruit participants for user research and usability "
     "testing.", False),
])
def test_digital_outcomes_call_off_is_digital_scope_unless_placeholder_or_participants(signal, config, summary, accepted):
    signal.source = "digital_outcomes"
    signal.title = "RM1043.9-2-Ministry Of Justice"
    signal.description = DOS_PAGE.format(buyer="Ministry Of Justice", title=signal.title, project="prj_1", summary=summary)
    signal.cpv_codes = []
    assert admitted(signal, config) is accepted


def test_digital_outcomes_wording_elsewhere_is_not_digital_scope(signal, config):
    signal.source = "find_tender"
    signal.title = "Cleaning services"
    signal.description = DOS_PAGE.format(buyer="Council", title="Cleaning services", project="Cleaning",
                                         summary="Provide office cleaning services for three council buildings.")
    signal.cpv_codes = ["90910000"]
    assert admitted(signal, config) is False


@pytest.mark.parametrize("title,accepted", [
    ("AI Delivery Partner for Local Government Support", True),
    ("AI Innovation Partner", True),
    ("Catering for the LCR AI Summit", False),
])
def test_titled_ai_partner_commissions(signal, config, title, accepted):
    signal.title = title
    signal.description = "The purpose of the commission is to secure a partner with local government knowledge."
    signal.cpv_codes = []
    assert admitted(signal, config) is accepted


@pytest.mark.parametrize("title,description,accepted", [
    ("Platform 360 - Omnichannel", "Exploring options for procuring an omnichannel platform to support consistent "
                                   "customer engagement.", True),
    ("Online Engagement Platform", "To provide an online engagement platform.", True),
    ("Loyalty Partner - Market Engagement", "Market engagement to explore the development of a bespoke loyalty "
                                            "programme.", True),
    ("Civil Service People Survey", "We would like to engage suppliers of employee listening platforms and tools.", True),
    ("Housing Management System", "Provision of a housing management system.", True),
    ("Housing related ICT Systems", "Preliminary market engagement to understand the systems available.", True),
    ("Loan Management System", "Exploring the market for a cloud-based loan management system.", True),
    ("Online Programme Management (OPM) System Provider", "A partner and online programme management provider.", True),
    ("Process automation", "Development and maintenance of robotic process automation for finance.", True),
    ("Revenues and Benefits", "Market engagement for a revenues and benefits system.", True),
    ("Revenues and benefits printing", "Printing and mailing for the revenues and benefits team.", False),
    ("Fuel cards", "The client requires a restricted fuel card that does not include a loyalty scheme.", False),
    ("Warehousing and fulfilment", "Retail products are made available via an omni channel approach.", False),
])
def test_uk_line_of_business_and_engagement_vocabulary(signal, config, title, description, accepted):
    signal.title, signal.description, signal.cpv_codes = title, description, []
    assert admitted(signal, config) is accepted


def test_digital_outcomes_summary_with_lower_case_numbered_list_is_not_truncated(signal, config):
    # Review fix: the numbered-heading lookahead must not stop at a lower-case list item.
    signal.source = "digital_outcomes"
    signal.title = "RM1043.9-1-Department"
    signal.description = DOS_PAGE.format(buyer="Department", title=signal.title, project="prj_2",
                                         summary="The supplier will deliver the following: 1. discovery of user needs "
                                                 "2. alpha prototypes 3. beta build")
    signal.cpv_codes = []
    assert admitted(signal, config) is True


def test_feedback_management_process_clause_is_not_a_platform(signal, config):
    signal.title = "Supported living services"
    signal.description = "The provider shall operate complaints and feedback management procedures for residents."
    signal.cpv_codes = ["85311000"]
    assert admitted(signal, config) is False


def test_digital_modernisation_programme_label_is_only_a_hint(signal, config):
    signal.title = "Print and mail services"
    signal.description = "As part of the council's digital modernisation programme, print volumes will fall."
    signal.cpv_codes = ["79810000"]
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    assert signal.delivery_priority == "other" and "transformation" not in signal.discovery_families
