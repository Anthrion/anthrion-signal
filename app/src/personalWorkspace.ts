import { useCallback, useEffect, useRef, useState } from 'react'
import { defaultMarketOptions, normaliseFilters, defaults, readFilters } from './lib'
import type { Filters } from './types'

export const PERSONAL_WORKSPACE_KEY = 'anthrion-personal-workspace-v1'
export const LAST_VIEW_KEY = 'anthrion-last-view-v1'

export function readLastView(storage: StorageAccess): Filters {
  try {
    const value: unknown = JSON.parse(storage.getItem(LAST_VIEW_KEY) || 'null')
    if (
      object(value) &&
      value.version === 1 &&
      object(value.filters) &&
      Object.values(value.filters).every((item) => typeof item === 'string' && item.length <= 2000)
    ) {
      return normaliseFilters({ ...value.filters, market: defaults.market })
    }
  } catch {
    /* Private browsing, invalid data and storage limits keep the defaults usable. */
  }
  return { ...defaults }
}

export function initialWorkspaceFilters(): Filters {
  // Shared URLs always specify their own view; a plain visit starts in the UK.
  if (window.location.search) return readFilters()
  try {
    return readLastView(window.localStorage)
  } catch {
    return { ...defaults }
  }
}

export function rememberLastView(storage: StorageAccess, filters: Filters) {
  try {
    storage.setItem(
      LAST_VIEW_KEY,
      JSON.stringify({ version: 1, filters: normaliseFilters(filters) }),
    )
  } catch {
    /* Remembering a view must never prevent browsing. */
  }
}
export interface SavedView {
  id: string
  name: string
  filters: Filters
  showHidden?: boolean
  createdAt: string
}
export interface MarketPreferences {
  pinned: string[]
  order: string[]
}
export interface PersonalWorkspace {
  version: 1
  savedViews: SavedView[]
  marketPreferences: MarketPreferences
}
export interface StorageAccess {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value)
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((v) => typeof v === 'string')
export function emptyPersonalWorkspace(): PersonalWorkspace {
  return {
    version: 1,
    savedViews: [],
    marketPreferences: {
      pinned: ['', 'GB', 'US', 'IT', 'NORDICS', 'DACH', 'ES', 'GR', 'BENELUX', 'FR'],
      order: defaultMarketOptions.map((m) => m.id),
    },
  }
}
export function normaliseMarketPreferences(value: MarketPreferences): MarketPreferences {
  const known = new Set<string>(defaultMarketOptions.map((m) => m.id))
  return {
    order: [
      ...new Set([
        ...value.order.filter((id) => known.has(id)),
        ...defaultMarketOptions.map((m) => m.id),
      ]),
    ],
    pinned: [...new Set(value.pinned.filter((id) => known.has(id)))],
  }
}
export function validPersonalWorkspace(value: unknown): value is PersonalWorkspace {
  if (
    !object(value) ||
    value.version !== 1 ||
    !Array.isArray(value.savedViews) ||
    !object(value.marketPreferences)
  )
    return false
  if (!strings(value.marketPreferences.pinned) || !strings(value.marketPreferences.order))
    return false
  return value.savedViews.every(
    (view) =>
      object(view) &&
      ['id', 'name', 'createdAt'].every((key) => typeof view[key] === 'string') &&
      object(view.filters) &&
      (view.showHidden === undefined || typeof view.showHidden === 'boolean') &&
      Object.values(view.filters).every((v) => typeof v === 'string'),
  )
}
export function readPersonalWorkspace(storage: StorageAccess): {
  state: PersonalWorkspace
  error: string
} {
  try {
    const raw = storage.getItem(PERSONAL_WORKSPACE_KEY)
    if (raw === null) return { state: emptyPersonalWorkspace(), error: '' }
    const parsed: unknown = JSON.parse(raw)
    if (!validPersonalWorkspace(parsed)) throw new Error('Invalid saved data')
    const previousDefaultPins = ['GB', 'US', 'IT', 'NORDICS', 'DACH', 'ES', 'GR']
    const untouchedPins =
      parsed.marketPreferences.pinned.length === previousDefaultPins.length &&
      previousDefaultPins.every((id) => parsed.marketPreferences.pinned.includes(id))
    return {
      state: {
        version: 1,
        savedViews: parsed.savedViews.map((v) => ({
          ...v,
          filters: normaliseFilters(v.filters),
          showHidden: v.showHidden ?? false,
        })),
        marketPreferences: normaliseMarketPreferences(
          // All used to be an implicit tab after UK, outside the saved arrangement.
          parsed.marketPreferences.order.includes('')
            ? parsed.marketPreferences
            : {
                order: ['', ...parsed.marketPreferences.order],
                pinned: [
                  '',
                  ...parsed.marketPreferences.pinned,
                  ...(untouchedPins ? ['BENELUX', 'FR'] : []),
                ],
              },
        ),
      },
      error: '',
    }
  } catch {
    return {
      state: emptyPersonalWorkspace(),
      error: 'Your market preferences could not be read. Existing browser data has been preserved.',
    }
  }
}
export function writePersonalWorkspace(
  storage: StorageAccess,
  edit: (value: PersonalWorkspace) => PersonalWorkspace,
) {
  const loaded = readPersonalWorkspace(storage)
  if (loaded.error) return loaded
  try {
    const state = edit(loaded.state)
    if (!validPersonalWorkspace(state)) throw new Error('Invalid preference data')
    storage.setItem(PERSONAL_WORKSPACE_KEY, JSON.stringify(state))
    return { state, error: '' }
  } catch {
    return {
      ...loaded,
      error: 'Your market preferences could not be saved in this browser.',
    }
  }
}
export function restoreSavedView(view: SavedView): Filters {
  return normaliseFilters(view.filters)
}
export function usePersonalWorkspace() {
  const initial = useRef<ReturnType<typeof readPersonalWorkspace> | null>(null)
  if (!initial.current) {
    try {
      initial.current = readPersonalWorkspace(window.localStorage)
    } catch {
      initial.current = {
        state: emptyPersonalWorkspace(),
        error: 'Personal storage is unavailable in this browser.',
      }
    }
  }
  const [state, setState] = useState(initial.current.state)
  const [storageError, setStorageError] = useState(initial.current.error)
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== PERSONAL_WORKSPACE_KEY && event.key !== null) return
      try {
        if (event.storageArea && event.storageArea !== window.localStorage) return
        const loaded = readPersonalWorkspace(window.localStorage)
        if (!loaded.error) setState(loaded.state)
        setStorageError(loaded.error)
      } catch {
        setStorageError('Personal storage is unavailable in this browser.')
      }
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  const editPreferences = useCallback((edit: (value: PersonalWorkspace) => PersonalWorkspace) => {
    try {
      const result = writePersonalWorkspace(window.localStorage, edit)
      if (!result.error) setState(result.state)
      setStorageError(result.error)
      return !result.error
    } catch {
      setStorageError('Your market preferences could not be saved in this browser.')
      return false
    }
  }, [])
  const arrangeMarkets = useCallback(
    (preferences: MarketPreferences) =>
      editPreferences((value) => ({
        ...value,
        marketPreferences: normaliseMarketPreferences(preferences),
      })),
    [editPreferences],
  )
  return { ...state, storageError, arrangeMarkets }
}
