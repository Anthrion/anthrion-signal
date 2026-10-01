import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useDeferredValue,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import {
  ArrowDownToLine,
  ArrowRight,
  Award,
  Bookmark,
  BookmarkCheck,
  Building2,
  CalendarClock,
  CalendarPlus,
  CalendarDays,
  Check,
  ChevronDown,
  Clock3,
  Eye,
  EyeOff,
  FileSearch,
  FileText,
  Globe2,
  History,
  Languages,
  Layers3,
  Link2,
  Menu,
  Radar,
  Search,
  SlidersHorizontal,
  Target,
  X,
} from 'lucide-react'
import type { Dataset, DisplayLanguage, EnglishText, Filters, Signal } from './types'
import { TranslationProvider, useSignalText, useTranslations } from './Translation'
import { RecommendedApproach } from './RecommendedApproach'
import { salesforcePrefill, salesforceSandbox } from './salesforce'
import {
  AmbientGlass,
  BrandSignature,
  ThemeToggle,
  MarketSection,
  MetalEdge,
  SearchScope,
  SortMenu,
  SourceNoticeLink,
  useNarrowScreen,
  useReducedMotion,
} from './WorkspaceUI'
import { DiscoveryCarousel } from './DiscoveryCarousel'
import { RollingNumber } from './RollingNumber'
import { SwitchGroup } from './Switch'
import { calm, pop } from './delight'
import { toggleTheme } from './theme'
import { VirtualSignalList } from './VirtualSignalList'
import { DismissDust } from './DismissDust'
import { useAwardHistory } from './useAwardHistory'
import { historySupplierScope, supplierHistoryMarket } from './supplierResearch'
import { distinctSources } from './researchPresentation'
import { useOpportunityData, useSignalDetail } from './useOpportunityData'
import { selectMarketEntries } from './dataClient'
import {
  initialWorkspaceFilters,
  rememberLastView,
  usePersonalWorkspace,
} from './personalWorkspace'
import { briefText, getPreferences, usePreferences } from './preferences'
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
  date,
  publicationDate,
  daysLeft,
  defaults,
  applicableFilters,
  download,
  explainSearch,
  filterSignals,
  gmailDraftURL,
  googleCalendarURL,
  hasPublishedAmount,
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
  recordURL,
  safeURL,
  selectedResponseDeadlineEvent,
  typeLabels,
  warmSearchText,
} from './lib'

const navItems = [
  { id: 'all', label: 'All Signals', icon: Layers3 },
  { id: 'live', label: 'Live Opportunities', short: 'Live', icon: Target },
  { id: 'early', label: 'Pre-market', icon: Radar },
  { id: 'closing', label: 'Closing Soon', icon: CalendarClock },
  { id: 'today', label: 'Added today', icon: CalendarDays },
]
const refinerItems = [...navItems, { id: 'awards', label: 'Awarded', icon: Award }]
const appURL = () => new URL(import.meta.env.BASE_URL, window.location.origin).href
// The menu and its map load on first use; pointing at the menu button prefetches them.
const loadMenu = () => import('./WorkspaceMenu')
const WorkspaceMenu = lazy(() => loadMenu().then((module) => ({ default: module.WorkspaceMenu })))

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
const validCompact = (value: unknown): value is boolean => typeof value === 'boolean'
const validRatio = (value: unknown): value is number =>
  typeof value === 'number' && value >= 30 && value <= 70

