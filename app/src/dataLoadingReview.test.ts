import { afterEach, describe, expect, test, vi } from 'vitest'
import type { Dataset, Signal } from './types'
import { recordDataset } from '../tests/fixtures/record'
import {
  defaultMarketOptions,
  filterSignals,
  defaults,
  matchesMarket,
  normaliseFilters,
} from './lib'
import { normaliseMarketPreferences } from './personalWorkspace'
import {
  BoundedCache,
  currentMarketPaths,
  isCurrentFeed,
  isSignalPage,
  loadCurrentDataset,
  loadManifest,
  mergeSignalPages,
} from './dataClient'
import type { SignalPage } from './dataClient'
import { resolveSignalSelection } from './useOpportunityData'
import { awardMarketPaths } from './useAwardHistory'

const dataset: Dataset = {
  ...recordDataset({} as Dataset),
  schema_version: '1.0',
  sources: [],
  capabilities: [],
  evidence_catalog: {},
  markets: {},
  translations: {},
}
const record = dataset.signals[0]
const path = 'current/GB-0123456789abcdef.json'
const detailPath = `records/${record.id}-0123456789abcdef.json`
const manifest: Dataset = {
  ...dataset,
  signals: [],
  current_feed: {
    version: '1.0',
    markets: { GB: { url: path, count: 1 } },
    records: { [record.id]: { url: detailPath, markets: ['GB'], view: 'opportunities' } },
  },
}
const page: SignalPage = {
  schema_version: '1.0',
  signals: [{ ...record, description: '', search_text: record.description, is_summary: true }],
}
const response = (value: unknown) => ({ ok: true, json: async () => value })
afterEach(() => vi.unstubAllGlobals())

describe('Benelux as a combined market', () => {
  const entry = (id: string, count = 1) => ({ url: `current/${id}-0123456789abcdef.json`, count })
  test('default preferences consolidate three countries while country facts and old links stay precise', () => {
    expect(defaultMarketOptions.map((m) => m.id)).toContain('BENELUX')
    expect(defaultMarketOptions.some((m) => ['BE', 'NL', 'LU'].includes(m.id))).toBe(false)
    const preferences = normaliseMarketPreferences({
      pinned: ['NL', 'BE', 'LU', 'GB'],
      order: ['BE', 'FR', 'NL', 'LU'],
    })
    expect(preferences.pinned).toEqual(['BENELUX', 'GB'])
    expect(preferences.order.slice(0, 2)).toEqual(['BENELUX', 'FR'])
    expect(preferences.order.filter((id) => id === 'BENELUX')).toHaveLength(1)
    expect(normaliseFilters({ market: 'benelux' }).market).toBe('BENELUX')
    expect(normaliseFilters({ market: 'BE' }).market).toBe('BE')
    expect(matchesMarket({ ...record, countries: ['LU'] }, 'BENELUX')).toBe(true)
    expect(matchesMarket({ ...record, countries: ['NL'] }, 'BE')).toBe(false)
  })
  test('All uses the group once; older indexes combine member shards without duplicate cross-border records', () => {
    const current_feed = {
      version: '1.0',
      markets: { BENELUX: entry('BENELUX', 3), BE: entry('BE'), NL: entry('NL'), LU: entry('LU') },
      records: {},
    }
    expect(currentMarketPaths({ ...dataset, current_feed }, '')).toEqual([entry('BENELUX').url])
    expect(currentMarketPaths({ ...dataset, current_feed }, 'BENELUX')).toEqual([
      entry('BENELUX').url,
    ])
    const legacy = {
      ...current_feed,
      markets: { BE: entry('BE'), NL: entry('NL'), LU: entry('LU') },
    }
    expect(currentMarketPaths({ ...dataset, current_feed: legacy }, 'BENELUX')).toHaveLength(3)
    const shared: Signal = {
      ...record,
      id: 'shared',
      countries: ['BE', 'NL'],
      deadline_at: '2099-01-01',
    }
    const luxembourg: Signal = { ...shared, id: 'luxembourg', countries: ['LU'] }
    const combined = mergeSignalPages([
      { schema_version: '1.0', signals: [shared] },
      { schema_version: '1.0', signals: [shared, luxembourg] },
    ]).signals
    expect(
      filterSignals(combined, { ...defaults, market: 'BENELUX' })
        .map((s) => s.id)
        .sort(),
    ).toEqual(['luxembourg', 'shared'])
    expect(filterSignals(combined, { ...defaults, market: '' })).toHaveLength(2)
    const award_history = Object.fromEntries(
      Object.entries(current_feed.markets).map(([id, item]) => [
        id,
        { ...item, url: item.url.replace('current/', 'awards/') },
      ]),
    )
    expect(awardMarketPaths({ ...dataset, award_history }, '')).toHaveLength(1)
  })
  test('DACH combines Germany, Austria and Switzerland while precise country links remain compatible', () => {
    const arranged = normaliseMarketPreferences({
      pinned: ['GB', 'DE', 'CH', 'AT'],
      order: ['DE', 'AT', 'FR', 'CH'],
    })
    expect(arranged.pinned).toEqual(['GB', 'DACH'])
    expect(arranged.order.slice(0, 2)).toEqual(['DACH', 'FR'])
    expect(defaultMarketOptions.some((m) => ['DE', 'AT', 'CH'].includes(m.id))).toBe(false)
    expect(normaliseFilters({ market: 'dach' }).market).toBe('DACH')
    expect(normaliseFilters({ market: 'DE' }).market).toBe('DE')
    expect(matchesMarket({ ...record, countries: ['CH'] }, 'DACH')).toBe(true)
    expect(matchesMarket({ ...record, countries: ['CH'] }, 'DE')).toBe(false)
    const current_feed = {
      version: '1.0',
      markets: { DACH: entry('DACH', 3), DE: entry('DE'), AT: entry('AT'), CH: entry('CH') },
      records: {},
    }
    expect(currentMarketPaths({ ...dataset, current_feed }, '')).toEqual([entry('DACH').url])
  })
})

