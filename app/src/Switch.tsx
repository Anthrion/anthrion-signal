import { useEffect, useLayoutEffect, useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { calm } from './delight'

export type SwitchOption<T extends string> = {
  value: T
  label: ReactNode
  /** Needed when the visible label is abbreviated or not plain text. */
  name?: string
}

/**
 * A physical switch: the choices sit in a recessed track and a raised thumb slides to the
 * chosen one. Pressing rocks the track towards that side; the thumb catches the light as it lands.
 */
export function SwitchGroup<T extends string>({
  value,
  options,
  onChange,
  label,
  labelledBy,
  className = '',
}: {
  value: T
  options: readonly SwitchOption<T>[]
  onChange: (value: T) => void
  label?: string
  labelledBy?: string
  className?: string
}) {
  const track = useRef<HTMLDivElement>(null)
  const glint = useRef<HTMLSpanElement>(null)
  const shown = useRef(value)
  const checked = options.findIndex((option) => option.value === value)

  useLayoutEffect(() => {
    const element = track.current
    if (!element) return
    const place = () => {
      const button = element.querySelector<HTMLElement>('button[aria-checked="true"]')
      element.dataset.thumb = button ? 'on' : 'off'
      if (!button) return
      element.style.setProperty('--thumb-x', `${button.offsetLeft}px`)
      element.style.setProperty('--thumb-y', `${button.offsetTop}px`)
      element.style.setProperty('--thumb-w', `${button.offsetWidth}px`)
      element.style.setProperty('--thumb-h', `${button.offsetHeight}px`)
    }
    place()
    const observer = new ResizeObserver(place)
    observer.observe(element)
    element.querySelectorAll('button').forEach((button) => observer.observe(button))
    return () => observer.disconnect()
    // Sizes change with fonts and responsive labels; the observer follows them.
  }, [value, options.length])

  useEffect(() => {
    // The thumb glides only after it has been placed, never in from the corner.
    const frame = requestAnimationFrame(() => {
      if (track.current) track.current.dataset.ready = ''
    })
    return () => cancelAnimationFrame(frame)
  }, [])

  useEffect(() => {
    if (shown.current === value) return
    shown.current = value
    if (calm()) return
    glint.current?.animate(
      [
        { transform: 'translateX(-140%) skewX(-20deg)', opacity: 0 },
        { opacity: 1, offset: 0.4 },
        { transform: 'translateX(260%) skewX(-20deg)', opacity: 0 },
      ],
      { duration: 700, delay: 140, easing: 'cubic-bezier(0.4, 0, 0.2, 1)' },
    )
  }, [value])

  const release = () => {
    if (track.current) delete track.current.dataset.press
  }
  const keys = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key]
    const target =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? options.length - 1
          : step
            ? (index + step + options.length) % options.length
            : -1
    if (target < 0) return
    event.preventDefault()
    onChange(options[target].value)
    const group = track.current
    requestAnimationFrame(() =>
      group?.querySelectorAll<HTMLButtonElement>('button[role="radio"]')[target]?.focus(),
    )
  }
  return (
    <div
      ref={track}
      className={`segmented switch ${className}`}
      role="radiogroup"
      aria-label={labelledBy ? undefined : label}
      aria-labelledby={labelledBy}
      onPointerUp={release}
      onPointerLeave={release}
      onPointerCancel={release}
    >
      <span className="switch-thumb" aria-hidden="true">
        <span className="switch-glint" ref={glint} />
      </span>
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          data-value={option.value}
          aria-checked={option.value === value}
          aria-label={option.name}
          tabIndex={index === Math.max(0, checked) ? 0 : -1}
          onPointerDown={(event) => {
            if (event.button !== 0 || !track.current) return
            track.current.dataset.press =
              options.length > 1 && index === 0
                ? 'start'
                : options.length > 1 && index === options.length - 1
                  ? 'end'
                  : 'centre'
          }}
          onClick={() => onChange(option.value)}
          onKeyDown={(event) => keys(event, index)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
