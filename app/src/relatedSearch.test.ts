import { expect, test } from 'vitest'
import { recordDataset } from '../tests/fixtures/record'
import { createRelatedIndex } from './relatedSearch'
import { emptyRelatedFilters, filterRelated } from './RelatedFilters'
import {
  countryLabels,
  hasAwardOutcome,
  isCombinedMarket,
  isHistoricalAward,
  matchesMarket,
} from './lib'
import type { Dataset, EnglishText, Signal } from './types'

const now = Date.parse('2026-09-21T10:00:00Z')
const base = recordDataset({} as Dataset, {
  deadline_at: '2026-11-01',
  matched_capabilities: [],
  buyer_id: 'buyer-one',
  buyer_identity_basis: 'identifier',
  procedure_id: 'proc-one',
  title: 'Citizen casework and grant assessment',
  description: 'Connect citizen casework to grant assessment workflows.',
}).signals[0]
const record = (id: string, changes: Partial<Signal> = {}) => ({
  ...base,
  id,
  buyer_id: `buyer-${id}`,
  procedure_id: `proc-${id}`,
  ...changes,
})

test('related search finds substantive text without capability tags, excludes boilerplate, self, expired and awards from live results', () => {
  const live = record('live', {
    countries: ['CA'],
    title: 'Grant assessment portal',
    description: 'Citizen casework and grant assessment workflows.',
  })
  const expired = record('expired', { deadline_at: '2025-01-01' })
  const award = record('award', {
    signal_type: 'AWARD',
    status: 'awarded',
    award_statuses: ['active'],
    award_date: '2025-01-01',
  })
  const noise = record('noise', {
    title: 'Public service contract',
    description:
      'The contracting authority requires software delivery and technical support for this project.',
  })
  const find = createRelatedIndex([base, live, expired, award, noise])
  expect(find(base, 'signals', now).map((m) => m.signal.id)).toEqual(['live'])
  expect(find(base, 'awards', now).map((m) => m.signal.id)).toEqual(['award'])
  expect(find(award, 'signals', now).map((m) => m.signal.id)).toContain('live')
  expect(find(base, 'signals', now)[0].relationship).toBe('similar_text')
})

test('cached translations connect original-language records and exact procedure links rank first', () => {
  const french = record('fr', {
    countries: ['FR'],
    title: 'Portail des aides citoyennes',
    description: 'Examen des dossiers de subvention.',
  })
  const translation = {
    title: 'Citizen grant assessment',
    description: 'Grant assessment workflows and citizen casework.',
  } as EnglishText
  const exact = record('exact', {
    title: 'Lot continuation',
    description: '',
    procedure_id: base.procedure_id,
  })
  const find = createRelatedIndex([base, french, exact], { fr: translation })
  expect(find(base, 'signals', now).map((m) => m.signal.id)).toEqual(['exact', 'fr'])
  expect(find(base, 'signals', now)[0].relationship).toBe('same_procedure')
})

test('related filters use inclusive award/deadline dates, require known values and keep currencies separate', () => {
  const award = record('a', {
    award_date: '2026-09-21',
    amount: {
      kind: 'award',
      minimum: 100000,
      maximum: 200000,
      currency: 'CAD',
      source_label: '',
      source_url: '',
    },
    incumbent_supplier: 'Équipe Conseil',
  })
  const filters = {
    ...emptyRelatedFilters,
    party: 'equipe',
    dateMode: 'range',
    from: '2026-09-21',
    to: '2026-09-21',
    valueMode: 'range',
    min: '100000',
    max: '200000',
    currency: 'CAD',
  }
  expect(filterRelated(award, filters, 'awards')).toBe(true)
  expect(filterRelated({ ...award, award_date: null }, filters, 'awards')).toBe(false)
  expect(
    filterRelated(
      { ...award, amount: undefined, value_max: null, value_min: null },
      filters,
      'awards',
    ),
  ).toBe(false)
  expect(filterRelated(award, { ...filters, currency: 'USD' }, 'awards')).toBe(false)
  expect(
    filterRelated(
      award,
      { ...emptyRelatedFilters, dateMode: 'from', from: '2026-11-02' },
      'signals',
    ),
  ).toBe(false)
})

test('historical source facts remain visible without promoting excluded awards, and all combined markets label their countries', () => {
  const award = record('past', {
    signal_type: 'AWARD',
    status: 'awarded',
    exclusion_reasons: ['outside_delivery_scope'],
  })
  expect(hasAwardOutcome(award)).toBe(true)
  expect(isHistoricalAward(award)).toBe(false)
  expect(['', 'NORDICS', 'BENELUX', 'DACH', 'NORTHAMERICA'].every(isCombinedMarket)).toBe(true)
  expect(isCombinedMarket('CA')).toBe(false)
  expect(countryLabels(record('ca', { countries: ['CA'] }))).toBe('Canada')
  expect(matchesMarket(record('ca', { countries: ['CA'] }), 'NORTHAMERICA')).toBe(true)
})