describe('independent loader regression review', () => {
  test('manifest validation rejects invalid counts, paths and mismatched record identities', () => {
    expect(isCurrentFeed(manifest.current_feed)).toBe(true)
    expect(
      isCurrentFeed({ ...manifest.current_feed, markets: { GB: { url: path, count: -1 } } }),
    ).toBe(false)
    expect(
      isCurrentFeed({
        ...manifest.current_feed,
        records: { [record.id]: { url: 'https://other.test/data.json', markets: ['GB'] } },
      }),
    ).toBe(false)
    expect(
      isCurrentFeed({
        ...manifest.current_feed,
        records: { other: { url: detailPath, markets: ['GB'] } },
      }),
    ).toBe(false)
    expect(isSignalPage({ ...page, signals: [page.signals[0], page.signals[0]] })).toBe(false)
    expect(isSignalPage({ ...page, translations: { broken: { title: null } } })).toBe(false)
  })
  test('malformed manifest JSON falls back to a verified complete legacy feed', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => {
            throw new SyntaxError('Invalid JSON')
          },
        })
        .mockResolvedValueOnce(response(dataset)),
    )
    expect(await loadManifest(new AbortController().signal, '/')).toEqual(dataset)
  })
  test('a partial search index cannot silently hide matches and falls back to the complete feed', async () => {
    const incomplete = {
      ...manifest,
      current_feed: { ...manifest.current_feed!, markets: { GB: { url: path, count: 2 } } },
    }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(response(incomplete))
      .mockResolvedValueOnce(response(page))
      .mockResolvedValueOnce(response(incomplete))
      .mockResolvedValueOnce(response(page))
      .mockResolvedValueOnce(response(dataset))
    vi.stubGlobal('fetch', fetcher)
    const loaded = await loadCurrentDataset(
      'GB',
      new AbortController().signal,
      new BoundedCache(),
      '/',
    )
    expect(loaded.signals).toHaveLength(dataset.signals.length)
    expect(loaded.signals[0].description).toBe(record.description)
    expect(fetcher.mock.calls.at(-1)?.[0]).toBe('/data/current.json')
  })
  test('a stale manifest refresh selects only the new generation and keeps its record pointer', async () => {
    const nextPath = 'current/GB-1123456789abcdef.json'
    const nextDetail = `records/${record.id}-1123456789abcdef.json`
    const next = {
      ...manifest,
      current_feed: {
        ...manifest.current_feed!,
        markets: { GB: { url: nextPath, count: 1 } },
        records: { [record.id]: { url: nextDetail, markets: ['GB'] } },
      },
    }
    const nextPage = {
      ...page,
      signals: [
        {
          ...page.signals[0],
          title: 'Amended platform procurement',
          search_text: 'Amended customer platform procurement',
        },
      ],
    }
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(response(manifest))
        .mockResolvedValueOnce({ ok: false, status: 404 })
        .mockResolvedValueOnce(response(next))
        .mockResolvedValueOnce(response(nextPage)),
    )
    const loaded = await loadCurrentDataset(
      'GB',
      new AbortController().signal,
      new BoundedCache(),
      '/',
    )
    expect(loaded.signals[0].title).toBe('Amended platform procurement')
    expect(resolveSignalSelection(loaded, record.id).path).toBe(nextDetail)
  })
  test('aborting while manifest JSON is decoded rejects without requesting the fallback', async () => {
    let deliver: (value: unknown) => void = () => {}
    const decoded = new Promise((resolve) => {
      deliver = resolve
    })
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: () => decoded })
    vi.stubGlobal('fetch', fetcher)
    const controller = new AbortController()
    const loading = loadManifest(controller.signal, '/')
    await Promise.resolve()
    controller.abort()
    deliver(manifest)
    await expect(loading).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  test('direct links resolve outside the loaded market and full fallback records never need another detail fetch', () => {
    expect(resolveSignalSelection(manifest, record.id).path).toBe(detailPath)
    expect(
      resolveSignalSelection({ ...dataset, current_feed: manifest.current_feed }, record.id).path,
    ).toBe('')
    expect(resolveSignalSelection({ ...manifest, signals: page.signals }, record.id).path).toBe(
      detailPath,
    )
  })
  test('cross-market duplicates with incompatible record versions are rejected', () => {
    expect(() =>
      mergeSignalPages([
        page,
        { ...page, signals: [{ ...page.signals[0], title: 'Different revision' }] },
      ]),
    ).toThrow('incompatible')
  })
})
