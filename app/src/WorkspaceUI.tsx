import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react'
import {
  Check,
  ChevronDown,
  ArrowDownWideNarrow,
  Square,
  SquareCheck,
  EyeOff,
  Globe2,
  Languages,
  Pencil,
  ExternalLink,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { DisplayLanguage } from './types'
import type { MarketPreferences } from './personalWorkspace'
import { LiquidMetal } from '@paper-design/shaders-react'
import { defaultMarketOptions, safeURL } from './lib'
import { applyGlassLight, brandLightPosition, scrollMovesSurface } from './glassLighting'
import { MarketOrganizer } from './MarketOrganizer'

const motionQuery =
  typeof window === 'undefined' ? null : window.matchMedia('(prefers-reduced-motion: reduce)')
const subscribeMotion = (listener: () => void) => {
  motionQuery?.addEventListener('change', listener)
  return () => motionQuery?.removeEventListener('change', listener)
}
export function useReducedMotion() {
  return useSyncExternalStore(
    subscribeMotion,
    () => motionQuery?.matches ?? false,
    () => false,
  )
}

let webglAvailable: boolean | undefined
function supportsMetal() {
  if (webglAvailable !== undefined) return webglAvailable
  try {
    const gl = document.createElement('canvas').getContext('webgl2')
    webglAvailable = !!gl
    gl?.getExtension('WEBGL_lose_context')?.loseContext()
  } catch {
    webglAvailable = false
  }
  return webglAvailable
}

export function AmbientGlass() {
  const reducedMotion = useReducedMotion()
  const [active, setActive] = useState(!document.hidden)
  useEffect(() => {
    const update = () => setActive(!document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  return (
    <div
      className="ambient-glass"
      aria-hidden="true"
      data-motion={reducedMotion ? 'paused' : 'flowing'}
    >
      {active && supportsMetal() && (
        <LiquidMetal
          className="ambient-glass-shader"
          shape="none"
          colorBack="#14211b"
          colorTint="#75998a"
          repetition={0.7}
          softness={0.92}
          shiftRed={0}
          shiftBlue={0.025}
          distortion={0.17}
          contour={0.12}
          angle={-35}
          speed={reducedMotion ? 0 : 0.045}
          frame={7000}
          scale={1.1}
          fit="cover"
          minPixelRatio={0.5}
          maxPixelCount={220000}
          style={{ position: 'absolute', inset: 0 }}
        />
      )}
    </div>
  )
}

export function MetalEdge({ prominent = false }: { prominent?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [visible, setVisible] = useState(false)
  const [active, setActive] = useState(!document.hidden)
  const reducedMotion = useReducedMotion()
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting))
    if (ref.current) observer.observe(ref.current)
    const visibility = () => setActive(!document.hidden)
    document.addEventListener('visibilitychange', visibility)
    return () => {
      observer.disconnect()
      document.removeEventListener('visibilitychange', visibility)
    }
  }, [])
  return (
    <span
      ref={ref}
      className={`metal-edge ${prominent ? 'metal-prominent' : ''}`}
      aria-hidden="true"
      data-motion={reducedMotion ? 'paused' : 'flowing'}
    >
      {visible && active && supportsMetal() && (
        <LiquidMetal
          className="metal-shader"
          shape="none"
          colorBack="#9da1a8"
          colorTint="#ffffff"
          repetition={2.4}
          softness={0.12}
          shiftRed={0.08}
          shiftBlue={0.11}
          distortion={0.34}
          contour={0.5}
          angle={52}
          speed={reducedMotion ? 0 : 0.34}
          frame={8000}
          scale={1.4}
          fit="cover"
          minPixelRatio={1}
          maxPixelCount={180000}
          style={{ position: 'absolute', inset: 0 }}
        />
      )}
    </span>
  )
}

export function BrandSignature({ onHome }: { onHome: () => void }) {
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [visible, setVisible] = useState(!document.hidden)
  const reducedMotion = useReducedMotion()
  const metalActive = (hovered || focused) && visible
  useEffect(() => {
    const visibility = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', visibility)
    return () => document.removeEventListener('visibilitychange', visibility)
  }, [])
  return (
    <a
      href={import.meta.env.BASE_URL}
      className="workspace-brand"
      onClick={(event) => {
        event.preventDefault()
        onHome()
      }}
      onFocus={(event) => setFocused(event.currentTarget.matches(':focus-visible'))}
      onBlur={() => setFocused(false)}
      aria-label="Anthrion signal home"
    >
      <span
        className="brand-wordmark"
        data-metal={metalActive}
        onPointerEnter={() => setHovered(true)}
        onPointerLeave={() => setHovered(false)}
      >
        <img src={`${import.meta.env.BASE_URL}assets/anthrion-logo.svg`} alt="Anthrion" />
        <span className="brand-metal-layer" aria-hidden="true">
          {metalActive && supportsMetal() && (
            <LiquidMetal
              className="brand-metal-shader"
              shape="none"
              colorBack="#a3b0b2"
              colorTint="#f4fbf8"
              repetition={2.5}
              softness={0.16}
              shiftRed={0.04}
              shiftBlue={0.07}
              distortion={0.28}
              contour={0.45}
              angle={58}
              speed={reducedMotion ? 0 : 0.3}
              frame={8000}
              scale={1.2}
              fit="cover"
              minPixelRatio={2}
              maxPixelCount={100000}
              style={{ position: 'absolute', inset: 0 }}
            />
          )}
        </span>
      </span>
      <em className="brand-signal" data-motion={reducedMotion ? 'paused' : 'flowing'}>
        signal
      </em>
    </a>
  )
}

export function SourceNoticeLink({
  href,
  compact = false,
  children = 'Open source notice',
}: {
  href: string
  compact?: boolean
  children?: ReactNode
}) {
  return (
    <a
      href={safeURL(href)}
      target="_blank"
      rel="noopener noreferrer"
      className={`button glass-source-button optical-glass${compact ? ' source-compact' : ''}`}
    >
      <span>{children}</span>
      <span className="source-link-icon" aria-hidden="true">
        <ExternalLink size={compact ? 14 : 16} />
      </span>
      <GlassReflection trackLight />
    </a>
  )
}

export function GlassReflection({ trackLight = false }: { trackLight?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const surface = ref.current?.parentElement
    if (!trackLight || !surface) return
    const brand =
      surface.closest('dialog')?.querySelector('.brand-signal') ||
      document.querySelector('.brand-signal')
    let frame = 0
    const update = () => {
      frame = 0
      if (document.hidden) return
      const bounds = surface.getBoundingClientRect()
      if (!bounds.width || !bounds.height) return
      applyGlassLight(
        surface,
        { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 },
        brandLightPosition(brand),
      )
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    const observer = new ResizeObserver(schedule)
    observer.observe(surface)
    if (brand) observer.observe(brand)
    const scroll = (event: Event) => {
      if (scrollMovesSurface(event, surface, brand)) schedule()
    }
    window.addEventListener('scroll', scroll, { capture: true, passive: true })
    window.addEventListener('resize', schedule)
    document.addEventListener('visibilitychange', schedule)
    schedule()
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('scroll', scroll, true)
      window.removeEventListener('resize', schedule)
      document.removeEventListener('visibilitychange', schedule)
    }
  }, [trackLight])
  return <span className="glass-reflection" ref={ref} aria-hidden="true" />
}

