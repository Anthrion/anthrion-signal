from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from anthrion_signal.caribbean_worldbank import (
    API, collect_worldbank_caribbean, normalise_worldbank_caribbean, parse_page,
)
from anthrion_signal.collectors import Http, RawRecord, SourceUnavailable
from anthrion_signal.discovery import lifecycle

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
SOURCE = {"id": "worldbank_caribbean", "name": "World Bank Caribbean procurement notices",
          "source_type": "official_api", "project_countries": ["Jamaica"], "page_size": 5,
          "refresh_hours": 6, "lookback_days": 365}


def row(number=1, **changes):
    return {"id": f"OP{number:08}", "noticedate": "22-Oct-2026", "notice_status": "Published",
        "notice_type": "Invitation for Bids", "project_ctry_name": "Jamaica", "project_id": "P123456",
        "project_name": "Digital government", "bid_reference_no": "JM-DIGITAL-10",
        "bid_description": "Implement a citizen case management portal",
        "notice_text": "<p>Implement a citizen portal with case management and system integration.</p>",
        "notice_lang_name": "English", "contact_organization": "Digital Services Agency",
        "contact_ctry_name": "United States", "submission_deadline_date": "2026-11-10T00:00:00Z",
        "submission_deadline_time": "14:30", **changes}


def normalise(value):
    return normalise_worldbank_caribbean(RawRecord(value, SOURCE, NOW.isoformat(), "worldbank_caribbean"))


def collect(rows, state=None, *, budget=10, source=None, fail_country=None, malformed=None, refresh=False):
    calls = []
    def handler(request):
        assert str(request.url).split("?")[0] == API
        assert "Authorization" not in request.headers
        params = request.url.params
        assert params["srt"] == "noticedate desc,id asc"
        assert "strdate" not in params and "qterm" not in params
        country = params["project_ctry_name_exact"]
        offset, size = int(params["os"]), int(params["rows"])
        calls.append((country, offset, size))
        if country == fail_country:
            return httpx.Response(503)
        values = rows.get(country, []) if isinstance(rows, dict) else rows
        payload = {"rows": size, "os": str(offset), "total": str(len(values)),
                   "procnotices": values[offset:offset + size]}
        if malformed:
            malformed(payload)
        return httpx.Response(200, json=payload)
    client = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    try:
        result = collect_worldbank_caribbean({**SOURCE, **(source or {})}, state or {}, NOW, client,
            {"max_pages": budget, "refresh_daily": refresh}, {})
    finally:
        client.close()
    return result, calls


def test_country_is_project_jurisdiction_and_local_deadline_is_not_invented_utc():
    signal = normalise(row(contact_name="Published procurement contact", contact_email="public@example.gov"))
    assert signal.countries == ["JM"]
    assert signal.buyer_name == "Digital Services Agency"
    assert signal.deadline_at == "2026-11-10T14:30"
    assert signal.deadlines[0].precision == "local_time"
    assert signal.deadlines[0].instant is None and signal.deadlines[0].timezone is None
    assert signal.published_at == "2026-10-22"
    assert signal.value_max is None
    assert signal.primary_source_url.endswith("/procurement-detail/OP00000001")
    assert signal.contacts[0]["source_url"] == signal.primary_source_url
    assert lifecycle(signal, NOW)[0] == "OPEN"
    date_only = normalise(row(submission_deadline_time=""))
    assert date_only.deadline_at == "2026-11-10"
    assert date_only.deadlines[0].precision == "date"
    assert lifecycle(normalise(row(submission_deadline_date="2026-10-01T00:00:00Z")), NOW)[0] == "EXPIRED"


@pytest.mark.parametrize(("country", "code"), [
    ("Caribbean", "CARIBBEANREGIONAL"), ("OECS Countries", "CARIBBEANREGIONAL"), ("Haiti", "HT"),
])
def test_regional_notices_do_not_get_bank_or_contact_hq_country(country, code):
    signal = normalise(row(project_ctry_name=country, contact_organization="", contact_ctry_name="Barbados"))
    assert signal.countries == [code] and signal.buyer_name is None
    assert signal.regions == ([country] if code == "CARIBBEANREGIONAL" else [])


