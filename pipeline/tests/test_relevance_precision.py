import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from anthrion_signal import cli
from anthrion_signal.collectors import Collection, RawRecord
from anthrion_signal.discovery import is_public_opportunity, prefilter
from anthrion_signal.discovery_retention import read_rejected, retain_rejected
from anthrion_signal.models import Dataset, Signal
from anthrion_signal.translation import TranslationQueue, available_translations, field_key
from anthrion_signal.utils import atomic_json

CORPUS = json.loads((Path(__file__).parent / "fixtures/relevance_review.json").read_text(encoding="utf-8"))
CORPUS += json.loads((Path(__file__).parent / "fixtures/relevance_review_2026_09_18.json").read_text(encoding="utf-8"))
CORPUS += json.loads((Path(__file__).parent / "fixtures/purchased_scope_review_2026_09_18.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CORPUS, ids=lambda case: case["signal"]["id"])
def test_reviewed_real_notices(case, config):
    signal = Signal.model_validate(case["signal"])
    original = (signal.title, signal.description, signal.content_hash, signal.raw_source_hash)
    translations = {signal.id: case["translation"]} if case.get("translation") else {}
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"], translations)
    if case["expected"] == "unavailable":
        assert not is_public_opportunity(signal, datetime(2026, 9, 15, 20, 29, 20, tzinfo=UTC))
    else:
        retained = signal.prefilter_score >= 12 and not signal.exclusion_reasons
        assert bool(retained) is (case["expected"] == "retain"), signal.exclusion_reasons
    assert original == (signal.title, signal.description, signal.content_hash, signal.raw_source_hash)


@pytest.mark.parametrize("title,description", [
    ("Breeding bird survey", "Lot 1: Field observation. Lot 2: Develop a CRM platform for the observations."),
    ("Marine sediment coring survey", "Lot 2: Implement an AI assistant for processing survey reports."),
    ("Tenant survey software", "Develop a platform to manage survey responses and customer relationships."),
    ("Internal audit services", "Lot 2: Implement a document intelligence platform."),
    ("Building automation", "Lot 2: Implement a data platform and AI agent for energy optimisation."),
    ("Supply of Microsoft licences", "Lot 2: Implement Salesforce and integrate with Microsoft 365."),
    ("Supply of Microsoft licences", "Lote 2: Desarrollo e integración de aplicaciones empresariales."),
    ("Field survey software", "Build software for collecting and validating observations."),
    ("Digitale Modernisierung", "Lieferung von Gegenständen: NW-Server. Los 2: Entwicklung von Anwendungen für das Kundenportal."),
    ("Occupational safety specialist", "Workplace risk assessment. Lot 2: Develop a staff case management platform."),
    ("Occupational coding service", "Develop an AI assistant to classify the survey responses."),
    ("Business development consultancy", "Implement Salesforce to track industry partners and investor relationships."),
    ("Audio visual equipment", "Supply room screens. Lot 2: Build software to manage appointments and room bookings."),
    ("Mechanical systems integration", "Provide ventilation and integrate its alerts with a CRM platform via APIs."),
    ("Supplier portal implementation", "Design and implement a portal where suppliers log in and submit bids."),
    ("Cashless parking machines", "Supply parking meters. Lot 2: Develop a CRM platform for digital payment support."),
    ("Clinical simulation manikins", "Supply training equipment. Lot 2: Implement an AI assistant for clinical enquiries."),
    ("Food inspection services", "Record inspection results in the council system. Lot 2: Develop a new case management system."),
])
def test_mixed_scope_protection(signal, config, title, description):
    signal.title, signal.description = title, description
    signal.cpv_codes = ["72000000", "90700000"]
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    assert not signal.exclusion_reasons
    assert signal.prefilter_score >= 12


@pytest.mark.parametrize('title, description', [
    ('Digital delivery partner', 'Design, deliver and operate digital products and services.'),
    ('Digital delivery partner', 'Deliver digital, data and technology services throughout the digital service lifecycle.'),
    ('Care services modernisation', 'Implement a clinical patient management system.'),
    ('Employee service', 'Implement a case management system for complaints and enquiries.'),
    ('Cashless parking', 'Provide digital parking payments for on-street and off-street parking.'),
    ('Citizen services', 'Build an incident management system for municipal services.'),
])
def test_explicit_digital_delivery_without_cpv_or_brand_survives(signal, config, title, description):
    signal.title, signal.description, signal.cpv_codes = title, description, []
    prefilter([signal], config['company_profile'], config['search_terms'], config['capabilities'])
    assert signal.prefilter_score >= 12 and not signal.exclusion_reasons


@pytest.mark.parametrize('service', ['complaint handling', 'stakeholder management', 'workforce scheduling'])
def test_human_services_do_not_gain_software_tags_from_administration(signal, config, service):
    signal.title = 'Housing staff training'
    signal.description = f'Train staff in {service}. Log in to the supplier portal to submit bids.'
    signal.cpv_codes = ['80500000']
    prefilter([signal], config['company_profile'], config['search_terms'], config['capabilities'])
    assert not signal.matched_capabilities
    assert signal.prefilter_score < 12


@pytest.mark.parametrize('title,description,cpv', [
    ('Paper records storage', 'Store paper files using the Records and Digital Solutions framework.', []),
    ('Multi Functional Devices & Digital Solutions', 'Printer framework call-off.', []),
    ('Cashless Parking Machines', 'Refurbishment of Parking Meters and purchase of new units.', ['38730000']),
    ('Clinical Simulation Manikins', 'Supply manikins with control software configuration and an online learning platform subscription.', ['33000000']),
    ('Food inspection services', 'Post inspection actions include updating the council computerised case management system.', ['90700000']),
])
def test_tools_or_framework_names_do_not_establish_software_delivery(signal, config, title, description, cpv):
    signal.title, signal.description, signal.cpv_codes = title, description, cpv
    prefilter([signal], config['company_profile'], config['search_terms'], config['capabilities'])
    assert signal.prefilter_score < 12 or signal.exclusion_reasons


def test_rejected_notice_is_losslessly_replayable_after_rule_change(tmp_path, signal, config, now):
    signal.title = "AI Adoption Programme"
    signal.description = "Support AI pilots and implement responsible AI adoption."
    signal.prefilter_score = 0
    assert retain_rejected(tmp_path, [signal], now, 12) == 1
    replay = read_rejected(tmp_path)
    assert len(replay) == 1
    assert replay[0].model_dump() == signal.model_dump()
    prefilter(replay, config["company_profile"], config["search_terms"], config["capabilities"])
    assert replay[0].prefilter_score >= 12
    assert not replay[0].exclusion_reasons
    retain_rejected(tmp_path, [signal, signal], now, 12)
    assert len(read_rejected(tmp_path)) == 1
    later = signal.model_copy(update={"updated_at": (now + timedelta(days=32)).isoformat(),
                                      "status": "cancelled", "content_hash": "changed"})
    retain_rejected(tmp_path, [later], now + timedelta(days=32), 12)
    assert read_rejected(tmp_path)[0].status == "cancelled"


def test_national_pre_gate_rejections_reach_common_classifier(monkeypatch, release, source, config, now):
    result = Collection(rejected_records=[RawRecord(release, source, now.isoformat())])
    monkeypatch.setattr(cli, "collect_with_backfill", lambda *args: result)
    monkeypatch.setattr(cli, "hydrate_sparse", lambda *args: None)
    _, records, _, _, count = cli._collect(source, {}, now, config)
    assert count == 1
    assert len(records) == 1
    assert records[0].title == release["tender"]["title"]


def test_negated_software_does_not_rescue_physical_survey(signal, config):
    signal.title = "Breeding bird survey"
    signal.description = "Field observation of bird species. The contractor is not required to develop software."
    signal.cpv_codes = ["90700000"]
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    assert signal.exclusion_reasons


@pytest.mark.parametrize("sidecar", ["missing", "empty", "stale", "damaged"])
def test_relevance_translation_survives_display_pruning(tmp_path, signal, config, sidecar):
    signal.title = "Brut- und Rastvogelerfassung"
    signal.description = "Erfassung der Vogelarten in den Schutzgebieten."
    signal.cpv_codes = ["90700000"]
    queue = TranslationQueue(tmp_path / "data/translation/cache.json")
    queue.prepare([signal])
    for original, english in [(signal.title, "Breeding and resting bird survey"),
                              (signal.description, "Survey of bird species in protected habitats.")]:
        queue.state["fields"][field_key(original)]["parts"][0]["result"] = {"text": english, "language": "de"}
    queue.save()
    saved = queue.path.read_bytes()
    path = tmp_path / "data/translation/translations.en.json"
    if sidecar != "missing":
        overlay = queue.overlay([signal])
        if sidecar == "empty":
            overlay["signals"] = {}
        else:
            overlay["signals"][signal.id]["source_hash"] = "obsolete"
        atomic_json(path, overlay)
        if sidecar == "damaged":
            path.write_text("invalid", encoding="utf-8")
    translations = available_translations(tmp_path, [signal])
    assert signal.id in translations
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"], translations)
    assert signal.scope_evidence[0]["rule"] == "field_surveys"
    assert queue.path.read_bytes() == saved
    changed = signal.model_copy(update={"description": "A new and different procurement scope."})
    assert available_translations(tmp_path, [changed]) == {}
    # Cache entries must still pass current translation validation.
    queue.state["fields"][field_key(signal.description)]["parts"][0]["result"]["text"] = signal.description
    queue.save()
    assert available_translations(tmp_path, [signal]) == {}


def test_export_recovers_canonical_candidate_on_rule_release(tmp_path, signal, config, monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda root: config)
    signal.title = "AI Adoption Programme"
    signal.description = "Support AI pilots and implement responsible AI adoption."
    signal.prefilter_score = 0
    signal.status = "planned"
    signal.notice_type = "planned"
    signal.deadline_at = None
    signal.response_deadlines = []
    closed = signal.model_copy(update={"id": "closed", "status": "cancelled"})
    dataset = Dataset(generated_at="2026-09-15T20:29:20Z", data_updated_at="2026-09-15T20:29:20Z",
                      profile_version="1", scoring_version="none",
                      run={"discovery_version": config["capabilities"]["version"], "discovery_signature": "previous-engine"},
                      sources=[], capabilities=[], markets={}, evidence_catalog={}, signals=[])
    atomic_json(tmp_path / "data/current.json", dataset.model_dump())
    path = tmp_path / "data/signals.jsonl"
    path.write_text(signal.model_dump_json() + "\n" + closed.model_dump_json() + "\n", encoding="utf-8")
    before = path.read_bytes()
    published = cli.export(tmp_path)
    assert [s.id for s in published.signals] == [signal.id]
    assert published.generated_at == dataset.generated_at
    assert path.read_bytes() == before
