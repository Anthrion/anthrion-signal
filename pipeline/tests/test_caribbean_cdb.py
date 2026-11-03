from copy import deepcopy
from datetime import UTC, datetime
from html import escape

import httpx
import pytest

from anthrion_signal.caribbean_cdb import (
    CURRENT, GENERAL, collect_cdb, normalise_cdb, parse_detail, parse_listing,
)
from anthrion_signal.collectors import Http, RawRecord, SourceUnavailable
from anthrion_signal.discovery import lifecycle

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
SOURCE = {"id": "caribbean_cdb", "name": "Caribbean Development Bank",
          "source_type": "official_public", "include_general": False, "refresh_hours": 6}


def entry(number=1, country="Saint Lucia", kind="current"):
    return {"url": CURRENT + f"/notice-{number}", "listing_title": "Citizen services project",
            "country": country, "sector": "Institutions", "listed_as": kind}


def listing(entries, following=None):
    rows = "".join(f'''<tr><td class="views-field-title"><a href="{e['url']}">{e['listing_title']}</a></td>
        <td class="views-field-field-cdb-country-tag">{e['country']}</td>
        <td class="views-field-field-sector-tag">{e['sector']}</td></tr>''' for e in entries)
    pager = f'<li class="pager__item--next"><a href="{following}">Next page</a></li>' if following else ""
    return f'''<html><main><table><thead><tr><th class="views-field-field-cdb-country-tag">Country</th></tr>
        </thead><tbody>{rows}</tbody></table><nav class="pager">{pager}</nav></main></html>'''


def detail(number=1, *, country="Saint Lucia", heading="REQUEST FOR EXPRESSIONS OF INTEREST",
           project="Digital services project", title="Implement case management and citizen services",
           date="Nov 11, 2026", clock="04:30 PM", extra="", overview="Implement citizen workflows."):
    facts = {"Project Name": project, "Role/Service": title, "Country": country, "Type": "Consultancy"}
    if date:
        facts["Deadline"] = f'<time datetime="2026-11-11T12:00:00Z">{date}</time>'
    fields = "".join(f'<div class="field-display--above"><div class="field--label">{k}</div><div>{v}</div></div>'
                     for k, v in facts.items())
    return f'''<html><article class="node--type-cdb-procurement-notices" data-history-node-id="{number}">
        <div class="quick-facts--wrap">{fields}<div class="field--node--field-cdb-time">{clock}</div>
        <a href="/countries-and-members/saint-lucia">Country</a>
        <a download href="/sites/default/files/terms.pdf">Terms of reference</a></div>
        <h4>Overview</h4><div class="field--node--body"><p><strong>{heading}</strong></p><p>{overview}</p></div>
        <div class="paragraph-list"><h3>Eligibility</h3><p>Consultants may form a consortium.</p>
        <h3>Instructions</h3><p>The future contract award notice will identify the successful bidder.</p>
        <p>Submit responses by the stated deadline. The authority may cancel the process before award.</p>
        <a href="https://government.example/clarification.pdf">Clarification</a>{extra}</div>
        </article></html>'''


def collect(pages, state=None, *, budget=10, general=False, refresh=False, robots="User-agent: *\nAllow: /"):
    calls = []
    def handler(request):
        assert "Authorization" not in request.headers
        url = str(request.url)
        calls.append(url)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        page = pages.get(url)
        if isinstance(page, int):
            return httpx.Response(page)
        assert page is not None, url
        return httpx.Response(200, text=page)
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    try:
        result = collect_cdb({**SOURCE, "include_general": general}, state or {}, NOW, http,
                             {"max_pages": budget, "refresh_daily": refresh}, {})
    finally:
        http.close()
    return result, calls


def signal(html=None, record=None):
    value = parse_detail(html or detail(), record or entry())
    return normalise_cdb(RawRecord(value, SOURCE, NOW.isoformat(), "caribbean_cdb"))


