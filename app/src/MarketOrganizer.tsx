import { useCallback, useEffect, useId, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { GripVertical, X } from 'lucide-react'
import { defaultMarketOptions } from './lib'
import type { MarketPreferences } from './personalWorkspace'

type Drag = {
  id: string
  pointerId: number
  handle: HTMLButtonElement
  startX: number
  startY: number
  y: number
  offset: number
  left: number
  width: number
  height: number
  active: boolean
}
type Preview = {
  id: string
  before: string | null
  changed: boolean
  top: number
  left: number
  width: number
  height: number
}

const marketName = (id: string) => defaultMarketOptions.find((market) => market.id === id)!.name

export function MarketOrganizer({
  preferences,
  onArrange,
  onClose,
}: {
  preferences: MarketPreferences
  onArrange: (preferences: MarketPreferences) => boolean
  onClose: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const list = useRef<HTMLOListElement>(null)
  const drag = useRef<Drag | null>(null)
  const frame = useRef(0)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const instructions = useId()
  const ordered = preferences.order.filter((id) =>
    defaultMarketOptions.some((market) => market.id === id),
  )

  const cancelDrag = useCallback(() => {
    const current = drag.current
    drag.current = null
    cancelAnimationFrame(frame.current)
    if (current?.handle.hasPointerCapture(current.pointerId))
      current.handle.releasePointerCapture(current.pointerId)
    setPreview(null)
  }, [])

  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    window.addEventListener('blur', cancelDrag)
    return () => {
      cancelDrag()
      element?.close()
      window.removeEventListener('blur', cancelDrag)
    }
  }, [cancelDrag])

  // A change in another tab must not be overwritten by an unfinished drag.
  useEffect(cancelDrag, [preferences, cancelDrag])

  const targetFor = (current: Drag) => {
    const rows = Array.from(list.current?.children ?? []) as HTMLLIElement[]
    const remaining = rows.filter((row) => row.dataset.marketId !== current.id)
    const before = remaining.find((row) => {
      const box = row.getBoundingClientRect()
      return current.y < box.top + box.height / 2
    })
    return before?.dataset.marketId ?? null
  }

  const place = (id: string, before: string | null, keyboard = false) => {
    const next = ordered.filter((market) => market !== id)
    const index = before === null ? next.length : next.indexOf(before)
    if (index < 0 || ordered.indexOf(id) === index) return
    next.splice(index, 0, id)
    if (onArrange({ ...preferences, order: next })) {
      setAnnouncement(`${marketName(id)}, position ${index + 1} of ${next.length}.`)
      if (keyboard)
        requestAnimationFrame(() =>
          list.current
            ?.querySelector<HTMLElement>(`[data-market-id="${id}"] button`)
            ?.scrollIntoView({ block: 'nearest' }),
        )
    }
  }

  const start = (event: ReactPointerEvent<HTMLButtonElement>, id: string) => {
    if (event.button !== 0 || !event.isPrimary || drag.current) return
    const box = event.currentTarget.parentElement!.getBoundingClientRect()
    event.preventDefault()
    event.currentTarget.focus({ preventScroll: true })
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = {
      id,
      pointerId: event.pointerId,
      handle: event.currentTarget,
      startX: event.clientX,
      startY: event.clientY,
      y: event.clientY,
      offset: event.clientY - box.top,
      left: box.left,
      width: box.width,
      height: box.height,
      active: false,
    }
    let previous = performance.now()
    const update = (now: number) => {
      const current = drag.current
      const container = list.current
      if (!current || !container) return
      const seconds = Math.min(now - previous, 40) / 1000
      previous = now
      if (current.active) {
        const bounds = container.getBoundingClientRect()
        const edge = 44
        const scroll =
          current.y < bounds.top + edge
            ? -Math.min(1, (bounds.top + edge - current.y) / edge)
            : current.y > bounds.bottom - edge
              ? Math.min(1, (current.y - bounds.bottom + edge) / edge)
              : 0
        container.scrollTop += scroll * 600 * seconds
        const before = targetFor(current)
        const remaining = ordered.filter((market) => market !== current.id)
        const index = before === null ? remaining.length : remaining.indexOf(before)
        const top = Math.max(
          0,
          Math.min(window.innerHeight - current.height, current.y - current.offset),
        )
        setPreview((old) =>
          old?.top === top && old.before === before
            ? old
            : { ...current, before, top, changed: ordered.indexOf(current.id) !== index },
        )
      }
      frame.current = requestAnimationFrame(update)
    }
    frame.current = requestAnimationFrame(update)
  }

  return (
    <dialog
      ref={dialog}
      className="market-organizer"
      aria-label="Organize markets"
      onCancel={(event) => {
        if (drag.current) {
          event.preventDefault()
          cancelDrag()
          setAnnouncement('Reordering cancelled.')
        } else onClose()
      }}
    >
      <header>
        <div>
          <h2>Your markets</h2>
          <p>Pin your markets. Drag to reorder.</p>
        </div>
        <button aria-label="Close market organizer" onClick={onClose}>
          <X size={19} />
        </button>
      </header>
      <p id={instructions} className="screen-reader-only">
        Drag to reorder, or use the up and down arrow keys. Home moves to the start; End moves to
        the end.
      </p>
      <p role="status" className="screen-reader-only">
        {announcement}
      </p>
      <ol ref={list} aria-label="Market order" data-dragging={!!preview}>
        {ordered.map((id, index) => (
          <li
            key={id}
            data-market-id={id}
            data-drag-source={preview?.id === id}
            data-drop-before={preview?.changed && preview.before === id}
            data-drop-after={
              preview?.changed && preview.before === null && index === ordered.length - 1
            }
          >
            <label>
              <input
                type="checkbox"
                aria-label={`Pin ${marketName(id)}`}
                checked={preferences.pinned.includes(id)}
                disabled={!!preview}
                onChange={(event) =>
                  onArrange({
                    ...preferences,
                    pinned: event.target.checked
                      ? [...preferences.pinned, id]
                      : preferences.pinned.filter((p) => p !== id),
                  })
                }
              />
              <span>{marketName(id)}</span>
              <small>{preferences.pinned.includes(id) ? 'Pinned' : 'More'}</small>
            </label>
            <button
              className="market-drag-handle"
              aria-label={`Reorder ${marketName(id)}`}
              aria-describedby={instructions}
              title="Drag to reorder"
              onPointerDown={(event) => start(event, id)}
              onPointerMove={(event) => {
                const current = drag.current
                if (!current || event.pointerId !== current.pointerId) return
                current.y = event.clientY
                current.active ||=
                  Math.hypot(event.clientX - current.startX, event.clientY - current.startY) >= 5
              }}
              onPointerUp={(event) => {
                const current = drag.current
                if (!current || event.pointerId !== current.pointerId) return
                current.y = event.clientY
                const before = current.active ? targetFor(current) : null
                cancelDrag()
                if (current.active) place(current.id, before)
              }}
              onPointerCancel={cancelDrag}
              onLostPointerCapture={cancelDrag}
              onKeyDown={(event) => {
                if (drag.current) return
                const target =
                  event.key === 'ArrowUp'
                    ? Math.max(0, index - 1)
                    : event.key === 'ArrowDown'
                      ? Math.min(ordered.length - 1, index + 1)
                      : event.key === 'Home'
                        ? 0
                        : event.key === 'End'
                          ? ordered.length - 1
                          : -1
                if (target < 0) return
                event.preventDefault()
                const remaining = ordered.filter((market) => market !== id)
                place(id, remaining[target] ?? null, true)
              }}
            >
              <GripVertical size={18} />
            </button>
          </li>
        ))}
      </ol>
      {preview && (
        <div
          className="market-drag-preview"
          aria-hidden="true"
          style={{
            top: preview.top,
            left: preview.left + 28,
            width: preview.width - 28,
            height: preview.height,
          }}
        >
          <span>{marketName(preview.id)}</span>
          <GripVertical size={18} />
        </div>
      )}
      <footer>
        <button className="button primary" onClick={onClose}>
          Done
        </button>
      </footer>
    </dialog>
  )
}
