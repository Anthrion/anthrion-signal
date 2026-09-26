import { useSyncExternalStore } from 'react'
import { PERSONAL_WORKSPACE_KEY, validPersonalWorkspace } from './personalWorkspace'

export const PREFERENCES_KEY = 'anthrion-preferences-v1'
export interface Preferences {
  /** Brief shows the opening passage of a notice; full shows the complete source text. */
  reading: 'full' | 'brief'
  /** Reviewed Recommended approach / Problems guidance. */
  approach: 'show' | 'hide'
  effects: 'full' | 'reduced'
  theme: 'dark' | 'light'
  /** Market for a plain visit, or 'last' to reopen the previous market. */
  startMarket: string
}
export const defaultPreferences: Preferences = {
  reading: 'full',
  approach: 'show',
  effects: 'full',
  theme: 'dark',
  startMarket: 'GB',
}
const choices: { [K in keyof Preferences]?: readonly string[] } = {
  reading: ['full', 'brief'],
  approach: ['show', 'hide'],
  effects: ['full', 'reduced'],
  theme: ['dark', 'light'],
}

export function normalisePreferences(value: unknown): Preferences {
  const result = { ...defaultPreferences }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return result
  const input = value as Record<string, unknown>
  for (const key of Object.keys(defaultPreferences) as (keyof Preferences)[]) {
    const candidate = input[key]
    if (typeof candidate !== 'string') continue
    const allowed = choices[key]
    if (allowed ? allowed.includes(candidate) : /^[A-Za-z]{0,16}$/.test(candidate))
      (result as Record<string, string>)[key] = candidate
  }
  return result
}

function read(): Preferences {
  try {
    return normalisePreferences(JSON.parse(localStorage.getItem(PREFERENCES_KEY) || 'null'))
  } catch {
    return { ...defaultPreferences }
  }
}

// One shared store: React views and the reduced-motion hook read the same value.
let current: Preferences = typeof window === 'undefined' ? { ...defaultPreferences } : read()
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((listener) => listener())
/** Page colours for each theme, for the browser chrome as well as the page itself. */
export const themeColour = { dark: '#151b19', light: '#f2f4f3' } as const
function applyDocument() {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.dataset.effects = current.effects
  root.dataset.theme = current.theme
  root.style.colorScheme = current.theme
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', themeColour[current.theme])
}
applyDocument()
if (typeof window !== 'undefined')
  window.addEventListener('storage', (event) => {
    if (event.key !== PREFERENCES_KEY && event.key !== null) return
    current = read()
    applyDocument()
    emit()
  })

export const getPreferences = () => current
export function subscribePreferences(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
/** Returns false when the browser refused to store the change; it still applies for this visit. */
export function setPreference<K extends keyof Preferences>(key: K, value: Preferences[K]) {
  current = normalisePreferences({ ...current, [key]: value })
  applyDocument()
  emit()
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(current))
    return true
  } catch {
    return false
  }
}
export function usePreferences() {
  return useSyncExternalStore(subscribePreferences, getPreferences, getPreferences)
}

/** Opening passage for Brief reading: the first paragraph, cut at a sentence near 600 characters. */
export function briefText(text: string, limit = 600) {
  const first =
    text
      .trim()
      .split(/\n\s*\n/)[0]
      ?.trim() || ''
  if (first.length <= limit) return { text: first, truncated: first.length < text.trim().length }
  const window = first.slice(0, limit)
  const sentence = Math.max(window.lastIndexOf('. '), window.lastIndexOf('; '))
  const cut = sentence > limit * 0.45 ? sentence + 1 : window.lastIndexOf(' ')
  return { text: `${first.slice(0, cut > 0 ? cut : limit).trimEnd()} …`, truncated: true }
}

// Browser-local backup of personal choices. Saved and hidden records merge; settings replace.
const listKeys = ['anthrion-saved-v1', 'anthrion-hidden-v1'] as const
const settingKeys = [
  'anthrion-language-v1',
  'anthrion-compact-reading-v1',
  'anthrion-pane-ratio-v1',
  PERSONAL_WORKSPACE_KEY,
  PREFERENCES_KEY,
] as const
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === 'string' && item.length <= 200)
const validators: Record<string, (value: unknown) => boolean> = {
  'anthrion-saved-v1': strings,
  'anthrion-hidden-v1': strings,
  'anthrion-language-v1': (value) => value === 'en' || value === 'original',
  'anthrion-compact-reading-v1': (value) => typeof value === 'boolean',
  'anthrion-pane-ratio-v1': (value) => typeof value === 'number' && value >= 30 && value <= 70,
  [PERSONAL_WORKSPACE_KEY]: validPersonalWorkspace,
  [PREFERENCES_KEY]: (value) => !!value && typeof value === 'object' && !Array.isArray(value),
}

export function createBackup(storage: Pick<Storage, 'getItem'>, now = new Date()) {
  const entries: Record<string, unknown> = {}
  for (const key of [...listKeys, ...settingKeys]) {
    try {
      const value: unknown = JSON.parse(storage.getItem(key) || 'null')
      if (value !== null && validators[key](value)) entries[key] = value
    } catch {
      /* A malformed entry is left out rather than blocking the rest of the backup. */
    }
  }
  return JSON.stringify(
    { app: 'anthrion-signal', version: 1, exported_at: now.toISOString(), entries },
    null,
    2,
  )
}

export function restoreBackup(storage: Pick<Storage, 'getItem' | 'setItem'>, text: string) {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return { restored: [] as string[], error: 'This file is not a Signal backup.' }
  }
  const backup = parsed as { app?: unknown; version?: unknown; entries?: unknown }
  if (
    !backup ||
    backup.app !== 'anthrion-signal' ||
    backup.version !== 1 ||
    !backup.entries ||
    typeof backup.entries !== 'object'
  )
    return { restored: [] as string[], error: 'This file is not a Signal backup.' }
  const entries = backup.entries as Record<string, unknown>
  const restored: string[] = []
  for (const key of [...listKeys, ...settingKeys]) {
    const value = entries[key]
    if (value === undefined || !validators[key](value)) continue
    let next = value
    if ((listKeys as readonly string[]).includes(key)) {
      let existing: string[] = []
      try {
        const stored: unknown = JSON.parse(storage.getItem(key) || '[]')
        if (strings(stored)) existing = stored
      } catch {
        /* Replace unreadable lists with the backup. */
      }
      next = [...new Set([...existing, ...(value as string[])])]
    }
    if (key === PREFERENCES_KEY) next = normalisePreferences(value)
    try {
      storage.setItem(key, JSON.stringify(next))
      restored.push(key)
    } catch {
      return { restored, error: 'This browser could not store the backup.' }
    }
  }
  return { restored, error: restored.length ? '' : 'The backup contained no Signal settings.' }
}
