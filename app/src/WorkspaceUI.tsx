import { useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import {
  Check,
  ChevronDown,
  ArrowDownWideNarrow,
  Globe2,
  Languages,
  Pencil,
  ExternalLink,
  WholeWord,
} from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import type { DisplayLanguage } from './types'
import type { MarketPreferences } from './personalWorkspace'
import { LiquidMetal, MeshGradient } from '@paper-design/shaders-react'
import { defaultMarketOptions, safeURL } from './lib'
import { applyGlassLight, brandLightPosition, scrollMovesSurface } from './glassLighting'
import { MarketOrganizer } from './MarketOrganizer'
import { usePreferences } from './preferences'
import { switchTheme, useTheme } from './theme'
import { SwitchGroup } from './Switch'

function mediaStore(query: string) {
  const media = typeof window === 'undefined' ? null : window.matchMedia(query)
  return {
    subscribe: (listener: () => void) => {
      media?.addEventListener('change', listener)
      return () => media?.removeEventListener('change', listener)
    },
    matches: () => media?.matches ?? false,
  }
}
const motion = mediaStore('(prefers-reduced-motion: reduce)')
const narrow = mediaStore('(max-width: 900px)')
/** The operating-system setting, or Signal's own Effects: Reduced preference. */
export function useReducedMotion() {
  const system = useSyncExternalStore(motion.subscribe, motion.matches, () => false)
  const { effects } = usePreferences()
  return system || effects === 'reduced'
}
export function useNarrowScreen() {
  return useSyncExternalStore(narrow.subscribe, narrow.matches, () => false)
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

// The ambient light behind the workspace: liquid chrome in the dark theme. The light theme
// uses mother-of-pearl, since the metal shader always carries near-black stripes.
const pearl = ['#ffffff', '#cfe4f3', '#f6ecd9', '#d2ecdf', '#d8def6']

export function AmbientGlass() {
  const reducedMotion = useReducedMotion()
  const theme = useTheme()
  const [active, setActive] = useState(!document.hidden)
  useEffect(() => {
    const update = () => setActive(!document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  const shared = {
    className: 'ambient-glass-shader',
    fit: 'cover' as const,
    minPixelRatio: 0.5,
    maxPixelCount: 220000,
    style: { position: 'absolute', inset: 0 } as CSSProperties,
  }
  return (
    <div
      className="ambient-glass"
      aria-hidden="true"
      data-motion={reducedMotion ? 'paused' : 'flowing'}
    >
      {active &&
        supportsMetal() &&
        (theme === 'light' ? (
          <MeshGradient
            key="pearl"
            {...shared}
            colors={pearl}
            distortion={0.85}
            swirl={0.3}
            speed={reducedMotion ? 0 : 0.06}
            frame={9000}
            scale={1.2}
          />
        ) : (
          <LiquidMetal
            key="chrome"
            {...shared}
            shape="none"
            colorBack="#0f1916"
            colorTint="#9cc3bb"
            repetition={1.1}
            softness={0.8}
            shiftRed={0.03}
            shiftBlue={0.1}
            distortion={0.22}
            contour={0.18}
            angle={-35}
            speed={reducedMotion ? 0 : 0.05}
            frame={7000}
            scale={1.1}
          />
        ))}
    </div>
  )
}

const edgeMetal = {
  dark: { back: '#9da1a8', tint: '#ffffff' },
  light: { back: '#7d6230', tint: '#c9a04e' },
}

export function MetalEdge({ prominent = false }: { prominent?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  const theme = useTheme()
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
          colorBack={edgeMetal[theme].back}
          colorTint={edgeMetal[theme].tint}
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

// The mark's six dots in the order they light: up the left of the A, over its apex, down the
// right, and last the centre, which sends out the signal.
const brandDots = [
  { x: 41.15, y: 72.15, tone: 'light' },
  { x: 41.15, y: 50.75, tone: 'dark' },
  { x: 62.45, y: 29.25, tone: 'dark' },
  { x: 83.75, y: 50.65, tone: 'dark' },
  { x: 83.75, y: 72.15, tone: 'light' },
  { x: 62.45, y: 50.65, tone: 'light' },
] as const

/** The Anthrion mark in its two blues, drawn over the wordmark so each dot can light. */
function BrandDots() {
  const id = `brand-halo-${useId().replace(/[^\w-]/g, '')}`
  const order = (index: number) => ({ '--order': index }) as CSSProperties
  return (
    <svg className="brand-dots" viewBox="31 17 378 65" aria-hidden="true">
      <defs>
        {(['light', 'dark'] as const).map((tone) => (
          <radialGradient key={tone} id={`${id}-${tone}`}>
            <stop offset="0" className={`brand-halo-${tone}`} stopOpacity="0.95" />
            <stop offset="0.45" className={`brand-halo-${tone}`} stopOpacity="0.35" />
            <stop offset="1" className={`brand-halo-${tone}`} stopOpacity="0" />
          </radialGradient>
        ))}
      </defs>
      {brandDots.map((dot, index) => (
        <circle
          key={`halo-${index}`}
          className="brand-dot-halo"
          cx={dot.x}
          cy={dot.y}
          r="19"
          fill={`url(#${id}-${dot.tone})`}
          style={order(index)}
        />
      ))}
      {brandDots.map((dot, index) => (
        <circle
          key={`dot-${index}`}
          className="brand-dot"
          data-tone={dot.tone}
          cx={dot.x}
          cy={dot.y}
          r="8.4"
          style={order(index)}
        />
      ))}
      {brandDots.map((dot, index) => (
        <circle
          key={`spark-${index}`}
          className="brand-dot-spark"
          cx={dot.x}
          cy={dot.y}
          r="8.4"
          style={order(index)}
        />
      ))}
      <circle className="brand-dot-ring" cx="62.45" cy="50.65" r="8.4" />
    </svg>
  )
}

// The light theme's metal is a darkish gold: the shader burns its stripes into this tint.
const brandMetal = {
  dark: { back: '#a3b0b2', tint: '#f4fbf8' },
  light: { back: '#7d6230', tint: '#c9a04e' },
}

export function BrandSignature({ onHome }: { onHome: () => void }) {
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [signalHovered, setSignalHovered] = useState(false)
  const [visible, setVisible] = useState(!document.hidden)
  const reducedMotion = useReducedMotion()
  const theme = useTheme()
  const metalActive = (hovered || focused) && visible
  const signalLit = signalHovered || focused
  const flash = useRef<HTMLSpanElement>(null)
  const sweep = useRef<Animation | null>(null)
  useEffect(() => {
    const visibility = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', visibility)
    return () => document.removeEventListener('visibilitychange', visibility)
  }, [])
  // The flash starts the moment the word is lit. When it is left, the light keeps travelling
  // while it fades, so the word settles back instead of snapping.
  useEffect(() => {
    if (signalLit && !reducedMotion && flash.current) {
      sweep.current?.cancel()
      sweep.current = flash.current.animate(
        [
          { backgroundPosition: '100% 50%', easing: 'cubic-bezier(0.45, 0, 0.25, 1)' },
          { backgroundPosition: '0% 50%', offset: 0.38 },
          { backgroundPosition: '0% 50%' },
        ],
        { duration: 3200, iterations: Infinity },
      )
      return
    }
    const fading = sweep.current
    if (!fading) return
    const stop = window.setTimeout(() => {
      fading.cancel()
      if (sweep.current === fading) sweep.current = null
    }, 480)
    return () => window.clearTimeout(stop)
  }, [signalLit, reducedMotion])
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
        data-lit={hovered || focused}
        onPointerEnter={() => setHovered(true)}
        onPointerLeave={() => setHovered(false)}
      >
        <img src={`${import.meta.env.BASE_URL}assets/anthrion-wordmark.svg`} alt="Anthrion" />
        <BrandDots />
        <span className="brand-metal-layer" aria-hidden="true">
          {metalActive && supportsMetal() && (
            <LiquidMetal
              className="brand-metal-shader"
              shape="none"
              colorBack={brandMetal[theme].back}
              colorTint={brandMetal[theme].tint}
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
      <em
        className="brand-signal"
        data-lit={signalLit}
        onPointerEnter={() => setSignalHovered(true)}
        onPointerLeave={() => setSignalHovered(false)}
      >
        signal
        <span className="signal-flash" ref={flash} aria-hidden="true">
          signal
        </span>
      </em>
    </a>
  )
}

const sunRays = Array.from({ length: 8 }, (_, index) => {
  const angle = (index * Math.PI) / 4
  const point = (radius: number) =>
    [12 + Math.cos(angle) * radius, 12 + Math.sin(angle) * radius].map((n) => n.toFixed(2))
  const [x1, y1] = point(8.2)
  const [x2, y2] = point(10.4)
  return { x1, y1, x2, y2 }
})

/** Sun in the light theme, moon in the dark; the next theme spreads from the pointer. */
export function ThemeToggle() {
  const theme = useTheme()
  const reducedMotion = useReducedMotion()
  const mask = `theme-moon-${useId().replace(/[^\w-]/g, '')}`
  const next = theme === 'dark' ? 'light' : 'dark'
  const label = `Switch to ${next} theme`
  return (
    <button
      type="button"
      className="theme-toggle"
      data-icon={theme}
      aria-label={label}
      title={label}
      aria-keyshortcuts="T"
      onClick={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect()
        // Keyboard activation has no pointer position; the circle then starts at the icon.
        const pointer = event.detail > 0
        switchTheme(
          next,
          {
            x: pointer ? event.clientX : bounds.left + bounds.width / 2,
            y: pointer ? event.clientY : bounds.top + bounds.height / 2,
          },
          !reducedMotion,
        )
      }}
    >
      <svg viewBox="0 0 24 24" width="19" height="19" aria-hidden="true">
        <mask id={mask}>
          <rect width="24" height="24" fill="#fff" />
          <circle className="theme-icon-cut" cx="17.5" cy="6.5" r="6" fill="#000" />
        </mask>
        <circle className="theme-icon-core" cx="12" cy="12" r="5" mask={`url(#${mask})`} />
        <g className="theme-icon-rays">
          {sunRays.map((ray, index) => (
            <line key={index} {...ray} />
          ))}
        </g>
      </svg>
    </button>
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
  const [lit, setLit] = useState(false)
  const reducedMotion = useReducedMotion()
  const glint = useRef<HTMLSpanElement>(null)
  // Pointed at, the glass catches a pass of light and its rim turns to liquid metal.
  const catchLight = () => {
    setLit(true)
    const band = glint.current?.firstElementChild
    if (reducedMotion || !glint.current || !band) return
    const timing = { duration: 950, easing: 'cubic-bezier(0.3, 0.1, 0.3, 1)' }
    glint.current.animate([{ opacity: 0 }, { opacity: 0.85, offset: 0.3 }, { opacity: 0 }], timing)
    band.animate(
      [
        { transform: 'translateX(-70%) rotate(18deg)' },
        { transform: 'translateX(360%) rotate(18deg)' },
      ],
      timing,
    )
  }
  return (
    <a
      href={safeURL(href)}
      target="_blank"
      rel="noopener noreferrer"
      className={`button glass-source-button optical-glass${compact ? ' source-compact' : ''}`}
      onPointerEnter={catchLight}
      onPointerLeave={() => setLit(false)}
      onFocus={(event) => event.currentTarget.matches(':focus-visible') && catchLight()}
      onBlur={() => setLit(false)}
    >
      <span>{children}</span>
      <span className="source-link-icon" aria-hidden="true">
        <ExternalLink size={compact ? 14 : 16} />
      </span>
      <GlassReflection trackLight />
      <span className="glass-glint" ref={glint} aria-hidden="true">
        <i />
      </span>
      {lit && !reducedMotion && <MetalEdge />}
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
  counts,
  language,
  onLanguage,
  preferences,
  onArrange,
}: {
  selected: string
  onSelect: (id: string) => void
  /** Current opportunities per market, when the manifest publishes them. */
  counts: Record<string, number>
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
  const tabs = useRef<HTMLElement>(null)
  const pinnedKey = pinned.map((market) => market.id).join('|')
  // One liquid-metal line glides between the pinned markets rather than jumping.
  useLayoutEffect(() => {
    const nav = tabs.current
    if (!nav) return
    const place = () => {
      const tab = nav.querySelector<HTMLElement>('button[aria-pressed="true"]')
      nav.dataset.indicator = tab ? 'on' : 'off'
      if (!tab) return
      nav.style.setProperty('--indicator-x', `${tab.offsetLeft + 5}px`)
      nav.style.setProperty('--indicator-w', `${Math.max(0, tab.offsetWidth - 10)}px`)
    }
    place()
    const observer = new ResizeObserver(place)
    observer.observe(nav)
    nav.querySelectorAll('button').forEach((button) => observer.observe(button))
    const ready = requestAnimationFrame(() => (nav.dataset.ready = ''))
    return () => {
      observer.disconnect()
      cancelAnimationFrame(ready)
    }
  }, [selected, pinnedKey])
  const marketButton = (id: string, name: string, label = name) => (
    <button key={id} aria-label={name} onClick={() => onSelect(id)} aria-pressed={selected === id}>
      <span>{label}</span>
    </button>
  )
  return (
    <section className="market-section" aria-label="Market selection">
      <nav className="market-tabs" aria-label="Markets" ref={tabs}>
        {pinned.map((market) =>
          marketButton(
            market.id,
            market.name,
            market.id === '' ? 'All' : market.id === 'GB' ? 'UK' : market.name,
          ),
        )}
        {pinned.some((market) => market.id === selected) && (
          <span className="market-active-line market-indicator" aria-hidden="true">
            <MetalEdge prominent />
          </span>
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
                  data-empty={counts[market.id] === 0 || undefined}
                  tabIndex={-1}
                  onClick={() => {
                    onSelect(market.id)
                    setMoreOpen(false)
                    moreTrigger.current?.focus()
                  }}
                >
                  <span>{market.name}</span>
                  {selected === market.id ? (
                    <Check size={14} />
                  ) : (
                    counts[market.id] !== undefined && (
                      <small aria-hidden="true">{counts[market.id].toLocaleString('en-GB')}</small>
                    )
                  )}
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
      <LanguageSwitch value={language} onChange={onLanguage} />
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
  { value: 'en', label: 'English', short: 'EN', icon: Languages },
  { value: 'original', label: 'Original', short: 'Orig', icon: Globe2 },
] as const

const languageSwitchOptions = languageOptions.map(({ value, label, short }) => ({
  value,
  name: label,
  label: (
    <>
      <span className="language-long">{label}</span>
      <span className="language-short">{short}</span>
    </>
  ),
}))

/** One click between the English translation and the source wording, for every record. */
export function LanguageSwitch({
  value,
  onChange,
}: {
  value: DisplayLanguage
  onChange: (value: DisplayLanguage) => void
}) {
  return (
    <SwitchGroup
      className="language-switch"
      label="Record language"
      value={value}
      onChange={onChange}
      options={languageSwitchOptions}
    />
  )
}

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
  ['relevance', 'Best match'],
  ['recent', 'Most recent'],
  ['updated', 'Recently updated'],
  ['deadline', 'Soonest deadline'],
  ['value', 'Highest value'],
  ['value-low', 'Lowest value'],
  ['capability', 'Capability A-Z'],
] as const

export function SortMenu({
  value,
  onChange,
  fixedLabel,
}: {
  value: string
  onChange: (value: string) => void
  /** Collections with a single meaningful order (awards) show it instead of the menu. */
  fixedLabel?: string
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
  if (fixedLabel)
    return (
      <div className="sort-menu">
        <button className="sort-trigger" disabled aria-label={`Sorted by ${fixedLabel}`}>
          <ArrowDownWideNarrow size={16} />
          <span>{fixedLabel}</span>
        </button>
      </div>
    )
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
        title={sortOptions[selected][1]}
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
            const length = sortOptions.length
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
        </div>
      )}
    </div>
  )
}

const scopeModes = [
  ['capability', 'Text + capabilities'],
  ['exact', 'Exact source text'],
] as const
const scopeMatches = [
  ['all', 'All words'],
  ['any', 'Any word'],
  ['phrase', 'Exact phrase'],
] as const

/** Search options live inside the search field; the icon marks a non-default scope. */
export function SearchScope({
  mode,
  match,
  onChange,
}: {
  mode: string
  match: string
  onChange: (patch: { searchMode?: string; match?: string }) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const custom = mode !== 'capability' || match !== 'all'
  useEffect(() => {
    if (!open) return
    ref.current?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus()
    const outside = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])
  const group = (
    legend: string,
    value: string,
    options: readonly (readonly [string, string])[],
    choose: (value: string) => void,
  ) => (
    <fieldset>
      <legend>{legend}</legend>
      <SwitchGroup
        label={legend}
        value={value}
        options={options.map(([key, text]) => ({ value: key, label: text }))}
        onChange={choose}
      />
    </fieldset>
  )
  return (
    <div
      className="search-scope"
      ref={ref}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false)
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.stopPropagation()
          setOpen(false)
          trigger.current?.focus()
        }
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="search-scope-trigger"
        aria-label="Search options"
        title="Search options"
        aria-haspopup="dialog"
        aria-expanded={open}
        data-custom={custom || undefined}
        onClick={() => setOpen(!open)}
      >
        <WholeWord size={17} />
      </button>
      {open && (
        <div className="search-scope-panel" role="dialog" aria-label="Search options">
          {group('Search in', mode, scopeModes, (searchMode) => onChange({ searchMode }))}
          {group('Match', match, scopeMatches, (value) => onChange({ match: value }))}
        </div>
      )}
    </div>
  )
}
