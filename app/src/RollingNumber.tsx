import { useLayoutEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { calm } from './delight'

/** One place of the number, keyed from the right so units stay units as the number changes. */
export type Place = { key: number; from: string; to: string }

/**
 * Pairs each place of the previous and next number. Places the next number gains arrive from
 * nothing (`from` is empty); places it loses leave to nothing (`to` is empty).
 */
export function pairPlaces(previous: string, next: string): Place[] {
  const length = Math.max(previous.length, next.length)
  return Array.from({ length }, (_, index) => {
    const key = length - 1 - index
    return {
      key,
      from: previous[previous.length - 1 - key] ?? '',
      to: next[next.length - 1 - key] ?? '',
    }
  })
}

const glyphs = '0123456789,'
const advances = new Map<string, Record<string, number>>()
/** Each glyph's width in ems in the element's font, so a wheel is exactly as wide as its digit. */
function glyphAdvances(element: HTMLElement) {
  const style = getComputedStyle(element)
  const key = [style.fontFamily, style.fontWeight, style.fontStyle, style.fontVariantNumeric].join()
  let widths = advances.get(key)
  if (!widths) {
    const probes = Array.from(glyphs, (glyph) => {
      const probe = document.createElement('span')
      probe.textContent = glyph
      probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;font-size:100px'
      element.append(probe)
      return probe
    })
    widths = Object.fromEntries(
      probes.map((probe) => [probe.textContent!, probe.getBoundingClientRect().width / 100]),
    )
    probes.forEach((probe) => probe.remove())
    advances.set(key, widths)
  }
  return widths
}

const isDigit = (char: string) => char >= '0' && char <= '9'
/** A wheel's position: its digit, or 0 for a place arriving from or leaving to nothing. */
const wheelAt = (char: string) => (isDigit(char) ? Number(char) : 0)
/** Long enough for the slowest wheel to settle before the number is plain text again. */
const settleAfter = 1100

/**
 * A count that rolls to a new value: for a moment each digit turns on its own wheel, as wide as
 * the digit it shows, then the number is plain text again. While the next value is loading
 * (`null`) the last one stays, dimmed; before there is any value `placeholder` shows.
 */
export function RollingNumber({
  value,
  placeholder = null,
}: {
  value: number | null
  placeholder?: ReactNode
}) {
  const [held, setHeld] = useState(value)
  if (value !== null && value !== held) setHeld(value)
  const shown = value ?? held
  const text = shown === null ? '' : shown.toLocaleString('en-GB')
  const element = useRef<HTMLSpanElement>(null)
  const drawn = useRef(text)
  const [roll, setRoll] = useState<{ places: Place[]; widths: Record<string, number> } | null>(null)
  useLayoutEffect(() => {
    const previous = drawn.current
    if (text === previous) return
    drawn.current = text
    if (!previous || !text || !element.current || calm()) {
      setRoll(null)
      return
    }
    const widths = glyphAdvances(element.current)
    // A roll already under way keeps its wheels and turns them on to the new value.
    setRoll((current) => ({
      places: pairPlaces(
        current ? current.places.map((place) => place.to).join('') : previous,
        text,
      ),
      widths,
    }))
    const settle = window.setTimeout(() => setRoll(null), settleAfter)
    return () => window.clearTimeout(settle)
  }, [text])
  if (shown === null) return <>{placeholder}</>
  return (
    <span className="rolling-number" ref={element} data-pending={value === null || undefined}>
      {roll ? (
        <>
          <span className="screen-reader-only">{text}</span>
          {roll.places.map(({ key, from, to }) => {
            const glyph = to || from
            return (
              <span
                className="roll-place"
                key={key}
                data-leaving={to ? undefined : true}
                data-arriving={from ? undefined : true}
                aria-hidden="true"
                style={
                  {
                    '--place': key,
                    '--from': wheelAt(from),
                    '--digit': wheelAt(to),
                    '--from-advance': roll.widths[from] ?? 0,
                    '--advance': roll.widths[to] ?? 0,
                  } as CSSProperties
                }
              >
                <span className="roll-wheel" data-mark={isDigit(glyph) ? undefined : glyph} />
              </span>
            )
          })}
        </>
      ) : (
        text
      )}
    </span>
  )
}
