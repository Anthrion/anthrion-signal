"""Independent positive/negative controls for the discovery precision/recall changes."""
import pytest

from anthrion_signal.discovery import prefilter


def classify(signal, config, title, description, cpv=()):
    signal.title, signal.description, signal.cpv_codes = title, description, list(cpv)
    prefilter([signal], config['company_profile'], config['search_terms'], config['capabilities'])
    return signal


@pytest.mark.parametrize('title,description', [
    ('PROCUREMENT OF AN AI PLATFORM', 'IMPLEMENTATION AND SUPPORT OF AN AI SYSTEM.'),
    ('RFI AI INTERPRETER', 'RECORDING, TRANSCRIPTION AND TRANSLATION.'),
    ('RFI AI Interpreter', 'Recording, transcription and translation.'),
])
def test_ai_delivery_is_independent_of_title_capitalisation(signal, config, title, description):
    result = classify(signal, config, title, description)
    assert 'ai' in result.matched_capabilities
    assert result.delivery_priority == 'ai'


@pytest.mark.parametrize('title', [
    "GARA APERTA AI SENSI DELL'ART.71 DEL D.LGS. 36/2023 PER UNA PIATTAFORMA SOFTWARE",
    'Servizi AI SENSI delle disposizioni vigenti',
    'Servizi AI FINI della gestione dei procedimenti',
])
def test_italian_preposition_is_local_not_a_case_ratio(signal, config, title):
    result = classify(signal, config, title, 'Una piattaforma software per servizi ai cittadini.')
    assert 'ai' not in result.matched_capabilities


def test_italian_legal_clause_does_not_erase_a_separate_ai_requirement(signal, config):
    result = classify(signal, config, 'GARA AI SENSI DI LEGGE: AI PLATFORM IMPLEMENTATION', '')
    assert 'ai' in result.matched_capabilities


@pytest.mark.parametrize('title,description', [
    ('MCP joint replacement', 'Supply metacarpophalangeal joint prostheses.'),
    ('RAG status reporting training', 'Staff training on red amber green reporting.'),
])
def test_unrelated_acronyms_do_not_become_ai_from_title_position(signal, config, title, description):
    result = classify(signal, config, title, description)
    assert not {'ai', 'genai'} & set(result.matched_capabilities)
    assert result.prefilter_score < 12


@pytest.mark.parametrize('description', [
    'Build an artificial intelligence application for forecasting using the existing GPU cluster.',
    'Develop an artificial intelligence software service for inference workloads.',
    'Procure GPU computing resources and implement an AI assistant for customer enquiries.',
    'AI software development using existing compute resources.',
])
def test_compute_context_preserves_a_separate_software_deliverable(signal, config, description):
    result = classify(signal, config, 'Prediction service', description)
    assert 'ai' in result.matched_capabilities
    assert result.prefilter_score >= 12


@pytest.mark.parametrize('description', [
    'Supply GPU computing resources for AI-based climate modelling.',
    'Server system for AI inference workloads.',
    'Supply a GPU cluster; development of AI software is not required.',
])
def test_hardware_capacity_does_not_invent_a_model_deliverable(signal, config, description):
    result = classify(signal, config, 'Hardware supply', description)
    assert 'ai' not in result.matched_capabilities


@pytest.mark.parametrize('spelling', ['AI Bietercockpit', 'AI_Bietercockpit', 'AI-Bietercockpit'])
def test_bidding_client_does_not_delete_real_scope_in_same_sentence(signal, config, spelling):
    result = classify(signal, config, 'Business service',
                      f'Procure a CRM platform and submit the bid using {spelling}.')
    assert 'crm' in result.matched_capabilities
    assert 'ai' not in result.matched_capabilities
    assert result.prefilter_score >= 12


@pytest.mark.parametrize('title,description', [
    ('ISO certification', 'Assess and certify the existing quality management system to ISO 9001.'),
    ('Employee Assistance Programme', 'Counselling and wellbeing support. Suppliers must operate a quality management system certified to ISO 9001.'),
    ('Warning system', 'Supply and install an emergency notification system consisting of sirens and loudspeakers.'),
    ('Fieldwork services', 'Tender documents are available on our internet portal.'),
    ('Fieldwork services', 'Consult the web portal to download the procurement documents.'),
])
def test_business_system_phrases_need_actual_digital_scope(signal, config, title, description):
    result = classify(signal, config, title, description)
    assert result.prefilter_score < 12
    assert not any(m.startswith('Published digital scope:') for m in result.prefilter_matches)


def test_quality_certification_does_not_prove_human_casework_is_software(signal, config):
    result = classify(signal, config, 'Employee support',
                      'Case management support for staff health requires a quality management system certified to ISO 9001.')
    assert 'service' not in result.matched_capabilities
    assert result.prefilter_score < 12


