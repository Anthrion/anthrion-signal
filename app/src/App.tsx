import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Bookmark,
  BookmarkCheck,
  Building2,
  CalendarClock,
  CalendarPlus,
  CalendarDays,
  Check,
  Clock3,
  Copy,
  ExternalLink,
  FileSearch,
  FileText,
  Globe2,
  Layers3,
  PanelTopClose,
  PanelTopOpen,
  Radar,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Target,
  X,
} from 'lucide-react'
import type { Dataset, DisplayLanguage, EnglishText, Filters, Signal } from './types'
import { TranslationProvider, useSignalText } from './Translation'
import {
  AmbientGlass,
  BrandSignature,
  MarketSection,
  MetalEdge,
  SortMenu,
  SourceNoticeLink,
  useReducedMotion,
} from './WorkspaceUI'
import { DiscoveryCarousel } from './DiscoveryCarousel'
import { VirtualSignalList } from './VirtualSignalList'
import { DismissDust } from './DismissDust'
import { useAwardHistory } from './useAwardHistory'
import { historySupplierScope, supplierHistoryMarket } from './supplierResearch'
import { distinctSources } from './researchPresentation'
import { useOpportunityData, useSignalDetail } from './useOpportunityData'
import {
  initialWorkspaceFilters,
  rememberLastView,
  usePersonalWorkspace,
} from './personalWorkspace'
import { deadlineEventCalendarURL } from './publicFacts'
import {
  BuyerLink,
  CapabilityTags,
  DeadlineEvents,
  deadlineFact,
  PaneDivider,
  ProcurementHistory,
  ResearchPage,
  ResearchProvider,
  ResearchTitle,
  SearchWorkspace,
  SourceDocuments,
  SupplierLinks,
  valueFact,
} from './ResearchUI'
import type { ResearchState } from './ResearchUI'
import {
  csv,
  countryLabels,
  isCombinedMarket,
  currencyOptions,
  date,
  defaults,
  download,
  explainSearch,
  filterSignals,
  gmailDraftURL,
  googleCalendarURL,
  isAvailableOpportunity,
  isHistoricalAward,
  hasAwardOutcome,
  isUpdated,
  lifecycleLabels,
  lifecycleState,
  markets,
  matchesMarket,
  responseDeadline,
  marketIsEnabled,
  readFilters,
  normaliseFilters,
  selectedResponseDeadlineEvent,
  typeLabels,
} from './lib'

const navItems = [
  { id: 'all', label: 'All Signals', icon: Layers3 },
  { id: 'live', label: 'Live Opportunities', icon: Target },
  { id: 'early', label: 'Pre-market', icon: Radar },
  { id: 'closing', label: 'Closing Soon', icon: CalendarClock },
  { id: 'today', label: 'Added today', icon: CalendarDays },
]

function useLocal<T>(key: string, initial: T, validate: (value: unknown) => value is T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem(key) || 'null')
      return validate(stored) ? stored : initial
    } catch {
      return initial
    }
  })
  const valueRef = useRef(value)
  const [storageError, setStorageError] = useState(false)
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(valueRef.current))
      setStorageError(false)
    } catch {
      setStorageError(true)
    }
  }, [key])
  const updateValue = useCallback(
    (update: React.SetStateAction<T>) => {
      let current = valueRef.current
      try {
        const stored: unknown = JSON.parse(localStorage.getItem(key) || 'null')
        if (validate(stored)) current = stored
      } catch {
        /* Keep usable in-memory preferences when storage is unavailable. */
      }
      const next = typeof update === 'function' ? (update as (previous: T) => T)(current) : update
      valueRef.current = next
      try {
        localStorage.setItem(key, JSON.stringify(next))
        setStorageError(false)
      } catch {
        setStorageError(true)
      }
      setValue(next)
    },
    [key, validate],
  )
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      try {
        if (event.storageArea !== localStorage || event.key !== key) return
        const stored: unknown = JSON.parse(event.newValue || 'null')
        if (validate(stored)) {
          valueRef.current = stored
          setValue(stored)
        }
      } catch {
        /* Keep the last valid preferences if storage is malformed. */
      }
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [key, validate])
  return [value, updateValue, storageError] as const
}

const validSaved = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((id) => typeof id === 'string')
const validLanguage = (value: unknown): value is DisplayLanguage =>
  value === 'en' || value === 'original'