export function MarketSection({
  selected,
  onSelect,
  language,
  onLanguage,
  preferences,
  onArrange,
}: {
  selected: string
  onSelect: (id: string) => void
  language: DisplayLanguage
  onLanguage: (language: DisplayLanguage) => void
  preferences: MarketPreferences
  onArrange: (preferences: MarketPreferences) => boolean
}) {
  const [moreOpen, setMoreOpen] = useState(false)
  const [organize, setOrganize] = useState(false)
  const moreRef = useRef<HTMLDivElement>(null)
  const moreTrigger = useRef<HTMLButtonElement>(null)
  const ordered = preferences.order
    .map((id) => defaultMarketOptions.find((m) => m.id === id))
    .filter((m): m is (typeof defaultMarketOptions)[number] => !!m)
  const pinned = ordered.filter((m) => preferences.pinned.includes(m.id))
  const more = ordered.filter((m) => !preferences.pinned.includes(m.id))
  useEffect(() => {
    if (!moreOpen) return
    const outside = (event: PointerEvent) => {
      if (!moreRef.current?.contains(event.target as Node)) setMoreOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [moreOpen])
  const marketButton = (id: string, name: string, label = name) => (
    <button key={id} aria-label={name} onClick={() => onSelect(id)} aria-pressed={selected === id}>
      <span>{label}</span>
      {selected === id && (
        <span className="market-active-line">
          <MetalEdge prominent />
        </span>
      )}
    </button>
  )
  return (
    <section className="market-section" aria-label="Market selection">
      <nav className="market-tabs" aria-label="Markets">
        {pinned.map((market) =>
          marketButton(
            market.id,
            market.name,
            market.id === '' ? 'All' : market.id === 'GB' ? 'UK' : market.name,
          ),
        )}
      </nav>
      <div
        className="more-markets"
        ref={moreRef}
        onPointerEnter={() => setMoreOpen(true)}
        onPointerLeave={() => {
          if (!moreRef.current?.contains(document.activeElement)) setMoreOpen(false)
        }}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget)) setMoreOpen(false)
        }}
      >
        <button
          className="more-markets-trigger"
          ref={moreTrigger}
          aria-haspopup="menu"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen(true)}
          onFocus={(e) => {
            if (
              !moreRef.current?.contains(e.relatedTarget as Node) &&
              e.currentTarget.matches(':focus-visible')
            )
              setMoreOpen(true)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setMoreOpen(true)
              requestAnimationFrame(() =>
                moreRef.current?.querySelector<HTMLElement>('[role="menuitemradio"]')?.focus(),
              )
            }
            if (e.key === 'Escape') setMoreOpen(false)
          }}
        >
          {!pinned.some((m) => m.id === selected)
            ? defaultMarketOptions.find((m) => m.id === selected)?.name
            : 'More'}
          <ChevronDown size={13} />
        </button>
        {moreOpen && (
          <div
            className="more-market-menu"
            role="menu"
            aria-label="More markets"
            onKeyDown={(e) => {
              const items = Array.from(
                e.currentTarget.querySelectorAll<HTMLButtonElement>('button'),
              )
              const index = items.indexOf(document.activeElement as HTMLButtonElement)
              const next =
                e.key === 'ArrowDown'
                  ? (index + 1) % items.length
                  : e.key === 'ArrowUp'
                    ? (index + items.length - 1) % items.length
                    : e.key === 'Home'
                      ? 0
                      : e.key === 'End'
                        ? items.length - 1
                        : -1
              if (next >= 0) {
                e.preventDefault()
                items[next]?.focus()
              }
              if (e.key === 'Escape') {
                e.preventDefault()
                setMoreOpen(false)
                moreTrigger.current?.focus()
              }
            }}
          >
            {more.length ? (
              more.map((market) => (
                <button
                  key={market.id}
                  role="menuitemradio"
                  aria-checked={selected === market.id}
                  tabIndex={-1}
                  onClick={() => {
                    onSelect(market.id)
                    setMoreOpen(false)
                    moreTrigger.current?.focus()
                  }}
                >
                  {market.name}
                  {selected === market.id && <Check size={14} />}
                </button>
              ))
            ) : (
              <p>All markets are pinned.</p>
            )}
          </div>
        )}
      </div>
      <button
        className="market-organize-button"
        aria-label="Organize markets"
        title="Organize markets"
        onClick={() => setOrganize(true)}
      >
        <Pencil size={14} />
      </button>
      <LanguageMenu value={language} onChange={onLanguage} />
      {organize && (
        <MarketOrganizer
          preferences={preferences}
          onArrange={onArrange}
          onClose={() => setOrganize(false)}
        />
      )}
    </section>
  )
}