def test_visible_deadline_overrides_false_noon_utc_and_full_sections_survive():
    notice = signal()
    assert notice.deadline_at == "2026-11-11T16:30"
    assert notice.deadlines[0].precision == "local_time" and notice.deadlines[0].instant is None
    assert notice.deadlines[0].source_text == "Nov 11, 2026 04:30 PM"
    assert "Consultants may form a consortium." in notice.description
    assert "The authority may cancel the process" in notice.description
    assert notice.signal_type == "LIVE_TENDER" and lifecycle(notice, NOW)[0] == "OPEN"
    assert notice.published_at is None and notice.value_max is None
    assert {d.title for d in notice.documents} == {"Terms of reference", "Clarification"}
    assert notice.countries == ["LC"] and notice.buyer_name is None


def test_publication_and_rfi_are_explicit_not_inferred_from_collection():
    html = detail(country="CDB", project="CDB - Request for Information/Market Sounding Notice",
        date="Jul 31, 2026", extra='<table><tr><td>Issue Date</td><td>26 June 2026</td></tr></table>')
    notice = signal(html, entry(country="CDB"))
    assert notice.published_at == "2026-06-26" and notice.signal_type == "RFI"
    assert notice.countries == ["CARIBBEANREGIONAL"] and notice.regions == ["CDB"]
    assert notice.buyer_name == "Caribbean Development Bank"
    assert lifecycle(notice, NOW)[0] == "EXPIRED"
    regional = signal(detail(country="Regional"), entry(country="Regional"))
    assert regional.buyer_name is None and regional.countries == ["CARIBBEANREGIONAL"]


@pytest.mark.parametrize(("heading", "expected"), [
    ("Notice of cancellation", "CANCELLED"), ("WITHDRAWN", "WITHDRAWN"),
    ("Contract award notice", "AWARDED"),
])
def test_explicit_terminal_heading_wins_over_active_listing(heading, expected):
    notice = signal(detail(heading=heading))
    assert lifecycle(notice, NOW)[0] == expected
    if expected == "AWARDED":
        assert not notice.deadlines


def test_general_notices_remain_future_without_made_up_deadline_or_amount():
    notice = signal(detail(date="", clock="", overview="Project financing of USD8,700,000 supports multiple contracts."),
                    entry(kind="general"))
    assert notice.signal_type == "PIPELINE" and lifecycle(notice, NOW)[0] == "FUTURE"
    assert not notice.deadlines and notice.value_max is None
    date_only = signal(detail(clock=""))
    assert date_only.deadline_at == "2026-11-11" and date_only.deadlines[0].precision == "date"


def test_complete_original_scope_and_source_id_survive_title_and_url_changes():
    full = "Mettre en œuvre la gestion des dossiers et un portail citoyen. " * 700
    notice = signal(detail(overview=escape(full)))
    assert full.strip() in notice.description and len(notice.description) > 24000
    # Source language stays undetermined, rather than forcing an English page shell onto French scope.
    assert notice.source_language == "und"
    revised = signal(detail(title="Revised services"), {**entry(), "url": CURRENT + "/new-slug"})
    assert notice.id == revised.id


def test_pending_details_and_next_page_resume_without_repeating_completed_requests():
    pages = {CURRENT: listing([entry()], "?page=1"), entry()["url"]: detail(),
             CURRENT + "?page=1": listing([entry(2)]), entry(2)["url"]: detail(2)}
    first, _ = collect(pages, budget=1)
    saved = deepcopy(first.state)
    assert not first.complete and first.state["feeds"]["current"]["pending"] == [entry()]
    second, calls = collect(pages, first.state, budget=3)
    assert second.complete and len(second.records) == 2 and CURRENT not in calls
    assert first.state == saved
    cached, calls = collect(pages, second.state)
    assert cached.complete and not cached.records and not calls
    refresh, _ = collect(pages, second.state, refresh=True)
    assert refresh.complete and not refresh.records
    revised_pages = {**pages, entry()["url"]: detail(heading="Notice of cancellation")}
    amended, _ = collect(revised_pages, second.state, refresh=True)
    assert len(amended.records) == 1 and amended.records[0].data["status"] == "cancelled"


