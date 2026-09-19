"""Evidence, financial meaning, entities and lifecycle boundaries for public research."""
from datetime import UTC, datetime

from anthrion_signal.collectors import RawRecord
from anthrion_signal.dedupe import merge, reconcile
from anthrion_signal.discovery import lifecycle, prefilter
from anthrion_signal.normalise import normalise_grants, normalise_ocds, normalise_ted
from anthrion_signal.notice_dates import response_deadline_instant
from anthrion_signal.public_context import attach_history, buyer_identity, history_entry, public_signal
from anthrion_signal.utils import digest


def test_public_evidence_exact_quote_approved_fields_and_qualification_unknown(signal, config):
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    signal.capability_evidence[0]["internal_notes"] = "never publish"
    result = public_signal(signal)
    assert set(result["matched_capabilities"]) == {e["capability"] for e in result["capability_evidence"]}
    for evidence in result["capability_evidence"]:
        assert evidence["quote"] in getattr(signal, evidence["field"])
        assert evidence["source_url"] == signal.primary_source_url
        assert "internal_notes" not in evidence
    assert result["delivery_role"]["kind"] == "direct_supplier"
    assert result["participation_requirements"]
    assert all(r["status"] == "needs_checking" and r["company_evidence"] is None for r in result["participation_requirements"])
    assert "analysis" not in result and "prefilter_score" not in result


def test_translated_evidence_retains_original_without_invented_sentence_alignment(signal, config):
    signal.title, signal.description = "Asiakastiedot", "Lyhyt kuvaus."
    translation = {"source_hash": digest([signal.title, signal.description]), "title": "Customer information system",
                   "description": "Implement a customer information system."}
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"], {signal.id: translation})
    result = public_signal(signal, translation)
    assert result["capability_evidence"]
    assert all(e["original_quote"] == getattr(signal, e["field"]) for e in result["capability_evidence"])
    assert not public_signal(signal, {**translation, "source_hash": "stale"})["matched_capabilities"]


def test_submission_portal_and_negation_never_produce_positive_public_evidence(signal, config):
    signal.title = "Procurement notice"
    signal.description = "Submit your bid through the customer portal. CRM implementation is not required."
    signal.cpv_codes = []
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    result = public_signal(signal)
    assert not {"portals", "crm"}.intersection(result["matched_capabilities"])


def test_grants_buyer_contact_range_and_date_precision(config, now):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "grants")
    raw = {"id": "123", "title": "Implement CRM", "status": "posted", "agency": "Department of Energy",
        "agencyDetails": {"agencyCode": "DOE-SC", "agencyName": "Office of Science"},
        "topAgencyDetails": {"agencyName": "Department of Energy"},
        "facts": {"agencyName": "Jane Example", "agencyContactName": "Jane Example", "agencyContactDesc": "Grant specialist",
                  "awardFloor": "250000", "awardCeiling": "200000000", "responseDateStr": "2026-10-19-00-00-00",
                  "synopsisDesc": '<p>Implement a CRM. <a href="https://science.osti.gov/full-rfa.pdf">Full RFA</a></p>'}}
    result = normalise_grants(RawRecord(raw, source, now.isoformat(), "grants"))
    assert result.buyer_name == "Office of Science" and result.agency_name == "Department of Energy"
    assert result.contacts[0]["name"] == "Jane Example" and result.buyer_name_conflicts == ["Jane Example"]
    assert result.amount.kind == "grant_range" and result.amount.minimum == 250000 and result.amount.maximum == 200000000
    assert result.deadline_at == "2026-10-19" and result.deadlines[0].instant is None
    assert result.documents[0].url.endswith("full-rfa.pdf")


def test_contact_shaped_legacy_synopsis_is_not_promoted_to_buyer(config, now):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "grants")
    result = normalise_grants(RawRecord({"id": "123", "title": "CRM", "facts": {"agencyName": "Jane Example"}}, source, now.isoformat(), "grants"))
    assert result.buyer_name is None and result.buyer_name_conflicts == ["Jane Example"]


def test_initial_applications_before_later_invited_stage_and_questions(config, now):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "ted")
    raw = {"publication-number": "123456-2026", "title-proc": {"eng": "CRM"}, "form-type": "competition",
           "deadline-receipt-request-date-lot": ["2026-10-01"], "deadline-receipt-tender-date-lot": ["2026-11-01"]}
    result = normalise_ted(RawRecord(raw, source, now.isoformat(), "ted"))
    assert result.deadline_at == "2026-10-01"
    assert [d.kind for d in result.deadlines] == ["application", "invited_submission"]