@pytest.mark.parametrize(("language", "code", "title", "description"), [
    ("French", "fr", "Mise en œuvre du portail citoyen", "Gestion des dossiers et intégration des données. "),
    ("Spanish; Castilian", "es", "Implementación del portal ciudadano", "Gestión de casos e integración de sistemas. "),
    ("English", "en", "Citizen services", "Integrate workflow systems and citizen requests. "),
])
def test_original_multilingual_full_text_and_stable_identifiers(language, code, title, description):
    signal = normalise(row(bid_description=title, notice_lang_name=language, notice_text=description * 1200))
    assert signal.source_language == code and signal.title == title
    assert signal.description == (description * 1200).strip()
    revised = normalise(row(bid_description=title + " revised", notice_lang_name=language))
    assert signal.id == revised.id and signal.procedure_id == revised.procedure_id
    another = normalise(row(2, bid_reference_no="JM-DIGITAL-11"))
    assert signal.procedure_id != another.procedure_id


@pytest.mark.parametrize(("changes", "expected"), [
    ({"notice_type": "Contract Award"}, "AWARDED"),
    ({"notice_status": "Cancelled"}, "CANCELLED"),
    ({"notice_status": "Withdrawn"}, "WITHDRAWN"),
    ({"notice_type": "General Procurement Notice", "submission_deadline_date": "", "submission_deadline_time": ""}, "FUTURE"),
])
def test_explicit_lifecycle_survives_normalization(changes, expected):
    signal = normalise(row(**changes))
    assert lifecycle(signal, NOW)[0] == expected
    if expected == "AWARDED":
        assert not signal.deadlines and signal.deadline_at is None


def test_general_procurement_notice_uses_the_published_project_name_when_bid_title_is_absent():
    value = row(notice_type="General Procurement Notice", project_name="Belize Reliant and Resilient Energy System Project",
                submission_deadline_date="", submission_deadline_time="")
    value.pop("bid_description")
    result, _ = collect([value])
    assert result.complete and len(result.records) == 1
    signal = normalise(value)
    assert signal.title == value["project_name"] and signal.procurement_stage == "planning"
    assert signal.description.startswith("Implement a citizen portal")
    invalid = {**value, "notice_type": "Invitation for Bids"}
    with pytest.raises(SourceUnavailable, match="malformed notice"):
        normalise(invalid)


def test_revised_notice_does_not_invent_a_current_response_route():
    signal = normalise(row(notice_status="Revised", submission_deadline_date="", submission_deadline_time=""))
    assert signal.status == "unknown" and lifecycle(signal, NOW)[0] == "UNKNOWN"
    with_deadline = normalise(row(notice_status="Revised"))
    assert lifecycle(with_deadline, NOW)[0] == "OPEN"


def test_all_source_notice_text_is_collected_without_keyword_filter_and_unchanged_rows_reuse_hashes():
    values = [row(1, bid_description="Projet de transformation", notice_lang_name="French"),
              row(2, bid_description="Replace water pipes")]
    first, _ = collect(values)
    assert first.complete and len(first.records) == 2
    cached, calls = collect(values, first.state)
    assert not cached.records and not calls and cached.complete
    refreshed, _ = collect(values, first.state, refresh=True)
    assert refreshed.complete and not refreshed.records
    changed = [{**values[0], "notice_status": "Cancelled"}, values[1]]
    revised, _ = collect(changed, refreshed.state, refresh=True)
    assert len(revised.records) == 1 and revised.records[0].data["notice_status"] == "Cancelled"


def test_offset_resumption_overlaps_anchor_and_converges_after_front_insert():
    values = [row(number) for number in range(10, 22)]
    first, calls = collect(values, budget=1)
    original = deepcopy(first.state)
    assert not first.complete and calls == [("Jamaica", 0, 5)]
    assert first.state["countries"]["Jamaica"]["offset"] == 4
    # A new earlier-sorting notice shifts the old anchor within the overlap.
    changed = [row(9), *values]
    second, calls = collect(changed, first.state, budget=8)
    assert first.state == original
    assert second.complete and calls[0][1] == 4
    assert {r.data["id"] for r in first.records + second.records} >= {r["id"] for r in values}
    # The newly inserted head is picked up by the next complete overlapping scan.
    third, _ = collect(changed, second.state, refresh=True)
    assert [r.data["id"] for r in third.records] == ["OP00000009"]