def test_failed_detail_is_deferred_without_blocking_same_feed_or_other_feed():
    pages = {CURRENT: listing([entry(), entry(3)]), GENERAL: listing([entry(2, kind="general")]),
             entry()["url"]: 404, entry(3)["url"]: detail(3), entry(2)["url"]: detail(2, date="", clock="")}
    result, _ = collect(pages, general=True)
    assert not result.complete and len(result.records) == 2
    assert {row.data["signal_type"] for row in result.records} == {"PIPELINE", "LIVE_TENDER"}
    assert not result.state["feeds"]["current"].get("pending")
    assert result.state["failed_details"][entry()["url"]]["entry"] == entry()
    assert entry()["url"] not in result.state["details"]
    fresh_pages = {**pages, CURRENT: listing([entry(), entry(3), entry(4)]), entry(4)["url"]: detail(4)}
    fresh, calls = collect(fresh_pages, result.state, general=True, refresh=True)
    assert entry()["url"] not in calls and [r.data["id"] for r in fresh.records] == ["4"]
    assert not fresh.complete  # The individual failed link remains visible as partial coverage.


def test_missing_listing_item_is_not_manufactured_as_cancellation():
    first, _ = collect({CURRENT: listing([entry()]), entry()["url"]: detail()})
    empty = '<main><div class="view-empty">No results found.</div></main>'
    later, _ = collect({CURRENT: empty, entry()["url"]: detail()}, first.state, refresh=True)
    assert later.complete and not later.records
    assert later.state["details"] == first.state["details"]
    cancelled, calls = collect({CURRENT: empty, entry()["url"]: detail(heading="Notice of cancellation")},
                               first.state, refresh=True)
    assert entry()["url"] in calls and len(cancelled.records) == 1
    assert cancelled.records[0].data["status"] == "cancelled"


@pytest.mark.parametrize("html", [
    "<html><main>Sign in</main></html>",
    listing([{**entry(), "country": "Germany"}]),
    listing([{**entry(), "url": "https://example.org/notice"}]),
    listing([entry()], "https://example.org/?page=1"),
    listing([entry()], "?page=0"),
])
def test_unrecognized_or_unsafe_listing_is_partial_and_does_not_queue_it(html):
    result, _ = collect({CURRENT: html}, budget=1)
    assert not result.complete and not result.records and not result.state["feeds"]


def test_disallowed_public_crawling_is_not_bypassed():
    result, calls = collect({}, robots="User-agent: *\nDisallow: /work-with-us/")
    assert not result.complete and not result.records
    assert calls == ["https://www.caribank.org/robots.txt"]


@pytest.mark.parametrize("html", [
    detail(country="Jamaica"), detail(date="Soon"), detail(clock="24:90 PM"),
    detail(date="", clock="04:30 PM"), "<main>Not found</main>",
])
def test_bad_detail_country_dates_and_shape_are_retained_for_retry_without_caching_success(html):
    first, _ = collect({CURRENT: listing([entry()])}, budget=1)
    prior = deepcopy(first.state)
    failed, _ = collect({entry()["url"]: html}, first.state, budget=1)
    assert not failed.complete and not failed.records
    assert failed.state["failed_details"][entry()["url"]]["entry"] == entry()
    assert not failed.state["details"] and first.state == prior


def test_unknown_detail_country_and_missing_id_are_not_normalized():
    with pytest.raises(SourceUnavailable, match="project country"):
        parse_detail(detail(country="Unknown"), entry())
    with pytest.raises(SourceUnavailable, match="identified"):
        parse_detail(detail().replace('data-history-node-id="1"', ''), entry())
    rows, following = parse_listing(listing([entry()], "?page=1"), CURRENT, "current")
    assert rows == [entry()] and following == CURRENT + "?page=1"
