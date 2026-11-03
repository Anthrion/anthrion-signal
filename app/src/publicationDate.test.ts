import { expect, test } from 'vitest'
import { date, publicationDate } from './lib'
import type { Signal } from './types'

test('TED publication dates follow the official calendar for every reader', () => {
  for (const timeZone of ['Europe/London', 'America/Los_Angeles', 'Asia/Tokyo']) {
    for (const published_at of [
      '2026-07-02',
      '2026-07-01T22:00:00+00:00',
      '2026-07-02T00:00:00+02:00',
    ]) {
      expect(publicationDate({ source: 'ted', published_at }, { timeZone })).toBe('2 Jul 2026')
    }
    expect(
      publicationDate({ source: 'ted', published_at: '2026-01-14T23:00:00Z' }, { timeZone }),
    ).toBe('15 Jan 2026')
  }
})

test('national-source dates and clock timestamps retain their semantics', () => {
  const published_at = '2026-07-01T22:00:00+00:00'
  const options = {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'Europe/London',
  } as const
  expect(publicationDate({ source: 'germany', published_at }, options)).toBe('1 Jul 2026')
  const provenance = [{ source: 'germany', published_at }] as Signal['provenance']
  expect(publicationDate({ source: 'ted', published_at, provenance }, options)).toBe('1 Jul 2026')
  expect(date(published_at, options)).toBe('1 Jul 2026')
  expect(publicationDate({ source: 'ted', published_at: null })).toBe('Not published')
})