const languageOptions = [
  { value: 'en', label: 'English', icon: Languages },
  { value: 'original', label: 'Original', icon: Globe2 },
] as const

export function LanguageMenu({
  value,
  onChange,
}: {
  value: DisplayLanguage
  onChange: (value: DisplayLanguage) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const options = useRef<(HTMLButtonElement | null)[]>([])
  const id = useId()
  const selected = value === 'en' ? 0 : 1
  const SelectedIcon = languageOptions[selected].icon
  useEffect(() => {
    if (!open) return
    options.current[selected]?.focus({ preventScroll: true })
    const outside = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open, selected])
  return (
    <div
      className="language-control"
      ref={ref}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false)
      }}
    >
      <button
        className="language-trigger"
        ref={trigger}
        aria-label={`Record language: ${languageOptions[selected].label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            setOpen(true)
          }
        }}
      >
        <SelectedIcon size={16} aria-hidden="true" />
        <span>{languageOptions[selected].label}</span>
        <ChevronDown size={13} aria-hidden="true" />
      </button>
      {open && (
        <div
          className="language-options"
          role="menu"
          id={id}
          aria-label="Record language"
          onKeyDown={(event) => {
            const index = options.current.indexOf(document.activeElement as HTMLButtonElement)
            const next =
              event.key === 'ArrowDown' || event.key === 'ArrowUp'
                ? (index + 1) % 2
                : event.key === 'Home' || event.key.toLowerCase() === 'e'
                  ? 0
                  : event.key === 'End' || event.key.toLowerCase() === 'o'
                    ? 1
                    : -1
            if (next >= 0) {
              event.preventDefault()
              options.current[next]?.focus({ preventScroll: true })
            }
            if (event.key === 'Escape') {
              event.preventDefault()
              setOpen(false)
              trigger.current?.focus({ preventScroll: true })
            }
            if (event.key === 'Tab') {
              setOpen(false)
              trigger.current?.focus({ preventScroll: true })
            }
          }}
        >
          {languageOptions.map(({ value: key, label, icon: Icon }, index) => (
            <button
              key={key}
              ref={(element) => {
                options.current[index] = element
              }}
              role="menuitemradio"
              aria-checked={value === key}
              tabIndex={-1}
              onClick={() => {
                onChange(key)
                setOpen(false)
                trigger.current?.focus({ preventScroll: true })
              }}
            >
              <Icon size={17} aria-hidden="true" />
              <span>{label}</span>
              <Check size={15} className="language-check" aria-hidden="true" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const sortOptions = [
  ['recent', 'Most recent'],
  ['updated', 'Recently updated'],
  ['deadline', 'Closing soon'],
  ['value', 'Highest value'],
  ['value-low', 'Lowest value'],
  ['capability', 'Capability A-Z'],
  ['awarded', 'Awarded'],
] as const

export function SortMenu({
  value,
  onChange,
  showHidden,
  onShowHidden,
}: {
  value: string
  onChange: (value: string) => void
  showHidden: boolean
  onShowHidden: (value: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const options = useRef<(HTMLButtonElement | null)[]>([])
  const id = useId()
  const selected = Math.max(
    0,
    sortOptions.findIndex(([key]) => key === value),
  )
  useEffect(() => {
    if (!open) return
    options.current[selected]?.focus()
    const outside = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open, selected])
  return (
    <div
      className="sort-menu"
      ref={ref}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false)
      }}
    >
      <button
        ref={trigger}
        className="sort-trigger"
        aria-label={`Sort opportunities: ${sortOptions[selected][1]}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen(!open)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault()
            setOpen(true)
          }
        }}
      >
        <ArrowDownWideNarrow size={16} />
        <span>{sortOptions[selected][1]}</span>
        {showHidden && <EyeOff className="sort-hidden-icon" size={14} aria-hidden="true" />}
        <ChevronDown size={14} />
      </button>
      {open && (
        <div
          className="sort-options"
          role="menu"
          id={id}
          aria-label="Sort opportunities"
          onKeyDown={(e) => {
            const index = options.current.indexOf(document.activeElement as HTMLButtonElement)
            const length = sortOptions.length + 1
            const last = length - 1
            const next =
              e.key === 'ArrowDown'
                ? (index + 1) % length
                : e.key === 'ArrowUp'
                  ? (index + last) % length
                  : e.key === 'Home'
                    ? 0
                    : e.key === 'End'
                      ? last
                      : -1
            if (next >= 0) {
              e.preventDefault()
              options.current[next]?.focus()
            }
            if (e.key === 'Escape') {
              e.preventDefault()
              setOpen(false)
              trigger.current?.focus()
            }
            if (e.key === 'Tab') setOpen(false)
            if (e.key.length === 1 && /[a-z]/i.test(e.key)) {
              const match = sortOptions.findIndex(([, label]) =>
                label.toLowerCase().startsWith(e.key.toLowerCase()),
              )
              if (match >= 0) {
                e.preventDefault()
                options.current[match]?.focus()
              }
            }
          }}
        >
          {sortOptions.map(([key, label], index) => (
            <button
              key={key}
              ref={(element) => {
                options.current[index] = element
              }}
              role="menuitemradio"
              aria-checked={value === key}
              tabIndex={-1}
              onClick={() => {
                onChange(key)
                setOpen(false)
                trigger.current?.focus()
              }}
            >
              <span>{label}</span>
              {value === key && <Check size={16} />}
            </button>
          ))}
          <div className="sort-divider" role="separator" />
          <button
            ref={(element) => {
              options.current[sortOptions.length] = element
            }}
            role="menuitemcheckbox"
            aria-checked={showHidden}
            tabIndex={-1}
            onClick={() => {
              onShowHidden(!showHidden)
              setOpen(false)
              trigger.current?.focus()
            }}
          >
            <span>Show hidden</span>
            {showHidden ? <SquareCheck size={16} /> : <Square size={16} />}
          </button>
        </div>
      )}
    </div>
  )
}
