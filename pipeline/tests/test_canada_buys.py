import csv
import io
from datetime import timedelta
from email.utils import format_datetime

import httpx
import pytest

from anthrion_signal.canada_buys import (BASE, CLOSING, PUBLISHED, REFERENCE, REQUIRED, SOLICITATION,
    collect_canada_buys, feeds, normalise_canada_buys, parse_snapshot, removed_canada_records)
from anthrion_signal.collectors import Http, RawRecord, SourceUnavailable
from anthrion_signal.discovery import lifecycle


def row(**changes):
    return {REFERENCE: "cb-100-123", SOLICITATION: "CRM-26", PUBLISHED: "2026-09-08", CLOSING: "2026-10-01T14:00:00",
        "title-titre-eng": "Case management implementation", "title-titre-fra": "Mise en œuvre de gestion des dossiers",
        "tenderDescription-descriptionAppelOffres-eng": "Implement Salesforce CRM and integrate case records.",
        "tenderDescription-descriptionAppelOffres-fra": "Mettre en œuvre Salesforce et intégrer les dossiers.",
        "tenderStatus-appelOffresStatut-eng": "Open", "contractingEntityName-nomEntitContractante-eng": "Federal department",
        "noticeType-avisType-eng": "RFP against Supply Arrangement", "procurementMethod-methodeApprovisionnement-eng": "Competitive - Limited Tendering",
        **changes}


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    fields = list(dict.fromkeys([*REQUIRED, *[key for item in rows for key in item]]))
    writer = csv.DictWriter(stream, fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def source(config):
    return {**next(s for s in config['sources']['sources'] if s['id'] == 'canada_buys'), 'minimum_open_rows': 1}


def normalise(config, now, value=None):
    value = row() if value is None else value
    return normalise_canada_buys(RawRecord({'_kind': 'tender', **value}, source(config), now.isoformat(), 'canada_buys'))


def collect(config, now, rows, state=None, **options):
    content = csv_bytes(rows)
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url).startswith(BASE)
        assert 'Authorization' not in request.headers
        headers = {'ETag': options.get('etag', '"version-1"'), 'Content-Length': str(len(content)), 'Last-Modified': format_datetime(now)}
        if request.method == 'HEAD':
            return httpx.Response(200, headers=headers)
        assert request.headers['If-Match'] == headers['ETag']
        return httpx.Response(200, headers={**headers, **options.get('get_headers', {})}, content=content)
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    try:
        result = collect_canada_buys({**source(config), **options.get('source', {})}, state or {}, now, http,
            {'max_pages': options.get('budget', 2), 'refresh_daily': options.get('refresh', True)}, {})
    finally:
        http.close()
    return result, calls


def test_fixed_est_deadline_and_source_membership_survive_normalization(config, now):
    signal = normalise(config, now, row(**{'noticeURL-URLavis-eng': 'https://example.gov/submit'}))
    assert signal.countries == ['CA'] and signal.source_language == 'en'
    assert signal.deadline_at == '2026-10-01T19:00:00+00:00'
    assert signal.deadlines[0].source_text == row()[CLOSING]
    assert signal.deadlines[0].timezone == '-05:00'
    assert 'Supply Arrangement' in signal.eligibility_text
    assert signal.value_max is None and signal.amount.kind == 'unknown'
    assert signal.primary_source_url.endswith('/tender-notice/cb-100-123')
    assert signal.documents[0].url == 'https://example.gov/submit'
    changed = normalise(config, now, row(**{'title-titre-eng': 'Revised platform', CLOSING: '2026-11-01T14:00:00'}))
    assert changed.id == signal.id
    assert changed.procedure_id == signal.procedure_id
    expired = normalise(config, now, row(**{CLOSING: '2025-10-01T14:00:00'}))
    assert lifecycle(expired, now)[0] == 'EXPIRED'  # Source still says Open.


def test_french_only_original_and_complete_long_scope_are_preserved(config, now):
    description = 'Mettre en œuvre un portail citoyen. ' * 1200
    signal = normalise(config, now, row(**{'title-titre-eng': '', 'tenderDescription-descriptionAppelOffres-eng': '',
        'tenderDescription-descriptionAppelOffres-fra': description}))
    assert signal.source_language == 'fr'
    assert signal.description == description.strip() and len(signal.description) > 24000


def test_award_is_historical_and_retains_amount_currency_supplier_and_distinct_id(config, now):
    value = {**row(), '_kind': 'award', 'awardStatus-attributionStatut-eng': 'Active', 'contractNumber-numeroContrat': 'C-1',
        'contractAmount-montantContrat': '120000.50', 'contractCurrency-contratMonnaie': 'CAD',
        'supplierLegalName-nomLegalFournisseur-eng': 'Example Ltd', 'awardDescription-descriptionAttribution-eng': 'Salesforce delivery',
        'contractAwardDate-dateAttributionContrat': '2026-09-05'}
    signal = normalise_canada_buys(RawRecord(value, source(config), now.isoformat(), 'canada_buys'))
    assert signal.signal_type == 'AWARD' and lifecycle(signal, now)[0] == 'AWARDED'
    assert signal.amount.maximum == 120000.5 and signal.amount.kind == 'award' and signal.currency == 'CAD'
    assert signal.winners[0]['name'] == 'Example Ltd' and signal.deadline_at is None
    assert signal.id != normalise(config, now).id
    assert signal.procedure_id == normalise(config, now).procedure_id