function IconButton({
  label,
  children,
  className = '',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button {...props} aria-label={label} title={label} className={`icon-button ${className}`}>
      {children}
    </button>
  )
}
function Modal({
  title,
  children,
  onClose,
  wide = false,
  drawer = false,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  wide?: boolean
  drawer?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current
    el?.showModal()
    el?.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      el?.close()
      document.body.style.overflow = previous
    }
  }, [])
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? 'wide' : ''} ${drawer ? 'drawer' : ''}`}
      aria-label={title}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal-top">
        <span>{title}</span>
        <IconButton label="Close panel" onClick={onClose}>
          <X size={20} />
        </IconButton>
      </div>
      {children}
    </dialog>
  )
}

function WorkspaceProviders({
  language,
  translations,
  children,
}: {
  language: DisplayLanguage
  translations: Dataset['translations']
  children: ReactNode
}) {
  return (
    <MotionConfig reducedMotion="user">
      <TranslationProvider language={language} translations={translations}>
        {children}
      </TranslationProvider>
    </MotionConfig>
  )
}

export default function App() {
  const [filters, setFilters] = useState<Filters>(initialWorkspaceFilters)
  const { data, error, loading, reload: load } = useOpportunityData({ market: filters.market })
  const personal = usePersonalWorkspace()
  useEffect(() => {
    try {
      rememberLastView(window.localStorage, filters)
    } catch {
      /* Storage is optional. */
    }
  }, [filters])
  const [researchStack, setResearchStack] = useState<
    (ResearchState & { translation?: EnglishText })[]
  >([])
  const research = researchStack.at(-1) || null
  const [compact, setCompact] = useLocal(
    'anthrion-compact-reading-v1',
    false,
    (value): value is boolean => typeof value === 'boolean',
  )
  const [paneRatio, setPaneRatio] = useLocal(
    'anthrion-pane-ratio-v1',
    50,
    (value): value is number => typeof value === 'number' && value >= 30 && value <= 70,
  )
  const [language, setLanguage] = useLocal<DisplayLanguage>(
    'anthrion-language-v1',
    'en',
    validLanguage,
  )
  const [saved, setSaved, storageError] = useLocal<string[]>('anthrion-saved-v1', [], validSaved)
  const [hidden, setHidden, hiddenStorageError] = useLocal<string[]>(
    'anthrion-hidden-v1',
    [],
    validSaved,
  )
  const [showHidden, setShowHidden] = useState(false)
  const [departing, setDeparting] = useState<Record<string, 'hide' | 'unhide'>>({})
  const pendingDepartures = useRef(
    new Map<string, { timer: ReturnType<typeof setTimeout>; complete: () => void }>(),
  )
  const pendingRowFocus = useRef<number | null>(null)
  const reducedMotion = useReducedMotion()
  const [showFilters, setShowFilters] = useState(false)
  const [detailOpen, setDetailOpen] = useState(
    () =>
      !!new URLSearchParams(location.search).get('signal') &&
      window.matchMedia('(max-width: 900px)').matches,
  )
  const [selected, setSelected] = useState<string | null>(() =>
    new URLSearchParams(location.search).get('signal'),
  )
  const [detailTab, setDetailTab] = useState('preview')
  const [toast, setToast] = useState('')
  const [time, setTime] = useState(Date.now())
  const viewingAwards = filters.view === 'awards'
  const viewingSaved = filters.view === 'saved'
  const needsSavedHistory =
    viewingSaved && saved.some((id) => !data?.signals.some((s) => s.id === id))
  const supplierPage = researchStack.filter((page) => page.kind === 'supplier').at(-1)
  const supplierMarket = supplierPage?.supplier
    ? supplierHistoryMarket(
        supplierPage.supplierRecord
          ? historySupplierScope(supplierPage.supplierRecord, data || undefined)
          : supplierPage.signal,
        supplierPage.supplier,
      )
    : ''
  const reuseMarketAwards = supplierMarket === filters.market || !filters.market
  const awards = useAwardHistory(
    data,
    viewingAwards ||
      needsSavedHistory ||
      researchStack.some((page) => page.kind === 'related') ||
      (!!supplierPage && reuseMarketAwards),
    filters.market,
  )
  const separateSupplierHistory = useAwardHistory(
    data,
    !!supplierPage && !reuseMarketAwards,
    supplierMarket,
  )
  const supplierHistory = reuseMarketAwards ? awards : separateSupplierHistory
  const feedHistoryLoading = (viewingAwards || needsSavedHistory) && awards.loading
  const feedHistoryError = viewingAwards || needsSavedHistory ? awards.error : ''
  const activeSignals = useMemo(
    () =>
      viewingAwards
        ? awards.signals
        : viewingSaved
          ? [...(data?.signals || []), ...awards.signals]
          : data?.signals || [],
    [viewingAwards, viewingSaved, data, awards.signals],
  )
  const translations = useMemo(
    () => ({ ...data?.translations, ...awards.translations }),
    [data?.translations, awards.translations],
  )
  const searchRef = useRef<HTMLInputElement>(null)
  const feedRef = useRef<HTMLDivElement>(null)
  useEffect(() => () => pendingDepartures.current.forEach(({ timer }) => clearTimeout(timer)), [])
  useEffect(() => {
    if (reducedMotion) pendingDepartures.current.forEach(({ complete }) => complete())
  }, [reducedMotion])
  useEffect(() => {
    const interval = setInterval(() => setTime(Date.now()), 60000)
    return () => clearInterval(interval)
  }, [])
  useEffect(() => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== defaults[key as keyof Filters]) params.set(key, value)
    })
    if (selected) params.set('signal', selected)
    history.replaceState(null, '', `${location.pathname}${params.size ? `?${params}` : ''}`)
  }, [filters, selected])
  useEffect(() => {
    const handler = () => {
      setFilters(readFilters())
      setSelected(new URLSearchParams(location.search).get('signal'))
      setDetailOpen(
        !!new URLSearchParams(location.search).get('signal') &&
          window.matchMedia('(max-width: 900px)').matches,
      )
    }
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [])
  useEffect(() => {
    if (toast) {
      const timeout = setTimeout(() => setToast(''), 3500)
      return () => clearTimeout(timeout)
    }
  }, [toast])
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (
        e.key === '/' &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
  const update = (patch: Partial<Filters>) => {
    setFilters((f) => normaliseFilters({ ...f, ...patch }))
    setSelected(null)
    setDetailOpen(false)
  }
  const navigate = (view: string) => {
    update({ view })
  }
  const toggleSave = (id: string) =>
    setSaved((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  const open = (id: string, tab = 'overview') => {
    setSelected(id)
    setDetailTab(tab === 'overview' ? 'preview' : tab)
    setDetailOpen(tab !== 'overview' || window.matchMedia('(max-width: 900px)').matches)
  }
  const hiddenIds = useMemo(() => new Set(hidden), [hidden])
  const visibleSignals = useMemo(
    () => activeSignals.filter((s) => hiddenIds.has(s.id) === showHidden),
    [activeSignals, hiddenIds, showHidden],
  )
  const filtered = useMemo(
    () => filterSignals(visibleSignals, filters, saved, time, data?.capabilities, translations),
    [data, visibleSignals, filters, saved, time, translations],
  )
  // Outgoing rows are visual only; counts, selection and export use saved intent immediately.
  const renderedFiltered = useMemo(() => {
    if (!Object.keys(departing).length) return filtered
    const visual = activeSignals.filter((s) => {
      const phase = departing[s.id]
      return (phase ? phase === 'unhide' : hiddenIds.has(s.id)) === showHidden
    })
    return filterSignals(visual, filters, saved, time, data?.capabilities, translations)
  }, [
    data,
    activeSignals,
    departing,
    filtered,
    filters,
    hiddenIds,
    saved,
    showHidden,
    time,
    translations,
  ])
  const marketSignals = useMemo(
    () =>
      (data?.signals || []).filter(
        (s) =>
          hiddenIds.has(s.id) === showHidden &&
          isAvailableOpportunity(s, time) &&
          matchesMarket(s, filters.market),
      ),
    [data, hiddenIds, showHidden, filters.market, time],
  )
  const marketName =
    markets.find((m) => m.id === filters.market)?.name ||
    data?.markets[filters.market]?.name ||
    (filters.market ? `Market ${filters.market}` : 'All markets')
  const marketEnabled = data
    ? marketIsEnabled(filters.market, data.markets)
    : filters.market === 'GB'
  const fresh = !!data && time - Date.parse(data.generated_at) < 26 * 3600000
  const activeFilterCount = Object.entries(filters).filter(
    ([k, v]) =>
      !['q', 'view', 'sort', 'market', 'searchMode', 'match'].includes(k) &&
      v !== defaults[k as keyof Filters],
  ).length
  const selectedSummary = selected
    ? visibleSignals.find(
        (s) =>
          s.id === selected &&
          (viewingAwards
            ? isHistoricalAward(s, time)
            : isAvailableOpportunity(s, time) || (viewingSaved && isHistoricalAward(s, time))),
      )
    : filtered[0]
  const detail = useSignalDetail(data, selectedSummary || selected)
  const selectedSignal = detail.signal || selectedSummary
  const displayTranslations = useMemo(
    () => ({
      ...translations,
      ...(detail.translation && selectedSignal ? { [selectedSignal.id]: detail.translation } : {}),
    }),
    [translations, detail.translation, selectedSignal],
  )
  const researchTranslations = useMemo(() => {
    const result = { ...translations }
    Object.assign(result, supplierHistory.translations)
    for (const page of researchStack) {
      delete result[page.signal.id]
      if (page.translation) result[page.signal.id] = page.translation
    }
    return result
  }, [translations, supplierHistory.translations, researchStack])
  useEffect(() => {
    if (
      !research ||
      detail.loading ||
      detail.error ||
      !detail.signal ||
      detail.signal.is_summary ||
      detail.signal.id !== research.signal.id ||
      detail.signal === research.signal
    )
      return
    setResearchStack((pages) =>
      pages.map((page) =>
        page === research
          ? {
              ...page,
              signal: detail.signal!,
              translation: detail.translation || translations[detail.signal!.id],
            }
          : page,
      ),
    )
  }, [research, detail.signal, detail.translation, detail.loading, detail.error, translations])
  useEffect(() => {
    if (
      selected &&
      activeSignals.some((s) => s.id === selected) &&
      hiddenIds.has(selected) !== showHidden
    ) {
      setSelected(null)
      setDetailOpen(false)
    }
  }, [selected, activeSignals, hiddenIds, showHidden])
  useEffect(() => {
    if (pendingRowFocus.current === null) return
    const next = filtered[Math.min(pendingRowFocus.current, filtered.length - 1)]
    pendingRowFocus.current = null
    const frame = requestAnimationFrame(() => {
      const button =
        next &&
        feedRef.current?.querySelector<HTMLButtonElement>(
          `[data-signal-id="${CSS.escape(next.id)}"] .row-select`,
        )
      if (button) button.focus({ preventScroll: true })
      else feedRef.current?.focus({ preventScroll: true })
    })
    return () => cancelAnimationFrame(frame)
  }, [hidden, filtered, departing])
  const dismiss = (id: string) => {
    if (pendingDepartures.current.has(id)) return
    const restoring = hiddenIds.has(id)
    const focusOrigin = document.activeElement
    const hadRowFocus = !!feedRef.current
      ?.querySelector(`[data-signal-id="${CSS.escape(id)}"]`)
      ?.contains(focusOrigin)
    let completed = false
    const commit = () => {
      if (completed) return
      completed = true
      clearTimeout(pendingDepartures.current.get(id)?.timer)
      pendingDepartures.current.delete(id)
      if (
        hadRowFocus &&
        (document.activeElement === focusOrigin || document.activeElement === document.body)
      )
        pendingRowFocus.current = filtered.findIndex((s) => s.id === id)
      setDeparting((current) => {
        const next = { ...current }
        delete next[id]
        return next
      })
    }
    setHidden((ids) =>
      restoring ? ids.filter((existing) => existing !== id) : ids.includes(id) ? ids : [...ids, id],
    )
    if (reducedMotion) commit()
    else {
      setDeparting((current) => ({ ...current, [id]: restoring ? 'unhide' : 'hide' }))
      // Unhide follows the CSS animation, with a fallback if its row leaves the viewport.
      pendingDepartures.current.set(id, {
        timer: setTimeout(commit, restoring ? 2000 : 620),
        complete: commit,
      })
    }
  }
  useEffect(() => {
    if (
      selected &&
      selectedSignal &&
      isHistoricalAward(selectedSignal) &&
      !viewingAwards &&
      !viewingSaved
    ) {
      setFilters((current) => ({ ...current, view: 'awards' }))
      return
    }
    if (!selected || !selectedSignal || matchesMarket(selectedSignal, filters.market)) return
    const market = markets.find((m) =>
      selectedSignal.countries.some((c) => (m.countries as readonly string[]).includes(c)),
    )
    setFilters({
      ...defaults,
      market: market?.id || selectedSignal.countries[0] || 'GB',
      view: isHistoricalAward(selectedSignal) ? 'awards' : 'all',
    })
  }, [selected, selectedSignal, filters.market, viewingAwards, viewingSaved])
  const listTitle =
    navItems.find((n) => n.id === filters.view)?.label ||
    { saved: 'Saved opportunities', awards: 'Awarded contracts' }[filters.view] ||
    'All signals'
  const share = async () => {
    try {
      await navigator.clipboard.writeText(location.href)
      setToast('View link copied')
    } catch {
      setToast('Use the address bar to share this view')
    }
  }
  const counts = useMemo(
    () =>
      Object.fromEntries(
        navItems.map((n) => [
          n.id,
          filterSignals(
            marketSignals,
            { ...defaults, market: filters.market, view: n.id },
            [],
            time,
          ).length,
        ]),
      ),
    [marketSignals, filters.market, time],
  )
  const switchMarket = (id: string) => {
    update({ market: id, source: '', region: '', buyer: '', cpv: '' })
  }

  return (
    <WorkspaceProviders language={language} translations={displayTranslations}>
      <ResearchProvider
        open={(value) => {
          setDetailOpen(false)
          setResearchStack((pages) => [
            ...pages,
            {
              ...value,
              translation:
                value.translation ||
                displayTranslations[value.signal.id] ||
                researchTranslations[value.signal.id],
            },
          ])
        }}
      >
        <div className={`app-shell console-shell ${compact ? 'compact-reading' : ''}`}>
          <AmbientGlass />
          <a className="skip-link" href="#main">
            Skip to opportunities
          </a>

          <main id="main" className="workspace-main">
            <header className="workspace-header">
              <BrandSignature onHome={() => update({ ...defaults, market: filters.market })} />
              <div className="workspace-search" role="search" aria-label="Opportunity search">
                <label className="search-box">
                  <Search size={16} />
                  <input
                    ref={searchRef}
                    aria-label="Search opportunities"
                    value={filters.q}
                    onChange={(e) => update({ q: e.target.value })}
                    placeholder="Search opportunities, buyers, keywords..."
                  />
                  {filters.q && (
                    <IconButton label="Clear search" onClick={() => update({ q: '' })}>
                      <X size={13} />
                    </IconButton>
                  )}
                </label>
                <button
                  aria-label="Filters"
                  title="Filters"
                  className={`button filter-button ${activeFilterCount ? 'has-filters' : ''}`}
                  onClick={() => setShowFilters(true)}
                >
                  <SlidersHorizontal size={16} />
                  <span>Filters</span>
                  {activeFilterCount > 0 && (
                    <span className="filter-count">{activeFilterCount}</span>
                  )}
                </button>
                <SortMenu
                  value={viewingAwards ? 'awarded' : filters.sort}
                  onChange={(sort) =>
                    update(
                      sort === 'awarded'
                        ? { view: 'awards', sort: 'recent', type: '', deadline: '', change: '' }
                        : { sort, ...(viewingAwards ? { view: 'all' } : {}) },
                    )
                  }
                  showHidden={showHidden}
                  onShowHidden={(value) => {
                    setShowHidden(value)
                    setSelected(null)
                    setDetailOpen(false)
                  }}
                />
              </div>
              <nav className="workspace-nav" aria-label="Workspace">
                <button
                  title="Saved opportunities"
                  aria-current={filters.view === 'saved' ? 'page' : undefined}
                  onClick={() => navigate('saved')}
                >
                  <Bookmark size={17} />
                  <span className="workspace-nav-label">Saved opportunities</span>
                  <small>
                    {
                      saved.filter(
                        (id) =>
                          marketSignals.some((s) => s.id === id) ||
                          (data?.current_feed?.records[id]?.view === 'awards' &&
                            (!filters.market ||
                              data.current_feed.records[id].markets.includes(filters.market)) &&
                            hiddenIds.has(id) === showHidden) ||
                          awards.knownSignals.some(
                            (s) =>
                              s.id === id &&
                              matchesMarket(s, filters.market) &&
                              hiddenIds.has(id) === showHidden,
                          ),
                      ).length
                    }
                  </small>
                </button>
              </nav>
              <div className="workspace-tools">
                <IconButton
                  label={compact ? 'Exit compact reading mode' : 'Compact reading mode'}
                  aria-pressed={compact}
                  onClick={() => setCompact(!compact)}
                >
                  {compact ? <PanelTopOpen size={17} /> : <PanelTopClose size={17} />}
                </IconButton>
                <IconButton
                  label="Check for updates"
                  onClick={() => void load()}
                  disabled={loading}
                >
                  <RefreshCw size={17} className={loading ? 'spin' : ''} />
                </IconButton>
              </div>
            </header>
            <div className="workspace-content">
              <MarketSection
                selected={filters.market}
                onSelect={switchMarket}
                language={language}
                onLanguage={setLanguage}
                preferences={personal.marketPreferences}
                onArrange={personal.arrangeMarkets}
              />
              {(error || (!fresh && data)) && (
                <div className="alert" role="status">
                  <Clock3 size={17} />
                  <span>
                    {error ||
                      `The feed was last refreshed ${date(data!.generated_at)}. Confirm current availability in the source notice.`}
                  </span>
                  <button onClick={() => void load()}>
                    Retry <RefreshCw size={13} />
                  </button>
                </div>
              )}
              {(storageError || hiddenStorageError) && (
                <div className="alert" role="status">
                  {hiddenStorageError
                    ? 'Hidden opportunities could not be saved in this browser. They may reappear after reloading.'
                    : 'Your browser could not save these opportunities. Export them to keep a copy.'}
                </div>
              )}
              {personal.storageError && (
                <div className="alert" role="status">
                  {personal.storageError}
                </div>
              )}

              <div className="discovery-band">
                {compact ? (
                  <nav className="compact-refiners" aria-label="Opportunity views">
                    {navItems.map(({ id, label }) => (
                      <button
                        key={id}
                        aria-pressed={filters.view === id}
                        onClick={() => {
                          setSelected(null)
                          setFilters({
                            ...defaults,
                            market: filters.market,
                            view: id,
                            sort: id === 'closing' ? 'deadline' : 'recent',
                          })
                        }}
                      >
                        {label}
                        <small>{counts[id] || 0}</small>
                      </button>
                    ))}
                  </nav>
                ) : (
                  <DiscoveryCarousel
                    items={navItems}
                    counts={counts}
                    selected={filters.view}
                    loading={!data}
                    onSelect={(view) => {
                      setSelected(null)
                      setFilters({
                        ...defaults,
                        market: filters.market,
                        view,
                        sort: view === 'closing' ? 'deadline' : 'recent',
                      })
                    }}
                  />
                )}
                <div className="discovery-export">
                  <IconButton
                    label="Export signals"
                    disabled={!data || !filtered.length}
                    onClick={() => {
                      download(
                        `anthrion-signals-${new Date().toISOString().slice(0, 10)}.csv`,
                        csv(filtered),
                        'text/csv;charset=utf-8',
                      )
                      setToast(`${filtered.length} signals exported`)
                    }}
                  >
                    <ArrowDownToLine size={18} />
                  </IconButton>
                </div>
              </div>
              <div className="feed-layout">
                <SearchWorkspace
                  filters={filters}
                  update={update}
                  data={data}
                  count={filtered.length}
                />
                <div
                  className="feed-heading screen-reader-only"
                  aria-live="polite"
                  aria-atomic="true"
                >
                  <h1>{listTitle}</h1>
                  <span className="count-badge">{filtered.length}</span>
                </div>
                <section
                  className="opportunity-console"
                  aria-label="Opportunity feed"
                  style={{ '--feed-ratio': paneRatio } as React.CSSProperties}
                >
                  <div
                    ref={feedRef}
                    className="signal-feed"
                    role="region"
                    aria-label="Opportunity records"
                    tabIndex={0}
                  >
                    {(loading && !data) || feedHistoryLoading ? (
                      <div className="loading-feed" aria-label="Loading opportunities">
                        {[1, 2, 3, 4, 5].map((i) => (
                          <div key={i} className="skeleton signal-skeleton" />
                        ))}
                      </div>
                    ) : (
                      <VirtualSignalList
                        signals={renderedFiltered}
                        scrollRef={feedRef}
                        resetKey={`${JSON.stringify(filters)}:${showHidden}`}
                        shiftKey={hidden.join('|')}
                        renderRow={(signal) => (
                          <SignalRow
                            key={signal.id}
                            signal={signal}
                            filters={filters}
                            data={data}
                            selected={selectedSignal?.id === signal.id}
                            saved={saved.includes(signal.id)}
                            hidden={
                              departing[signal.id]
                                ? departing[signal.id] === 'unhide'
                                : hiddenIds.has(signal.id)
                            }
                            departure={departing[signal.id]}
                            onDepartureEnd={() =>
                              pendingDepartures.current.get(signal.id)?.complete()
                            }
                            onSave={() => toggleSave(signal.id)}
                            onOpen={(tab) => open(signal.id, tab)}
                            onHide={() => dismiss(signal.id)}
                            now={time}
                          />
                        )}
                      />
                    )}
                    {feedHistoryError && (
                      <div className="empty-state" role="alert">
                        <h3>{feedHistoryError}</h3>
                        <button
                          className="button secondary"
                          onClick={() => {
                            awards.retry()
                            void load()
                          }}
                        >
                          Try again
                        </button>
                      </div>
                    )}
                    {!loading &&
                      !feedHistoryLoading &&
                      !feedHistoryError &&
                      renderedFiltered.length === 0 && (
                        <div className="empty-state">
                          {marketEnabled ? <FileSearch size={30} /> : <Globe2 size={30} />}
                          <h3>
                            {!marketEnabled
                              ? `No signals for ${marketName}`
                              : showHidden
                                ? 'No hidden signals'
                                : filters.view === 'saved'
                                  ? 'No saved opportunities'
                                  : 'No matching signals'}
                          </h3>
                          <p>
                            {!marketEnabled
                              ? 'There are no monitored sources in this market yet.'
                              : showHidden
                                ? 'No hidden signals match this market and these filters.'
                                : filters.view === 'saved'
                                  ? 'Your saved opportunities will appear here.'
                                  : 'Try a broader search or adjust your filters.'}
                          </p>
                          <button
                            className="button secondary"
                            onClick={() =>
                              showHidden
                                ? setShowHidden(false)
                                : !marketEnabled
                                  ? switchMarket('GB')
                                  : update({ ...defaults, market: filters.market, view: 'all' })
                            }
                          >
                            {showHidden
                              ? 'Return to signals'
                              : marketEnabled
                                ? 'Explore all signals'
                                : 'Explore United Kingdom'}
                            <ArrowRight size={14} />
                          </button>
                        </div>
                      )}
                  </div>
                  <PaneDivider value={paneRatio} onChange={setPaneRatio} />
                  <aside
                    className="console-inspector"
                    id="selected-opportunity"
                    aria-label="Selected opportunity"
                    tabIndex={0}
                  >
                    {detail.loading ? (
                      <div className="inspector-empty" role="status">
                        <FileSearch size={25} />
                        <span>Loading full record…</span>
                      </div>
                    ) : detail.error ? (
                      <div className="inspector-empty" role="alert">
                        <span>{detail.error}</span>
                        <button className="button secondary" onClick={detail.retry}>
                          Try again
                        </button>
                      </div>
                    ) : selectedSignal && data ? (
                      <ConsoleDetail
                        signal={selectedSignal}
                        data={data}
                        onInspect={(tab) => {
                          setSelected(selectedSignal.id)
                          setDetailTab(tab)
                          setDetailOpen(true)
                        }}
                      />
                    ) : (
                      <div className="inspector-empty">
                        <FileSearch size={30} />
                        <span>{loading ? 'Loading opportunities' : 'No opportunity selected'}</span>
                      </div>
                    )}
                  </aside>
                </section>
              </div>
            </div>
          </main>
          <AnimatePresence>
            {toast && (
              <motion.div
                role="status"
                className="toast"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Check size={16} />
                {toast}
              </motion.div>
            )}
          </AnimatePresence>
          {showFilters && data && (
            <Modal title="Refine opportunities" onClose={() => setShowFilters(false)}>
              <FilterPanel
                filters={filters}
                update={update}
                data={viewingAwards || viewingSaved ? { ...data, signals: activeSignals } : data}
                count={filtered.length}
                onClose={() => setShowFilters(false)}
                onReset={() => update({ ...defaults, view: filters.view, market: filters.market })}
              />
            </Modal>
          )}
          {data &&
            researchStack.map((page, index) => (
              <TranslationProvider
                key={`${index}-${page.kind}-${page.signal.id}`}
                language={language}
                translations={researchTranslations}
              >
                <ResearchPage
                  state={page}
                  now={time}
                  active={index === researchStack.length - 1}
                  data={data}
                  language={language}
                  onLanguage={setLanguage}
                  renderRecord={(signal) => <ResearchRecord signal={signal} data={data} />}
                  awards={page.kind === 'supplier' ? supplierHistory.signals : awards.signals}
                  loading={page.kind === 'supplier' ? supplierHistory.loading : awards.loading}
                  error={page.kind === 'supplier' ? supplierHistory.error : awards.error}
                  onRetry={page.kind === 'supplier' ? supplierHistory.retry : awards.retry}
                  nested={index > 0}
                  onBack={() => setResearchStack((pages) => pages.slice(0, -1))}
                  onHome={() => {
                    setResearchStack([])
                    update(defaults)
                  }}
                />
              </TranslationProvider>
            ))}
          {detailOpen && selectedSignal && data && (
            <Modal
              title="Opportunity intelligence"
              onClose={() => setDetailOpen(false)}
              wide
              drawer
            >
              {detail.loading ? (
                <div className="inspector-empty" role="status">
                  <FileSearch size={25} />
                  <span>Loading full record…</span>
                </div>
              ) : detail.error ? (
                <div className="inspector-empty" role="alert">
                  <span>{detail.error}</span>
                  <button className="button secondary" onClick={detail.retry}>
                    Try again
                  </button>
                </div>
              ) : detailTab === 'preview' ? (
                <ConsoleDetail signal={selectedSignal} data={data} onInspect={setDetailTab} />
              ) : (
                <SignalDetail
                  signal={selectedSignal}
                  data={data}
                  tab={detailTab}
                  setTab={setDetailTab}
                  onShare={() => void share()}
                  onBack={() => {
                    if (window.matchMedia('(max-width: 900px)').matches) setDetailTab('preview')
                    else setDetailOpen(false)
                  }}
                />
              )}
            </Modal>
          )}
          {selected &&
            data &&
            !awards.loading &&
            !awards.error &&
            !detail.loading &&
            !loading &&
            !selectedSignal &&
            !data.current_feed?.records[selected] &&
            !activeSignals.some((s) => s.id === selected) && (
              <Modal title="Opportunity unavailable" onClose={() => setSelected(null)}>
                <div className="empty-state">
                  <FileSearch size={30} />
                  <h3>This signal is no longer in the current feed</h3>
                  <button className="button primary" onClick={() => setSelected(null)}>
                    Back to opportunities
                  </button>
                </div>
              </Modal>
            )}
        </div>
      </ResearchProvider>
    </WorkspaceProviders>
  )
}

function recordTypeLabel(signal: Signal) {
  if (isHistoricalAward(signal)) return 'Contract award'
  if (signal.source === 'digital_outcomes' && lifecycleState(signal) === 'UNKNOWN')
    return 'Application window unconfirmed'
  return typeLabels[signal.signal_type]
}

function SignalRow({
  signal: s,
  filters,
  data,
  selected,
  saved,
  hidden,
  departure,
  onDepartureEnd,
  onSave,
  onOpen,
  onHide,
  now,
}: {
  signal: Signal
  filters: Filters
  data: Dataset | null
  selected: boolean
  saved: boolean
  hidden: boolean
  departure?: 'hide' | 'unhide'
  onDepartureEnd: () => void
  onSave: () => void
  onOpen: (tab?: string) => void
  onHide: () => void
  now: number
}) {
  const text = useSignalText(s)
  const searchMatch = filters.q
    ? explainSearch(s, filters.q, data?.capabilities, data?.translations?.[s.id], {
        mode: filters.searchMode,
        match: filters.match,
      })
    : null
  return (
    <div className="row-motion" data-signal-id={s.id} data-departure={departure}>
      <article
        className={`signal-row type-${s.signal_type.toLowerCase()} ${selected ? 'selected' : ''}`}
        onAnimationEnd={(event) => {
          if (event.target === event.currentTarget && event.animationName === 'restore-signal')
            onDepartureEnd()
        }}
        onClick={(event) => {
          if (!(event.target as HTMLElement).closest('button, input, label, a')) onOpen()
        }}
      >
        {selected && <MetalEdge />}
        <button
          className="row-select"
          aria-label={text.title}
          aria-pressed={selected}
          aria-controls="selected-opportunity"
          onClick={() => onOpen()}
        >
          <span className="row-copy">
            <span className="row-meta">
              <span>{recordTypeLabel(s)}</span>
              {isUpdated(s, now) && <span className="row-updated">Updated</span>}
              {isCombinedMarket(filters.market) && (
                <span className="row-country">{countryLabels(s)}</span>
              )}
            </span>
            <span className="row-title">{text.title}</span>
            <span className="row-buyer">
              <Building2 size={12} />
              <span>{text.buyerName}</span>
            </span>
            {searchMatch?.basis === 'capability' && (
              <span className="row-search-match">
                Matched capability:{' '}
                {searchMatch.capabilities
                  .map(
                    (id) =>
                      data?.capabilities.find((capability) => capability.id === id)?.label || id,
                  )
                  .join(', ')}
              </span>
            )}
          </span>
          <span className="row-numbers">
            {(s.value_max !== null || s.value_min !== null || s.amount) && (
              <>
                <strong>{valueFact(s).value}</strong>
                {valueFact(s).label !== 'Estimated contract value' && (
                  <small>{valueFact(s).label}</small>
                )}
              </>
            )}
            {isHistoricalAward(s) ? (
              <span>
                {s.award_date ? `Awarded ${date(s.award_date)}` : `Notice ${date(s.published_at)}`}
              </span>
            ) : (
              responseDeadline(s) && <span>{date(responseDeadline(s))}</span>
            )}
          </span>
        </button>
        <div className="row-utilities">
          <IconButton
            label={saved ? 'Unsave opportunity' : 'Save opportunity in this browser'}
            className={saved ? 'is-saved' : ''}
            onClick={onSave}
          >
            {saved ? <BookmarkCheck size={17} /> : <Bookmark size={17} />}
          </IconButton>
          <label className="hide-control">
            <input
              type="checkbox"
              checked={departure ? departure === 'hide' : hidden}
              disabled={!!departure}
              onChange={onHide}
              aria-label={`${hidden ? 'Unhide' : 'Hide'} ${text.title}`}
            />
            <span>{hidden ? 'Unhide' : 'Hide'}</span>
          </label>
        </div>
      </article>
      {departure === 'hide' && <DismissDust id={s.id} />}
    </div>
  )
}

function ResearchRecord({ signal, data }: { signal: Signal; data: Dataset }) {
  const [tab, setTab] = useState('preview')
  return (
    <div className="research-full-record">
      {tab === 'preview' ? (
        <ConsoleDetail signal={signal} data={data} onInspect={setTab} />
      ) : (
        <SignalDetail
          signal={signal}
          data={data}
          tab={tab}
          setTab={setTab}
          onBack={() => setTab('preview')}
          onShare={() => {
            const url = new URL(import.meta.env.BASE_URL, location.origin)
            url.searchParams.set('signal', signal.id)
            url.searchParams.set('market', '')
            url.searchParams.set('view', hasAwardOutcome(signal) ? 'awards' : 'all')
            void navigator.clipboard?.writeText(url.href).catch(() => {})
          }}
        />
      )}
    </div>
  )
}

function RecordIntegrations({ signal }: { signal: Signal }) {
  const text = useSignalText(signal)
  const assetRoot = `${import.meta.env.BASE_URL}assets/integrations/`
  const gmailURL = gmailDraftURL(
    signal,
    new URL(import.meta.env.BASE_URL, window.location.origin).href,
    text,
  )
  return (
    <div className="record-integrations" role="group" aria-label="Record integrations">
      {isAvailableOpportunity(signal, Date.now()) && (
        <button
          type="button"
          className="record-integration"
          disabled
          aria-label="Salesforce (coming soon)"
          title="Salesforce — coming soon"
        >
          <img src={`${assetRoot}salesforce.svg`} alt="" width="34" height="24" />
        </button>
      )}
      <a
        className="record-integration record-integration-gmail"
        href={gmailURL}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Share this opportunity in Gmail (opens a new tab)"
        title="Share in Gmail"
      >
        <img src={`${assetRoot}gmail.svg`} alt="" width="28" height="28" />
      </a>
      <button
        type="button"
        className="record-integration"
        disabled
        aria-label="Slack (coming soon)"
        title="Slack — coming soon"
      >
        <img
          className="record-integration-slack"
          src={`${assetRoot}slack.png`}
          alt=""
          width="28"
          height="28"
        />
      </button>
    </div>
  )
}

function DeadlineCalendarButton({ signal }: { signal: Signal }) {
  const text = useSignalText(signal)
  const event = selectedResponseDeadlineEvent(signal)
  const appURL = new URL(import.meta.env.BASE_URL, window.location.origin).href
  const href = event
    ? deadlineEventCalendarURL(signal, event, appURL, text)
    : signal.deadlines?.length
      ? null
      : googleCalendarURL(signal, appURL, text)
  if (!href) return null
  return (
    <a
      className="deadline-calendar-button"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Add deadline to Google Calendar (opens a new tab)"
      title="Add deadline to Google Calendar"
    >
      <CalendarPlus size={20} />
    </a>
  )
}

function ConsoleDetail({
  signal: s,
  data,
  onInspect,
}: {
  signal: Signal
  data: Dataset
  onInspect: (tab: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const text = useSignalText(s)
  useEffect(() => {
    ref.current?.scrollTo({ top: 0 })
  }, [s.id])
  const paragraphs = (
    text.description?.trim() ||
    'No description was published. Review the source notice for details.'
  )
    .split(/\n\s*\n/)
    .filter((paragraph) => paragraph.trim())
  return (
    <div className="console-detail">
      <div
        className="inspector-scroll"
        ref={ref}
        tabIndex={0}
        role="region"
        aria-label="Opportunity record"
      >
        <div className="inspector-content">
          <div className="inspector-heading">
            <div>
              <h2>
                <ResearchTitle signal={s}>{text.title}</ResearchTitle>
              </h2>
              <div className="inspector-buyerline">
                <p className="inspector-buyer">
                  <BuyerLink signal={s} />
                </p>
              </div>
            </div>
          </div>
          <div className="inspector-overview">
            <div className="inspector-overview-content">
              <dl className="inspector-facts">
                <div>
                  <dt>Notice type</dt>
                  <dd>
                    <FileText size={20} />
                    <span>{recordTypeLabel(s)}</span>
                  </dd>
                </div>
                <div>
                  <dt>{valueFact(s).label}</dt>
                  <dd>
                    <Layers3 size={20} />
                    <span>{valueFact(s).value}</span>
                  </dd>
                </div>
                <div>
                  <dt>
                    {hasAwardOutcome(s)
                      ? s.award_date
                        ? 'Awarded'
                        : 'Award notice published'
                      : deadlineFact(s).label}
                  </dt>
                  <dd className="inspector-deadline">
                    <DeadlineCalendarButton signal={s} />
                    <span>
                      {hasAwardOutcome(s)
                        ? date(s.award_date || s.published_at)
                        : deadlineFact(s).value}
                      {!hasAwardOutcome(s) && deadlineFact(s).dateOnly && (
                        <small className="cutoff-note">Cutoff time unconfirmed</small>
                      )}
                    </span>
                  </dd>
                </div>
              </dl>
              <section className="inspector-capabilities">
                <h3>Capabilities</h3>
                <CapabilityTags signal={s} data={data} />
              </section>
              {hasAwardOutcome(s) && (
                <section className="inspector-capabilities">
                  <h3>Awarded supplier</h3>
                  <p>
                    <SupplierLinks signal={s} />
                  </p>
                </section>
              )}
            </div>
            <RecordIntegrations signal={s} />
          </div>
          {(!['OPEN', 'EARLY_ENGAGEMENT'].includes(lifecycleState(s)) ||
            !!s.exclusion_reasons?.length) && (
            <p className="lifecycle-note">
              <Clock3 size={14} />
              <span>{s.lifecycle_reason || lifecycleLabels[lifecycleState(s)]}</span>
            </p>
          )}
          <div className="inspector-summary">
            {text.original && (
              <span className="translation-status" title="English translation is not available yet">
                Original text
              </span>
            )}
            {paragraphs.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        </div>
      </div>
      <footer className="record-action-dock" aria-label="Record actions">
        <button className="record-detail-button" onClick={() => onInspect('overview')}>
          <ExternalLink size={18} />
          <span>Full details</span>
        </button>
        <SourceNoticeLink href={s.primary_source_url} />
      </footer>
    </div>
  )
}

function FilterPanel({
  filters: f,
  update,
  data,
  count,
  onClose,
  onReset,
}: {
  filters: Filters
  update: (v: Partial<Filters>) => void
  data: Dataset
  count: number
  onClose: () => void
  onReset: () => void
}) {
  const select = (
    label: string,
    key: keyof Filters,
    choices: { value: string; label: string }[],
  ) => (
    <label>
      {label}
      <select aria-label={label} value={f[key]} onChange={(e) => update({ [key]: e.target.value })}>
        <option value="">Any</option>
        {choices.map((o) => (
          <option value={o.value} key={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
  return (
    <>
      <div className="filter-grid">
        {f.view !== 'awards' &&
          select(
            'Opportunity type',
            'type',
            Object.entries(typeLabels)
              .filter(([value]) => !['AWARD', 'RENEWAL_SIGNAL'].includes(value))
              .map(([value, label]) => ({ value, label })),
          )}
        {select(
          'Source',
          'source',
          data.sources
            .filter((s) => s.enabled || data.signals.some((record) => record.source === s.id))
            .map((s) => ({ value: s.id, label: s.name })),
        )}
        {select(
          'Capability',
          'capability',
          data.capabilities.map((c) => ({ value: c.id, label: c.label })),
        )}
        {select(
          'Sector',
          'sector',
          [...new Set(data.signals.flatMap((s) => s.categories))]
            .sort()
            .map((s) => ({ value: s, label: s })),
        )}
        {f.view !== 'awards' &&
          select('Deadline', 'deadline', [
            { value: '7', label: 'Next 7 days' },
            { value: '14', label: 'Next 14 days' },
            { value: '30', label: 'Next 30 days' },
            { value: '90', label: 'Next 90 days' },
          ])}
        {f.view !== 'awards' &&
          select('Freshness', 'change', [
            { value: 'new', label: 'New in 24 hours' },
            { value: 'updated', label: 'Updated in 24 hours' },
          ])}
        <label>
          Buyer
          <input
            value={f.buyer}
            placeholder="Buyer name"
            onChange={(e) => update({ buyer: e.target.value })}
          />
        </label>
        {f.view === 'awards' && (
          <>
            <label>
              Awarded supplier
              <input
                value={f.supplier}
                placeholder="Supplier name"
                onChange={(e) => update({ supplier: e.target.value })}
              />
            </label>
            <div className="filter-value-range">
              <label>
                Awarded from
                <input
                  type="date"
                  value={f.awardFrom}
                  onChange={(e) => update({ awardFrom: e.target.value })}
                />
              </label>
              <label>
                Awarded to
                <input
                  type="date"
                  value={f.awardTo}
                  onChange={(e) => update({ awardTo: e.target.value })}
                />
              </label>
            </div>
          </>
        )}
        {select('Amount type', 'amountType', [
          { value: 'estimated_contract', label: 'Estimated contract value' },
          { value: 'framework_ceiling', label: 'Framework ceiling' },
          { value: 'grant_range', label: 'Published grant range' },
          { value: 'programme_funding', label: 'Programme funding' },
          { value: 'award', label: 'Award value' },
          { value: 'annual_spend', label: 'Annual spend' },
          { value: 'unknown', label: 'Unspecified amount type' },
        ])}
        <label>
          Region
          <input
            value={f.region}
            placeholder="Region or location code"
            onChange={(e) => update({ region: e.target.value })}
          />
        </label>
        <div className="filter-value-range">
          <label>
            CPV code
            <input
              value={f.cpv}
              inputMode="numeric"
              placeholder="e.g. 722"
              onChange={(e) => update({ cpv: e.target.value })}
            />
          </label>
          {select('Currency', 'currency', currencyOptions(data.signals))}
        </div>
        <div className="filter-value-range">
          <label>
            Minimum value
            <input
              type="number"
              min="0"
              value={f.minValue}
              placeholder="No minimum"
              onChange={(e) => update({ minValue: e.target.value })}
            />
          </label>
          <label>
            Maximum value
            <input
              type="number"
              min="0"
              value={f.maxValue}
              placeholder="No maximum"
              onChange={(e) => update({ maxValue: e.target.value })}
            />
          </label>
        </div>
      </div>
      <div className="modal-actions">
        <button className="button secondary" onClick={onReset}>
          Reset filters
        </button>
        <button className="button primary" onClick={onClose}>
          Show {count} signals <ArrowRight size={15} />
        </button>
      </div>
    </>
  )
}

function SignalDetail({
  signal: s,
  data,
  tab,
  setTab,
  onShare,
  onBack,
}: {
  signal: Signal
  data: Dataset
  tab: string
  setTab: (tab: string) => void
  onShare: () => void
  onBack: () => void
}) {
  const contentRef = useRef<HTMLDivElement>(null)
  const text = useSignalText(s)
  const tabs = ['overview', 'sources']
  const activeTab = tabs.includes(tab) ? tab : 'overview'
  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0 })
  }, [activeTab, s.id])
  const facts = [
    [valueFact(s).label, valueFact(s, false).value],
    [deadlineFact(s).label, deadlineFact(s).value],
    ...(hasAwardOutcome(s)
      ? [
          [
            'Awarded supplier',
            s.winners?.map((winner) => winner.name).join(', ') ||
              s.incumbent_supplier ||
              'Not published',
          ],
          ['Award date', s.award_date ? date(s.award_date) : 'Not published'],
        ]
      : []),
    ['Published', date(s.published_at)],
    [
      'Contract period',
      s.contract_start || s.contract_end
        ? `${date(s.contract_start)} to ${date(s.contract_end)}`
        : 'Not published',
    ],
    ['Framework', s.framework || 'Not specified'],
    ['Region', s.regions.join(', ') || s.countries.join(', ') || 'Not specified'],
    ['Procurement lots', s.lot_ids.join(', ') || 'Not published'],
    ['CPV classifications', s.cpv_codes.join(', ') || 'Not published'],
  ]
  return (
    <>
      <div className="detail-heading" tabIndex={0} role="region" aria-label="Opportunity heading">
        <div className="detail-eyebrow">
          <span className="type-label">{recordTypeLabel(s)}</span>
        </div>
        <h2>
          <ResearchTitle signal={s}>{text.title}</ResearchTitle>
        </h2>
        <div className="buyer">
          <Building2 size={14} />
          <BuyerLink signal={s} />
        </div>
        <div className="detail-actions">
          <DeadlineCalendarButton signal={s} />
          <IconButton label="Copy opportunity link" onClick={onShare}>
            <Copy size={16} />
          </IconButton>
        </div>
      </div>
      <div className="detail-tabs" role="tablist" aria-label="Opportunity detail sections">
        {tabs.map((t) => (
          <button
            key={t}
            role="tab"
            id={`detail-tab-${t}`}
            aria-controls="detail-panel"
            aria-selected={activeTab === t}
            tabIndex={activeTab === t ? 0 : -1}
            onClick={() => setTab(t)}
            onKeyDown={(event) => {
              const current = tabs.indexOf(t)
              const index =
                event.key === 'ArrowRight'
                  ? (current + 1) % tabs.length
                  : event.key === 'ArrowLeft'
                    ? (current + tabs.length - 1) % tabs.length
                    : event.key === 'Home'
                      ? 0
                      : event.key === 'End'
                        ? tabs.length - 1
                        : -1
              if (index < 0) return
              event.preventDefault()
              setTab(tabs[index])
              document.getElementById(`detail-tab-${tabs[index]}`)?.focus()
            }}
          >
            {t === 'overview' ? 'Overview' : 'Sources & timeline'}
          </button>
        ))}
      </div>
      <div
        ref={contentRef}
        className="detail-content"
        role="tabpanel"
        id="detail-panel"
        aria-labelledby={`detail-tab-${activeTab}`}
        tabIndex={0}
      >
        {activeTab === 'overview' ? (
          <>
            <section className="detail-section">
              <h3>Capabilities</h3>
              <CapabilityTags signal={s} data={data} />
            </section>
            <section className="detail-section">
              <h3>Published deadlines</h3>
              <DeadlineEvents signal={s} />
            </section>
            <section className="detail-section">
              <h3>Opportunity scope</h3>
              {text.original && (
                <span
                  className="translation-status"
                  title="English translation is not available yet"
                >
                  Original text
                </span>
              )}
              <p className="detail-summary">
                {text.description?.trim() ||
                  'No description was published. Review the source notice for details.'}
              </p>
              <p className="lifecycle-note">
                {lifecycleLabels[lifecycleState(s)]}:{' '}
                {s.lifecycle_reason || 'Confirm the latest status in the source notice.'}
              </p>
            </section>
            <section className="detail-section">
              <h3>Commercial & procurement facts</h3>
              <dl className="facts-grid">
                {facts.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{label === 'Awarded supplier' ? <SupplierLinks signal={s} /> : value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          </>
        ) : (
          <>
            <section className="detail-section">
              <h3>Source provenance</h3>
              <div className="provenance-list">
                {s.provenance.map((p, i) => (
                  <div key={`${p.source}-${p.release_id}-${i}`}>
                    <span className="source-icon">
                      <FileText size={16} />
                    </span>
                    <div>
                      {distinctSources(
                        [p.url],
                        [
                          s.primary_source_url,
                          ...s.provenance.slice(0, i).map((previous) => previous.url),
                        ],
                      ).length ? (
                        <SourceNoticeLink href={p.url} compact>
                          {p.source_name}
                        </SourceNoticeLink>
                      ) : (
                        <strong>{p.source_name}</strong>
                      )}
                      <small>Reference {p.release_id || 'Not published'}</small>
                      <small>
                        Checked{' '}
                        {date(p.retrieved_at, {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
              {s.ocid && (
                <p className="ocid">
                  OCID <code>{s.ocid}</code>
                </p>
              )}
            </section>
            <section className="detail-section">
              <h3>Documents</h3>
              <SourceDocuments signal={s} excludedSources={s.provenance.map((p) => p.url)} />
            </section>
            <section className="detail-section">
              <ProcurementHistory
                signal={s}
                excludedSources={[
                  ...s.provenance.map((p) => p.url),
                  ...s.documents.map((doc) => doc.url),
                ]}
              />
            </section>
            <section className="detail-section">
              <h3>Timeline</h3>
              <ol className="timeline">
                {[...s.changes].reverse().map((c, i) => (
                  <li key={i}>
                    <span />
                    <div>
                      <strong>
                        {c.kind === 'discovered' ? 'First discovered' : 'Material update'}
                      </strong>
                      <time>
                        {date(c.at, {
                          day: 'numeric',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </time>
                      {!!c.fields.length && (
                        <p>{c.fields.map((f) => f.replaceAll('_', ' ')).join(', ')}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
              <dl className="facts-grid">
                <div>
                  <dt>First seen</dt>
                  <dd>{date(s.first_seen_at)}</dd>
                </div>
                <div>
                  <dt>Last checked</dt>
                  <dd>{date(s.last_seen_at)}</dd>
                </div>
                <div>
                  <dt>Last material update</dt>
                  <dd>{date(s.last_material_update)}</dd>
                </div>
              </dl>
            </section>
          </>
        )}
      </div>
      <footer className="record-action-dock" aria-label="Record actions">
        <button className="record-detail-button" onClick={onBack}>
          <ArrowLeft size={18} />
          <span>Back to record</span>
        </button>
        <SourceNoticeLink href={s.primary_source_url} />
      </footer>
    </>
  )
}
