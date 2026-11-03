import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from anthrion_signal.boamp_caribbean import (
    API_URL,
    VERSION,
    _period,
    _territories,
    collect_boamp_caribbean,
    normalise_boamp_caribbean,
)
from anthrion_signal.collectors import RawRecord, SourceUnavailable
from anthrion_signal.dedupe import compatible_identifiers, exact_keys, merge


NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
SOURCE = {"id": "boamp_caribbean", "name": "BOAMP Caribbean", "source_type": "official_notice", "url": API_URL}
FIXTURES = {row["idweb"]: row for row in json.loads((Path(__file__).parent / "fixtures/boamp_caribbean.json").read_text(encoding="utf-8"))}


def row(ident):
    data = copy.deepcopy(FIXTURES[ident])
    data["id"] = data["idweb"]
    return data


def signal(ident, data=None):
    return normalise_boamp_caribbean(RawRecord(data or row(ident), SOURCE, NOW.isoformat(), "boamp_caribbean"))


class Api:
    def __init__(self, *pages):
        self.pages, self.calls = list(pages), []

    def json(self, url, params):
        self.calls.append((url, params))
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page


def collect(api, state=None, budget=20, source=None, frozen=NOW):
    return collect_boamp_caribbean(source or SOURCE, state or {}, frozen, api,
                                  {"max_pages": budget, "lookback_days": 30}, {})


def test_fnsimple_preserves_french_scope_lots_and_local_deadline_precision():
    s = signal("26-103580")
    assert s.countries == ["MQ"] and s.source_language == "fr"
    assert "Aménagement intérieur" in s.description and "Plomberie" in s.description
    assert "Deux visites seront organisées" in s.description
    assert s.lot_ids == ["1", "2"]
    assert s.deadline_at == "2026-11-13"  # API falsely labels naive clock as +00:00.
    assert s.deadlines[0].precision == "local_time"
    assert s.deadlines[0].time == "12:00:00" and s.deadlines[0].instant is None
    assert s.published_at == "2026-10-23" and s.status == "active"
    assert s.buyer_identifiers == ["FR-SIRET:24972006100103"]


def test_publication_departments_do_not_make_guyane_a_caribbean_notice():
    data = row("26-103716")
    assert data["code_departement"] == ["973", "972", "971"]
    assert signal("26-103716", data) is None


@pytest.mark.parametrize(("postal", "expected"), [("97133", {"BL"}), ("97150", {"MF"}), ("97100", {"GP"}), ("97256", {"MQ"}), ("97300", {"GF"})])
def test_postal_location_overrides_broad_nuts(postal, expected):
    assert _territories({"cbc:PostalZone": postal, "cbc:CountrySubentityCode": {"#text": "FRY10"}}) == expected


def test_named_mainland_commune_is_not_inferred_as_saint_barthelemy():
    assert _territories("Saint-Barthélemy d'Anjou") == set()
    assert _territories("Collectivité de Saint-Barthélemy") == {"BL"}
    assert _territories({"cac:Country": {"cbc:IdentificationCode": {"#text": "BLM"}}}) == {"BL"}


def test_saint_martin_is_not_guadeloupe_despite_971_postcode():
    s = signal("26-101686")
    assert s.countries == ["MF"] and s.value_max == 195000 and s.currency == "EUR"


def test_eforms_reads_complete_scope_known_offset_and_framework_amount():
    s = signal("26-102567")
    assert s.countries == ["MQ"] and s.source_language == "fr"
    assert "27 arrêts" in s.description and "Valeur technique" in s.description
    assert s.deadline_at == "2026-11-25T16:00:00+00:00"
    assert len(s.deadlines) == 2 and all(f.precision == "instant" for f in s.deadlines)
    assert s.amount.kind == "framework_ceiling" and s.value_max == 1030000
    assert s.procedure_identifiers == ["ted-procedure:55c42057-b5fd-4daa-bacb-e8edef86902c"]
    assert any("pack/annonce_marche_public" in doc.url for doc in s.documents)


def test_long_original_scope_keeps_requirements_after_default_text_limit():
    data = row("26-102567")
    project = data["donnees"]["EFORMS"]["ContractNotice"]["cac:ProcurementProject"]
    project["cbc:Description"] = {"#text": "Description du marché. " * 1300 + "Intégration CRM Salesforce requise."}
    assert "Intégration CRM Salesforce requise." in signal("26-102567", data).description