function IconButton({
  label,
  children,
  className = '',
  title,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button
      {...props}
      aria-label={label}
      title={title ?? label}
      className={`icon-button ${className}`}
    >
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
  sheet = false,
  actions,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  wide?: boolean
  drawer?: boolean
  /** A right-hand panel that leaves the results visible beside it. */
  sheet?: boolean
  actions?: ReactNode
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
      className={`modal ${wide ? 'wide' : ''} ${drawer ? 'drawer' : ''} ${sheet ? 'sheet' : ''}`}
      aria-label={title}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal-top">
        <span>{title}</span>
        <div className="modal-top-actions">
          {actions}
          <IconButton label="Close panel" onClick={onClose}>
            <X size={20} />
          </IconButton>
        </div>
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
  const reducedMotion = useReducedMotion()
  return (
    <MotionConfig reducedMotion={reducedMotion ? 'always' : 'user'}>
      <TranslationProvider language={language} translations={translations}>
        {children}
      </TranslationProvider>
    </MotionConfig>
  )
}

export default function App() {
  const [filters, setFilters] = useState<Filters>(() =>
    initialWorkspaceFilters(getPreferences().startMarket),
  )
  const activeFilters = useMemo(() => applicableFilters(filters), [filters])
  // Typing stays immediate: the feed, its counts and its highlights follow the query at
  // background priority, and React abandons a stale pass when the next key arrives.
  const deferredQuery = useDeferredValue(filters.q)
  const settledFilters = JSON.stringify({ ...filters, q: '' })
  const listFilters = useMemo(
    () => ({ ...(JSON.parse(settledFilters) as Filters), q: deferredQuery }),
    [settledFilters, deferredQuery],
  )
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
  const [compact, setCompact] = useLocal('anthrion-compact-reading-v1', false, validCompact)
  const [paneRatio, setPaneRatio] = useLocal('anthrion-pane-ratio-v1', 50, validRatio)
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
  const narrowScreen = useNarrowScreen()
  const [showFilters, setShowFilters] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [reveal, setReveal] = useState<{ index: number; nonce: number } | null>(null)
  const [detailOpen, setDetailOpen] = useState(
    () =>
      !!new URLSearchParams(location.search).get('signal') &&
      window.matchMedia('(max-width: 900px)').matches,
  )
  const [selected, setSelected] = useState<string | null>(() =>
    new URLSearchParams(location.search).get('signal'),
  )
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
  const open = (id: string) => {
    setSelected(id)
    setDetailOpen(window.matchMedia('(max-width: 900px)').matches)
  }
  const hiddenIds = useMemo(() => new Set(hidden), [hidden])
  const visibleSignals = useMemo(
    () => activeSignals.filter((s) => hiddenIds.has(s.id) === showHidden),
    [activeSignals, hiddenIds, showHidden],
  )
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
  // The market's search text is prepared while the browser is idle, before anyone types.
  useEffect(() => warmSearchText(marketSignals, translations), [marketSignals, translations])
  // One text-search pass serves both the list and the refiner counts: every refiner
  // counts the opportunities that match the current search and filters.
  const opportunityMatches = useMemo(
    () =>
      filterSignals(
        marketSignals,
        { ...listFilters, view: 'all', sort: 'recent', supplier: '', awardFrom: '', awardTo: '' },
        saved,
        time,
        data?.capabilities,
        translations,
      ),
    [marketSignals, listFilters, saved, time, data?.capabilities, translations],
  )
  const filtered = useMemo(
    () =>
      viewingAwards || viewingSaved
        ? filterSignals(visibleSignals, listFilters, saved, time, data?.capabilities, translations)
        : filterSignals(opportunityMatches, { ...listFilters, q: '' }, saved, time),
    [
      viewingAwards,
      viewingSaved,
      visibleSignals,
      opportunityMatches,
      listFilters,
      saved,
      time,
      data?.capabilities,
      translations,
    ],
  )
  // Outgoing rows are visual only; counts, selection and export use saved intent immediately.
  const renderedFiltered = useMemo(() => {
    if (!Object.keys(departing).length) return filtered
    const visual = activeSignals.filter((s) => {
      const phase = departing[s.id]
      return (phase ? phase === 'unhide' : hiddenIds.has(s.id)) === showHidden
    })
    return filterSignals(visual, listFilters, saved, time, data?.capabilities, translations)
  }, [
    data,
    activeSignals,
    departing,
    filtered,
    listFilters,
    hiddenIds,
    saved,
    showHidden,
    time,
    translations,
  ])
  const counts = useMemo(
    () =>
      Object.fromEntries(
        navItems.map((n) => [
          n.id,
          filterSignals(
            opportunityMatches,
            { ...defaults, market: filters.market, view: n.id, sort: 'recent' },
            [],
            time,
          ).length,
        ]),
      ),
    [opportunityMatches, filters.market, time],
  )
  const awardCount = useMemo(
    () =>
      selectMarketEntries(Object.entries(data?.award_history || {}), filters.market).reduce(
        (total, [, page]) => total + page.count,
        0,
      ),
    [data, filters.market],
  )
  // Until the awards are loaded the card shows the market's published total.
  const awardMatches = useMemo(
    () =>
      awards.loadedSignals &&
      filterSignals(
        awards.loadedSignals.filter((s) => hiddenIds.has(s.id) === showHidden),
        { ...listFilters, view: 'awards', sort: 'recent', type: '', deadline: '', change: '' },
        saved,
        time,
        data?.capabilities,
        translations,
      ).length,
    [
      awards.loadedSignals,
      hiddenIds,
      showHidden,
      listFilters,
      saved,
      time,
      data?.capabilities,
      translations,
    ],
  )
  const refinerCounts = useMemo(
    (): Record<string, number> => ({ ...counts, awards: awardMatches ?? awardCount }),
    [counts, awardMatches, awardCount],
  )
  // What the Hidden lens will show in this collection.
  const hiddenCount = useMemo(() => {
    if (!hiddenIds.size) return 0
    if (viewingAwards) return (awards.loadedSignals || []).filter((s) => hiddenIds.has(s.id)).length
    return (data?.signals || []).filter(
      (s) =>
        hiddenIds.has(s.id) &&
        matchesMarket(s, filters.market) &&
        (viewingSaved ? saved.includes(s.id) : isAvailableOpportunity(s, time)),
    ).length
  }, [
    hiddenIds,
    viewingAwards,
    viewingSaved,
    awards.loadedSignals,
    data,
    filters.market,
    saved,
    time,
  ])
  const marketCounts = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(data?.current_feed?.markets || {}).map(([id, page]) => [id, page.count]),
      ),
    [data],
  )
  const marketName =
    markets.find((m) => m.id === filters.market)?.name ||
    data?.markets[filters.market]?.name ||
    (filters.market ? `Market ${filters.market}` : 'All markets')
  const marketEnabled = data
    ? marketIsEnabled(filters.market, data.markets)
    : filters.market === 'GB'
  // The feed's publication time stays while the next market loads, so its notice does not blink.
  const [feedTime, setFeedTime] = useState(data?.generated_at ?? '')
  if (data && data.generated_at !== feedTime) setFeedTime(data.generated_at)
  const stale = !!feedTime && time - Date.parse(feedTime) >= 26 * 3600000
  const activeFilterCount = Object.entries(activeFilters).filter(
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
  const openResearch = (value: ResearchState) => {
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
  }
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
  // Desktop shortcuts act on the selected record. Typing, menus and pages keep their keys.
  const shortcut = useRef<(event: KeyboardEvent) => void>(() => {})
  const handleShortcut = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement
    if (
      event.defaultPrevented ||
      event.isComposing ||
      event.metaKey ||
      event.ctrlKey ||
      event.altKey
    )
      return
    if (target.isContentEditable || target.closest?.('input, textarea, select')) return
    if (document.querySelector('dialog[open], [role="menu"], [role="dialog"]')) return
    const key = event.key.toLowerCase()
    if (key === '/') {
      event.preventDefault()
      searchRef.current?.focus()
      return
    }
    if (key === 'l') {
      event.preventDefault()
      setLanguage(language === 'en' ? 'original' : 'en')
      return
    }
    if (key === 't') {
      event.preventDefault()
      toggleTheme()
      return
    }
    const current = selectedSignal
    const index = current ? renderedFiltered.findIndex((s) => s.id === current.id) : -1
    if (key === 'j' || key === 'k') {
      const next =
        renderedFiltered[
          Math.max(0, Math.min(renderedFiltered.length - 1, index + (key === 'j' ? 1 : -1)))
        ]
      if (!next) return
      event.preventDefault()
      setSelected(next.id)
      setReveal({ index: renderedFiltered.indexOf(next), nonce: Date.now() })
      return
    }
    if (!current) return
    const opener =
      document.activeElement instanceof HTMLElement ? document.activeElement : document.body
    if (key === 's') toggleSave(current.id)
    else if (key === 'h') dismiss(current.id)
    else if (key === 'o')
      window.open(safeURL(current.primary_source_url), '_blank', 'noopener,noreferrer')
    else if (key === 'c') openResearch({ kind: 'related', signal: current, opener })
    else if (key === 'b') openResearch({ kind: 'buyer', signal: current, opener })
    else return
    event.preventDefault()
  }
  useLayoutEffect(() => {
    shortcut.current = handleShortcut
  })
  useEffect(() => {
    const handler = (event: KeyboardEvent) => shortcut.current(event)
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
  const listTitle =
    navItems.find((n) => n.id === filters.view)?.label ||
    { saved: 'Saved opportunities', awards: 'Awarded contracts' }[filters.view] ||
    'All signals'
  const switchMarket = (id: string) => {
    update({ market: id, source: '', region: '', buyer: '', cpv: '' })
  }
  const selectView = (view: string) => {
    update({ view })
  }
  const toggleHidden = () => {
    if (!showHidden && !viewingAwards && !viewingSaved && filters.view !== 'all')
      update({ view: 'all' })
    else {
      setSelected(null)
      setDetailOpen(false)
    }
    setShowHidden(!showHidden)
  }
  const savedCount = saved.filter(
    (id) =>
      marketSignals.some((s) => s.id === id) ||
      (data?.current_feed?.records[id]?.view === 'awards' &&
        (!filters.market || data.current_feed.records[id].markets.includes(filters.market)) &&
        hiddenIds.has(id) === showHidden) ||
      awards.knownSignals.some(
        (s) => s.id === id && matchesMarket(s, filters.market) && hiddenIds.has(id) === showHidden,
      ),
  ).length
  // Records matching the market, collection and search, before the other filters,
  // so each filter option can show how many results it would leave.
  const filterPool = useMemo(
    () =>
      showFilters
        ? filterSignals(
            viewingAwards || viewingSaved ? visibleSignals : marketSignals,
            {
              ...defaults,
              market: filters.market,
              view: filters.view,
              q: listFilters.q,
              searchMode: filters.searchMode,
              match: filters.match,
            },
            saved,
            time,
            data?.capabilities,
            translations,
          )
        : [],
    [
      showFilters,
      viewingAwards,
      viewingSaved,
      visibleSignals,
      marketSignals,
      filters.market,
      filters.view,
      listFilters.q,
      filters.searchMode,
      filters.match,
      saved,
      time,
      data?.capabilities,
      translations,
    ],
  )
  const refinerChips = compact || narrowScreen
  // The chosen view's chip is always shown whole, even where the row scrolls past it.
  const chipRow = useRef<HTMLElement>(null)
  const chipsShown = useRef(false)
  const revealChip = useCallback((smooth: boolean) => {
    const row = chipRow.current
    const chip = row?.querySelector<HTMLElement>('[aria-pressed="true"]')
    if (!row || !chip) return
    const bounds = row.getBoundingClientRect()
    const box = chip.getBoundingClientRect()
    // Chips snap by their start, so a hidden chip is brought to the row's start: the snap keeps it.
    if (box.left < bounds.left - 0.5 || box.right > bounds.right + 0.5)
      row.scrollBy({
        left: box.left - bounds.left,
        behavior: smooth && !calm() ? 'smooth' : 'auto',
      })
  }, [])
  useLayoutEffect(() => {
    revealChip(chipsShown.current)
    chipsShown.current = !!chipRow.current
  }, [filters.view, refinerChips, revealChip])
  // A narrower screen can push the chosen chip out of the row again.
  useEffect(() => {
    const row = chipRow.current
    if (!row) return
    const observer = new ResizeObserver(() => revealChip(false))
    observer.observe(row)
    return () => observer.disconnect()
  }, [refinerChips, revealChip])

  return (
    <WorkspaceProviders language={language} translations={displayTranslations}>
      <ResearchProvider open={openResearch}>
        <div className={`app-shell console-shell ${refinerChips ? 'compact-reading' : ''}`}>
          <AmbientGlass />
          <a className="skip-link" href="#main">
            Skip to opportunities
          </a>

          <main id="main" className="workspace-main">
            <header className="workspace-header">
              <BrandSignature onHome={() => update({ ...defaults, market: filters.market })} />
              <div className="workspace-search" role="search" aria-label="Opportunity search">
                <div
                  className="search-box"
                  onPointerDown={(event) => {
                    if (!(event.target as HTMLElement).closest('button, input'))
                      requestAnimationFrame(() => searchRef.current?.focus())
                  }}
                >
                  <Search size={16} aria-hidden="true" />
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
                  <SearchScope mode={filters.searchMode} match={filters.match} onChange={update} />
                </div>
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
                  value={filters.sort}
                  onChange={(sort) => update({ sort })}
                  fixedLabel={viewingAwards ? 'Latest awards' : undefined}
                />
              </div>
              <nav className="workspace-nav" aria-label="Workspace">
                <button
                  title="Saved opportunities"
                  aria-label={`Saved opportunities, ${savedCount}`}
                  aria-current={viewingSaved ? 'page' : undefined}
                  onClick={() => navigate('saved')}
                >
                  <Bookmark size={17} />
                  <small key={savedCount} className="nav-count">
                    {savedCount}
                  </small>
                </button>
                <button
                  title="Hidden"
                  aria-label={`Hidden, ${hiddenCount}`}
                  aria-pressed={showHidden}
                  onClick={toggleHidden}
                >
                  <EyeOff size={17} />
                  <small key={hiddenCount} className="nav-count">
                    {hiddenCount}
                  </small>
                </button>
                <ThemeToggle />
              </nav>
              <div className="workspace-tools">
                <IconButton
                  label="Workspace menu"
                  aria-haspopup="dialog"
                  aria-expanded={menuOpen}
                  className={stale ? 'needs-attention' : ''}
                  onPointerEnter={() => void loadMenu()}
                  onFocus={() => void loadMenu()}
                  onClick={() => setMenuOpen(true)}
                >
                  <Menu size={20} />
                </IconButton>
              </div>
            </header>
            <div className="workspace-content">
              <MarketSection
                selected={filters.market}
                onSelect={switchMarket}
                counts={marketCounts}
                language={language}
                onLanguage={setLanguage}
                preferences={personal.marketPreferences}
                onArrange={personal.arrangeMarkets}
              />
              {(error || stale) && (
                <div className="alert" role="status">
                  <Clock3 size={17} />
                  <span>
                    {error ||
                      `The feed was last refreshed ${date(feedTime)}. Confirm current availability in the source notice.`}
                  </span>
                  <button onClick={() => void load()}>Retry</button>
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
                {refinerChips ? (
                  <nav className="compact-refiners" aria-label="Opportunity views" ref={chipRow}>
                    {refinerItems.map(({ id, label, icon: Icon }) => (
                      <button
                        key={id}
                        aria-pressed={filters.view === id}
                        onClick={() => {
                          // Reveal the chosen chip without resetting the current sort or filters.
                          if (filters.view === id) revealChip(true)
                          selectView(id)
                        }}
                      >
                        <Icon size={15} aria-hidden="true" />
                        {label}
                        <small>
                          <RollingNumber
                            value={data ? refinerCounts[id] || 0 : null}
                            placeholder="–"
                          />
                        </small>
                      </button>
                    ))}
                  </nav>
                ) : (
                  <DiscoveryCarousel
                    items={refinerItems}
                    counts={refinerCounts}
                    selected={filters.view}
                    loading={!data}
                    onSelect={selectView}
                  />
                )}
                <div className="discovery-export">
                  <IconButton
                    label="Export signals"
                    title={`Export ${filtered.length.toLocaleString('en-GB')} signals as CSV`}
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
                  filters={activeFilters}
                  update={update}
                  data={data}
                  extra={
                    showHidden && (
                      <button
                        className="state-chip"
                        onClick={() => setShowHidden(false)}
                        aria-label="Stop showing hidden records"
                      >
                        <EyeOff size={12} aria-hidden="true" />
                        <span>Hidden</span>
                        <X size={12} aria-hidden="true" />
                      </button>
                    )
                  }
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
                        resetKey={`${JSON.stringify(listFilters)}:${showHidden}`}
                        shiftKey={hidden.join('|')}
                        reveal={reveal}
                        renderRow={(signal) => (
                          <SignalRow
                            key={signal.id}
                            signal={signal}
                            filters={listFilters}
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
                            onOpen={() => open(signal.id)}
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
                      <ConsoleDetail signal={selectedSignal} data={data} />
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
          {menuOpen && (
            <Suspense fallback={null}>
              <WorkspaceMenu
                data={data}
                market={filters.market}
                onMarket={switchMarket}
                language={language}
                onLanguage={setLanguage}
                compact={compact}
                onCompact={setCompact}
                loading={loading}
                onRefresh={() => void load()}
                onClose={() => setMenuOpen(false)}
                onNotice={setToast}
                now={time}
              />
            </Suspense>
          )}
          {showFilters && data && (
            <Modal title="Filters" onClose={() => setShowFilters(false)} sheet>
              <FilterPanel
                filters={activeFilters}
                update={update}
                data={viewingAwards || viewingSaved ? { ...data, signals: activeSignals } : data}
                pool={filterPool}
                saved={saved}
                now={time}
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
              title={recordTypeLabel(selectedSignal)}
              onClose={() => setDetailOpen(false)}
              wide
              drawer
              actions={
                <IconButton
                  label={
                    saved.includes(selectedSignal.id)
                      ? 'Unsave opportunity'
                      : 'Save opportunity in this browser'
                  }
                  className={saved.includes(selectedSignal.id) ? 'is-saved' : ''}
                  onClick={(event) => {
                    if (!saved.includes(selectedSignal.id)) pop(event.currentTarget)
                    toggleSave(selectedSignal.id)
                  }}
                >
                  {saved.includes(selectedSignal.id) ? (
                    <BookmarkCheck size={19} />
                  ) : (
                    <Bookmark size={19} />
                  )}
                </IconButton>
              }
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
              ) : (
                <ConsoleDetail signal={selectedSignal} data={data} />
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

/** The response date; in its last fifteen days a countdown follows on its own line. */
function RowDeadline({ signal, now }: { signal: Signal; now: number }) {
  const deadline = responseDeadline(signal, now)
  if (!deadline) return null
  const days = daysLeft(signal, now)
  const sameYear = new Date(deadline).getFullYear() === new Date(now).getFullYear()
  const closing = days !== null && days > 0 && days <= 15
  return (
    <span className="row-deadline">
      <span>
        {date(deadline, {
          day: 'numeric',
          month: 'short',
          ...(sameYear ? {} : { year: 'numeric' }),
        })}
      </span>
      {closing && (
        <em>
          <Clock3 size={12} aria-hidden="true" />
          <span aria-hidden="true">{days}d</span>
          <span className="screen-reader-only">
            {days} {days === 1 ? 'day' : 'days'} left
          </span>
        </em>
      )}
    </span>
  )
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
  onOpen: () => void
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
  const amount = hasPublishedAmount(s) ? valueFact(s) : null
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
            {amount && (
              <>
                <strong>{amount.value}</strong>
                {amount.label !== 'Estimated contract value' && <small>{amount.label}</small>}
              </>
            )}
            {isHistoricalAward(s) ? (
              <span>
                {s.award_date ? `Awarded ${date(s.award_date)}` : `Notice ${publicationDate(s)}`}
              </span>
            ) : (
              <RowDeadline signal={s} now={now} />
            )}
          </span>
        </button>
        <div className="row-utilities">
          <IconButton
            label={saved ? 'Unsave opportunity' : 'Save opportunity in this browser'}
            className={saved ? 'is-saved' : ''}
            onClick={(event) => {
              if (!saved) pop(event.currentTarget)
              onSave()
            }}
          >
            {saved ? <BookmarkCheck size={17} /> : <Bookmark size={17} />}
          </IconButton>
          <IconButton
            label={`${hidden ? 'Unhide' : 'Hide'} ${text.title}`}
            title={hidden ? 'Unhide' : 'Hide'}
            className="hide-toggle"
            disabled={!!departure}
            onClick={onHide}
          >
            {hidden ? <Eye size={16} /> : <EyeOff size={16} />}
          </IconButton>
        </div>
      </article>
      {departure === 'hide' && <DismissDust id={s.id} />}
    </div>
  )
}

function ResearchRecord({ signal, data }: { signal: Signal; data: Dataset }) {
  return (
    <div className="research-full-record">
      <ConsoleDetail signal={signal} data={data} />
    </div>
  )
}

function RecordShare({ signal, data }: { signal: Signal; data: Dataset }) {
  const text = useSignalText(signal)
  const { language } = useTranslations()
  const salesforce = salesforcePrefill(signal, salesforceSandbox, text, language)
  const assetRoot = `${import.meta.env.BASE_URL}assets/integrations/`
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 1800)
    return () => clearTimeout(timer)
  }, [copied])
  return (
    <div className="record-integrations" role="group" aria-label="Record integrations">
      {data.current_feed?.records[signal.id]?.view !== 'history' &&
        isAvailableOpportunity(signal, Date.now()) &&
        (salesforce ? (
          <a
            className="record-integration"
            href={salesforce.href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Review lead in Salesforce sandbox (opens a new tab)"
            title="Review lead in Salesforce sandbox"
          >
            <img src={`${assetRoot}salesforce.svg`} alt="" width="34" height="24" />
          </a>
        ) : (
          <button
            type="button"
            className="record-integration"
            disabled
            aria-label="Salesforce prefill unavailable"
            title="This record cannot fit in a Salesforce draft link. Copy its details into a new Lead."
          >
            <img src={`${assetRoot}salesforce.svg`} alt="" width="34" height="24" />
          </button>
        ))}
      <a
        className="record-integration record-integration-gmail"
        href={gmailDraftURL(signal, appURL(), text)}
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
      <button
        type="button"
        className="record-integration record-integration-link"
        aria-label={copied ? 'Link copied' : 'Copy link to this opportunity'}
        title={copied ? 'Link copied' : 'Copy link'}
        onClick={() => {
          navigator.clipboard
            ?.writeText(recordURL(signal, appURL()))
            .then(() => setCopied(true))
            .catch(() => {})
        }}
      >
        {copied ? <Check size={19} /> : <Link2 size={19} />}
      </button>
    </div>
  )
}

function DeadlineCalendarButton({ signal }: { signal: Signal }) {
  const text = useSignalText(signal)
  const event = selectedResponseDeadlineEvent(signal)
  const href = event
    ? deadlineEventCalendarURL(signal, event, appURL(), text)
    : signal.deadlines?.length
      ? null
      : googleCalendarURL(signal, appURL(), text)
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

/** Brief or full source text, with a per-record switch to the other language. */
function RecordDescription({
  signal,
  language,
  onLanguage,
}: {
  signal: Signal
  language: DisplayLanguage
  onLanguage: (language: DisplayLanguage) => void
}) {
  const text = useSignalText(signal)
  const { translations } = useTranslations()
  const { reading } = usePreferences()
  const [expanded, setExpanded] = useState('')
  const english = translations?.[signal.id]
  const bilingual =
    !!english &&
    ((!!english.title && english.title !== signal.title) ||
      (!!english.description && english.description !== signal.description))
  const full =
    text.description?.trim() ||
    'No description was published. Review the source notice for details.'
  const brief = reading === 'brief' && expanded !== signal.id ? briefText(full) : null
  const shown = brief?.truncated ? brief.text : full
  return (
    <div className="inspector-summary">
      {(text.original || bilingual) && (
        <div className="summary-tools">
          {text.original && (
            <span className="translation-status" title="English translation is not available yet">
              Original text
            </span>
          )}
          {bilingual && (
            <button
              className="language-peek"
              onClick={() => onLanguage(language === 'en' ? 'original' : 'en')}
              title={
                language === 'en' ? 'Show the original wording' : 'Show the English translation'
              }
            >
              <Languages size={14} aria-hidden="true" />
              {language === 'en' ? 'Original' : 'English'}
            </button>
          )}
        </div>
      )}
      {shown
        .split(/\n\s*\n/)
        .filter((paragraph) => paragraph.trim())
        .map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      {brief?.truncated && (
        <button className="read-more" onClick={() => setExpanded(signal.id)}>
          Full text
          <ChevronDown size={15} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

/** Everything the notice publishes beyond the headline facts, in one scroll. */
function RecordDetails({ signal: s }: { signal: Signal }) {
  // Source history renders only once opened, and closes again for the next record.
  const [historyFor, setHistoryFor] = useState('')
  const historyRef = useRef<HTMLDetailsElement>(null)
  // Opened from the dock: brought into view once its contents exist, not while it is still empty.
  useEffect(() => {
    const panel = historyRef.current
    if (historyFor !== s.id || !panel?.dataset.reveal) return
    delete panel.dataset.reveal
    panel.scrollIntoView({ block: 'start', behavior: calm() ? 'auto' : 'smooth' })
  }, [historyFor, s.id])
  const events = s.deadlines || []
  const headlineEvent = hasAwardOutcome(s) ? undefined : selectedResponseDeadlineEvent(s)
  // A single response date already appears above; questions, superseded dates and
  // lot-specific cutoffs still need their own label, provenance and calendar action.
  const additionalDates =
    events.length > 1 || events.some((event) => event !== headlineEvent || event.lot_id)
  // Until Signal sees a change, last_material_update carries the notice's own date, which
  // can precede the first collection (a notice published before its market was added).
  const updated = Date.parse(s.last_material_update)
  const publicationDayOnly =
    /^\d{4}-\d{2}-\d{2}$/.test(s.published_at || '') &&
    publicationDate({ ...s, published_at: s.last_material_update }) === publicationDate(s)
  const sourceDates = {
    changed: updated > Date.parse(s.first_seen_at),
    updatedAtSource:
      !!s.last_material_update &&
      !publicationDayOnly &&
      updated !== Date.parse(s.published_at || ''),
  }
  const facts = [
    ['Published', s.published_at ? publicationDate(s) : ''],
    [
      'Contract period',
      s.contract_start || s.contract_end
        ? `${date(s.contract_start)} to ${date(s.contract_end)}`
        : '',
    ],
    ['Extension end', s.extension_end ? date(s.extension_end) : ''],
    ['Framework', s.framework || ''],
    ['Region', s.regions.join(', ')],
    ['Lots', s.lot_ids.join(', ')],
    ['CPV', s.cpv_codes.join(', ')],
  ].filter(([, value]) => value)
  const distinctDocuments = s.documents.filter(
    (doc) =>
      !!doc.pages?.length ||
      !!doc.previous_revisions?.length ||
      distinctSources([doc.url], [s.primary_source_url]).length,
  )
  return (
    <div className="record-details">
      {additionalDates && (
        <section className="record-section">
          <h3>Key dates</h3>
          <DeadlineEvents signal={s} />
        </section>
      )}
      {!!facts.length && (
        <section className="record-section">
          <h3>Details</h3>
          <dl className="record-facts">
            {facts.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      <section className="record-section record-procurement">
        <ProcurementHistory
          signal={s}
          showLotSummary={false}
          showContract={false}
          excludedSources={[...s.provenance.map((p) => p.url), ...s.documents.map((d) => d.url)]}
        />
      </section>
      {!!distinctDocuments.length && (
        <section className="record-section">
          <h3>Documents</h3>
          <SourceDocuments signal={s} excludedSources={s.provenance.map((p) => p.url)} />
        </section>
      )}
      <details
        key={s.id}
        ref={historyRef}
        className="record-history"
        onToggle={(event) => setHistoryFor(event.currentTarget.open ? s.id : '')}
      >
        <summary>
          <History size={15} aria-hidden="true" />
          Source history
        </summary>
        {historyFor === s.id && (
          <>
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
            <dl className="record-facts">
              <div>
                <dt>First seen</dt>
                <dd>{date(s.first_seen_at)}</dd>
              </div>
              <div>
                <dt>Last checked</dt>
                <dd>{date(s.last_seen_at)}</dd>
              </div>
              {sourceDates.changed ? (
                <div>
                  <dt>Last material update</dt>
                  <dd>{date(s.last_material_update)}</dd>
                </div>
              ) : (
                sourceDates.updatedAtSource && (
                  <div>
                    <dt>Updated at source</dt>
                    <dd>{date(s.last_material_update)}</dd>
                  </div>
                )
              )}
            </dl>
          </>
        )}
      </details>
    </div>
  )
}

function ConsoleDetail({ signal: s, data }: { signal: Signal; data: Dataset }) {
  const ref = useRef<HTMLDivElement>(null)
  const { language, translations } = useTranslations()
  const [peek, setPeek] = useState<{ id: string; language: DisplayLanguage } | null>(null)
  const shown = peek?.id === s.id ? peek.language : language
  useEffect(() => {
    ref.current?.scrollTo({ top: 0 })
  }, [s.id])
  useEffect(() => setPeek(null), [language])
  const source = s.provenance[0]
  const history = s.buyer_history_ref?.count ?? s.buyer_history?.length ?? 0
  return (
    <TranslationProvider language={shown} translations={translations}>
      <ConsoleRecord
        signal={s}
        data={data}
        scrollRef={ref}
        language={shown}
        onLanguage={(value) => setPeek({ id: s.id, language: value })}
        history={history}
        footer={
          <footer className="record-action-dock" aria-label="Record actions">
            <button
              className="record-detail-button"
              onClick={() => {
                const panel = ref.current?.querySelector<HTMLDetailsElement>('.record-history')
                if (!panel) return
                if (panel.open)
                  panel.scrollIntoView({ block: 'start', behavior: calm() ? 'auto' : 'smooth' })
                else {
                  // The history renders when it opens; it scrolls into view once rendered.
                  panel.dataset.reveal = 'true'
                  panel.open = true
                }
              }}
            >
              <History size={17} aria-hidden="true" />
              <span>
                {source?.source_name || 'Source'}
                <small>checked {date(s.last_seen_at, { day: 'numeric', month: 'short' })}</small>
              </span>
            </button>
            <SourceNoticeLink href={s.primary_source_url} />
          </footer>
        }
      />
    </TranslationProvider>
  )
}

function ConsoleRecord({
  signal: s,
  data,
  scrollRef,
  language,
  onLanguage,
  history,
  footer,
}: {
  signal: Signal
  data: Dataset
  scrollRef: React.RefObject<HTMLDivElement | null>
  language: DisplayLanguage
  onLanguage: (language: DisplayLanguage) => void
  history: number
  footer: ReactNode
}) {
  const text = useSignalText(s)
  return (
    <div className="console-detail">
      <div
        className="inspector-scroll"
        ref={scrollRef}
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
                  <BuyerLink signal={s} count={history > 1 ? history : undefined} />
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
                    <span className={hasPublishedAmount(s) ? '' : 'fact-absent'}>
                      {hasPublishedAmount(s) ? valueFact(s).value : 'Not published'}
                    </span>
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
                        ? s.award_date
                          ? date(s.award_date)
                          : publicationDate(s)
                        : deadlineFact(s).value}
                      {!hasAwardOutcome(s) && deadlineFact(s).dateOnly && (
                        <small className="cutoff-note">Cutoff time unconfirmed</small>
                      )}
                    </span>
                  </dd>
                </div>
              </dl>
              {!!s.matched_capabilities.length && (
                <section className="inspector-capabilities">
                  <h3>Capabilities</h3>
                  <CapabilityTags signal={s} data={data} />
                </section>
              )}
              <RecommendedApproach signal={s} />
              {hasAwardOutcome(s) && (
                <section className="inspector-capabilities">
                  <h3>Awarded supplier</h3>
                  <p>
                    <SupplierLinks signal={s} />
                  </p>
                </section>
              )}
            </div>
            <RecordShare signal={s} data={data} />
          </div>
          {(!['OPEN', 'EARLY_ENGAGEMENT'].includes(lifecycleState(s)) ||
            !!s.exclusion_reasons?.length) && (
            <p className="lifecycle-note">
              <Clock3 size={14} />
              <span>{s.lifecycle_reason || lifecycleLabels[lifecycleState(s)]}</span>
            </p>
          )}
          <RecordDescription signal={s} language={language} onLanguage={onLanguage} />
          <RecordDetails signal={s} />
        </div>
      </div>
      {footer}
    </div>
  )
}

const closingOptions = [
  { value: '', label: 'Any' },
  { value: '7', label: '7 days' },
  { value: '14', label: '14 days' },
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
]

function FilterPanel({
  filters: f,
  update,
  data,
  pool,
  saved,
  now,
  count,
  onClose,
  onReset,
}: {
  filters: Filters
  update: (v: Partial<Filters>) => void
  data: Dataset
  /** Records in the market, collection and search, before the filters below. */
  pool: Signal[]
  saved: string[]
  now: number
  count: number
  onClose: () => void
  onReset: () => void
}) {
  const awards = f.view === 'awards'
  // Each option counts the results it would leave, given every other active filter.
  const facets = useMemo(() => {
    const tally = (key: keyof Filters, values: (s: Signal) => string[]) => {
      const counts = new Map<string, number>()
      for (const s of filterSignals(pool, { ...f, q: '', [key]: '' }, saved, now))
        for (const value of new Set(values(s))) counts.set(value, (counts.get(value) || 0) + 1)
      return counts
    }
    return {
      capability: tally('capability', (s) => s.matched_capabilities),
      type: tally('type', (s) => [s.signal_type]),
      source: tally('source', (s) => s.provenance.map((p) => p.source)),
      sector: tally('sector', (s) => s.categories),
    }
  }, [pool, f, saved, now])
  const currencies = useMemo(
    () =>
      [
        ...new Set(
          [...data.signals.map((s) => s.currency), f.currency].filter(
            (c): c is string => !!c && /^[A-Z]{3}$/.test(c),
          ),
        ),
      ].sort(),
    [data.signals, f.currency],
  )
  const currencyNames = useMemo(() => new Intl.DisplayNames('en-GB', { type: 'currency' }), [])
  const select = (
    label: string,
    key: keyof Filters,
    choices: { value: string; label: string }[],
    counts?: Map<string, number>,
  ) => (
    <label className="filter-field">
      <span>{label}</span>
      <select aria-label={label} value={f[key]} onChange={(e) => update({ [key]: e.target.value })}>
        <option value="">Any</option>
        {choices
          .filter((o) => !counts || counts.get(o.value) || f[key] === o.value)
          .map((o) => (
            <option value={o.value} key={o.value}>
              {o.label}
              {counts ? ` (${(counts.get(o.value) || 0).toLocaleString('en-GB')})` : ''}
            </option>
          ))}
      </select>
    </label>
  )
  const text = (label: string, key: keyof Filters, placeholder: string, numeric = false) => (
    <label className="filter-field">
      <span>{label}</span>
      <input
        value={f[key]}
        placeholder={placeholder}
        inputMode={numeric ? 'numeric' : undefined}
        onChange={(e) => update({ [key]: e.target.value })}
      />
    </label>
  )
  const moreActive = ['source', 'sector', 'region', 'cpv', 'amountType', 'change'].filter(
    (key) => f[key as keyof Filters],
  ).length
  return (
    <>
      <div className="filter-sheet">
        {select(
          'Capability',
          'capability',
          [...data.capabilities]
            .sort((a, b) => a.label.localeCompare(b.label, 'en-GB'))
            .map((c) => ({ value: c.id, label: c.label })),
          facets.capability,
        )}
        {!awards && (
          <div className="filter-field">
            <span id="filter-closing">Closing within</span>
            <SwitchGroup
              labelledBy="filter-closing"
              value={f.deadline}
              options={closingOptions}
              onChange={(deadline) => update({ deadline })}
            />
          </div>
        )}
        <div className="filter-field">
          <span>Value</span>
          <div className="filter-value-row">
            <input
              type="number"
              min="0"
              aria-label="Minimum value"
              value={f.minValue}
              placeholder="Minimum"
              onChange={(e) => update({ minValue: e.target.value })}
            />
            <span aria-hidden="true">–</span>
            <input
              type="number"
              min="0"
              aria-label="Maximum value"
              value={f.maxValue}
              placeholder="Maximum"
              onChange={(e) => update({ maxValue: e.target.value })}
            />
            <select
              aria-label="Currency"
              value={f.currency}
              onChange={(e) => update({ currency: e.target.value })}
            >
              <option value="">Any currency</option>
              {currencies.map((currency) => {
                const name = currencyNames.of(currency)
                return (
                  <option key={currency} value={currency}>
                    {name && name !== currency ? `${currency} · ${name}` : currency}
                  </option>
                )
              })}
            </select>
          </div>
        </div>
        {text('Buyer', 'buyer', 'Buyer name')}
        {awards && (
          <>
            {text('Awarded supplier', 'supplier', 'Supplier name')}
            <div className="filter-field">
              <span>Awarded</span>
              <div className="filter-value-row">
                <input
                  type="date"
                  aria-label="Awarded from"
                  value={f.awardFrom}
                  onChange={(e) => update({ awardFrom: e.target.value })}
                />
                <span aria-hidden="true">–</span>
                <input
                  type="date"
                  aria-label="Awarded to"
                  value={f.awardTo}
                  onChange={(e) => update({ awardTo: e.target.value })}
                />
              </div>
            </div>
          </>
        )}
        {!awards &&
          select(
            'Notice type',
            'type',
            Object.entries(typeLabels)
              .filter(([value]) => !['AWARD', 'RENEWAL_SIGNAL'].includes(value))
              .map(([value, label]) => ({ value, label })),
            facets.type,
          )}
        <details className="filter-more" open={moreActive > 0}>
          <summary>
            More filters
            {moreActive > 0 && <span className="filter-count">{moreActive}</span>}
          </summary>
          <div className="filter-more-grid">
            {select(
              'Source',
              'source',
              data.sources
                .filter((s) => s.enabled || facets.source.has(s.id) || f.source === s.id)
                .map((s) => ({ value: s.id, label: s.name })),
              facets.source,
            )}
            {select(
              'Sector',
              'sector',
              [...new Set(data.signals.flatMap((s) => s.categories))]
                .sort()
                .map((s) => ({ value: s, label: s })),
              facets.sector,
            )}
            {text('Region', 'region', 'Region or location code')}
            {text('CPV code', 'cpv', 'e.g. 722', true)}
            {select('Amount type', 'amountType', [
              { value: 'estimated_contract', label: 'Estimated contract value' },
              { value: 'framework_ceiling', label: 'Framework ceiling' },
              { value: 'grant_range', label: 'Published grant range' },
              { value: 'programme_funding', label: 'Programme funding' },
              { value: 'award', label: 'Award value' },
              { value: 'annual_spend', label: 'Annual spend' },
              { value: 'unknown', label: 'Unspecified amount type' },
            ])}
            {!awards &&
              select('Freshness', 'change', [
                { value: 'new', label: 'New in 24 hours' },
                { value: 'updated', label: 'Updated in 24 hours' },
              ])}
          </div>
        </details>
      </div>
      <div className="modal-actions">
        <button className="button secondary" onClick={onReset}>
          Reset
        </button>
        <button className="button primary" onClick={onClose}>
          Show {count.toLocaleString('en-GB')} {awards ? 'awards' : 'signals'}{' '}
          <ArrowRight size={15} />
        </button>
      </div>
    </>
  )
}
