from datetime import UTC, datetime, timedelta

import pytest

from anthrion_signal.caribbean_portals import (
    VERSION,
    _response_deadline,
    collect_caribbean_portal,
    normalise_caribbean_portal,
    parse_portal_detail,
    parse_portal_listing,
)
from anthrion_signal.collectors import RawRecord, SourceUnavailable


NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
MS_URL = "https://tenders.gov.ms/listings/digital-services"
LC_URL = "https://www.finance.gov.lc/tenders/view/867"
SOURCE = {"id": "ms_tenders", "name": "Montserrat tenders", "source_type": "official_portal",
          "url": "https://tenders.gov.ms", "portal": "montserrat"}


def ms_listing(links=("/listings/digital-services",), next_page=None):
    cards = "".join(f'<div class="list-group-item"><h3><a href="{link}">Digital services</a></h3>'
                    '<span>Published: Oct 22, 2026</span><span>Active</span></div>' for link in links)
    paging = f'<a href="{next_page}">Next &rsaquo;</a>' if next_page else ""
    return '<turbo-frame id="listings">' + cards + paging + '</turbo-frame>'


def ms_detail(status="Active", title="Digital services", deadline="Oct 27, 2026 - 12:00 PM"):
    return f'''<div id="listing_d5def178-892a-492e-b968-645372101fae">
      <h4>Title</h4><p>{title}</p><h4>Description</h4>
      <div class="trix-content">Implement a case management service with a citizen portal and API integration.</div>
      <h4>Procuring Entity</h4><p>Office of the Premier</p>
      <h4>Publish Date</h4><p>Oct 22, 2026</p><h4>Deadline Date</h4><p>{deadline}</p>
      <h4>Status</h4><p>{status}</p><h4>Category</h4><p>Consultancy</p>
      <a href="/rails/active_storage/blobs/redirect/public-document/Specification.pdf">Download</a>
      </div><div id="addendum_1"><p>Correction</p>
      <a href="/rails/active_storage/blobs/redirect/public-addendum/Addendum%201.pdf">Download</a></div>'''


def lc_detail(category="Request for Expressions of Interest", description=None):
    description = description or ('Design a case management system and integrate its public portal. '
        'Expressions of interest must be received by Wednesday November 11, 2026 at 09:30 AST (UTC−04:00).')
    return f'''<div id="main-container"><div class="content"><h2>Digital services</h2>
      <div><b>Category: </b>{category}<br><b>Public Reference: </b>LC-DIGITAL-123<br>
      <b>Implementing Agency: </b>Ministry of Finance<br></div>
      <div><b>Status:</b><span>Open - 2030-02-28</span></div><b>Description:</b><br>
      <p>{description}</p><h5>Tender Dossier / Supporting Documents</h5>
      <a href="/tenders/download/3141/Notice.pdf">Notice.pdf</a><h5>Ask a Question</h5>
      <p>This is a contact form, not procurement scope.</p></div></div>'''


class Pages:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def html(self, url):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return value


def collect(pages, state=None, budget=40, frozen=NOW, source=SOURCE):
    return collect_caribbean_portal(source, state or {}, frozen, pages,
                                   {"max_pages": budget, "lookback_days": 30}, {})


def test_montserrat_full_scope_identity_dates_and_addenda():
    hit = parse_portal_listing(ms_listing(), SOURCE["url"], "montserrat")[0][0]
    record = parse_portal_detail(ms_detail(), hit, "montserrat")
    assert record["description"].startswith("Implement a case management")
    assert record["id"] == "ms:d5def178-892a-492e-b968-645372101fae"
    assert record["published_at"] == "2026-10-22"
    assert record["deadline_at"] == "2026-10-27T12:00:00-04:00"
    assert record["buyer"] == "Office of the Premier"
    assert len(record["documents"]) == 2
    assert record["documents"][1]["title"] == "Addendum 1.pdf"
    signal = normalise_caribbean_portal(RawRecord(record, SOURCE, NOW.isoformat(), "caribbean_portal"))
    assert signal.source_language == "en" and signal.countries == ["MS"]
    assert signal.currency is None and signal.value_max is None
    assert signal.updated_at is None  # A collection time is not a source update date.
    assert signal.published_at == "2026-10-22"
    record["title"] = "Corrected digital services"
    record["url"] = "https://tenders.gov.ms/listings/corrected-title"
    changed = normalise_caribbean_portal(RawRecord(record, SOURCE, NOW.isoformat(), "caribbean_portal"))
    assert changed.id == signal.id


