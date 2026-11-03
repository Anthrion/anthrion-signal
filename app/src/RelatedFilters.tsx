import { Search, SlidersHorizontal } from 'lucide-react'
import { useId, useRef } from 'react'
import { responseDeadline, searchText } from './lib'
import type { EnglishText, Signal } from './types'

export const emptyRelatedFilters = {
  q: '',
  party: '',
  dateMode: '',
  from: '',
  to: '',
  valueMode: '',
  min: '',
  max: '',
  currency: '',
}
export type RelatedFilterState = typeof emptyRelatedFilters
export function filterRelated(
  signal: Signal,
  filters: RelatedFilterState,
  kind: 'signals' | 'awards',
  translation?: EnglishText,
) {
  if (filters.q) {
    const text = searchText(
      [
        signal.title,
        signal.description || signal.search_text,
        signal.buyer_name,
        signal.incumbent_supplier,
        ...(signal.winners || []).map((w) => w.name),
        translation?.title,
        translation?.description,
      ].join(' '),
    )
    if (
      !searchText(filters.q)
        .split(/\s+/)
        .filter(Boolean)
        .every((word) => text.includes(word))
    )
      return false
  }
  const party =
    kind === 'awards'
      ? [signal.incumbent_supplier, ...(signal.winners || []).map((w) => w.name)].join(' ')
      : signal.buyer_name || ''
  if (filters.party && !searchText(party).includes(searchText(filters.party))) return false
  const day = (kind === 'awards' ? signal.award_date : responseDeadline(signal))?.slice(0, 10)
  if (
    filters.dateMode &&
    ((filters.from && (!day || day < filters.from)) || (filters.to && (!day || day > filters.to)))
  )
    return false
  if (filters.currency && (signal.amount?.currency || signal.currency) !== filters.currency)
    return false
  if (filters.valueMode && (filters.min || filters.max)) {
    const value =
      signal.amount?.maximum ?? signal.amount?.minimum ?? signal.value_max ?? signal.value_min
    if (
      value == null ||
      (filters.min && value < Number(filters.min)) ||
      (filters.max && value > Number(filters.max))
    )
      return false
  }
  return true
}
export function RelatedFilters({
  value,
  onChange,
  kind,
  currencies,
}: {
  value: RelatedFilterState
  onChange: (value: RelatedFilterState) => void
  kind: 'signals' | 'awards'
  currencies: string[]
}) {
  const id = useId()
  const details = useRef<HTMLDetailsElement>(null)
  const update = (change: Partial<RelatedFilterState>) => onChange({ ...value, ...change })
  const active = [value.party, value.dateMode, value.valueMode, value.currency].filter(
    Boolean,
  ).length
  const invalidDate = !!value.from && !!value.to && value.from > value.to
  const invalidValue = !!value.min && !!value.max && Number(value.min) > Number(value.max)
  const valueReady = currencies.length <= 1 || !!value.currency
  return (
    <div className="related-controls">
      <label className="related-search">
        <Search size={15} aria-hidden="true" />
        <input
          aria-label={`Search related ${kind}`}
          placeholder="Search"
          value={value.q}
          onChange={(e) => update({ q: e.target.value })}
        />
      </label>
      <details
        ref={details}
        className="related-filter-menu"
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.stopPropagation()
            if (details.current) details.current.open = false
            details.current?.querySelector('summary')?.focus()
          }
        }}
      >
        <summary>
          <SlidersHorizontal size={14} />
          Filters{active > 0 && <span>{active}</span>}
        </summary>
        <div className="related-filter-panel">
          <label>
            {kind === 'awards' ? 'Supplier' : 'Buyer'}
            <input value={value.party} onChange={(e) => update({ party: e.target.value })} />
          </label>
          <fieldset>
            <legend>{kind === 'awards' ? 'Award date' : 'Deadline'}</legend>
            <select
              aria-label={`${kind === 'awards' ? 'Award date' : 'Deadline'} filter`}
              value={value.dateMode}
              onChange={(e) => update({ dateMode: e.target.value, from: '', to: '' })}
            >
              <option value="">Any date</option>
              <option value="from">From</option>
              <option value="to">Until</option>
              <option value="range">Date range</option>
            </select>
            <div className="related-range">
              {['from', 'range'].includes(value.dateMode) && (
                <label>
                  From
                  <input
                    type="date"
                    value={value.from}
                    max={value.to || undefined}
                    aria-describedby={invalidDate ? `${id}-date` : undefined}
                    onChange={(e) => update({ from: e.target.value })}
                  />
                </label>
              )}
              {['to', 'range'].includes(value.dateMode) && (
                <label>
                  To
                  <input
                    type="date"
                    value={value.to}
                    min={value.from || undefined}
                    onChange={(e) => update({ to: e.target.value })}
                  />
                </label>
              )}
            </div>
            {invalidDate && (
              <p id={`${id}-date`} role="alert">
                End date must follow start date.
              </p>
            )}
          </fieldset>
          <fieldset>
            <legend>{kind === 'awards' ? 'Award value' : 'Published value'}</legend>
            <select
              aria-label="Currency"
              value={value.currency}
              onChange={(e) =>
                update({
                  currency: e.target.value,
                  ...(!e.target.value && currencies.length > 1
                    ? { valueMode: '', min: '', max: '' }
                    : {}),
                })
              }
            >
              <option value="">
                {currencies.length > 1 ? 'Choose currency for a range' : 'Any currency'}
              </option>
              {currencies.map((currency) => (
                <option key={currency}>{currency}</option>
              ))}
            </select>
            <select
              aria-label="Value filter"
              disabled={!valueReady}
              value={value.valueMode}
              onChange={(e) => update({ valueMode: e.target.value, min: '', max: '' })}
            >
              <option value="">Any value</option>
              <option value="from">At least</option>
              <option value="to">At most</option>
              <option value="range">Value range</option>
            </select>
            <div className="related-range">
              {['from', 'range'].includes(value.valueMode) && (
                <label>
                  Minimum
                  <input
                    type="number"
                    min="0"
                    value={value.min}
                    onChange={(e) => update({ min: e.target.value })}
                  />
                </label>
              )}
              {['to', 'range'].includes(value.valueMode) && (
                <label>
                  Maximum
                  <input
                    type="number"
                    min="0"
                    value={value.max}
                    onChange={(e) => update({ max: e.target.value })}
                  />
                </label>
              )}
            </div>
            {invalidValue && <p role="alert">Maximum must be at least the minimum.</p>}
          </fieldset>
          <div className="related-filter-actions">
            <button onClick={() => onChange({ ...emptyRelatedFilters, q: value.q })}>
              Clear filters
            </button>
            <button
              onClick={() => {
                if (details.current) details.current.open = false
              }}
            >
              Done
            </button>
          </div>
        </div>
      </details>
    </div>
  )
}
