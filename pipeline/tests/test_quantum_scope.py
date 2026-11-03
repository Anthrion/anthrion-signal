"""Specialist computing milestones must not masquerade as business-app delivery."""
import json
from pathlib import Path

import pytest

from anthrion_signal.discovery import prefilter
from anthrion_signal.models import Signal
from anthrion_signal.utils import digest


def classify(signal, config):
    prefilter([signal], config['company_profile'], config['search_terms'], config['capabilities'])
    return signal.prefilter_score >= 12 and not signal.exclusion_reasons


def test_quantum_genesis_source_notice_is_not_business_application_delivery(config):
    source = json.loads((Path(__file__).parent / 'fixtures/quantum_genesis.json').read_text(encoding='utf-8'))
    signal = Signal.model_validate(source)
    assert not classify(signal, config)
    assert not signal.matched_capabilities
    assert signal.scope_evidence[0]['rule'] == 'quantum_computer_delivery'
    for field in ('title', 'description', 'content_hash', 'raw_source_hash', 'primary_source_url'):
        assert getattr(signal, field) == source[field]


@pytest.mark.parametrize('title,description', [
    ('Quantum prototype programme', 'Develop fault-tolerant quantum computers. The initiative supports quantum computing application development for scientific discovery.'),
    ('Quantum hardware scaling', 'Scaling quantum hardware for logical qubits. Application development for quantum algorithms is part of the scientific workflows.'),
    ('Quantum prototype fabrication', 'Manufacture quantum hardware. The Quantum Computer for Application Development and Discovery Science programme provides the funding.'),
])
def test_unseen_scientific_programmes_are_not_crm_delivery(signal, config, title, description):
    signal.title, signal.description, signal.cpv_codes = title, description, ['72000000']
    assert not classify(signal, config)
    assert 'transformation' not in signal.matched_capabilities


@pytest.mark.parametrize('description,capability', [
    ('Develop fault-tolerant quantum computers. Lot 2: Implement Salesforce for partner management.', 'salesforce'),
    ('Scaling quantum hardware. Lot 2: Build a customer portal for research partners.', 'portals'),
    ('Develop fault-tolerant quantum computers. Lot 2: Provide API integration for our CRM platform.', 'integration'),
    ('Develop fault-tolerant quantum computers. Lot 2: Implement an AI assistant for staff enquiries.', 'ai'),
    ('CRM application development for a quantum computing laboratory undertaking scientific discovery.', 'crm'),
    ('The Quantum Computer for Application Development and Discovery Science programme requires customer portal application development.', 'portals'),
    ('Application development for quantum algorithms and scientific workflows. Separately, business application development will automate staff approvals.', 'transformation'),
    ('Build a grant portal for application development and submission.', 'portals'),
])
def test_real_business_scope_survives_including_same_sentence(signal, config, description, capability):
    signal.title, signal.description, signal.cpv_codes = 'Quantum research centre services', description, []
    assert classify(signal, config)
    assert capability in signal.matched_capabilities


@pytest.mark.parametrize('title,description', [
    ('Application development', 'Develop applications for the council.'),
    ('Quantum research institute', 'Application development services for internal operations.'),
    ('Quantum computing services', 'Further details are in the tender documents.'),
    ('Post-quantum migration', 'Professional services and API integration for post-quantum cryptography readiness.'),
])
def test_generic_software_and_sparse_or_security_scopes_are_preserved(signal, config, title, description):
    signal.title, signal.description, signal.cpv_codes = title, description, ['72000000']
    assert classify(signal, config)


def test_exact_hash_translation_obeys_same_scope_rules(signal, config):
    signal.title, signal.description, signal.cpv_codes = 'Quanteninitiative', 'Entwicklung fehlertoleranter Quantencomputer.', []
    overlay = {signal.id: {'source_hash': digest([signal.title, signal.description]), 'title': 'Quantum prototype programme',
        'description': 'Develop fault-tolerant quantum computers for application development and discovery science.'}}
    prefilter([signal], config['company_profile'], config['search_terms'], config['capabilities'], overlay)
    assert signal.prefilter_score == 0
    assert signal.scope_evidence[0]['basis'] == 'english_translation'
    assert signal.title == 'Quanteninitiative'


def test_negated_crm_delivery_does_not_rescue_quantum_hardware(signal, config):
    signal.title = 'Quantum hardware fabrication'
    signal.description = 'Develop fault-tolerant quantum computers. CRM implementation is not required.'
    signal.cpv_codes = ['72000000']
    assert not classify(signal, config)


def test_explicitly_excluded_hardware_is_not_the_purchased_scope(signal, config):
    signal.title = 'Quantum research services'
    signal.description = 'The contractor is not required to develop quantum hardware. Further service details will follow.'
    signal.cpv_codes = ['72000000']
    assert classify(signal, config)
