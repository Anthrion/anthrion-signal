import { describe, expect, test } from 'vitest'
import {
  briefText,
  createBackup,
  defaultPreferences,
  normalisePreferences,
  PREFERENCES_KEY,
  restoreBackup,
} from './preferences'
import { countryCoverage } from './coverage'
import { coverageReview } from './marketCoverage'
import { defaults } from './lib'
import { PERSONAL_WORKSPACE_KEY, readLastView, rememberLastView } from './personalWorkspace'
import type { Dataset } from './types'

function storage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial))
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => void values.set(key, value),
    values,
  }
}

describe('workspace preferences', () => {
  test('unknown or malformed values fall back field by field', () => {
    expect(normalisePreferences(null)).toEqual(defaultPreferences)
    expect(
      normalisePreferences({ reading: 'brief', approach: 'maybe', effects: 1, startMarket: 'DE' }),
    ).toEqual({ ...defaultPreferences, reading: 'brief', startMarket: 'DE' })
    expect(normalisePreferences({ startMarket: '<script>' }).startMarket).toBe('GB')
  })

  test('the theme is dark unless light was chosen', () => {
    expect(defaultPreferences.theme).toBe('dark')
    expect(normalisePreferences({ theme: 'light' }).theme).toBe('light')
    expect(normalisePreferences({ theme: 'sepia' }).theme).toBe('dark')
    expect(normalisePreferences({ theme: 1 }).theme).toBe('dark')
  })

  test('brief reading keeps the opening paragraph and cuts long ones at a sentence', () => {
    expect(briefText('Short scope.')).toEqual({ text: 'Short scope.', truncated: false })
    expect(briefText('First paragraph.\n\nSecond paragraph.')).toEqual({
      text: 'First paragraph.',
      truncated: true,
    })
    const long = `${'Integration and data migration services. '.repeat(20)}Tail`
    const brief = briefText(long)
    expect(brief.truncated).toBe(true)
    expect(brief.text.length).toBeLessThanOrEqual(602)
    expect(brief.text).toMatch(/services\. …$/)
  })

  test('a plain visit opens the preferred market, or the remembered one', () => {
    const memory = storage()
    rememberLastView(memory, { ...defaults, market: 'FR', q: 'CRM' })
    expect(readLastView(memory).market).toBe('GB')
    expect(readLastView(memory, 'DE')).toEqual({ ...defaults, market: 'DE', q: 'CRM' })
    expect(readLastView(memory, 'last')).toEqual({ ...defaults, market: 'FR', q: 'CRM' })
    expect(readLastView(storage(), 'last').market).toBe('GB')
  })

  test('backups merge saved and hidden records and replace settings', () => {
    const source = storage({
      'anthrion-saved-v1': JSON.stringify(['sig_a', 'sig_b']),
      'anthrion-hidden-v1': JSON.stringify(['sig_x']),
      'anthrion-language-v1': JSON.stringify('original'),
      'anthrion-pane-ratio-v1': JSON.stringify(99),
      [PREFERENCES_KEY]: JSON.stringify({ reading: 'brief' }),
    })
    const backup = createBackup(source, new Date('2026-09-23T10:00:00Z'))
    const parsed = JSON.parse(backup)
    expect(parsed).toMatchObject({ app: 'anthrion-signal', version: 1 })
    expect(parsed.entries['anthrion-pane-ratio-v1']).toBeUndefined()

    const target = storage({ 'anthrion-saved-v1': JSON.stringify(['sig_c', 'sig_a']) })
    const result = restoreBackup(target, backup)
    expect(result.error).toBe('')
    expect(JSON.parse(target.getItem('anthrion-saved-v1')!)).toEqual(['sig_c', 'sig_a', 'sig_b'])
    expect(JSON.parse(target.getItem('anthrion-hidden-v1')!)).toEqual(['sig_x'])
    expect(JSON.parse(target.getItem('anthrion-language-v1')!)).toBe('original')
    expect(JSON.parse(target.getItem(PREFERENCES_KEY)!)).toEqual({
      ...defaultPreferences,
      reading: 'brief',
    })
  })

  test('a backup is rejected unless it is a Signal backup with valid entries', () => {
    const target = storage()
    expect(restoreBackup(target, 'not json').error).toMatch(/not a Signal backup/)
    expect(restoreBackup(target, '{"app":"other","version":1,"entries":{}}').error).toMatch(
      /not a Signal backup/,
    )
    const invalid = JSON.stringify({
      app: 'anthrion-signal',
      version: 1,
      entries: { 'anthrion-saved-v1': [1, 2], [PERSONAL_WORKSPACE_KEY]: { version: 2 } },
    })
    expect(restoreBackup(target, invalid)).toEqual({
      restored: [],
      error: 'The backup contained no Signal settings.',
    })
    expect(target.values.size).toBe(0)
  })
})

describe('country coverage', () => {
  const dataset = {
    markets: {
      GB: { name: 'United Kingdom', enabled: true },
      DE: { name: 'Germany', enabled: true },
      MT: { name: 'Malta', enabled: true },
      XX: { name: 'Disabled', enabled: false },
    },
    sources: [
      { id: 'fts', name: 'Find a Tender', enabled: true, countries: ['GB'] },
      { id: 'ted', name: 'TED Europe', enabled: true, countries: ['DE', 'MT'] },
      { id: 'old', name: 'Retired', enabled: false, countries: ['DE'] },
    ],
    signals: [],
    current_feed: {
      version: '1.0',
      markets: {
        GB: { url: 'current/GB-0.json', count: 3 },
        DE: { url: 'current/DE-0.json', count: 2 },
        DACH: { url: 'current/DACH-0.json', count: 2 },
      },
      records: {
        a: { url: '', markets: ['GB'] },
        b: { url: '', markets: ['GB'] },
        c: { url: '', markets: ['GB', 'DE'] },
        d: { url: '', markets: ['DE'], view: 'opportunities' },
        e: { url: '', markets: ['GB'], view: 'awards' },
      },
    },
  } as unknown as Dataset

  const reviewed = (id: string) => ({
    estimate: coverageReview.countries[id]?.estimate ?? null,
    missing: coverageReview.countries[id]?.missing ?? [],
  })

  test('each monitored country carries its reviewed estimate and current count', () => {
    expect(countryCoverage(dataset)).toEqual([
      { id: 'GB', name: 'United Kingdom', count: 3, ...reviewed('GB'), sources: ['Find a Tender'] },
      { id: 'DE', name: 'Germany', count: 2, ...reviewed('DE'), sources: ['TED Europe'] },
      { id: 'MT', name: 'Malta', count: 0, ...reviewed('MT'), sources: ['TED Europe'] },
    ])
  })

  test('reviewed estimates are whole percentages with named gaps', () => {
    for (const [id, review] of Object.entries(coverageReview.countries)) {
      expect(id).toMatch(/^[A-Z]{2}$/)
      expect(Number.isInteger(review.estimate)).toBe(true)
      expect(review.estimate).toBeGreaterThanOrEqual(0)
      expect(review.estimate).toBeLessThanOrEqual(100)
      expect(review.missing.every((name) => typeof name === 'string' && !!name.trim())).toBe(true)
    }
  })

  test('without a manifest the loaded records are counted', () => {
    const legacy = {
      ...dataset,
      current_feed: undefined,
      signals: [{ countries: ['DE', 'DE'] }, { countries: ['GB'] }],
    } as unknown as Dataset
    expect(countryCoverage(legacy).map((c) => [c.id, c.count])).toEqual([
      ['GB', 1],
      ['DE', 1],
      ['MT', 0],
    ])
  })
})