def test_only_contracting_buyer_address_routes_notice_not_appeals_body():
    data = row("26-102567")
    notice = data["donnees"]["EFORMS"]["ContractNotice"]
    notice["cac:ProcurementProject"].pop("cac:RealizedLocation")
    for lot in notice["cac:ProcurementProjectLot"]:
        lot["cac:ProcurementProject"].pop("cac:RealizedLocation", None)
    orgs = notice["ext:UBLExtensions"]["ext:UBLExtension"]["ext:ExtensionContent"]["efext:EformsExtension"]["efac:Organizations"]["efac:Organization"]
    orgs[0]["efac:Company"]["cac:PostalAddress"]["cbc:PostalZone"] = "97300"
    assert signal("26-102567", data) is None  # Martinique tribunal must not route Guyane buyer.


def test_partial_award_keeps_lot_outcomes_without_aliasing_entire_tender():
    s = signal("26-102530")
    assert s.signal_type == "AWARD" and s.status == "awarded" and s.deadline_at is None
    assert s.award_date == "2026-07-22" and s.incumbent_supplier == "TK Elevator France SAS"
    assert {lot.id: lot.status for lot in s.lots} == {"LOT-0001": "awarded", "LOT-0002": "unsuccessful"}
    assert s.external_ids == ["boamp:26-102530"]
    assert s.amount.kind == "framework_ceiling"  # EUR 2m is maximum, not EUR 776430 tender price.


def test_cancellation_never_exposes_future_response_deadline():
    s = signal("26-102186")
    assert s.status == "cancelled" and s.deadline_at is None and not s.deadlines
    assert "boamp:26-99273" in s.external_ids


@pytest.mark.parametrize("ident", ["26-102086", "26-103698", "26-103594"])
def test_corrections_do_not_trust_stale_structured_deadline(ident):
    s = signal(ident)
    assert s.status == "amended" and s.deadline_at is None and not s.deadlines
    assert len(s.external_ids) == 2
    if ident == "26-102086":
        assert "09 Novembre 2026" in s.description


def test_explicit_correction_alias_merges_only_publisher_referenced_notice():
    initial, correction = signal("26-101686"), signal("26-103594")
    assert initial.ocid is None and correction.ocid is None
    assert compatible_identifiers(initial, correction)
    assert set(exact_keys(initial)) & set(exact_keys(correction))


def test_sparse_correction_preserves_original_scope_and_supersedes_obsolete_deadline():
    original = signal("26-101686")
    data = row("26-103594")
    correction = normalise_boamp_caribbean(RawRecord(data, SOURCE, NOW.isoformat(), "boamp_caribbean"), original)
    assert original.description in correction.description
    assert len(correction.description) > len(original.description)
    assert {lot.id for lot in original.lots} <= {lot.id for lot in correction.lots}
    revised, _ = merge(original, correction)
    assert revised.deadline_at is None and revised.response_deadlines == []
    assert all(fact.status == "superseded" for fact in revised.deadlines)
    repeated = normalise_boamp_caribbean(RawRecord(data, SOURCE, NOW.isoformat(), "boamp_caribbean"), revised)
    assert repeated.description == revised.description


def test_mapa_typed_replacement_date_is_used():
    s = signal("26-103047")
    assert s.status == "amended" and s.deadline_at == "2026-11-20"
    assert s.deadlines[0].time == "17:00:00" and s.deadlines[0].precision == "local_time"
    assert "restauration écologique" in s.description


def test_mapa_initial_full_requirements_and_document_link():
    s = signal("26-102178")
    assert s.countries == ["MQ"] and s.deadline_at == "2026-11-20"
    assert "Capacité technique" in s.description and "24 mois" in s.description
    assert any(doc.url == "https://www.marches-securises.fr" for doc in s.documents)


def test_non_competition_notice_is_not_invented_as_open_tender():
    data = row("26-103580")
    data["nature"] = "PRE_INFORMATION"
    s = signal("26-103580", data)
    assert s.status == "unknown" and s.signal_type == "STRATEGIC_INTENT"


def test_conflicting_ubl_offsets_are_not_guessed():
    assert _period({"cbc:EndDate": "2026-11-01-04:00", "cbc:EndTime": "12:00:00+02:00"}) is None
    assert _period({"cbc:EndDate": "2026-11-01", "cbc:EndTime": "12:00:00"}) == "2026-11-01T12:00:00"


