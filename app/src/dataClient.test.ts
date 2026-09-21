import { afterEach, describe, expect, test, vi } from 'vitest'
import {
  BoundedCache,
  currentMarketPaths,
  fetchJSON,
  isCurrentFeed,
  loadManifest,
  loadPages,
  mergeSignalPages,
  recordDetail,
  safeDataPath,
} from './dataClient'
import type { SignalPage } from './dataClient'

async function gzip(body: string) {
  return new Uint8Array(
    await new Response(
      new Blob([body]).stream().pipeThrough(new CompressionStream('gzip')),
    ).arrayBuffer(),
  )
}
import type { Dataset } from './types'
import { recordDataset } from '../tests/fixtures/record'
import { awardMarketPaths } from './useAwardHistory'
import { validBuyerPage } from './useBuyerHistory'

const record = recordDataset({} as Dataset).signals[0]
const path = 'current/GB-0123456789abcdef.json'
const page: SignalPage = {
  schema_version: '1.0',
  signals: [{ ...record, search_text: record.description }],
}
const dataset: Dataset = {
  ...recordDataset({} as Dataset),
  schema_version: '1.0',
  sources: [],
  capabilities: [],
  evidence_catalog: {},
  markets: {},
  translations: {},
}
afterEach(() => vi.unstubAllGlobals())
describe('versioned static data', () => {
  test('bounded cache evicts least recently used values and never retains an oversized page', () => {
    const cache = new BoundedCache<number>(2, 10)
    cache.set('a', 1, 3)
    cache.set('b', 2, 3)
    cache.get('a')
    cache.set('c', 3, 3)
    expect(cache.get('b')).toBeUndefined()
    expect(cache.get('a')).toBe(1)
    cache.set('huge', 99, 11)
    expect(cache.size).toBe(2)
    expect(cache.get('huge')).toBeUndefined()
  })
  test('All markets loads all required search shards and deduplicates overlapping Nordic records', () => {
    const current_feed = {
      version: '1.0',
      markets: {
        GB: { url: path, count: 1 },
        FI: { url: 'current/FI-1123456789abcdef.json', count: 1 },
        NORDICS: { url: 'current/NORDICS-2123456789abcdef.json', count: 1 },
      },
      records: {},
    }
    expect(currentMarketPaths({ ...dataset, current_feed }, '')).toHaveLength(2)
    expect(currentMarketPaths({ ...dataset, current_feed }, 'FI')).toEqual([
      current_feed.markets.FI.url,
    ])
    expect(mergeSignalPages([page, page]).signals).toEqual(page.signals)
    expect(
      awardMarketPaths(
        {
          ...dataset,
          award_history: { NORDICS: { url: 'awards/NORDICS-0123456789abcdef.json', count: 1 } },
        },
        'FI',
      ),
    ).toHaveLength(1)
  })
  test('hashed paths cannot escape the published data directory or switch origin', () => {
    for (const candidate of [
      '../secret.json',
      'https://elsewhere.test/a',
      '/current/GB-0123456789abcdef.json',
      'current/GB-0123456789abcdef.json?x=1',
      'current/%2e%2e/GB-0123456789abcdef.json',
    ])
      expect(() => safeDataPath(candidate, 'current')).toThrow()
    expect(safeDataPath(path, 'current')).toBe(path)
  })
  test('an older deployment without a manifest remains usable', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404 })
      .mockResolvedValueOnce({ ok: true, json: async () => dataset })
    vi.stubGlobal('fetch', fetcher)
    expect(await loadManifest(new AbortController().signal, '/signal/')).toEqual(dataset)
    expect(fetcher.mock.calls.map((call) => call[0])).toEqual([
      '/signal/data/manifest.json',
      '/signal/data/current.json',
    ])
  })
  test('compressed history selects the requested record, preserves Unicode and accepts HTTP-decoded content', async () => {
    const url = 'history/abc-0123456789abcdef.json.gz'
    const payload = {
      schema_version: '1.0',
      records: {
        first: { signal: { ...record, id: 'first', title: 'Other notice' } },
        second: { signal: { ...record, id: 'second', title: 'Portail français' } },
      },
    }
    const body = JSON.stringify(payload)
    for (const bytes of [await gzip(body), new TextEncoder().encode(body)]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(bytes)))
      const result = await fetchJSON(url, new AbortController().signal, '/')
      expect(recordDetail(result, 'second')?.signal.title).toBe('Portail français')
      expect(recordDetail(result, 'missing')).toBeNull()
      expect(recordDetail({ schema_version: '1.0', signal: record }, record.id)?.signal).toEqual(
        record,
      )
    }
    expect(
      isCurrentFeed({
        version: '1.0',
        markets: {},
        records: {
          second: { url, markets: ['FR'], view: 'history' },
        },
      }),
    ).toBe(true)
    expect(
      isCurrentFeed({
        version: '1.0',
        markets: {},
        records: {
          second: { url, markets: ['FR'], view: 'opportunities' },
        },
      }),
    ).toBe(false)
  })
  test('corrupt and oversized compressed history cannot be decoded into an unbounded page', async () => {
    const url = 'history/abc-0123456789abcdef.json.gz'
    for (const bytes of [
      new Uint8Array([0x1f, 0x8b, 0]),
      await gzip('x'.repeat(16 * 1024 * 1024 + 1)),
    ]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(bytes)))
      await expect(fetchJSON(url, new AbortController().signal, '/')).rejects.toThrow()
    }
  })
  test('cancelled market requests cannot populate caches after their response arrives', async () => {
    let deliver: (value: unknown) => void = () => {}
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise((resolve) => {
            deliver = resolve
          }),
      ),
    )
    const controller = new AbortController()
    const cache = new BoundedCache<SignalPage>()
    const loading = loadPages([path], 'current', controller.signal, cache, '/')
    controller.abort()
    deliver({ ok: true, json: async () => page })
    await expect(loading).rejects.toMatchObject({ name: 'AbortError' })
    expect(cache.size).toBe(0)
  })
  test('a failed search shard rejects the complete result instead of returning misleading partial counts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(
      loadPages([path], 'current', new AbortController().signal, new BoundedCache(), '/'),
    ).rejects.toThrow('503')
  })
  test('buyer pages must match the requested identity and preserve histories beyond fifty entries', () => {
    const records = Array.from({ length: 75 }, (_, i) => ({
      signal_id: `s-${i}`,
      title: 'Procurement',
      status: 'awarded',
      source_url: 'https://example.gov/notice',
      lot_ids: [],
    }))
    const buyerPage = { schema_version: '1.0', buyer_id: 'buyer-one', records }
    expect(validBuyerPage(buyerPage, 'buyer-one')).toBe(true)
    expect(validBuyerPage(buyerPage, 'buyer-two')).toBe(false)
    expect(records).toHaveLength(75)
  })
})
