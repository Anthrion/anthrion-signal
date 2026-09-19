import type { CurrentFeedManifest, Dataset, EnglishText, Signal } from './types'
import { marketGroups } from './lib'

export interface SignalPage {
  schema_version: string
  signals: Signal[]
  translations?: Record<string, EnglishText>
}
export interface DetailPage {
  schema_version: string
  signal: Signal
  translation?: EnglishText
}
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value)
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((v) => typeof v === 'string')
export function isEnglishText(value: unknown): value is EnglishText {
  return (
    object(value) &&
    ['source_hash', 'version', 'title', 'description'].every(
      (key) => typeof value[key] === 'string',
    ) &&
    ['buyer_name', 'buyer_original'].every(
      (key) => value[key] == null || typeof value[key] === 'string',
    )
  )
}
export class BoundedCache<T> {
  private entries = new Map<string, { value: T; bytes: number }>()
  private bytes = 0
  constructor(
    private maxEntries = 12,
    private maxBytes = 32 * 1024 * 1024,
  ) {}
  get(key: string) {
    const entry = this.entries.get(key)
    if (!entry) return undefined
    this.entries.delete(key)
    this.entries.set(key, entry)
    return entry.value
  }
  set(key: string, value: T, bytes = JSON.stringify(value).length * 2) {
    this.delete(key)
    if (bytes > this.maxBytes) return
    this.entries.set(key, { value, bytes })
    this.bytes += bytes
    while (this.entries.size > this.maxEntries || this.bytes > this.maxBytes)
      this.delete(this.entries.keys().next().value!)
  }
  delete(key: string) {
    const entry = this.entries.get(key)
    if (entry) {
      this.bytes -= entry.bytes
      this.entries.delete(key)
    }
  }
  values() {
    return [...this.entries.values()].map((entry) => entry.value)
  }
  get size() {
    return this.entries.size
  }
}
export function isSignal(value: unknown): value is Signal {
  if (!object(value)) return false
  const s = value
  return (
    ['id', 'title', 'description', 'status', 'source', 'signal_type', 'primary_source_url'].every(
      (f) => typeof s[f] === 'string',
    ) &&
    ['countries', 'matched_capabilities', 'categories', 'cpv_codes', 'regions', 'lot_ids'].every(
      (f) => strings(s[f]),
    ) &&
    ['provenance', 'documents', 'changes'].every((f) => Array.isArray(s[f])) &&
    (s.provenance as unknown[]).every((p) => object(p) && typeof p.source === 'string') &&
    (s.external_ids === undefined || strings(s.external_ids)) &&
    (s.discovery_families === undefined || strings(s.discovery_families)) &&
    (s.is_summary === undefined || typeof s.is_summary === 'boolean')
  )
}
export function isSignalPage(value: unknown): value is SignalPage {
  const page = value as SignalPage | null
  return (
    !!page &&
    ['1.0', '2.0'].includes(page.schema_version) &&
    Array.isArray(page.signals) &&
    page.signals.every(isSignal) &&
    new Set(page.signals.map((s) => s.id)).size === page.signals.length &&
    (page.translations === undefined ||
      (object(page.translations) && Object.values(page.translations).every(isEnglishText)))
  )
}
export function isDataset(value: unknown): value is Dataset {
  const data = value as Dataset | null
  return (
    isSignalPage(value) &&
    !!data &&
    Array.isArray(data.sources) &&
    Array.isArray(data.capabilities) &&
    object(data.evidence_catalog) &&
    object(data.markets) &&
    Object.values(data.markets).every(
      (market) =>
        object(market) && typeof market.enabled === 'boolean' && typeof market.name === 'string',
    ) &&
    data.capabilities.every(
      (cap) =>
        object(cap) &&
        typeof cap.id === 'string' &&
        typeof cap.label === 'string' &&
        typeof cap.family === 'string' &&
        (cap.search_terms === undefined || strings(cap.search_terms)),
    ) &&
    (data.current_feed === undefined || isCurrentFeed(data.current_feed)) &&
    (data.award_history === undefined || isMarketManifest(data.award_history, 'awards'))
  )
}
function isMarketManifest(value: unknown, kind: 'current' | 'awards') {
  return (
    object(value) &&
    Object.entries(value).every(([id, entry]) => {
      if (
        !/^[A-Z]+$/.test(id) ||
        !object(entry) ||
        typeof entry.url !== 'string' ||
        !Number.isSafeInteger(entry.count) ||
        Number(entry.count) < 0
      )
        return false
      try {
        return safeDataPath(entry.url, kind).startsWith(`${kind}/${id}-`)
      } catch {
        return false
      }
    })
  )
}
export function isCurrentFeed(value: unknown): value is CurrentFeedManifest {
  return (
    object(value) &&
    value.version === '1.0' &&
    isMarketManifest(value.markets, 'current') &&
    object(value.records) &&
    Object.entries(value.records).every(([id, entry]) => {
      if (
        !/^[A-Za-z0-9_-]{1,100}$/.test(id) ||
        !object(entry) ||
        typeof entry.url !== 'string' ||
        !strings(entry.markets) ||
        (entry.view !== undefined && !['opportunities', 'awards'].includes(String(entry.view)))
      )
        return false
      try {
        return safeDataPath(entry.url, 'records').startsWith(`records/${id}-`)
      } catch {
        return false
      }
    })
  )
}
export function safeDataPath(path: string, kind: 'current' | 'awards' | 'records' | 'buyers') {
  const patterns = {
    current: /^current\/[A-Z]+-[a-f0-9]{16}\.json$/,
    awards: /^awards\/[A-Z]+-[a-f0-9]{16}\.json$/,
    records: /^records\/[A-Za-z0-9_-]+-[a-f0-9]{16}\.json$/,
    buyers: /^buyers\/buyer_[A-Za-z0-9_-]+-[a-f0-9]{16}\.json$/,
  }
  if (!patterns[kind].test(path)) throw new Error('The data file reference could not be verified.')
  return path
}
export async function fetchJSON(
  path: string,
  signal: AbortSignal,
  base = import.meta.env.BASE_URL,
  fresh = false,
): Promise<unknown> {
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
  const response = await fetch(`${base}data/${path}`, {
    signal,
    ...(fresh ? { cache: 'no-cache' as const } : {}),
  })
  if (!response.ok) throw new Error(`Data request failed (${response.status}).`)
  const value: unknown = await response.json()
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
  return value
}
export async function loadManifest(signal: AbortSignal, base?: string): Promise<Dataset> {
  try {
    const value = await fetchJSON('manifest.json', signal, base, true)
    if (!isDataset(value) || !value.current_feed || value.current_feed.version !== '1.0')
      throw new Error('Invalid manifest')
    return value
  } catch (error) {
    if (signal.aborted) throw error
    const legacy = await fetchJSON('current.json', signal, base, true)
    if (!isDataset(legacy)) throw new Error('The opportunity feed could not be verified.')
    return legacy
  }
}
export function currentMarketPaths(data: Dataset, market: string): string[] {
  if (!data.current_feed) return []
  const entries = Object.entries(data.current_feed.markets)
  const selected = selectMarketEntries(entries, market)
  return [...new Set(selected.map(([, page]) => safeDataPath(page.url, 'current')))].sort()
}
export function nonoverlappingMarkets<T>(entries: [string, T][]): [string, T][] {
  // Group shards are published unions. Loading both would repeat their countries.
  const grouped = new Set(
    Object.entries(marketGroups).flatMap(([group, countries]) =>
      entries.some(([id]) => id === group) ? countries : [],
    ),
  )
  return entries.filter(([id]) => !grouped.has(id))
}
export function selectMarketEntries<T>(entries: [string, T][], market: string): [string, T][] {
  if (!market || market === 'ALL') return nonoverlappingMarkets(entries)
  const direct = entries.filter(([id]) => id === market)
  if (direct.length) return direct
  const members = marketGroups[market]
  if (members) return entries.filter(([id]) => members.includes(id))
  const group = Object.entries(marketGroups).find(([, countries]) =>
    countries.includes(market),
  )?.[0]
  return group ? entries.filter(([id]) => id === group) : []
}
export function mergeSignalPages(pages: SignalPage[]) {
  const signals = new Map<string, Signal>()
  const versions = new Map<string, string>()
  for (const signal of pages.flatMap((page) => page.signals)) {
    const version = JSON.stringify(signal)
    if (versions.has(signal.id) && versions.get(signal.id) !== version)
      throw new Error('The market indexes contain incompatible record versions.')
    signals.set(signal.id, signal)
    versions.set(signal.id, version)
  }
  return {
    signals: [...signals.values()],
    translations: Object.fromEntries(
      pages.flatMap((p) => Object.entries(p.translations || {})),
    ) as Record<string, EnglishText>,
  }
}
export async function loadPages(
  paths: string[],
  kind: 'current' | 'awards',
  signal: AbortSignal,
  cache: BoundedCache<SignalPage>,
  base?: string,
  expectedCounts: Record<string, number> = {},
): Promise<SignalPage[]> {
  // Bound simultaneous requests when All markets expands into many shards.
  const pages = new Array<SignalPage>(paths.length)
  let next = 0
  const batch = new AbortController()
  const abort = () => batch.abort()
  if (signal.aborted) abort()
  else signal.addEventListener('abort', abort, { once: true })
  try {
    await Promise.all(
      Array.from({ length: Math.min(4, paths.length) }, async () => {
        while (next < paths.length) {
          const index = next++
          const path = safeDataPath(paths[index], kind)
          if (batch.signal.aborted) throw new DOMException('Aborted', 'AbortError')
          const cached = cache.get(path)
          if (cached) {
            if (
              expectedCounts[path] !== undefined &&
              cached.signals.length !== expectedCounts[path]
            )
              throw new Error('The data file count does not match its manifest.')
            pages[index] = cached
            continue
          }
          const page = await fetchJSON(path, batch.signal, base)
          if (batch.signal.aborted) throw new DOMException('Aborted', 'AbortError')
          if (
            !isSignalPage(page) ||
            (kind === 'current' && page.signals.some((s) => typeof s.search_text !== 'string'))
          )
            throw new Error('The data file could not be verified.')
          if (expectedCounts[path] !== undefined && page.signals.length !== expectedCounts[path])
            throw new Error('The data file count does not match its manifest.')
          cache.set(path, page)
          pages[index] = page
        }
      }),
    )
  } catch (error) {
    batch.abort()
    throw error
  } finally {
    signal.removeEventListener('abort', abort)
  }
  return pages
}
export async function loadCurrentDataset(
  market: string,
  signal: AbortSignal,
  cache: BoundedCache<SignalPage>,
  base?: string,
): Promise<Dataset> {
  const hydrate = async (manifest: Dataset) => {
    if (manifest.signals.length || !manifest.current_feed) return manifest
    const counts = Object.fromEntries(
      Object.values(manifest.current_feed.markets).map((page) => [page.url, page.count]),
    )
    const pages = await loadPages(
      currentMarketPaths(manifest, market),
      'current',
      signal,
      cache,
      base,
      counts,
    )
    const merged = mergeSignalPages(pages)
    if (
      merged.signals.some(
        (s) =>
          !manifest.current_feed!.records[s.id] ||
          manifest.current_feed!.records[s.id].view === 'awards',
      )
    )
      throw new Error('The search index and record manifest disagree.')
    return { ...manifest, ...merged }
  }
  try {
    return await hydrate(await loadManifest(signal, base))
  } catch (error) {
    if (signal.aborted) throw error
    try {
      return await hydrate(await loadManifest(signal, base))
    } catch (retryError) {
      if (signal.aborted) throw retryError
      const fallback = await fetchJSON('current.json', signal, base, true)
      if (!isDataset(fallback)) throw new Error('The opportunity feed could not be verified.')
      return fallback
    }
  }
}