@pytest.mark.parametrize('title,description', [
    ('Quality management platform', 'Implement a SaaS quality management system with approval workflows.'),
    ('Patient and colleague notification system', 'Procurement of a notification system for patient messages.'),
    ('Internet portal delivery', 'Build an internet portal for citizens and publish tender documents on our web portal.'),
    ('Learning Management System', 'Supply and support a learning management system.'),
    ('Safety and communications', 'Install sirens and develop a notification system software platform for staff messaging.'),
])
def test_concrete_business_system_delivery_survives_context_checks(signal, config, title, description):
    result = classify(signal, config, title, description)
    assert result.prefilter_score >= 12
    assert not result.exclusion_reasons


def test_funding_to_build_an_operational_ai_application_retains_delivery_tier(signal, config):
    signal.signal_type = 'FUNDING'
    result = classify(signal, config, 'Resident enquiry tools',
                      'Funding to build an artificial intelligence software application that triages council enquiries.')
    assert 'ai' in result.matched_capabilities


def test_funding_with_negated_procurement_stays_a_research_hint(signal, config):
    signal.signal_type = 'FUNDING'
    result = classify(signal, config, 'Research into artificial intelligence',
                      'Research on artificial intelligence software, without implementation or procurement.')
    assert 'ai' not in result.matched_capabilities
    assert result.prefilter_score >= 12


@pytest.mark.parametrize('description', [
    'Support development of innovative, reliable, cost-effective, sustainable multimodal AI-based clinical decision support tools.',
    'Catalyze the development and testing of Artificial Intelligence (AI)-enabled, image-centered, multimodal Clinical Decision Support tools, developed as Software as a Medical Device.',
    'Funding to develop artificial intelligence models for operational clinical decision support.',
])
def test_funding_for_ai_tools_is_not_mistaken_for_topic_only_research(signal, config, description):
    signal.signal_type = 'FUNDING'
    result = classify(signal, config, 'Clinical decision support innovation', description)
    assert 'ai' in result.matched_capabilities


def test_supplier_ordering_system_does_not_make_goods_into_software(signal, config):
    result = classify(signal, config, 'Literature supply',
                      "Orders are made by the customer via the supplier's electronic ordering system and books delivered to their address.")
    assert result.prefilter_score < 12
    result = classify(signal, config, 'Book supply and software',
                      "Order books via the supplier's ordering system and implement a new ordering system for our staff.")
    assert result.prefilter_score >= 12


def test_security_management_process_does_not_prove_analytics_software(signal, config):
    result = classify(signal, config, 'External information security officer',
                      'Development of an Information Security Management System and reporting on risk assessments to the board.')
    assert 'analytics' not in result.matched_capabilities


@pytest.mark.parametrize('route', ['under', 'via', 'from'])
def test_framework_name_does_not_make_hardware_a_digital_workplace_project(signal, config, route):
    result = classify(signal, config, 'Network appliance supply',
                      f'Supply network hardware awarded {route} the NHS Digital Workplace Solutions Framework.')
    assert result.prefilter_score < 12
    result = classify(signal, config, 'Digital workplace',
                      f'Implement a digital workplace for staff, procured {route} a framework agreement.')
    assert result.prefilter_score >= 12


def test_certification_of_asset_management_process_is_not_a_software_purchase(signal, config):
    result = classify(signal, config, 'Annual assurance service',
                      'ISO 55001 certification and recertification of the asset management system.')
    assert result.prefilter_score < 12
    result = classify(signal, config, 'Asset management software',
                      'Implement a SaaS asset management system compliant with ISO 55001 certification requirements.')
    assert result.prefilter_score >= 12


@pytest.mark.parametrize('title,description', [
    ('Annual certification audits', 'Carry out ISO 55001 certification. Provide assurance that our asset management system remains effective.'),
    ('Room and Venue Booking System', 'The requirement is for external venue hire with refreshments for staff events.'),
])
def test_process_or_physical_service_scope_corroborates_an_ambiguous_system_name(signal, config, title, description):
    result = classify(signal, config, title, description)
    assert result.prefilter_score < 12
    assert not any(m.startswith('Published digital scope:') for m in result.prefilter_matches)


@pytest.mark.parametrize('title,description', [
    ('Asset management system', 'Certification to ISO 55001 is required. The supplier will implement a SaaS application for asset records.'),
    ('Room and Venue Booking System', 'Implement software to automate venue hire and room reservations.'),
    ('Room and Venue Booking System', 'Supply a booking system for our facilities.'),
])
def test_software_delivery_or_sparse_scope_is_not_lost_to_ambiguous_system_guards(signal, config, title, description):
    result = classify(signal, config, title, description)
    assert result.prefilter_score >= 12
    assert not result.exclusion_reasons


@pytest.mark.parametrize('description', [
    'Development work on a content management system.',
    'Build a new public service using a content management system.',
    'Maintenance work on our learning management system.',
])
def test_delivery_using_or_working_on_a_business_system_is_not_incidental_use(signal, config, description):
    result = classify(signal, config, 'Information estate improvements', description)
    assert result.prefilter_score >= 12
    assert not result.exclusion_reasons
