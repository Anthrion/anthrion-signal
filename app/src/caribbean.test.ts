import { describe, expect, test } from 'vitest'
import { caribbeanCountries, selectableMarket } from './caribbean'
import { countryLabels, defaultMarketOptions, matchesMarket, marketIsEnabled } from './lib'
import { emptyPersonalWorkspace, normaliseMarketPreferences } from './personalWorkspace'
import { currentMarketPaths } from './dataClient'
import { awardMarketPaths } from './useAwardHistory'
import type { Dataset } from './types'

describe('combined Caribbean market', () => {
  test('one selectable market retains precise country labels and regional source facts', () => {
    const ids = defaultMarketOptions.map((m) => m.id)
    expect(ids[ids.indexOf('FR') + 1]).toBe('CARIBBEAN')
    expect(ids.filter((id) => caribbeanCountries.includes(id))).toEqual([])
    for (const country of ['DO', 'LC', 'GP', 'CARIBBEANREGIONAL']) {
      expect(matchesMarket({ countries: [country] }, 'CARIBBEAN')).toBe(true)
      expect(selectableMarket(country)).toBe('CARIBBEAN')
    }
    expect(matchesMarket({ countries: ['FR'] }, 'CARIBBEAN')).toBe(false)
    expect(matchesMarket({ countries: ['US'] }, 'CARIBBEAN')).toBe(false)
    expect(selectableMarket('DE')).toBe('DE')
    expect(countryLabels({ countries: ['DO', 'LC', 'DO', 'CARIBBEANREGIONAL'] })).toBe(
      'Dominican Republic · Saint Lucia · Caribbean (regional)',
    )
    expect(marketIsEnabled('CARIBBEAN', { LC: { enabled: true } })).toBe(true)
    expect(marketIsEnabled('CARIBBEAN', { GB: { enabled: true } })).toBe(false)
  })

  test('default pin is added once after France without undoing explicit unpin or drag', () => {
    const fresh = emptyPersonalWorkspace().marketPreferences
    expect(fresh.pinned[fresh.pinned.indexOf('FR') + 1]).toBe('CARIBBEAN')
    const migrated = normaliseMarketPreferences({
      order: ['', 'DACH', 'FR', 'GB'],
      pinned: ['', 'DACH', 'FR'],
    })
    expect(migrated.pinned).toEqual(['', 'DACH', 'FR', 'CARIBBEAN'])
    const custom = {
      order: ['CARIBBEAN', ...migrated.order.filter((id) => id !== 'CARIBBEAN')],
      pinned: ['', 'FR'],
    }
    expect(normaliseMarketPreferences(custom)).toEqual(custom)
    expect(normaliseMarketPreferences({ order: ['FR'], pinned: ['DACH'] }).pinned).toEqual(['DACH'])
  })

  test('All loads regional and country notices once for both live and awarded views', () => {
    const entries = Object.fromEntries(
      ['GB', 'DO', 'LC', 'CARIBBEANREGIONAL', 'CARIBBEAN'].map((id) => [
        id,
        { url: `current/${id}-0123456789abcdef.json.gz`, count: 1 },
      ]),
    )
    const data = {
      current_feed: { version: '1.0', markets: entries, records: {} },
      award_history: Object.fromEntries(
        Object.entries(entries).map(([id, ref]) => [
          id,
          { ...ref, url: ref.url.replace('current/', 'awards/') },
        ]),
      ),
    } as Dataset
    expect(new Set(currentMarketPaths(data, ''))).toEqual(
      new Set([entries.GB.url, entries.CARIBBEAN.url]),
    )
    expect(currentMarketPaths(data, 'CARIBBEAN')).toEqual([entries.CARIBBEAN.url])
    expect(new Set(awardMarketPaths(data, ''))).toEqual(
      new Set(['awards/GB-0123456789abcdef.json.gz', 'awards/CARIBBEAN-0123456789abcdef.json.gz']),
    )
    delete data.current_feed!.markets.CARIBBEAN
    delete data.award_history!.CARIBBEAN
    expect(currentMarketPaths(data, 'CARIBBEAN')).toHaveLength(3)
    expect(awardMarketPaths(data, 'CARIBBEAN')).toHaveLength(3)
  })
})
