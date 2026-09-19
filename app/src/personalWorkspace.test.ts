import { describe, expect, test } from 'vitest'
import { defaults } from './lib'
import {
  emptyPersonalWorkspace,
  normaliseMarketPreferences,
  PERSONAL_WORKSPACE_KEY,
  readPersonalWorkspace,
  restoreSavedView,
  writePersonalWorkspace,
  readLastView,
  rememberLastView,
} from './personalWorkspace'
import type { StorageAccess } from './personalWorkspace'

function memoryStorage(initial: string | null = null) {
  let value = initial
  return {
    getItem: (_key: string) => value,
    setItem: (_key: string, next: string) => {
      value = next
    },
  } satisfies StorageAccess
}
describe('personal views and market preferences', () => {
  test('last-view memory restores filters while a plain visit starts in the UK', () => {
    const storage = memoryStorage()
    rememberLastView(storage, {
      ...defaults,
      view: 'awards',
      q: 'CRM',
      market: 'FR',
      supplier: 'Example',
    })
    expect(readLastView(storage)).toEqual({
      ...defaults,
      view: 'awards',
      q: 'CRM',
      supplier: 'Example',
    })
    expect(readLastView(memoryStorage('{broken'))).toEqual(defaults)
    const blocked = {
      getItem() {
        throw Error('Blocked')
      },
      setItem() {
        throw Error('Blocked')
      },
    }
    expect(readLastView(blocked)).toEqual(defaults)
    expect(() => rememberLastView(blocked, defaults)).not.toThrow()
  })
  test('All, groups and countries can be independently pinned and reordered', () => {
    expect(emptyPersonalWorkspace().marketPreferences.pinned).toEqual([
      '',
      'GB',
      'US',
      'IT',
      'NORDICS',
      'DACH',
      'ES',
      'GR',
      'BENELUX',
      'FR',
    ])
    expect(
      normaliseMarketPreferences({
        pinned: ['BENELUX', 'BE', 'DACH', 'DE', ''],
        order: ['BE', '', 'DE', 'BENELUX'],
      }).pinned,
    ).toEqual(['BENELUX', 'BE', 'DACH', 'DE', ''])
    const legacy = memoryStorage(
      JSON.stringify({
        ...emptyPersonalWorkspace(),
        marketPreferences: { pinned: ['FR', 'BENELUX'], order: ['FR', 'BENELUX', 'GB'] },
      }),
    )
    expect(readPersonalWorkspace(legacy).state.marketPreferences.pinned).toEqual([
      '',
      'FR',
      'BENELUX',
    ])
  })
  test('a named view restores all search, market, financial and award filters', () => {
    const filters = {
      ...defaults,
      q: 'Kundenmanagement',
      searchMode: 'exact',
      match: 'phrase',
      market: '',
      view: 'awards',
      supplier: 'Example Ltd',
      awardFrom: '2024-01-01',
      awardTo: '2026-12-31',
      currency: 'EUR',
      amountType: 'award',
      minValue: '2000',
      maxValue: '500000',
      buyer: 'Buyer',
      source: 'ted',
      region: 'Europe',
      cpv: '72',
      capability: 'crm',
    }
    const storage = memoryStorage()
    const view = { id: 'one', name: 'European awards', createdAt: '2026-09-18', filters }
    expect(
      writePersonalWorkspace(storage, (state) => ({ ...state, savedViews: [view] })).error,
    ).toBe('')
    expect(restoreSavedView(readPersonalWorkspace(storage).state.savedViews[0])).toEqual(filters)
  })
  test('malformed and future-version storage remains untouched', () => {
    for (const raw of ['{broken', JSON.stringify({ ...emptyPersonalWorkspace(), version: 99 })]) {
      const storage = memoryStorage(raw)
      expect(writePersonalWorkspace(storage, () => emptyPersonalWorkspace()).error).not.toBe('')
      expect(storage.getItem(PERSONAL_WORKSPACE_KEY)).toBe(raw)
    }
  })
  test('preference edits reread storage so a stale tab preserves another tab’s saved views', () => {
    const storage = memoryStorage()
    const view = {
      id: 'one',
      name: 'Saved in another tab',
      filters: defaults,
      createdAt: '2026-09-18',
    }
    writePersonalWorkspace(storage, (state) => ({ ...state, savedViews: [view] }))
    writePersonalWorkspace(storage, (state) => ({
      ...state,
      marketPreferences: { pinned: ['FR'], order: ['FR'] },
    }))
    expect(readPersonalWorkspace(storage).state.savedViews).toEqual([
      { ...view, showHidden: false },
    ])
  })
  test('saved views preserve the hidden-record filter while older views default to visible records', () => {
    const storage = memoryStorage()
    const view = {
      id: 'one',
      name: 'Hidden CRM',
      createdAt: '2026-09-18',
      filters: defaults,
      showHidden: true,
    }
    writePersonalWorkspace(storage, (state) => ({
      ...state,
      savedViews: [view, { ...view, id: 'old', showHidden: undefined }],
    }))
    const views = readPersonalWorkspace(storage).state.savedViews
    expect(views.map((saved) => saved.showHidden)).toEqual([true, false])
    const invalid = JSON.stringify({
      ...emptyPersonalWorkspace(),
      savedViews: [{ ...view, showHidden: 'true' }],
    })
    const invalidStorage = memoryStorage(invalid)
    expect(writePersonalWorkspace(invalidStorage, () => emptyPersonalWorkspace()).error).not.toBe(
      '',
    )
    expect(invalidStorage.getItem(PERSONAL_WORKSPACE_KEY)).toBe(invalid)
  })
  test('pinning never removes a supported market from More and malformed IDs are discarded', () => {
    const arranged = normaliseMarketPreferences({
      pinned: ['FR', 'FR', 'invalid'],
      order: ['IE', 'FR', 'invalid'],
    })
    expect(arranged.pinned).toEqual(['FR'])
    expect(arranged.order.slice(0, 2)).toEqual(['IE', 'FR'])
    expect(arranged.order).toContain('GB')
    expect(arranged.order).not.toContain('invalid')
  })
  test('write failures are reported without claiming a change was persisted', () => {
    const storage = {
      getItem: () => null,
      setItem: () => {
        throw new Error('Quota exceeded')
      },
    }
    const result = writePersonalWorkspace(storage, (state) => ({
      ...state,
      marketPreferences: { pinned: ['FR'], order: ['FR'] },
    }))
    expect(result.error).not.toBe('')
    expect(result.state.marketPreferences.pinned).toContain('GB')
  })
})
