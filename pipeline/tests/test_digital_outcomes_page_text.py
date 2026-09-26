from datetime import timedelta

import httpx
from bs4 import BeautifulSoup

from anthrion_signal.collectors import Http, collect_digital, notice_text, without_page_furniture
from anthrion_signal.utils import clean

# The Contract Award Service's page structure, reduced to one notice.
DETAIL = """<main class="govuk-width-container" id="main-content">
<div class="govuk-width-container"><div class="govuk-phase-banner">
<p class="govuk-phase-banner__content"><strong class="govuk-tag">Beta</strong>
<span class="govuk-phase-banner__text">This is a new service – your feedback will help us to improve it.</span></p>
</div></div>
<div class="govuk-width-container">
<div class="govuk-breadcrumbs"><ol class="govuk-breadcrumbs__list">
<li class="govuk-breadcrumbs__list-item"><a class="govuk-breadcrumbs__link" href="/">Home</a></li>
<li class="govuk-breadcrumbs__list-item"><a class="govuk-breadcrumbs__link" href="/digital-outcomes/opportunities">Digital Outcomes opportunities</a></li>
<li class="govuk-breadcrumbs__list-item">Procurement details</li></ol></div>
<p class="govuk-body">Example Council</p>
<h1 class="govuk-heading-l">CRM platform replacement</h1>
<div class="callout-panel">24 October 2026 Application closing date</div>
<div class="govuk-inset-text"><strong>Search criteria used:</strong><br>
12 results found in Lot 2: Digital capability and delivery partner and where the supplier provides Salesforce</div>
<dl class="govuk-summary-list"><dt>1. Project name</dt><dd>CRM platform replacement</dd>
<dt>2. Summary of work</dt><dd>Replace the council's case management CRM.</dd></dl>
<div class="govuk-width-container"><div class="govuk-grid-row"><div class="govuk-grid-column-full">
<div class="ccs-help-panel"><h2 class="govuk-heading-m">Help</h2>
<p class="govuk-body">You can contact us by email, phone or using the
<a class="govuk-link" href="https://www.gca.gov.uk/contact">enquiry form (opens in a new tab)</a> .</p>
<h2 class="govuk-heading-m">Email:</h2><p><a href="mailto:info@gca.gov.uk">info@gca.gov.uk</a></p>
<h2 class="govuk-heading-m">Telephone:</h2><p>0345 410 2222</p>
<p>GCA customer services team is available Monday to Friday, 9am to 5pm.</p>
</div></div></div></div>
</div></main>"""
NOTICE = (
    "Example Council CRM platform replacement 24 October 2026 Application closing date "
    "Search criteria used: 12 results found in Lot 2: Digital capability and delivery partner "
    "and where the supplier provides Salesforce 1. Project name CRM platform replacement "
    "2. Summary of work Replace the council's case management CRM."
)
CACHED = (
    "Beta This is a new service – your feedback will help us to improve it. Home Digital "
    f"Outcomes opportunities Procurement details {NOTICE} Help You can contact us by email, "
    "phone or using the enquiry form (opens in a new tab) . Email: info@gca.gov.uk Telephone: "
    "0345 410 2222 GCA customer services team is available Monday to Friday, 9am to 5pm."
)


def digital_source(config):
    return next(s for s in config["sources"]["sources"] if s["id"] == "digital_outcomes")


def serve(status, calls):
    listing = (
        '<main><li><a href="/digital-outcomes/opportunity-details/1">CRM platform replacement</a>'
        f"<p>Example Council</p><p>{status}</p><p>Replace the council CRM.</p></li></main>"
    )

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        return httpx.Response(200, text=DETAIL if "opportunity-details" in request.url.path else listing)

    return Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)


def test_details_keep_the_notice_and_drop_the_page_furniture(config, now):
    calls = []
    result = collect_digital(digital_source(config), {}, now, serve("open", calls), config["runtime"], {})
    [record] = result.records
    assert record.data["description"] == NOTICE
    assert record.data["deadline"].startswith("2026-10-24")
    # The buyer's own supplier search is part of the notice, not furniture.
    assert "where the supplier provides Salesforce" in record.data["description"]


def test_cached_descriptions_lose_the_furniture_without_another_request(config, now):
    calls = []
    state = {
        "digital_details": {
            "1": {
                "data": {"description": CACHED, "deadline": "2026-10-24"},
                "fetched_at": (now - timedelta(days=3)).isoformat(),
                "signature": "earlier listing",
            }
        }
    }
    result = collect_digital(
        digital_source(config), state, now, serve("closed", calls), config["runtime"], {}
    )
    [record] = result.records
    assert record.data["description"] == NOTICE
    assert record.data["deadline"].startswith("2026-10-24")
    assert not [path for path in calls if "opportunity-details" in path]


def test_a_page_read_now_and_its_cached_text_agree():
    page = BeautifulSoup(DETAIL, "html.parser").select_one("main")
    cached = clean(BeautifulSoup(DETAIL, "html.parser").select_one("main").get_text(" ", strip=True))
    assert clean(notice_text(page)) == without_page_furniture(cached) == NOTICE
    assert without_page_furniture(NOTICE) == NOTICE


def test_notice_text_that_resembles_furniture_is_kept():
    for text in (
        "Home Digital Outcomes opportunities for the Home Office, with a help desk.",
        "Help You can contact the buyer through the portal before 9am to 5pm cut-offs.",
        "The supplier will run a Beta This is a new service pilot.",
    ):
        assert without_page_furniture(text) == text
