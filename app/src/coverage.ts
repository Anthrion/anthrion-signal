import type { Dataset } from './types'
import { coverageReview } from './marketCoverage'

export type CountryCoverage = {
  id: string
  name: string
  /** Current opportunities that name this country. */
  count: number
  /** Estimated share of the country's publicly listed opportunities Signal's sources reach. */
  estimate: number | null
  /** The main listing sources Signal does not collect, largest first. */
  missing: string[]
  sources: string[]
}

/** Monitored countries with their reviewed coverage estimate and current signal count. */
export function countryCoverage(data: Dataset | null): CountryCoverage[] {
  if (!data) return []
  const feed = data.current_feed
  const counted = new Map<string, number>()
  if (!feed)
    for (const signal of data.signals)
      for (const country of new Set(signal.countries))
        counted.set(country, (counted.get(country) || 0) + 1)
  return Object.entries(data.markets)
    .filter(([id, market]) => market.enabled && /^[A-Z]{2}$/.test(id))
    .map(([id, market]) => {
      const review = coverageReview.countries[id]
      return {
        id,
        name: market.name,
        count: feed ? (feed.markets[id]?.count ?? 0) : counted.get(id) || 0,
        estimate: review?.estimate ?? null,
        missing: review?.missing ?? [],
        sources: data.sources
          .filter((source) => source.enabled && source.countries?.includes(id))
          .map((source) => source.name),
      }
    })
}