def test_lucia_does_not_confuse_catalogue_expiry_with_response_deadline():
    hit = {"url": LC_URL, "published_at": "2026-10-22"}
    record = parse_portal_detail(lc_detail(), hit, "saint_lucia")
    assert record["deadline_at"] == "2026-11-11T09:30:00-04:00"
    assert record["published_at"] == "2026-10-22"
    assert record["reference"] == "LC-DIGITAL-123"
    assert "contact form" not in record["description"]
    assert record["status"] == "active"
    award = parse_portal_detail(lc_detail("Award of Contracts"), hit, "saint_lucia")
    assert award["status"] == "awarded" and award["deadline_at"] is None
    source = {**SOURCE, "portal": "saint_lucia", "id": "lc_finance"}
    signal = normalise_caribbean_portal(RawRecord(award, source, NOW.isoformat(), "caribbean_portal"))
    assert signal.signal_type == "AWARD" and signal.countries == ["LC"]
    assert signal.procedure_identifiers == ["LC-DIGITAL-123"]


@pytest.mark.parametrize("description", [
    "Contract award is expected on November 12, 2026.",
    "Office hours are 09:30 AST. A project starts on November 12, 2026.",
    "Expressions of interest must be received by November 31, 2026.",
    "Expressions of interest must be received by November 11, 2026. "
    "Proposals must be submitted by November 15, 2026.",
    "Bids must be submitted by November 11, 2026 at 09:30. "
    "Proposals must be submitted by November 11, 2026 at 15:30.",
])
def test_no_invented_or_ambiguous_response_date(description):
    assert _response_deadline(description, "America/St_Lucia") is None
    record = parse_portal_detail(lc_detail(description=description), {"url": LC_URL}, "saint_lucia")
    assert record["deadline_at"] is None and record["status"] == "unknown"


def test_date_only_stays_date_only():
    record = parse_portal_detail(ms_detail(deadline="Oct 27, 2026"), {"url": MS_URL}, "montserrat")
    assert record["deadline_at"] == "2026-10-27"
    assert _response_deadline("Bids must be submitted by 27 October 2026.", "America/St_Lucia") == "2026-10-27"


@pytest.mark.parametrize(("clock", "expected"), [
    ("09:30 GMT", "2026-11-11T09:30:00+00:00"),
    ("09:30 UTC", "2026-11-11T09:30:00+00:00"),
    ("09:30 AST (UTC−04:00)", "2026-11-11T09:30:00-04:00"),
    ("09:30 UTC+01:30", "2026-11-11T09:30:00+01:30"),
    ("3:30 p.m. AST", "2026-11-11T15:30:00-04:00"),
    ("09:30 UTC+25:00", None),
    ("09:30 EST", "2026-11-11T09:30:00"),
    ("09:30 AST (UTC+01:00)", None),
])
def test_explicit_deadline_timezone_takes_precedence_over_portal_timezone(clock, expected):
    assert _response_deadline(f"Bids must be submitted by November 11, 2026 at {clock}.", "America/St_Lucia") == expected


def test_listing_pagination_and_lucia_column_mapping():
    html = '''<table><tr><th>Title</th><th>Category</th><th>Published</th></tr><tr>
      <td><a href="/tenders/view/867">Digital services</a></td><td>Request for Expressions of Interest</td>
      <td>Open</td><td>Open - 12/11/2026</td><td>Ministry</td><td>22/10/2026</td></tr></table>
      <a href="/tenders/index/page:2">Next</a>'''
    hits, next_page = parse_portal_listing(html, "https://www.finance.gov.lc/tenders/index", "saint_lucia")
    assert next_page == "https://www.finance.gov.lc/tenders/index/page:2"
    assert hits[0]["published_at"] == "2026-10-22" and "deadline_at" not in hits[0]
    hits, next_page = parse_portal_listing(ms_listing(next_page="/?page=2"), SOURCE["url"], "montserrat")
    assert next_page == "https://tenders.gov.ms?page=2"


@pytest.mark.parametrize("html", ["<html>Sign in</html>", '<turbo-frame id="listings"></turbo-frame>',
    ms_listing(links=("https://evil.example/listings/phishing",)),
    ms_listing(next_page="https://evil.example/?page=2")])
def test_malformed_or_off_host_pages_fail_closed(html):
    with pytest.raises(SourceUnavailable):
        parse_portal_listing(html, SOURCE["url"], "montserrat")


def test_listing_and_details_resume_without_duplicate_fetches():
    pages = Pages({SOURCE["url"]: ms_listing(("/listings/a", "/listings/b")),
                   "https://tenders.gov.ms/listings/a": ms_detail(),
                   "https://tenders.gov.ms/listings/b": ms_detail(title="Second service")})
    first = collect(pages, budget=2)
    assert not first.complete and len(first.records) == 1 and "watermark" not in first.state
    assert len(first.state["pending"]["queue"]) == 1
    second = collect(pages, first.state, budget=1)
    assert second.complete and len(second.records) == 1
    assert pages.calls.count(SOURCE["url"]) == 1
    assert "pending" not in second.state
    assert collect(Pages({}), second.state).records == []