def test_date_only_deadlines_stay_open_through_last_possible_calendar_day(signal):
    signal.deadline_at, signal.response_deadlines = "2026-10-19", []
    signal.deadlines = []
    assert lifecycle(signal, datetime(2026, 10, 20, 4, tzinfo=UTC))[0] == "OPEN"
    assert lifecycle(signal, datetime(2026, 10, 20, 12, tzinfo=UTC))[0] == "EXPIRED"
    assert response_deadline_instant("2026-10-25", "Europe/London").utcoffset().total_seconds() == 0
    assert response_deadline_instant("2026-06-25", "Europe/London").utcoffset().total_seconds() == 3600


def test_enquiry_deadline_is_not_a_tender_cutoff(release, source, now):
    release["tender"].pop("tenderPeriod")
    release["tender"]["enquiryPeriod"] = {"endDate": "2026-10-01"}
    result = normalise_ocds(RawRecord(release, source, now.isoformat()))
    assert result.deadline_at is None and result.deadlines[0].kind == "questions"


def test_untimed_extension_keeps_previous_revision(signal, release, source, now):
    release["tender"]["tenderPeriod"]["endDate"] = "2026-11-01"
    release["date"] = now.isoformat()
    update = normalise_ocds(RawRecord(release, source, now.isoformat()))
    result, changed = merge(signal, update)
    assert changed and result.deadline_at == "2026-11-01"
    assert [d.status for d in result.deadlines] == ["current", "superseded"]


def test_framework_estimate_is_not_automatically_a_ceiling(release, source, now):
    release["tender"]["techniques"] = {"hasFrameworkAgreement": True}
    result = normalise_ocds(RawRecord(release, source, now.isoformat()))
    assert result.framework == "Framework agreement" and result.amount.kind == "estimated_contract"


def test_partial_award_cannot_retire_other_lots(release, source, now):
    release["tender"]["lots"] = [{"id": "1", "title": "Servers"}, {"id": "2", "title": "CRM", "status": "active"}]
    original = normalise_ocds(RawRecord(release, source, now.isoformat()))
    release["id"], release["tag"] = "award-1", ["award"]
    release["awards"] = [{"id": "a1", "status": "active", "relatedLots": ["1"], "date": "2026-09-09",
                          "value": {"amount": 15000, "currency": "GBP"}, "suppliers": [{"id": "supplier-1", "name": "Server Co"}]}]
    award = normalise_ocds(RawRecord(release, source, now.isoformat()), original)
    records, _, _ = reconcile([original], [award])
    assert len(records) == 2
    remaining = next(s for s in records if s.id == original.id)
    assert lifecycle(remaining, now)[0] == "OPEN"
    assert [(lot.id, lot.status) for lot in remaining.lots] == [("1", "awarded"), ("2", "active")]
    assert award.amount.kind == "award" and award.amount.maximum == 15000
    assert award.award_date.startswith("2026-09-09") and award.winners[0]["lot_ids"] == ["1"]
    release["id"] = "award-2"
    release["tender"].pop("lots")
    release["awards"][0]["relatedLots"] = ["2"]
    second = normalise_ocds(RawRecord(release, source, now.isoformat()), award)
    all_records, _, _ = reconcile(records, [second])
    assert len(all_records) == 3
    retired = next(s for s in all_records if s.id == original.id)
    assert retired.status == "complete" and lifecycle(retired, now)[0] == "CLOSED"

    release["id"], release["tag"] = "award-1-cancelled", ["awardCancellation"]
    release["awards"][0].update(status="cancelled", relatedLots=["1"])
    cancellation = normalise_ocds(RawRecord(release, source, now.isoformat()), award)
    assert cancellation.id == award.id
    cancelled_records, _, _ = reconcile(all_records, [cancellation])
    reopened = next(s for s in cancelled_records if s.id == original.id)
    assert reopened.status == original.status and lifecycle(reopened, now)[0] == "OPEN"
    assert [(lot.id, lot.status) for lot in reopened.lots] == [("1", "unknown"), ("2", "awarded")]
    assert "lot_award_baseline" not in public_signal(reopened)


def test_cancelled_award_with_retained_winner_cannot_close_lots(release, source, now):
    release["tender"]["lots"] = [{"id": "1", "title": "CRM", "status": "active"}]
    original = normalise_ocds(RawRecord(release, source, now.isoformat()))
    for status, award_statuses in [("cancelled", []), ("withdrawn", []), ("active", ["cancelled"])]:
        award = original.model_copy(update={"id": "cancelled-award", "signal_type": "AWARD", "lot_id": "1",
            "status": status, "award_statuses": award_statuses, "source_urls": ["https://example.org/cancelled"],
            "external_ids": [], "winners": [{"name": "Prior winner", "lot_ids": ["1"]}]})
        records, _, _ = reconcile([original], [award])
        remaining = next(s for s in records if s.id == original.id)
        assert remaining.lots[0].status == "active" and lifecycle(remaining, now)[0] == "OPEN"


