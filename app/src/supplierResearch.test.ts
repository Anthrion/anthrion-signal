import { expect, test } from 'vitest'
import type { Signal } from './types'
import {
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
