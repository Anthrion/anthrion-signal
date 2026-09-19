import { useCallback, useEffect, useRef, useState } from 'react'
import { defaultMarketOptions, defaultMarketGroup, normaliseFilters } from './lib'
import type { Filters } from './types'

export const PERSONAL_WORKSPACE_KEY = 'anthrion-personal-workspace-v1'
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
const identifier = () =>
  globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
export function emptyPersonalWorkspace(): PersonalWorkspace {
  return {
    version: 1,
    savedViews: [],
    marketPreferences: {
      pinned: ['GB', 'US', 'IT', 'NORDICS', 'DACH', 'ES', 'GR'],
      order: defaultMarketOptions.map((m) => m.id),
    },
  }
}
export function normaliseMarketPreferences(value: MarketPreferences): MarketPreferences {
  const known = new Set<string>(defaultMarketOptions.map((m) => m.id))
  const group = defaultMarketGroup
  return {
    order: [
      ...new Set([
        ...value.order.map(group).filter((id) => known.has(id)),
        ...defaultMarketOptions.map((m) => m.id),
      ]),
    ],
    pinned: [...new Set(value.pinned.map(group).filter((id) => known.has(id)))],
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
    return {
      state: {
        version: 1,
        savedViews: parsed.savedViews.map((v) => ({
          ...v,
          filters: normaliseFilters(v.filters),
          showHidden: v.showHidden ?? false,
        })),
        marketPreferences: normaliseMarketPreferences(parsed.marketPreferences),
      },
      error: '',
    }
  } catch {
    return {
      state: emptyPersonalWorkspace(),
      error:
        'Your saved views and market preferences could not be read. Existing browser data has been preserved.',
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
      error: 'Your views and market preferences could not be saved in this browser.',
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
      setStorageError('Your views and market preferences could not be saved in this browser.')
      return false
    }
  }, [])
  const saveView = useCallback(
    (name: string, filters: Filters, showHidden = false) => {
      if (!name.trim()) return false
      return editPreferences((value) => ({
        ...value,
        savedViews: [
          ...value.savedViews,
          {
            id: identifier(),
            name: name.trim(),
            filters: normaliseFilters(filters),
            showHidden,
            createdAt: new Date().toISOString(),
          },
        ],
      }))
    },
    [editPreferences],
  )
  const removeView = useCallback(
    (id: string) =>
      editPreferences((value) => ({
        ...value,
        savedViews: value.savedViews.filter((v) => v.id !== id),
      })),
    [editPreferences],
  )
  const arrangeMarkets = useCallback(
    (preferences: MarketPreferences) =>
      editPreferences((value) => ({
        ...value,
        marketPreferences: normaliseMarketPreferences(preferences),
      })),
    [editPreferences],
  )
  return { ...state, storageError, saveView, removeView, arrangeMarkets }
}
