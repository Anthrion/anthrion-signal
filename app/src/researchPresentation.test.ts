import { expect, test } from 'vitest'
import type { HistoryRecord, Signal } from './types'
import { distinctSources, historySources, lotIds, meaningfulLots } from './researchPresentation'

test('source links collapse repeated notice anchors and query ordering without losing distinct notices', () => {
  const notice = 'https://example.org/notice?id=12&language=en'
  expect(
    distinctSources([
      notice,
      `${notice}#lot-2`,
      'https://example.org/notice?language=en&id=12',
      'https://example.org/notice?id=13&language=en',
      'https://other.example.org/notice?id=12&language=en',
      'https://example.org/specification.pdf',
      'javascript:alert(1)',
      '',
      undefined,
    ]),
  ).toEqual([
    notice,
    'https://example.org/notice?id=13&language=en',
    'https://other.example.org/notice?id=12&language=en',
    'https://example.org/specification.pdf',
  ])
  expect(distinctSources([`${notice}#history`], [notice])).toEqual([])
})

test('lots with only an identifier become one summary while real scope, dates, amounts and outcomes stay', () => {
  const base = {
    id: 'LOT-0001',
    title: '',
    description: '',
    status: 'unknown',
    source_url: 'https://example.org/notice',
  }
  const lots: NonNullable<Signal['lots']> = [
    { ...base, title: 'Lot LOT-0001', description: 'Lot 1' },
    { ...base, id: 'LOT-0002', title: 'Lot 2' },
    { ...base, id: '3', title: 'CRM implementation' },
    { ...base, id: '4', description: 'Integration with existing financial systems.' },
    { ...base, id: '5', deadline_at: '2026-11-01' },
    { ...base, id: '6', value_max: 0, currency: 'EUR' },
    { ...base, id: '7', status: 'cancelled' },
  ]
  expect(meaningfulLots(lots).map((lot) => lot.id)).toEqual(['3', '4', '5', '6', '7'])
  expect(lotIds({ lot_ids: ['LOT-0001', 'LOT-0002'], lots })).toEqual([
    'LOT-0001',
    'LOT-0002',
    '3',
    '4',
    '5',
    '6',
    '7',
  ])
})

test('history collects each distinct source across amounts, lots and winners once', () => {
  const notice = 'https://example.org/notice/12'
  const record = {
    source_url: notice,
    amount: { source_url: `${notice}#value` },
    lots: [{ source_url: `${notice}#lot-1` }, { source_url: 'https://example.org/spec.pdf' }],
    winners: [{ source_url: 'https://example.org/award/14' }],
  } as HistoryRecord
  expect(historySources(record)).toEqual([
    notice,
    'https://example.org/spec.pdf',
    'https://example.org/award/14',
  ])
})