def test_api_pagination_resumes_older_active_notices_and_full_scope():
    first, second, third = row("26-101686"), row("26-102178"), row("26-102186")
    api = Api({"total_count": 3, "results": [first, second]})
    a = collect(api, budget=1, source={**SOURCE, "limit": 2})
    assert not a.complete and len(a.records) == 2 and "watermark" not in a.state
    query = api.calls[0][1]["where"]
    assert "datelimitereponse >=" in query and "objet" not in query
    b_api = Api({"total_count": 1, "results": [third]})
    b = collect(b_api, state=a.state, source={**SOURCE, "limit": 2})
    assert b.complete and len(b.records) == 1 and "pending" not in b.state
    assert "dateparution >= date'2026-10-20'" in b_api.calls[0][1]["where"]
    assert "NOT (idweb in ('26-102178'))" in b_api.calls[0][1]["where"]
    assert "offset" not in b_api.calls[0][1]
    assert b.state["watermark"] == NOW.isoformat()
    assert b.records[0].data["donnees"] and b.records[0].kind == "boamp_caribbean"


def test_invalid_short_snapshot_cannot_advance_watermark_or_cursor():
    result = collect(Api({"total_count": 2, "results": [row("26-102178")]}))
    assert not result.complete and not result.records and "watermark" not in result.state
    assert result.state["pending"]["seen_ids"] == []


def test_repeated_page_fails_without_skipping_or_duplicating():
    data = row("26-102178")
    api = Api({"total_count": 2, "results": [data]}, {"total_count": 1, "results": [data]})
    result = collect(api, source={**SOURCE, "limit": 1})
    assert not result.complete and len(result.records) == 1
    assert "did not advance" in result.message and "watermark" not in result.state
    assert result.state["pending"]["seen_ids"] == []
    assert result.state["pending"]["seen_ids"] == []


def test_source_failure_preserves_checkpoint_and_respects_retry():
    state = {"query_version": VERSION, "watermark": (NOW - timedelta(days=2)).isoformat()}
    api = Api(SourceUnavailable("rate limit", status_code=429, retry_at=NOW + timedelta(hours=1)))
    result = collect(api, state)
    assert not result.complete and result.state["watermark"] == state["watermark"]
    assert result.state["pending"]["seen_ids"] == []


def test_same_day_insertion_before_old_cursor_is_collected():
    a, c, b = (row("26-102178") for _ in range(3))
    for record, ident in ((a, "26-100001"), (b, "26-100002"), (c, "26-100003")):
        record["idweb"] = record["id"] = ident
    first = collect(Api({"total_count": 3, "results": [a, c]}), budget=1, source={**SOURCE, "limit": 2})
    api = Api({"total_count": 1, "results": [b]})
    second = collect(api, state=first.state, source={**SOURCE, "limit": 2})
    assert second.complete and [raw.data["idweb"] for raw in second.records] == ["26-100002"]
    assert "NOT (idweb in ('26-100001','26-100003'))" in api.calls[0][1]["where"]


def test_deleting_an_already_seen_notice_cannot_shift_past_an_unseen_notice():
    a, b, c = (row("26-102178") for _ in range(3))
    for record, ident in ((a, "26-100001"), (b, "26-100002"), (c, "26-100003")):
        record["idweb"] = record["id"] = ident
    first = collect(Api({"total_count": 3, "results": [a, b]}), budget=1, source={**SOURCE, "limit": 2})
    # The publisher deletes a after page1. Exact exclusion still returns c.
    api = Api({"total_count": 1, "results": [c]})
    second = collect(api, state=first.state, source={**SOURCE, "limit": 2})
    assert second.complete and second.records[0].data["idweb"] == "26-100003"
    assert "offset" not in api.calls[0][1]


def test_source_natural_id_collation_does_not_fail_at_six_digit_notice_numbers():
    a, b, c = (row("26-102178") for _ in range(3))
    for record, ident in ((a, "26-99605"), (b, "26-100178"), (c, "26-100423")):
        record["idweb"] = ident
    result = collect(Api({"total_count": 3, "results": [a, b]}, {"total_count": 1, "results": [c]}),
                     source={**SOURCE, "limit": 2})
    assert result.complete and [raw.data["idweb"] for raw in result.records] == ["26-99605", "26-100178", "26-100423"]


def test_duplicate_id_within_one_page_cannot_claim_complete_snapshot():
    data = row("26-102178")
    result = collect(Api({"total_count": 2, "results": [data, data]}))
    assert not result.complete and not result.records and "watermark" not in result.state


