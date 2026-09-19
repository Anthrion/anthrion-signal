import { expect, test } from 'vitest'
import type { Dataset, HistoryRecord, Signal } from './types'
import {
  awardHistoryRecord,
  historySupplierAwards,
  historySupplierScope,
  historySuppliers,
  publishedSuppliers,
  samePublishedSupplier,
  supplierAwards,
  supplierHistoryMarket,
} from './supplierResearch'

const winner = {
  name: 'Example Delivery Ltd',
  identifiers: [],
  lot_ids: [],
  source_url: 'https://example.com/award',
}
const award = {
  id: 'award',
  title: 'CRM',
  signal_type: 'AWARD',
  lifecycle_state: 'AWARDED',
  status: 'awarded',
  countries: ['GB'],
  source: 'ted',
  award_date: '2025-02-01',
  winners: [winner],
  award_statuses: ['active'],
  related_signal_id: null,
} as unknown as Signal

test('supplier history uses exact published identity and keeps namesakes separate', () => {
  expect(
    samePublishedSupplier(winner, award, { ...winner, name: ' EXAMPLE  DELIVERY LTD ' }, award),
  ).toBe(true)
  expect(
    samePublishedSupplier(
      winner,
      award,
      { ...winner, name: 'Example Delivery Services Ltd' },
      award,
    ),
  ).toBe(false)
  expect(samePublishedSupplier(winner, award, winner, { ...award, countries: ['US'] })).toBe(false)
  expect(samePublishedSupplier(winner, award, winner, { ...award, source: 'another' })).toBe(false)
  const identified = { ...winner, identifiers: ['GB-COH:01234567'] }
  expect(
    samePublishedSupplier(
      identified,
      award,
      { ...identified, name: 'Renamed Ltd' },
      { ...award, countries: ['FR'], source: 'another' },
    ),
  ).toBe(true)
  expect(
    samePublishedSupplier(
      identified,
      award,
      { ...winner, identifiers: ['GB-COH:76543210'] },
      award,
    ),
  ).toBe(false)
  expect(
    samePublishedSupplier(
      { ...winner, identifiers: ['ORG-0001'] },
      award,
      { ...winner, name: 'Unrelated Ltd', identifiers: ['ORG-0001'] },
      award,
    ),
  ).toBe(false)
})

test('supplier timeline deduplicates award notices, orders actual award dates, and excludes live incumbents', () => {
  const newer = { ...award, id: 'newer', award_date: '2026-03-01' }
  const live = {
    ...award,
    id: 'live',
    signal_type: 'LIVE_TENDER',
    lifecycle_state: 'OPEN',
    status: 'active',
    award_statuses: [],
  }
  expect(
    supplierAwards(award, winner, [newer, award, newer, live]).map((record) => record.id),
  ).toEqual(['newer', 'award'])
  expect(publishedSuppliers(live)).toEqual([])
  expect(
    publishedSuppliers({
      ...award,
      winners: [],
      incumbent_supplier: 'Example Ltd / Partner Ltd',
    })[0].name,
  ).toBe('Example Ltd / Partner Ltd')
})

test('supplier history loads all markets only when identity matching can cross their boundaries', () => {
  expect(supplierHistoryMarket(award, winner)).toBe('GB')
  expect(supplierHistoryMarket(award, { ...winner, identifiers: ['ORG-0001'] })).toBe('GB')
  expect(supplierHistoryMarket(award, { ...winner, identifiers: ['GB-COH:01234567'] })).toBe('')
  expect(supplierHistoryMarket({ ...award, countries: ['GB', 'FR'] }, winner)).toBe('')
})

const retainedAward = (): HistoryRecord => ({
  ...awardHistoryRecord(award),
  signal_id: 'retained-award',
  source_url: 'https://example.com/retained-award',
  title: 'Historical contract outside the current capability feed',
})

test('buyer-history suppliers include the selected retained award and matching history without borrowing the current opportunity identity', () => {
  const selected = retainedAward()
  const sameSupplier = { ...selected, signal_id: 'older', award_date: '2024-01-01' }
  const otherCountry = { ...selected, signal_id: 'namesake-abroad', countries: ['DE'] }
  const otherSource = { ...selected, signal_id: 'other-source', source: 'other' }
  const live = {
    ...selected,
    signal_id: 'live-incumbent',
    signal_type: 'LIVE_TENDER',
    status: 'active',
  }
  const cancelled = { ...selected, signal_id: 'cancelled', award_statuses: ['cancelled'] }
  expect(
    historySupplierAwards(
      selected,
      winner,
      [sameSupplier, otherCountry, otherSource, live, cancelled],
      [award],
    ).map((record) => record.signal_id),
  ).toEqual(['award', 'retained-award', 'older'])
  expect(historySuppliers(live)).toEqual([])
  expect(historySuppliers(cancelled)).toEqual([])
  expect(historySuppliers({ ...selected, award_statuses: ['pending'] })).toEqual([])
  for (const notice_type of ['UK5', 'veat', 'dir-awa-pre'])
    expect(historySuppliers({ ...selected, notice_type })).toEqual([])
  expect(historySuppliers({ ...selected, title: 'CANCELLED CRM contract' })).toEqual([])
  expect(historySupplierAwards(selected, { ...winner, name: 'Unrelated Ltd' }, [], [])).toEqual([])
})

test('registry identity can connect compact history across borders but conflicting identifiers remain separate', () => {
  const identified = { ...winner, identifiers: ['GB-COH:01234567'] }
  const selected = { ...retainedAward(), winners: [identified] }
  const abroad = {
    ...selected,
    signal_id: 'abroad',
    countries: ['FR'],
    source: 'other',
    winners: [{ ...identified, name: 'Renamed Delivery Ltd' }],
  }
  const conflict = {
    ...selected,
    signal_id: 'conflict',
    winners: [{ ...winner, identifiers: ['GB-COH:76543210'] }],
  }
  expect(
    historySupplierAwards(selected, identified, [abroad, conflict], []).map(
      (record) => record.signal_id,
    ),
  ).toEqual(['abroad', 'retained-award'])
})

test('legacy histories without source identity stay separate until the actual full award supplies it', () => {
  const selected = { ...retainedAward(), source: undefined, countries: undefined }
  const full = { ...award, id: selected.signal_id }
  const other = { ...retainedAward(), signal_id: 'other-retained' }
  expect(
    historySupplierAwards(selected, winner, [other], [award]).map((record) => record.signal_id),
  ).toEqual(['retained-award'])
  expect(
    historySupplierAwards(selected, winner, [other], [award, full]).map(
      (record) => record.signal_id,
    ),
  ).toEqual(['award', 'other-retained', 'retained-award'])
  const data = {
    current_feed: { records: { [selected.signal_id]: { markets: ['DACH', 'DE'] } } },
  } as unknown as Dataset
  expect(historySupplierScope(selected, data)).toEqual({ source: '', countries: ['DE'] })
  expect(historySupplierScope(selected)).toEqual({ source: '', countries: [] })
})
