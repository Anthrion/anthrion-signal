import gzip
from datetime import UTC, datetime

import pytest

from anthrion_signal import cli
from anthrion_signal.award_history import export_awards
from anthrion_signal.collectors import RawRecord
from anthrion_signal.discovery import is_public_award, is_public_opportunity, lifecycle, prefilter
from anthrion_signal.discovery_retention import retain_rejected
from anthrion_signal.dedupe import exact_keys
from anthrion_signal.models import Dataset
from anthrion_signal.normalise import normalise_ocds
from anthrion_signal.notice_dates import digital_deadline
from anthrion_signal.utils import atomic_json, read_json


@pytest.mark.parametrize('text, expected', [
    ('Tender submission deadline 05/10/2026 at 10:00am', '2026-10-05T10:00:00+01:00'),
    ('Tender submission deadline 12:00 19/06/2026 Compliance checks', '2026-06-19T12:00:00+01:00'),
    ('Application closing date: 5 January 2027 at 3pm', '2027-01-05T15:00:00+00:00'),
    ('Tender submission deadline will be 12 Noon Friday 29th May 2026.', '2026-05-29T12:00:00+01:00'),
    ('2 October 2026 Application closing date. Tender submission deadline 2 October 2026 at 11:30pm', '2026-10-02T23:30:00+01:00'),
    ('Deadline for receipt of bids 9 September 2026. Stage 2 tender submission deadline 26 October 2026', '2026-09-09'),
    ('CoP deadline 18/09/2026 12:00. Stage 2 tender submission deadline 02/11/2026', '2026-09-18T12:00:00+01:00'),
    ('Deadline for clarification questions 4 October 2026. Latest start date 8 December 2026.', None),
    ('Tender submission deadline TBC. Contract award 8 December 2026.', None),
    ('Tender submission deadline 31/02/2026', None),
    ('Tender submission deadline 29 June at 13:00', None),
    ('Tender Phase - Stage 1: 26 Aug 2026 - Deadline of Submission to Clarification Questions; 09 Sep 2026 - Deadline for Submission of Bids. Tender Phase - Stage 2: 26 Oct 2026 - Deadline for Submission of Bids.', '2026-09-09'),
])
def test_published_digital_application_dates(text, expected):
    assert digital_deadline(text) == expected


def test_numeric_deadline_retires_cached_open_listing(signal, config):
    signal.source = 'digital_outcomes'
    signal.status = 'open'
    signal.description = 'CRM implementation. Tender submission deadline 12:00 19/06/2026'
    signal.deadline_at = None
    signal.response_deadlines = []
    prefilter([signal], config['company_profile'], config['search_terms'], config['capabilities'])
    assert signal.deadline_at == '2026-06-19T12:00:00+01:00'
    assert lifecycle(signal, datetime(2026, 9, 18, tzinfo=UTC))[0] == 'EXPIRED'
    assert not is_public_opportunity(signal, datetime(2026, 9, 18, tzinfo=UTC))


def test_past_planned_start_does_not_invent_deadline_or_revive_old_calloff(signal):
    signal.source, signal.status = 'digital_outcomes', 'open'
    signal.description = 'Digital delivery. Latest start date 2026-08-03. Tender submission deadline 29th June 13:00.'
    signal.deadline_at, signal.response_deadlines = None, []
    signal.deadlines = []
    now = datetime(2026, 9, 18, tzinfo=UTC)
    assert lifecycle(signal, now)[0] == 'UNKNOWN'
    # An indicative start date cannot justify deleting otherwise relevant scope.
    # UNKNOWN remains reviewable in All Signals, never in the Live category.
    assert is_public_opportunity(signal, now)
    signal.description += ' Revised tender submission deadline 25 September 2026 at 4pm.'
    assert is_public_opportunity(signal, now)


def test_date_only_digital_deadline_keeps_the_whole_uk_closing_day(signal):
    signal.source, signal.deadline_at, signal.response_deadlines = 'digital_outcomes', '2026-09-24', []
    assert lifecycle(signal, datetime(2026, 9, 24, 21, tzinfo=UTC))[0] == 'OPEN'
    assert lifecycle(signal, datetime(2026, 9, 24, 23, tzinfo=UTC))[0] == 'EXPIRED'
    assert signal.deadline_at == '2026-09-24'