def test_day_query_limit_keeps_checkpoint_and_never_claims_complete(monkeypatch):
    monkeypatch.setattr("anthrion_signal.boamp_caribbean.MAX_DAY_IDS", 1)
    a, b = row("26-102178"), row("26-102178")
    a["idweb"], b["idweb"] = "26-100001", "26-100002"
    api = Api({"total_count": 3, "results": [a, b]})
    first = collect(api, source={**SOURCE, "limit": 2})
    assert not first.complete and "bounded query size" in first.message
    assert len(first.records) == 2 and first.state["pending"]["seen_ids"] == ["26-100001", "26-100002"]
    assert "watermark" not in first.state
    no_requests = Api()
    second = collect(no_requests, state=first.state)
    assert not second.complete and not no_requests.calls and second.state["pending"] == first.state["pending"]


def test_fresh_complete_source_skips_requests_without_marking_absent_notices_closed():
    api = Api()
    result = collect(api, {"query_version": VERSION, "watermark": NOW.isoformat()})
    assert result.complete and not api.calls and not result.records


def test_unknown_schema_fails_visibly_instead_of_silently_losing_scope():
    data = row("26-102178")
    data["donnees"] = {"futureSchema": {"title": "Unknown"}}
    result = collect(Api({"total_count": 1, "results": [data]}))
    assert not result.complete and "unsupported original notice schema" in result.message
    assert not result.records and "watermark" not in result.state


def test_json_string_body_matches_decoded_source_fixture():
    data = row("26-102567")
    data["donnees"] = json.dumps(data["donnees"])
    assert signal("26-102567", data).description == signal("26-102567").description


def test_api_origin_is_fixed():
    with pytest.raises(SourceUnavailable, match="documented public dataset"):
        collect(Api(), source={**SOURCE, "url": "https://example.com/notices"})


def test_sparse_correction_hydrates_original_before_emitting_either_revision():
    correction, original = row("26-103594"), row("26-101686")
    api = Api({"total_count": 1, "results": [correction]}, {"total_count": 1, "results": [original]})
    result = collect(api)
    assert result.complete and [raw.data["idweb"] for raw in result.records] == ["26-101686", "26-103594"]
    assert api.calls[1][1]["where"] == "idweb in ('26-101686')"
    first = normalise_boamp_caribbean(result.records[0])
    second = normalise_boamp_caribbean(result.records[1], first)
    assert first.description in second.description and "DCE a été modifié" in second.description
    assert "pending_corrections" not in result.state and result.state["watermark"] == NOW.isoformat()
    assert all(raw.data["date"] == raw.data["dateparution"] for raw in result.records)


def test_correction_staging_survives_budget_resume_without_an_incomplete_signal():
    first = collect(Api({"total_count": 1, "results": [row("26-103594")]}), budget=1)
    assert not first.complete and not first.records and "watermark" not in first.state
    assert first.state["scan_watermark"] == NOW.isoformat() and "26-103594" in first.state["pending_corrections"]
    api = Api({"total_count": 1, "results": [row("26-101686")]})
    second = collect(api, first.state, budget=1)
    assert second.complete and len(second.records) == 2 and len(api.calls) == 1
    assert api.calls[0][1]["where"] == "idweb in ('26-101686')"


def test_one_missing_parent_does_not_block_a_different_resolved_correction():
    api = Api({"total_count": 2, "results": [row("26-103594"), row("26-103698")]},
              {"total_count": 1, "results": [row("26-101686")]})
    result = collect(api)
    assert not result.complete and [raw.data["idweb"] for raw in result.records] == ["26-101686", "26-103594"]
    assert set(result.state["pending_corrections"]) == {"26-103698"}
    assert "watermark" not in result.state


def test_missing_parent_is_backed_off_while_fresh_index_and_records_continue():
    api = Api({"total_count": 1, "results": [row("26-103594")]}, {"total_count": 0, "results": []})
    first = collect(api)
    assert not first.complete and not first.records
    no_calls = Api()
    paused = collect(no_calls, first.state, frozen=NOW + timedelta(hours=1))
    assert not paused.complete and not no_calls.calls
    fresh = row("26-103580")
    resumed = collect(Api({"total_count": 1, "results": [fresh]}, {"total_count": 0, "results": []}),
                      paused.state, frozen=NOW + timedelta(hours=13))
    assert not resumed.complete and [raw.data["idweb"] for raw in resumed.records] == [fresh["idweb"]]
    assert resumed.state["scan_watermark"] == (NOW + timedelta(hours=13)).isoformat()
    assert "watermark" not in resumed.state


