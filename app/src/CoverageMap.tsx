import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { coverageMap } from './coverageGeometry'
import type { CountryCoverage } from './coverage'

// One hue, monotone lightness (validated for each theme's surface): readable with deuteranopia.
const breaks = [20, 40, 60, 80]
const labels = ['<20%', '20–40', '40–60', '60–80', '80%+']
const classOf = (estimate: number) => breaks.filter((limit) => estimate >= limit).length
const about = (estimate: number) => `~${Math.round(estimate)}%`

export default function CoverageMap({
  countries,
  selected,
  onSelect,
}: {
  countries: CountryCoverage[]
  selected: string[]
  onSelect: (id: string) => void
}) {
  const frame = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null)
  const tip = useRef<HTMLDivElement>(null)
  // Half the tooltip's measured width keeps it inside the frame at either edge.
  const [tipHalf, setTipHalf] = useState(90)
  useLayoutEffect(() => {
    if (tip.current) setTipHalf(tip.current.offsetWidth / 2 + 4)
  }, [hover?.id])
  const byId = useMemo(
    () => new Map(countries.filter((c) => c.estimate !== null).map((c) => [c.id, c])),
    [countries],
  )
  const ranked = useMemo(
    () =>
      [...byId.values()].sort(
        (a, b) => b.estimate! - a.estimate! || b.count - a.count || a.name.localeCompare(b.name),
      ),
    [byId],
  )
  const active = hover ? byId.get(hover.id) : undefined
  const point = (event: ReactPointerEvent, id: string) => {
    const box = frame.current?.getBoundingClientRect()
    if (box) setHover({ id, x: event.clientX - box.left, y: event.clientY - box.top })
  }
  const highlight = (id: string) => {
    const box = frame.current?.getBoundingClientRect()
    const path = frame.current?.querySelector<SVGGraphicsElement>(`[data-country="${id}"]`)
    const shape = path?.getBoundingClientRect()
    if (box && shape)
      setHover({ id, x: shape.left - box.left + shape.width / 2, y: shape.top - box.top })
  }
  const pick = (id: string) => {
    if (byId.has(id)) onSelect(id)
  }
  const { width, height, inset } = coverageMap
  return (
    <div className="coverage">
      <div
        className="coverage-frame"
        ref={frame}
        onPointerLeave={() => setHover(null)}
        data-hovering={!!hover}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Estimated source reach: ${ranked
            .map((c) => `${c.name} about ${Math.round(c.estimate!)}%`)
            .join(', ')}`}
        >
          <path className="coverage-land" d={coverageMap.context} />
          <rect
            className="coverage-inset"
            x={inset.x}
            y={inset.y}
            width={inset.width}
            height={inset.height}
            rx="5"
          />
          <path className="coverage-land" d={coverageMap.insetContext} />
          {coverageMap.countries.map(({ id, d }) => {
            const country = byId.get(id)
            return (
              <path
                key={id}
                d={d}
                data-country={id}
                data-class={country ? classOf(country.estimate!) : undefined}
                data-selected={selected.includes(id) || undefined}
                data-hover={hover?.id === id || undefined}
                className={country ? 'coverage-country' : 'coverage-land coverage-empty'}
                onPointerMove={country ? (event) => point(event, id) : undefined}
                onClick={() => pick(id)}
              />
            )
          })}
          {/* Outlines are drawn above every country, so neighbours never cover part of one. */}
          {coverageMap.countries
            .filter(({ id }) => hover?.id === id || selected.includes(id))
            .map(({ id, d }) => (
              <path
                key={`outline-${id}`}
                d={d}
                className="coverage-outline"
                data-hover={hover?.id === id || undefined}
                data-selected={selected.includes(id) || undefined}
                aria-hidden="true"
              />
            ))}
          {Object.entries(coverageMap.markers).map(([id, [x, y]]) => {
            const country = byId.get(id)
            if (!country) return null
            return (
              <g key={id}>
                <circle
                  className="coverage-marker"
                  cx={x}
                  cy={y}
                  r="2.4"
                  data-class={classOf(country.estimate!)}
                  data-selected={selected.includes(id) || undefined}
                />
                <circle
                  className="coverage-hit"
                  cx={x}
                  cy={y}
                  r={id === 'LU' ? 4 : 7}
                  onPointerMove={(event) => point(event, id)}
                  onClick={() => pick(id)}
                />
              </g>
            )
          })}
        </svg>
        {active && hover && (
          <div
            ref={tip}
            className="coverage-tooltip"
            role="status"
            // Near the top edge (the inset) the tooltip opens below the pointer instead.
            data-below={hover.y < 96 || undefined}
            style={{
              left: Math.min(
                Math.max(hover.x, tipHalf),
                (frame.current?.clientWidth || 300) - tipHalf,
              ),
              top: hover.y,
            }}
          >
            <span>{active.name}</span>
            <strong>{about(active.estimate!)}</strong>
            <small>
              {active.sources.length === 1 ? active.sources[0] : `${active.sources.length} sources`}
              {` · ${active.count.toLocaleString('en-GB')} signals`}
            </small>
            {!!active.missing.length && (
              <small className="coverage-missing">
                Not collected: {active.missing.slice(0, 2).join(', ')}
              </small>
            )}
          </div>
        )}
      </div>
      <div className="coverage-legend" aria-label="Estimated source reach">
        <span className="coverage-legend-title">Estimated source reach</span>
        <ol>
          {labels.map((label, index) => (
            <li key={label}>
              <i data-class={index} aria-hidden="true" />
              {label}
            </li>
          ))}
          <li className="coverage-legend-empty">
            <i aria-hidden="true" />
            Not covered
          </li>
        </ol>
        <small className="coverage-basis">
          Source availability before collection limits and relevance filtering.
        </small>
      </div>
      <details className="coverage-table">
        <summary>
          Countries <span>{ranked.length}</span>
        </summary>
        <ol>
          {ranked.map((country) => (
            <li key={country.id}>
              <button
                aria-pressed={selected.length === 1 && selected[0] === country.id}
                onClick={() => pick(country.id)}
                onPointerEnter={() => highlight(country.id)}
                onPointerLeave={() => setHover(null)}
                onFocus={() => highlight(country.id)}
                onBlur={() => setHover(null)}
              >
                <i data-class={classOf(country.estimate!)} aria-hidden="true" />
                <span>{country.name}</span>
                <strong>{about(country.estimate!)}</strong>
              </button>
            </li>
          ))}
        </ol>
      </details>
    </div>
  )
}