def test_no_fuzzy_identity_merge_and_local_buyer_ids_scoped(signal):
    other = signal.model_copy(deep=True)
    other.id, other.ocid, other.external_ids, other.source_urls = "different", None, [], ["https://example.org/different"]
    other.title = signal.title + " services"
    records, _, _ = reconcile([signal], [other])
    assert len(records) == 2
    signal.buyer_id, signal.buyer_identifiers = None, ["buyer-1"]
    other.buyer_id, other.buyer_identifiers, other.source = None, ["buyer-1"], "another-source"
    assert buyer_identity(signal)[0] != buyer_identity(other)[0]
    signal.buyer_id, signal.buyer_identifiers, signal.source, signal.countries = None, [], "ted", ["FR"]
    other.buyer_id, other.buyer_identifiers, other.source, other.countries = None, [], "ted", ["BE"]
    signal.buyer_name = other.buyer_name = "Ministry of Interior"
    assert buyer_identity(signal)[0] != buyer_identity(other)[0]


def test_buyer_history_keeps_all_known_awards_and_source_facts(signal):
    history = [signal.model_copy(update={"id": "award_" + str(i), "signal_type": "AWARD", "status": "awarded"}) for i in range(60)]
    attach_history([signal], history)
    assert len(signal.buyer_history) == 61
    assert all("amount" in item and "source_url" in item and "contract_end" in item for item in signal.buyer_history)
    assert all(item["source"] == signal.source and item["countries"] == signal.countries
               and item["buyer_name"] == signal.buyer_name and item["buyer_id"] == signal.buyer_id
               for item in signal.buyer_history)


def test_history_supplier_scope_and_cancellation_come_from_each_actual_notice(signal):
    cancelled = signal.model_copy(update={"id": "cancelled-award", "source": "other-source",
        "countries": ["CH"], "buyer_id": "other-buyer", "buyer_name": "Another buyer",
        "signal_type": "AWARD", "award_statuses": ["cancelled"]})
    item = history_entry(cancelled)
    assert item["source"] == "other-source" and item["countries"] == ["CH"]
    assert item["buyer_id"] == "other-buyer" and item["buyer_name"] == "Another buyer"
    assert item["award_statuses"] == ["cancelled"]


def test_native_french_and_dutch_delivery_aliases_survive_public_evidence(signal, config):
    for title, text in [("Logiciel de gestion de la relation client", "Mise en œuvre et maintenance du logiciel CRM."),
                        ("Klantrelatiebeheer", "Implementatie van het CRM-systeem en API-koppelingen.")]:
        signal.title, signal.description, signal.cpv_codes = title, text, []
        prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
        result = public_signal(signal)
        assert "crm" in result["matched_capabilities"]
        assert any(e["capability"] == "crm" and e["basis"] != "english_translation" for e in result["capability_evidence"])


def test_existing_system_is_context_but_stated_integration_is_delivery(signal):
    for passage, expected in [("The existing CRM software was developed in 2018.", "existing_system"),
                              ("Integrate the new CRM with the existing finance system.", "delivery")]:
        signal.description, signal.matched_capabilities = passage, ["crm"]
        signal.capability_evidence = [{"capability": "crm", "field": "description", "basis": "original",
                                       "strength": "needs", "phrase": "CRM", "quote": passage}]
        assert public_signal(signal)["capability_evidence"][0]["context"] == expected


def test_native_and_translated_participation_requirements_keep_source(signal):
    for text in ["Les candidats doivent posséder une licence obligatoire.",
                 "De leverancier moet een verplichte certificering aantonen.",
                 "Der Bieter muss mindestens drei relevante Referenzen nachweisen.",
                 "The supplier must hold the required licence."]:
        signal.description, signal.eligibility_text = text, None
        requirements = public_signal(signal)["participation_requirements"]
        assert requirements and requirements[0]["source_quote"] == text
    signal.description = "Alkuperäinen vaatimus."
    translated = {"source_hash": digest([signal.title, signal.description]), "description": "The supplier must hold a security clearance."}
    item = public_signal(signal, translated)["participation_requirements"][0]
    assert item["source_quote"] == signal.description and item["translated_quote"] == translated["description"]
    signal.description = "A security clearance is not required."
    assert not public_signal(signal)["participation_requirements"]


def test_legacy_award_amount_and_generated_advice_are_not_source_proof(signal):
    signal.signal_type, signal.amount = "AWARD", None
    signal.description = "CRM implementation."
    signal.eligibility_text = "Multiple lot deadlines are published. The next remaining date is shown; check the source notice for the relevant lot."
    result = public_signal(signal)
    assert result["amount"]["kind"] == "unknown"
    assert not result["participation_requirements"]