def test_multi_step_correction_chain_is_persisted_and_replayed_in_source_order():
    correction, middle, original = row("26-103594"), row("26-103594"), row("26-101686")
    middle.update(idweb="26-100111", id="26-100111", dateparution="2026-10-22")
    correction["annonce_lie"] = ["26-100111"]
    first = collect(Api({"total_count": 1, "results": [correction]}, {"total_count": 1, "results": [middle]}), budget=2)
    assert not first.complete and not first.records
    assert "26-100111" in first.state["pending_corrections"]["26-103594"]["parents"]
    second = collect(Api({"total_count": 1, "results": [original]}), first.state, budget=1)
    assert second.complete and [raw.data["idweb"] for raw in second.records] == ["26-101686", "26-100111", "26-103594"]


def test_correction_chain_cycle_is_not_emitted_or_requested_forever():
    correction = row("26-103594")
    correction["annonce_lie"] = [correction["idweb"]]
    api = Api({"total_count": 1, "results": [correction]})
    result = collect(api)
    assert not result.complete and not result.records and len(api.calls) == 1
    assert "cycle" in result.state["pending_corrections"][correction["idweb"]]["message"]


def test_parent_without_proved_caribbean_location_cannot_be_routed_by_its_correction():
    correction = row("26-103594")
    correction["annonce_lie"] = ["26-103716"]
    result = collect(Api({"total_count": 1, "results": [correction]}, {"total_count": 1, "results": [row("26-103716")]}))
    assert not result.complete and not result.records
    assert "26-103716" not in result.state["pending_corrections"][correction["idweb"]]["parents"]


def test_parent_endpoint_cannot_inject_an_unrequested_notice():
    result = collect(Api({"total_count": 1, "results": [row("26-103594")]},
                         {"total_count": 1, "results": [row("26-102178")]}))
    assert not result.complete and not result.records and "unexpected identifier" in result.message


def test_correction_chain_depth_limit_keeps_staged_scope_for_review(monkeypatch):
    monkeypatch.setattr("anthrion_signal.boamp_caribbean.MAX_PARENT_DEPTH", 0)
    result = collect(Api({"total_count": 1, "results": [row("26-103594")]},
                         {"total_count": 1, "results": [row("26-101686")]}))
    assert not result.complete and not result.records
    assert "safe depth" in result.state["pending_corrections"]["26-103594"]["message"]


def test_cancelled_sparse_correction_retires_notice_without_waiting_for_missing_parent():
    correction = row("26-103594")
    correction["etat"] = "ANNULATION"
    result = collect(Api({"total_count": 1, "results": [correction]}))
    assert result.complete and len(result.records) == 1
    assert normalise_boamp_caribbean(result.records[0]).status == "cancelled"


def test_cli_normalization_retains_hydrated_scope_and_does_not_rewind_on_replay(monkeypatch):
    from anthrion_signal import cli

    result = collect(Api({"total_count": 1, "results": [row("26-103594")]},
                         {"total_count": 1, "results": [row("26-101686")]}))
    source = {**SOURCE, "website": "https://www.boamp.fr", "enabled": True, "collector": "boamp_caribbean"}
    config = {"runtime": {}, "search_terms": {}, "capabilities": {}}
    monkeypatch.setattr(cli, "collect_with_backfill", lambda *args: result)
    monkeypatch.setattr(cli, "hydrate_sparse", lambda *args: None)
    _, records, _, health, count = cli._collect(source, {}, NOW, config)
    assert health.status == "healthy" and count == 2
    assert len(records) == 2 and records[0].description in records[1].description
    revised, _ = merge(records[0], records[1])
    # An additional amendment must inherit the current canonical scope, even
    # when this refresh also replays its older initial notice first.
    latest = row("26-103594")
    latest.update(idweb="26-104001", id="26-104001", date="2026-10-24", dateparution="2026-10-24")
    latest["annonce_lie"] = ["26-101686"]
    latest["donnees"]["FNSimple"]["rectificatif"]["infosRectif"] = "Nouvelle annexe technique ajoutée au dossier."
    result.records = [result.records[0], RawRecord(latest, SOURCE, (NOW + timedelta(days=1)).isoformat(), "boamp_caribbean")]
    _, replayed, _, health, count = cli._collect(source, {}, NOW + timedelta(days=1), config, [revised])
    assert health.status == "healthy" and count == 2 and revised.description in replayed[-1].description
    assert "Nouvelle annexe technique" in replayed[-1].description