def test_new_pagination_continues_next_run():
    page2 = "https://tenders.gov.ms?page=2"
    pages = Pages({SOURCE["url"]: ms_listing(("/listings/a",), "/?page=2"),
                   page2: ms_listing(("/listings/b",)),
                   "https://tenders.gov.ms/listings/a": ms_detail(),
                   "https://tenders.gov.ms/listings/b": ms_detail()})
    first = collect(pages, budget=1)
    assert not first.complete and first.records == []
    second = collect(pages, first.state, budget=3)
    assert second.complete and len(second.records) == 2
    assert pages.calls.count(SOURCE["url"]) == 1


def test_initial_lucia_details_prioritise_new_publications_over_lexical_id_order():
    listing = '''<table><tr><th>Title</th><th>Category</th><th>Published</th></tr>
      <tr><td><a href="/tenders/view/1">Older service</a></td><td>Request for Expressions of Interest</td>
      <td>Open</td><td>Open - 12/11/2026</td><td>Ministry</td><td>01/09/2026</td></tr>
      <tr><td><a href="/tenders/view/900">New service</a></td><td>Request for Expressions of Interest</td>
      <td>Open</td><td>Open - 12/11/2026</td><td>Ministry</td><td>22/10/2026</td></tr></table>'''
    source = {**SOURCE, "id": "lc_finance", "portal": "saint_lucia", "url": "https://www.finance.gov.lc/tenders/index"}
    pages = Pages({source["url"]: listing, "https://www.finance.gov.lc/tenders/view/900": lc_detail()})
    result = collect(pages, budget=2, source=source)
    assert not result.complete and len(result.records) == 1
    assert result.records[0].data["id"] == "lc:900"
    assert result.state["pending"]["queue"][0]["url"].endswith("/1")


def test_unavailable_detail_does_not_starve_other_notices_or_forge_closure():
    pages = Pages({SOURCE["url"]: ms_listing(("/listings/a", "/listings/b")),
                   "https://tenders.gov.ms/listings/a": SourceUnavailable("Missing", status_code=404),
                   "https://tenders.gov.ms/listings/b": ms_detail()})
    result = collect(pages)
    assert not result.complete and len(result.records) == 1
    assert result.state["pending"]["queue"][0]["url"].endswith("/a")
    assert "watermark" not in result.state
    assert result.records[0].data["status"] == "active"


def test_permanently_missing_detail_does_not_block_newly_published_notices():
    missing = SourceUnavailable("Missing", status_code=404)
    pages = Pages({SOURCE["url"]: ms_listing(("/listings/a", "/listings/b")),
                   "https://tenders.gov.ms/listings/a": missing,
                   "https://tenders.gov.ms/listings/b": ms_detail()})
    first = collect(pages)
    assert not first.complete and first.state["pending"]["refresh_listing"]
    pages = Pages({SOURCE["url"]: ms_listing(("/listings/a", "/listings/b", "/listings/c")),
                   "https://tenders.gov.ms/listings/a": missing,
                   "https://tenders.gov.ms/listings/c": ms_detail(title="New citizen portal")})
    second = collect(pages, first.state, frozen=NOW + timedelta(hours=1))
    assert not second.complete and pages.calls[0] == SOURCE["url"]
    assert [record.data["title"] for record in second.records] == ["New citizen portal"]
    assert "https://tenders.gov.ms/listings/b" in second.state["detail_cache"]
    assert not second.rejected_records


def test_removed_record_requires_its_actual_detail_status():
    old = {"query_version": VERSION, "detail_cache": {
        MS_URL: {"fetched_at": (NOW - timedelta(days=2)).isoformat(), "status": "active"}}}
    pages = Pages({SOURCE["url"]: '<turbo-frame id="listings">No tenders found</turbo-frame>',
                   MS_URL: ms_detail(status="Under Evaluation")})
    result = collect(pages, old)
    assert result.complete and result.records[0].data["status"] == "closed"
    failing = collect(Pages({SOURCE["url"]: "<html>Failure</html>"}), old)
    assert not failing.complete and not failing.records
    assert old["detail_cache"][MS_URL]["status"] == "active"


def test_denied_detail_stops_host_requests_and_preserves_pending_work():
    pages = Pages({SOURCE["url"]: ms_listing(("/listings/a", "/listings/b")),
                   "https://tenders.gov.ms/listings/a": SourceUnavailable("Denied", status_code=403)})
    result = collect(pages)
    assert not result.complete and len(pages.calls) == 2
    assert len(result.state["pending"]["queue"]) == 2
    assert "retry_at" in result.state and not result.records


def test_untrusted_state_url_cannot_change_the_origin():
    state = {"query_version": VERSION, "pending": {"next": None, "seen": [], "hits": {},
        "queue": [{"url": "https://evil.example/listings/secret"}]}}
    pages = Pages({})
    result = collect(pages, state)
    assert not result.complete and not pages.calls