def test_csv_reads_multiline_quotes_and_latest_amendment_without_keyword_gate():
    older = row(**{'amendmentNumber-numeroModification': '000'})
    newer = row(**{'amendmentNumber-numeroModification': '001', 'amendmentDate-dateModification': '2026-09-09',
        'tenderDescription-descriptionAppelOffres-eng': 'A "quoted" requirement,\nwith a second line.'})
    unrelated = row(**{REFERENCE: 'SSC-26-00034400:T', 'title-titre-eng': 'Water samples'})
    parsed = parse_snapshot(csv_bytes([newer, older, unrelated]), 'tender')
    assert len(parsed) == 2
    assert parsed['tender:cb-100-123'] == newer
    assert 'tender:SSC-26-00034400:T' in parsed
    ninth = {**newer, 'amendmentNumber-numeroModification': '9'}
    tenth = {**newer, 'amendmentNumber-numeroModification': '10', 'title-titre-eng': 'Latest scope'}
    assert parse_snapshot(csv_bytes([tenth, ninth]), 'tender')['tender:cb-100-123'] == tenth
    with pytest.raises(SourceUnavailable, match='conflicting'):
        parse_snapshot(csv_bytes([older, {**older, 'title-titre-eng': 'Conflicting title'}]), 'tender')
    with pytest.raises(SourceUnavailable):
        parse_snapshot(b'Not a valid CSV', 'tender')


def test_bounded_bootstrap_resumes_same_snapshot_and_validates_before_checkpoint(config, now):
    rows = [row(), row(**{REFERENCE: 'cb-200'})]
    first, calls = collect(config, now, rows, source={'max_records_per_feed': 1})
    assert len(calls) == 2 and len(first.records) == 1 and not first.complete
    assert first.state['feeds']['new']['pending'] == 1
    second, _ = collect(config, now + timedelta(minutes=30), rows, first.state, source={'max_records_per_feed': 1})
    assert len(second.records) == 1 and second.records[0].data[REFERENCE] != first.records[0].data[REFERENCE]
    broken, _ = collect(config, now, rows, first.state, get_headers={'ETag': 'different'})
    assert not broken.records and broken.state.get('feeds') == first.state['feeds']


def test_absence_never_invents_award_and_only_confirmed_removals_retire(config, now):
    signal = normalise(config, now)
    assert not removed_canada_records([signal], {'feeds': {'open': {'missing': {'tender:cb-100-123': 'v1'}}}}, now.isoformat())
    gone = removed_canada_records([signal], {'feeds': {'open': {'removed': ['tender:cb-100-123']}}}, now.isoformat())
    assert len(gone) == 1 and gone[0].status == 'not_listed' and gone[0].signal_type == signal.signal_type
    assert lifecycle(gone[0], now)[0] == 'CLOSED'
    assert not removed_canada_records(gone, {'feeds': {'open': {'removed': ['tender:cb-100-123']}}}, now.isoformat())
    assert not removed_canada_records([signal.model_copy(update={'status': 'cancelled'})], {'feeds': {'open': {'removed': ['tender:cb-100-123']}}}, now.isoformat())


def test_open_list_absence_requires_two_different_verified_snapshots(config, now):
    first, _ = collect(config, now, [row(), row(**{REFERENCE: 'cb-200'})], budget=4)
    second, _ = collect(config, now + timedelta(days=1), [row(**{REFERENCE: 'cb-200'})], first.state, budget=4, etag='"v2"')
    assert second.state['feeds']['open']['missing'] == {'tender:cb-100-123': '"v2"'}
    assert not second.state['feeds']['open']['removed']
    same, _ = collect(config, now + timedelta(days=2), [row(**{REFERENCE: 'cb-200'})], second.state, budget=4, etag='"v2"')
    assert not same.state['feeds']['open']['removed']
    confirmed, _ = collect(config, now + timedelta(days=3), [row(**{REFERENCE: 'cb-200'})], same.state, budget=4, etag='"v3"')
    assert confirmed.state['feeds']['open']['removed'] == ['tender:cb-100-123']


def test_fiscal_year_and_free_endpoint_names(now):
    assert feeds(now)[-1][1] == '2026-2027-awardNotice-avisAttribution.csv'
    assert feeds(now.replace(month=2))[-1][1] == '2025-2026-awardNotice-avisAttribution.csv'
