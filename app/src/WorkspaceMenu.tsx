import { useEffect, useId, useMemo, useRef } from 'react'
import { Download, RefreshCw, Upload, X } from 'lucide-react'
import { SwitchGroup } from './Switch'
import type { Dataset, DisplayLanguage } from './types'
import { date, defaultMarketOptions, download, markets } from './lib'
import { createBackup, restoreBackup, setPreference, usePreferences } from './preferences'
import { countryCoverage } from './coverage'
import CoverageMap from './CoverageMap'
import './workspace-menu.css'

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  className = '',
}: {
  label: string
  value: T
  options: readonly (readonly [T, string])[]
  onChange: (value: T) => void
  className?: string
}) {
  const id = useId()
  const choices = useMemo(
    () => options.map(([key, text]) => ({ value: key, label: text })),
    [options],
  )
  return (
    <div className={`menu-setting ${className}`}>
      <span id={id}>{label}</span>
      <SwitchGroup labelledBy={id} value={value} options={choices} onChange={onChange} />
    </div>
  )
}

const ago = (value: string, now: number) => {
  const minutes = Math.max(0, Math.round((now - Date.parse(value)) / 60000))
  if (!Number.isFinite(minutes)) return ''
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  return hours < 48 ? `${hours} h ago` : `${Math.round(hours / 24)} days ago`
}