def test_large_feed_shift_restarts_safely_and_missing_rows_are_not_deleted():
    values = [row(number) for number in range(20, 32)]
    first, _ = collect(values, budget=1)
    shifted = [row(number) for number in range(1, 12)] + values
    replay, calls = collect(shifted, first.state, budget=12)
    assert calls[0][1] == 4 and calls[1][1] == 0
    assert not replay.state["countries"]["Jamaica"].get("pending")
    assert {r.data["id"] for r in first.records + replay.records} == {r["id"] for r in shifted}
    smaller, _ = collect([row(21)], replay.state, refresh=True)
    assert smaller.complete
    assert all(r.data["notice_status"] != "Cancelled" for r in smaller.records)


def test_short_page_before_reported_tail_never_completes_the_inventory():
    values = [row(number) for number in range(1, 21)]
    result, _ = collect(values, budget=1, malformed=lambda p: p.update(procnotices=p["procnotices"][:1]))
    assert not result.complete and not result.records
    assert result.state["countries"] == {}


def test_resume_beyond_shrunken_feed_tail_restarts_without_inventing_closure():
    first, _ = collect([row(number) for number in range(1, 13)], budget=1)
    assert first.state["countries"]["Jamaica"]["offset"] == 4
    result, calls = collect([row(1), row(2)], first.state, budget=3)
    assert [offset for _, offset, _ in calls] == [4, 0]
    assert not result.state["countries"]["Jamaica"].get("pending")
    assert "checked_at" in result.state["countries"]["Jamaica"]
    assert not result.records and not result.rejected_records


def test_country_rotation_and_failed_page_preserve_independent_progress():
    countries = ["Jamaica", "Haiti"]
    values = {"Jamaica": [row(i) for i in range(1, 10)], "Haiti": [row(20, project_ctry_name="Haiti")]}
    first, _ = collect(values, budget=1, source={"project_countries": countries})
    second, calls = collect(values, first.state, budget=1, source={"project_countries": countries})
    assert calls[0][0] == "Haiti"
    assert len(second.records) == 1 and not second.complete
    old = deepcopy(second.state)
    failure, _ = collect(values, second.state, budget=1, fail_country="Jamaica",
                         source={"project_countries": countries})
    assert not failure.complete and failure.state["countries"] == old["countries"]
    assert second.state == old


def test_scan_stops_at_verified_date_boundary_and_does_not_emit_old_notices():
    first, calls = collect([row(), row(2, noticedate="01-Jan-2020")], budget=5)
    assert first.complete and len(calls) == 1
    assert [r.data["id"] for r in first.records] == ["OP00000001"]
    empty, _ = collect([])
    assert empty.complete and not empty.records


@pytest.mark.parametrize("alter", [
    lambda p: p.update(total="not a number"),
    lambda p: p.update(os="10"),
    lambda p: p.update(procnotices=[]),
    lambda p: p["procnotices"][0].update(project_ctry_name="India"),
    lambda p: p["procnotices"][0].update(noticedate="not a date"),
    lambda p: p["procnotices"][0].update(notice_type="Unknown open call"),
    lambda p: p["procnotices"][0].update(notice_status="Unknown"),
    lambda p: p["procnotices"][0].update(submission_deadline_time="25:15"),
])
def test_malformed_pages_do_not_advance_or_promote_unverified_opportunities(alter):
    result, _ = collect([row()], malformed=alter, budget=1)
    assert not result.complete and not result.records and result.state["countries"] == {}


def test_unsorted_page_and_cross_country_normalization_are_rejected():
    with pytest.raises(SourceUnavailable, match="ordering"):
        parse_page({"os": "0", "total": "2", "procnotices": [row(2), row(1)]}, "Jamaica", 0, 5)
    with pytest.raises(SourceUnavailable, match="project country"):
        normalise(row(project_ctry_name="India"))


def test_forced_refresh_budget_and_clock_precision_are_not_hidden():
    countries = ["Jamaica", "Haiti"]
    values = {"Jamaica": [row()], "Haiti": [row(20, project_ctry_name="Haiti")]}
    first, _ = collect(values, source={"project_countries": countries})
    partial, _ = collect(values, first.state, budget=1, refresh=True, source={"project_countries": countries})
    assert not partial.complete