def test_awards_use_archive_and_cache_without_reviving_cancellations(tmp_path, signal, config, now, monkeypatch):
    award = signal.model_copy(update={'signal_type': 'AWARD', 'status': 'complete', 'lifecycle_state': 'AWARDED'})
    cancelled = award.model_copy(update={'id': 'cancelled', 'status': 'cancelled'})
    old = award.model_copy(update={'id': 'archived', 'countries': ['SE'], 'updated_at': '2025-01-01T00:00:00Z'})
    archive = tmp_path / 'data/archive/2025-01.jsonl.gz'
    archive.parent.mkdir(parents=True)
    archive.write_bytes(gzip.compress((old.model_dump_json() + '\n' + award.model_copy(update={'id': 'cancelled'}).model_dump_json()).encode()))
    def read(manifest, market):
        return read_json(tmp_path / 'app/public/data' / manifest[market]['url'], {})
    first = export_awards(tmp_path, [award, cancelled], config, now)
    assert first['GB']['count'] == 1
    assert [s['id'] for s in read(first, 'NORDICS')['signals']] == ['archived']
    assert 'analysis' not in read(first, 'GB')['signals'][0]
    assert not is_public_opportunity(award, now)
    # Identical scope reuses decisions; no hourly full-history classification.
    monkeypatch.setattr('anthrion_signal.award_history.prefilter', lambda *args: pytest.fail('Unchanged award was rescored'))
    assert export_awards(tmp_path, [award, cancelled], config, now) == first


def test_award_cache_invalidates_changed_scope_and_never_deletes_sources(tmp_path, signal, config, now):
    award = signal.model_copy(update={'signal_type': 'AWARD', 'status': 'complete'})
    first = export_awards(tmp_path, [award], config, now)
    assert first['GB']['count'] == 1
    award.title, award.description, award.cpv_codes = 'Outdoor sauna operation', 'Provide a sauna service.', ['98330000']
    second = export_awards(tmp_path, [award], config, now)
    assert second['GB']['count'] == 0
    assert first['GB']['url'] != second['GB']['url']


@pytest.mark.parametrize('changes', [
    {'status': 'cancelled'}, {'status': 'unsuccessful'}, {'signal_type': 'RENEWAL_SIGNAL'},
    {'title': 'CANCELLED CRM procurement'}, {'notice_type': 'veat'}, {'notice_type': 'UK5'},
    {'award_statuses': ['pending']}, {'award_statuses': ['cancelled', 'unsuccessful']},
])
def test_non_awards_never_enter_history(signal, now, changes):
    award = signal.model_copy(update={'signal_type': 'AWARD', 'status': 'complete', **changes})
    assert not is_public_award(award, now)


def test_award_statuses_and_supplier_attribution(release, source, now):
    release['tag'] = ['award']
    release['awards'] = [
        {'status': 'cancelled', 'suppliers': [{'name': 'Withdrawn supplier'}]},
        {'status': 'active', 'suppliers': [{'name': 'Winning supplier'}]},
    ]
    award = normalise_ocds(RawRecord(release, source, now.isoformat()))
    assert award.award_statuses == ['cancelled', 'active']
    assert award.incumbent_supplier == 'Winning supplier'
    assert is_public_award(award, now)


def test_code_only_release_recovers_rejected_digital_work(tmp_path, signal, config, monkeypatch):
    monkeypatch.setattr(cli, 'load_config', lambda root: config)
    signal.title = 'Multidisciplinary digital delivery'
    signal.description = 'Design and deliver digital products and services throughout the digital service lifecycle.'
    signal.source, signal.status, signal.deadline_at = 'digital_outcomes', 'open', '2099-10-05'
    signal.response_deadlines, signal.prefilter_score, signal.cpv_codes = [], 0, []
    retain_rejected(tmp_path, [signal], datetime(2026, 9, 18, tzinfo=UTC), 12)
    dataset = Dataset(generated_at='2026-09-18T00:00:00Z', data_updated_at='2026-09-18T00:00:00Z',
                      profile_version='1', scoring_version='none', sources=[], capabilities=[],
                      markets={}, evidence_catalog={}, signals=[], run={'discovery_signature': 'old'})
    atomic_json(tmp_path / 'data/current.json', dataset.model_dump())
    canonical = tmp_path / 'data/signals.jsonl'
    canonical.write_text('', encoding='utf-8')
    assert [s.id for s in cli.export(tmp_path).signals] == [signal.id]
    assert canonical.read_text(encoding='utf-8') == ''
    # A newer archived cancellation must win over the rejected old tender.
    closed = signal.model_copy(update={'status': 'cancelled', 'updated_at': '2026-09-19T12:00:00Z'})
    archive = tmp_path / 'data/archive/2026-09.jsonl.gz'
    archive.parent.mkdir(parents=True)
    archive.write_bytes(gzip.compress(closed.model_dump_json().encode()))
    atomic_json(tmp_path / 'data/archive_index.json', {key: {'month': '2026-09', 'id': closed.id} for key in exact_keys(closed)})
    assert cli.export(tmp_path).signals == []