export function WorkspaceMenu({
  data,
  market,
  onMarket,
  language,
  onLanguage,
  compact,
  onCompact,
  loading,
  onRefresh,
  onClose,
  onNotice,
  now,
}: {
  data: Dataset | null
  market: string
  onMarket: (id: string) => void
  language: DisplayLanguage
  onLanguage: (value: DisplayLanguage) => void
  compact: boolean
  onCompact: (value: boolean) => void
  loading: boolean
  onRefresh: () => void
  onClose: () => void
  onNotice: (message: string) => void
  now: number
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const file = useRef<HTMLInputElement>(null)
  const preferences = usePreferences()
  const countries = useMemo(() => countryCoverage(data), [data])
  const selectedCountries: string[] = market
    ? [...(markets.find((m) => m.id === market)?.countries || [market])]
    : []
  const sources = (data?.sources || []).filter((source) => source.enabled)
  const health = ['healthy', 'partial', 'failed']
    .map((status) => [status, sources.filter((source) => source.status === status).length] as const)
    .filter(([, count]) => count)
  const allHealthy = sources.every((source) => source.status === 'healthy')
  useEffect(() => {
    const element = ref.current
    const opener = document.activeElement as HTMLElement | null
    element?.showModal()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      element?.close()
      document.body.style.overflow = previous
      if (opener?.isConnected) opener.focus({ preventScroll: true })
    }
  }, [])
  const restore = async (input: HTMLInputElement) => {
    const chosen = input.files?.[0]
    input.value = ''
    if (!chosen) return
    try {
      const result = restoreBackup(window.localStorage, await chosen.text())
      // Existing hooks listen for storage events; announce each restored key to them.
      for (const key of result.restored)
        window.dispatchEvent(
          new StorageEvent('storage', {
            key,
            newValue: window.localStorage.getItem(key),
            storageArea: window.localStorage,
          }),
        )
      onNotice(result.error || 'Backup restored')
    } catch {
      onNotice('This browser could not read the backup.')
    }
  }
  return (
    <dialog
      ref={ref}
      className="workspace-menu"
      aria-label="Workspace"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <header className="workspace-menu-top">
        <h2>Workspace</h2>
        <button className="icon-button" aria-label="Close workspace menu" onClick={onClose}>
          <X size={20} />
        </button>
      </header>
      <div className="workspace-menu-body">
        <section aria-labelledby="menu-preferences">
          <h3 id="menu-preferences">Preferences</h3>
          <Segmented
            label="Reading"
            value={preferences.reading}
            options={[
              ['brief', 'Brief'],
              ['full', 'Full text'],
            ]}
            onChange={(value) => setPreference('reading', value)}
          />
          <Segmented
            label="Recommended approach"
            value={preferences.approach}
            options={[
              ['show', 'Show'],
              ['hide', 'Hide'],
            ]}
            onChange={(value) => setPreference('approach', value)}
          />
          <Segmented
            label="Language"
            value={language}
            options={[
              ['en', 'English'],
              ['original', 'Original'],
            ]}
            onChange={onLanguage}
          />
          <Segmented
            label="Refiners"
            className="menu-setting-desktop"
            value={compact ? 'compact' : 'cards'}
            options={[
              ['cards', 'Cards'],
              ['compact', 'Compact'],
            ]}
            onChange={(value) => onCompact(value === 'compact')}
          />
          <Segmented
            label="Effects"
            value={preferences.effects}
            options={[
              ['full', 'Full'],
              ['reduced', 'Reduced'],
            ]}
            onChange={(value) => setPreference('effects', value)}
          />
          <label className="menu-setting">
            <span>Start in</span>
            <select
              value={preferences.startMarket}
              onChange={(event) => setPreference('startMarket', event.target.value)}
            >
              <option value="last">Last used</option>
              {defaultMarketOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </label>
        </section>

        <section aria-labelledby="menu-coverage">
          <h3 id="menu-coverage">Coverage</h3>
          {data ? (
            <CoverageMap
              countries={countries}
              selected={selectedCountries}
              onSelect={(id) => {
                onMarket(id)
                onClose()
              }}
            />
          ) : (
            <div className="coverage-placeholder" />
          )}
          {!!sources.length && (
            <details className="menu-sources">
              <summary>
                <span className={`status-dot ${allHealthy ? '' : 'amber'}`} />
                {health.map(([status, count]) => `${count} ${status}`).join(' · ')}
              </summary>
              <ul>
                {sources.map((source) => (
                  <li key={source.id}>
                    <span
                      className={`status-dot ${source.status === 'healthy' ? '' : 'amber'}`}
                      aria-hidden="true"
                    />
                    <span>{source.name}</span>
                    <small>{source.status}</small>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>

        <section aria-labelledby="menu-backup">
          <h3 id="menu-backup">Saved, hidden and settings</h3>
          <div className="menu-backup">
            <button
              onClick={() => {
                try {
                  download(
                    `anthrion-signal-backup-${new Date(now).toISOString().slice(0, 10)}.json`,
                    createBackup(window.localStorage, new Date(now)),
                    'application/json',
                  )
                  onNotice('Backup downloaded')
                } catch {
                  onNotice('This browser could not read your settings.')
                }
              }}
            >
              <Download size={15} />
              Export backup
            </button>
            <button onClick={() => file.current?.click()}>
              <Upload size={15} />
              Import backup
            </button>
            <input
              ref={file}
              type="file"
              accept=".json,application/json"
              hidden
              onChange={(event) => void restore(event.currentTarget)}
            />
          </div>
        </section>

        <section aria-labelledby="menu-shortcuts" className="menu-shortcuts">
          <h3 id="menu-shortcuts">Shortcuts</h3>
          <dl>
            {(
              [
                [['/'], 'Search'],
                [['J', 'K'], 'Next · previous'],
                [['S'], 'Save'],
                [['H'], 'Hide'],
                [['O'], 'Source notice'],
                [['C'], 'Context'],
                [['B'], 'Buyer history'],
                [['L'], 'English · original'],
                [['T'], 'Light · dark theme'],
                [['Esc'], 'Close'],
              ] as const
            ).map(([keys, action]) => (
              <div key={action}>
                <dt>
                  {keys.map((key) => (
                    <kbd key={key}>{key}</kbd>
                  ))}
                </dt>
                <dd>{action}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
      <footer className="workspace-menu-footer">
        <span>
          {data
            ? `Updated ${date(data.generated_at, {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
              })} · ${ago(data.generated_at, now)}`
            : 'Loading opportunities'}
        </span>
        <button
          className="icon-button"
          aria-label="Check for updates"
          title="Check for updates"
          disabled={loading}
          onClick={onRefresh}
        >
          <RefreshCw size={17} className={loading ? 'spin' : ''} />
        </button>
      </footer>
    </dialog>
  )
}
