"""Trust-boundary regression tests using only synthetic pages and HTTP transports."""
import httpx
import pytest
from bs4 import BeautifulSoup

from anthrion_signal.collectors import Http, RawRecord, SourceUnavailable, official_notice_links
from anthrion_signal.normalise import normalise_html
from anthrion_signal.utils import official_notice_url

NOTICE = 'https://www.find-tender.service.gov.uk/Notice/012345-2026'


@pytest.mark.parametrize('url', [
    'https://evil.invalid/www.find-tender.service.gov.uk/Notice/012345-2026',
    'https://www.find-tender.service.gov.uk.evil.invalid/Notice/012345-2026',
    'https://www.find-tender.service.gov.uk@evil.invalid/Notice/012345-2026',
    'https://user:password@www.find-tender.service.gov.uk/Notice/012345-2026',
    'javascript:alert(1)', 'https://[invalid',
    'https://www.find-tender.service.gov.uk:444/Notice/012345-2026',
    'https://www.find-tender.service.gov.uk/Notice/../api',
    'https://www.find-tender.service.gov.uk/Notice/search',
])
def test_official_notice_rejects_lookalikes_and_invalid_links(url):
    assert official_notice_url(url) == ''


def test_official_notice_resolution_and_deduplication():
    html = BeautifulSoup(f'''<a href="{NOTICE}?utm_source=ccs#details">Notice</a>
        <a href="//www.find-tender.service.gov.uk/Notice/012345-2026/">Duplicate</a>
        <a href="/Notice/012345-2026">CCS relative path, not FTS</a>
        <a href="https://evil.invalid/?url={NOTICE}">Fake</a>''', 'html.parser')
    assert official_notice_links(html, 'https://www.gca.gov.uk/agreements/example') == [NOTICE]
    assert official_notice_links(BeautifulSoup('<a href="/Notice/012345-2026">N</a>', 'html.parser'), NOTICE) == [NOTICE]


def test_normalisation_rechecks_links_and_preserves_primary_record(config, now):
    source = next(s for s in config['sources']['sources'] if s['id'] == 'upcoming_agreements')
    primary = 'https://www.gca.gov.uk/agreements/example'
    data = dict(id='example', title='CRM agreement', description='CRM framework', url=primary,
                signal_type='PIPELINE', stage='planning',
                source_links=[NOTICE + '?utm_source=ccs#fragment', NOTICE, 'javascript:alert(1)',
                              'https://evil.invalid/?notice=' + NOTICE])
    signal = normalise_html(RawRecord(data, source, now.isoformat()))
    assert signal.primary_source_url == primary
    assert signal.source_urls == [primary, NOTICE]
    assert [d.url for d in signal.documents] == [NOTICE]


@pytest.mark.parametrize('location', [
    'https://evil.invalid/api', '//evil.invalid/api', 'http://example.gov.uk/api',
    'https://example.gov.uk:444/api', 'https://user:password@example.gov.uk/api',
    'https://[invalid',
])
def test_json_rejects_redirect_before_sending_any_off_origin_request(location):
    sent = []
    def handler(request):
        sent.append(str(request.url))
        return httpx.Response(302, headers={'Location': location})
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    with pytest.raises(SourceUnavailable):
        http.json('https://example.gov.uk/api')
    assert sent == ['https://example.gov.uk/api']


def test_json_allows_relative_same_origin_redirect_with_its_own_query():
    sent = []
    def handler(request):
        sent.append(str(request.url))
        if len(sent) == 1:
            return httpx.Response(307, headers={'Location': '/v2/api?cursor=next'})
        return httpx.Response(200, json={'records': []})
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    assert http.json('https://example.gov.uk/api', params={'limit': 10}) == {'records': []}
    assert sent == ['https://example.gov.uk/api?limit=10', 'https://example.gov.uk/v2/api?cursor=next']


def test_json_allows_https_upgrade_and_bounds_redirect_loops():
    def handler(request):
        if request.url.scheme == 'http':
            return httpx.Response(301, headers={'Location': 'https://example.gov.uk/api'})
        return httpx.Response(200, json={'ok': True})
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    assert http.json('http://example.gov.uk/api') == {'ok': True}
    sent = []
    def loop(request):
        sent.append(str(request.url))
        return httpx.Response(302, headers={'Location': '/loop'})
    http = Http(transport=httpx.MockTransport(loop), sleeper=lambda _: None)
    with pytest.raises(SourceUnavailable, match='redirect limit'):
        http.json('https://example.gov.uk/api')
    assert len(sent) == 6
