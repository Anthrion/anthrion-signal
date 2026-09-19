import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ArrowLeft, ArrowUpRight, Building2, FileText, GripVertical, Search, X } from 'lucide-react'
import type { Dataset, Filters, HistoryRecord, Signal } from './types'
import { amount, date, defaults, responseDeadline, selectedResponseDeadlineEvent } from './lib'
import {
  amountLabels,
  amountPresentation,
  deadlinePresentation,
  deadlineEventCalendarURL,
} from './publicFacts'
import { relatedAwards } from './research'
import { useBuyerHistory } from './useBuyerHistory'
import { useSignalText } from './Translation'
import { BrandSignature, MetalEdge, SourceNoticeLink } from './WorkspaceUI'
import {
  awardHistoryRecord,
  historySuppliers,
  historySupplierAwards,
  publishedSuppliers,
  supplierAwards,
} from './supplierResearch'
import type { PublishedSupplier } from './supplierResearch'
import {
  descriptiveLotText,
  distinctSources,
  historySources,
  lotIds,
  meaningfulLots,
  sourceKey,
} from './researchPresentation'
export type ResearchState = {
  kind: 'buyer' | 'related' | 'supplier'
  signal: Signal
  opener: HTMLElement
  supplier?: PublishedSupplier
  supplierRecord?: HistoryRecord
  supplierRecords?: HistoryRecord[]
}
const ResearchContext = createContext<{ open: (value: ResearchState) => void }>({ open: () => {} })
export function ResearchProvider({
  open,
  children,
}: {
  open: (value: ResearchState) => void
  children: ReactNode
}) {
  return <ResearchContext.Provider value={{ open }}>{children}</ResearchContext.Provider>
}
export function ResearchTitle({ signal, children }: { signal: Signal; children: ReactNode }) {
  const { open } = useContext(ResearchContext)
  return (
    <button
      className="research-title-link"
      onClick={(event) => open({ kind: 'related', signal, opener: event.currentTarget })}
      title="Research this opportunity and related awards"
    >
      {children}
      <ArrowUpRight size={17} aria-hidden="true" />
    </button>
  )
}
export function BuyerLink({ signal }: { signal: Signal }) {
  const { open } = useContext(ResearchContext)
  const text = useSignalText(signal)
  return (
    <button
      className="buyer-history-link"
      onClick={(event) => open({ kind: 'buyer', signal, opener: event.currentTarget })}
      aria-label={`View buyer history for ${text.buyerName}`}
    >
      {text.buyerName}
      <ArrowUpRight size={13} aria-hidden="true" />
    </button>
  )
}
export function SupplierLinks({ signal }: { signal: Signal }) {
  const { open } = useContext(ResearchContext)
  const winners = publishedSuppliers(signal)
  return winners.length ? (
    <span className="supplier-links">
      {winners.map((supplier, index) => (
        <button
          key={`${supplier.name}-${index}`}
          className="supplier-history-link"
          aria-label={`View awarded contracts for ${supplier.name}`}
          onClick={(event) =>
            open({ kind: 'supplier', signal, supplier, opener: event.currentTarget })
          }
        >
          {supplier.name}
          <ArrowUpRight size={13} aria-hidden="true" />
        </button>
      ))}
    </span>
  ) : (
    <span>Supplier not published</span>
  )
}
export function SourceLink({ href, children = 'Source' }: { href: string; children?: ReactNode }) {
  return (
    <SourceNoticeLink href={href} compact>
      {children}
    </SourceNoticeLink>
  )
}

function ResearchSurface({
  className = '',
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`research-surface ${className}`}>
      <MetalEdge />
      {children}
    </section>
  )
}

function SourceLinks({
  urls,
  excluded = [],
}: {
  urls: (string | null | undefined)[]
  excluded?: string[]
}) {
  const links = distinctSources(urls, excluded)
  return links.length ? (
    <div className="research-source-links">
      {links.map((href, index) => (
        <SourceLink key={sourceKey(href)} href={href}>
          {links.length === 1 ? 'Source' : `Source ${index + 1}`}
        </SourceLink>
      ))}
    </div>
  ) : null
}

function LotSummary({ record }: { record: Pick<Signal, 'lot_ids' | 'lots'> | HistoryRecord }) {
  const ids = lotIds(record)
  return ids.length ? (
    <p className="lot-summary">
      {ids.length === 1 ? 'Lot' : 'Lots'} {ids.join(' · ')}
    </p>
  ) : null
}

function LotDetails({ lots }: { lots: NonNullable<Signal['lots']> }) {
  return (
    <div className="lot-grid">
      {meaningfulLots(lots).map((lot) => (
        <article key={lot.id}>
          <span className="section-eyebrow">
            Lot {lot.id}
            {lot.status !== 'unknown' ? ` · ${lot.status.replaceAll('_', ' ')}` : ''}
          </span>
          {descriptiveLotText(lot.title, lot.id) && <h4>{lot.title}</h4>}
          {descriptiveLotText(lot.description, lot.id) && <p>{lot.description}</p>}
          {lot.deadline_at && <small>Deadline {date(lot.deadline_at)}</small>}
          {(lot.value_min != null || lot.value_max != null) && (
            <small>{amount(lot.value_max ?? lot.value_min ?? null, lot.currency || null)}</small>
          )}
        </article>
      ))}
    </div>
  )
}

function RelatedAwardCard({
  award,
  reason,
  excludedSources = [],
}: {
  award: Signal
  reason: string
  excludedSources?: string[]
}) {
  const text = useSignalText(award)
  const financial = valueFact(award)
  return (
    <article className="related-award">
      <div className="award-reason">{reason}</div>
      <h3>{text.title}</h3>
      <p className="muted">
        <BuyerLink signal={award} />
      </p>
      <p className="award-winner">
        <SupplierLinks signal={award} />
      </p>
      <div className="award-facts">
        <span>
          {award.award_date ? `Awarded ${date(award.award_date)}` : 'Award date not published'}
        </span>
        <span className="award-amount">
          <small>{financial.label}</small>
          <strong>{financial.value}</strong>
        </span>
      </div>
      {!!award.lot_ids?.length && <small>Lots {award.lot_ids.join(', ')}</small>}
      <SourceLinks urls={[award.primary_source_url]} excluded={excludedSources} />
    </article>
  )
}

export function CapabilityTags({ signal, data }: { signal: Signal; data: Dataset }) {
  return (
    <div className="capability-tags" aria-label="Capabilities">
      {signal.matched_capabilities.map((id) => (
        <span key={id}>{data.capabilities.find((c) => c.id === id)?.label || id}</span>
      ))}
      {!signal.matched_capabilities.length && <span className="muted">Not specified</span>}
    </div>
  )
}

export function valueFact(signal: Signal, compact = true) {
  return amountPresentation(signal, compact)
}
export function deadlineFact(signal: Signal) {
  const event = selectedResponseDeadlineEvent(signal)
  if (event) return { ...deadlinePresentation(event), dateOnly: event.precision === 'date' }
  const deadline = responseDeadline(signal)
  return {
    label: 'Deadline',
    value: deadline ? date(deadline) : 'Not published',
    dateOnly: !!deadline && /^\d{4}-\d{2}-\d{2}$/.test(deadline),
  }
}

export function DeadlineEvents({ signal }: { signal: Signal }) {
  const text = useSignalText(signal)
  const events = signal.deadlines || []
  if (!events.length)
    return (
      <p className="muted">
        {deadlineFact(signal).value}
        {deadlineFact(signal).dateOnly ? ' · Cutoff time unconfirmed' : ''}
      </p>
    )
  return (
    <div className="deadline-events">
      {events.map((event, index) => {
        const fact = deadlinePresentation(event)
        const href = deadlineEventCalendarURL(
          signal,
          event,
          new URL(import.meta.env.BASE_URL, location.origin).href,
          text,
        )
        return (
          <div className="deadline-event" key={`${event.kind}-${event.date}-${index}`}>
            <div>
              <strong>{fact.label}</strong>
              <p>{fact.value}</p>
              <small>
                {event.status !== 'current'
                  ? event.status === 'conflicting'
                    ? 'Conflicting dates — check source'
                    : 'Superseded'
                  : event.precision === 'date'
                    ? 'Cutoff time unconfirmed · all-day reminder'
                    : 'Published cutoff'}
                {event.lot_id ? ` · Lot ${event.lot_id}` : ''}
              </small>
            </div>
            <div className="deadline-event-links">
              <SourceLinks
                urls={[event.source_url]}
                excluded={[
                  signal.primary_source_url,
                  ...events.slice(0, index).map((previous) => previous.source_url),
                ]}
              />
              {href && (
                <a href={href} target="_blank" rel="noopener noreferrer" className="text-action">
                  Add to calendar
                  <ArrowUpRight size={12} />
                </a>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function SourceDocuments({
  signal,
  excludedSources = [],
}: {
  signal: Signal
  excludedSources?: string[]
}) {
  if (!signal.documents.length)
    return <p className="muted">No supporting documents were linked in the collected notice.</p>
  const status: Record<string, string> = {
    linked: 'Linked document',
    cached: 'Text available',
    missing: 'Document missing',
    inaccessible: 'Currently inaccessible',
    unsupported: 'Preview unavailable',
    needs_ocr: 'Scanned document',
    too_large: 'Open to read',
    permission_required: 'Access required',
  }
  return (
    <div className="source-document-list">
      {signal.documents.map((doc, index) => (
        <article className="source-document" key={`${doc.url}-${index}`}>
          <div className="document-title">
            <FileText size={18} />
            {distinctSources(
              [doc.url],
              [
                signal.primary_source_url,
                ...excludedSources,
                ...signal.documents.slice(0, index).map((previous) => previous.url),
              ],
            ).length ? (
              <SourceLink href={doc.url}>{doc.title}</SourceLink>
            ) : (
              <strong>{doc.title}</strong>
            )}
          </div>
          <div className="document-meta">
            <span>{status[doc.status || 'linked'] || 'Linked document'}</span>
            {doc.page_count && <span>{doc.page_count} pages</span>}
            {doc.revision && <span>Revision {doc.revision}</span>}
            {doc.retrieved_at && <span>Checked {date(doc.retrieved_at)}</span>}
          </div>
          {!!doc.pages?.length && (
            <details>
              <summary>Read page evidence</summary>
              <div className="document-pages">
                {doc.pages.map((page) => (
                  <section key={page.page}>
                    <SourceLink href={`${doc.url.split('#')[0]}#page=${page.page}`}>
                      Page {page.page}
                    </SourceLink>
                    <p>{page.text}</p>
                  </section>
                ))}
              </div>
            </details>
          )}
          {!!doc.previous_revisions?.length && (
            <details>
              <summary>
                {doc.previous_revisions.length} earlier{' '}
                {doc.previous_revisions.length === 1 ? 'revision' : 'revisions'}
              </summary>
              {doc.previous_revisions.map((revision) => (
                <p key={revision.content_hash}>
                  {revision.revision || 'Earlier version'} · {date(revision.retrieved_at || null)}
                </p>
              ))}
            </details>
          )}
        </article>
      ))}
    </div>
  )
}

export function ProcurementHistory({
  signal,
  showLotSummary = true,
  excludedSources = [],
}: {
  signal: Signal
  showLotSummary?: boolean
  excludedSources?: string[]
}) {
  const lots = meaningfulLots(signal.lots)
  const history = (signal.procedure_history || []).filter(
    (record) => record.signal_id !== signal.id,
  )
  const lotSources = distinctSources(
    [
      ...(signal.lots || []).map((lot) => lot.source_url),
      ...(signal.procedure_history || [])
        .filter((record) => record.signal_id === signal.id)
        .flatMap(historySources),
    ],
    [signal.primary_source_url, ...excludedSources],
  )
  return (
    <div className="procurement-history">
      {showLotSummary && <LotSummary record={signal} />}
      {(signal.contract_start || signal.contract_end) && (
        <p>
          Contract period: {date(signal.contract_start || null)} to{' '}
          {date(signal.contract_end || null)}
        </p>
      )}
      {signal.extension_end && <p>Extension end: {date(signal.extension_end)}</p>}
      {!!lots.length && (
        <>
          <h3>Published lots</h3>
          <LotDetails lots={lots} />
        </>
      )}
      <SourceLinks urls={lotSources} />
      {!!history.length && (
        <>
          <h3>Procurement history</h3>
          <HistoryTimeline
            records={history}
            origin={signal}
            excludedSources={[signal.primary_source_url, ...excludedSources, ...lotSources]}
          />
        </>
      )}
    </div>
  )
}
function HistorySignalTitle({ signal }: { signal: Signal }) {
  return <>{useSignalText(signal).title}</>
}

function HistorySupplierLinks({
  record,
  records,
  origin,
}: {
  record: HistoryRecord
  records: HistoryRecord[]
  origin: Signal
}) {
  const { open } = useContext(ResearchContext)
  const suppliers = historySuppliers(record)
  return suppliers.length ? (
    <span className="supplier-links">
      {suppliers.map((supplier, index) => (
        <button
          key={`${supplier.name}-${index}`}
          className="supplier-history-link"
          aria-label={`View awarded contracts for ${supplier.name}`}
          onClick={(event) =>
            open({
              kind: 'supplier',
              signal: origin,
              supplier,
              supplierRecord: record,
              supplierRecords: records,
              opener: event.currentTarget,
            })
          }
        >
          {supplier.name}
          <ArrowUpRight size={13} aria-hidden="true" />
        </button>
      ))}
    </span>
  ) : (
    <strong>{record.winners?.map((winner) => winner.name).join(', ') || record.supplier}</strong>
  )
}

function HistoryTimeline({
  records,
  signals = [],
  origin,
  supplierRecords = records,
  excludedSources = [],
}: {
  records: HistoryRecord[]
  signals?: Signal[]
  origin?: Signal
  supplierRecords?: HistoryRecord[]
  excludedSources?: string[]
}) {
  const byId = new Map(signals.map((signal) => [signal.id, signal]))
  const seenSources = [...excludedSources]
  return (
    <ol className="research-timeline">
      {[...records]
        .sort((a, b) =>
          (b.award_date || b.published_at || '').localeCompare(
            a.award_date || a.published_at || '',
          ),
        )
        .map((record, index) => {
          const sources = distinctSources(historySources(record), seenSources)
          seenSources.push(...sources)
          const lots = meaningfulLots(record.lots)
          return (
            <li key={`${record.signal_id}-${index}`}>
              <div className="timeline-marker" />
              <div>
                <div className="history-date">
                  {record.award_date
                    ? `Awarded ${date(record.award_date)}`
                    : record.published_at
                      ? `Published ${date(record.published_at)}`
                      : 'Date not published'}
                  <span>{record.status.replaceAll('_', ' ')}</span>
                </div>
                <h3>
                  {byId.has(record.signal_id) ? (
                    <HistorySignalTitle signal={byId.get(record.signal_id)!} />
                  ) : (
                    record.title
                  )}
                </h3>
                <LotSummary record={record} />
                {byId.has(record.signal_id) && (
                  <p>
                    <BuyerLink signal={byId.get(record.signal_id)!} />
                  </p>
                )}
                {!!(record.supplier || record.winners?.length) && (
                  <p className="award-winner">
                    {byId.has(record.signal_id) ? (
                      <SupplierLinks signal={byId.get(record.signal_id)!} />
                    ) : origin ? (
                      <HistorySupplierLinks
                        record={record}
                        records={supplierRecords}
                        origin={origin}
                      />
                    ) : (
                      <strong>
                        {record.winners?.map((winner) => winner.name).join(', ') || record.supplier}
                      </strong>
                    )}
                  </p>
                )}
                {record.amount && (
                  <p className="history-amount">
                    {amountLabels[record.amount.kind]}{' '}
                    <strong>
                      {record.amount.minimum != null &&
                      record.amount.maximum != null &&
                      record.amount.minimum !== record.amount.maximum
                        ? `${amount(record.amount.minimum, record.amount.currency || null)}–${amount(record.amount.maximum, record.amount.currency || null)}`
                        : amount(
                            record.amount.maximum ?? record.amount.minimum ?? null,
                            record.amount.currency || null,
                          )}
                    </strong>
                  </p>
                )}
                {!!(
                  record.contract_start ||
                  record.contract_end ||
                  record.extension_end ||
                  lots.length
                ) && (
                  <details className="history-contract">
                    <summary>Contract & lot details</summary>
                    {(record.contract_start || record.contract_end) && (
                      <p>
                        Contract period: {date(record.contract_start || null)} to{' '}
                        {date(record.contract_end || null)}
                      </p>
                    )}
                    {record.extension_end && <p>Extension end: {date(record.extension_end)}</p>}
                    {!!lots.length && <LotDetails lots={lots} />}
                  </details>
                )}
                <SourceLinks urls={sources} />
              </div>
            </li>
          )
        })}
    </ol>
  )
}

export function SearchWorkspace({
  filters,
  update,
  data,
  count,
}: {
  filters: Filters
  update: (patch: Partial<Filters>) => void
  data: Dataset | null
  count: number
}) {
  const chips = Object.entries(filters).filter(
    ([key, value]) =>
      !['view', 'sort', 'market', 'score', 'confidence', 'recommendation'].includes(key) &&
      value !== defaults[key as keyof Filters] &&
      value !== '',
  )
  const names: Record<string, string> = {
    q: 'Search',
    source: 'Source',
    type: 'Notice',
    capability: 'Capability',
    sector: 'Sector',
    buyer: 'Buyer',
    supplier: 'Supplier',
    awardFrom: 'Awarded from',
    awardTo: 'Awarded before',
    region: 'Region',
    cpv: 'CPV',
    minValue: 'Minimum',
    maxValue: 'Maximum',
    currency: 'Currency',
    deadline: 'Deadline',
    change: 'Change',
    searchMode: 'Search in',
    match: 'Match',
    amountType: 'Amount type',
  }
  return (
    <div className="search-workspace">
      <div className="search-intent">
        <label>
          <span>Search in</span>
          <select
            aria-label="Search mode"
            value={filters.searchMode}
            onChange={(e) => update({ searchMode: e.target.value })}
          >
            <option value="capability">Text + capabilities</option>
            <option value="exact">Exact source text</option>
          </select>
        </label>
        <label>
          <span>Match</span>
          <select
            aria-label="Word matching"
            value={filters.match}
            onChange={(e) => update({ match: e.target.value })}
          >
            <option value="all">All words</option>
            <option value="any">Any word</option>
            <option value="phrase">Exact phrase</option>
          </select>
        </label>
        <span className="search-result-count">
          {count.toLocaleString()}{' '}
          {filters.view === 'awards'
            ? count === 1
              ? 'award'
              : 'awards'
            : count === 1
              ? 'signal'
              : 'signals'}
        </span>
      </div>
      {!!chips.length && (
        <div className="active-filter-chips" aria-label="Active filters">
          {chips.map(([key, value]) => (
            <button
              key={key}
              onClick={() => update({ [key]: defaults[key as keyof Filters] })}
              aria-label={`Remove ${names[key] || key} filter`}
            >
              <span>
                {names[key] || key}:{' '}
                {key === 'capability'
                  ? data?.capabilities.find((c) => c.id === value)?.label || value
                  : value.replaceAll('_', ' ')}
              </span>
              <X size={12} />
            </button>
          ))}
          <button
            className="clear-all"
            onClick={() =>
              update({
                ...defaults,
                market: filters.market,
                view: filters.view,
                sort: filters.sort,
              })
            }
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  )
}

export function PaneDivider({
  value,
  onChange,
}: {
  value: number
  onChange: (value: number) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [bounds, setBounds] = useState({ min: 30, max: 70 })
  const limits = (element: HTMLElement) => {
    const width = element.parentElement?.getBoundingClientRect().width || 1000
    return {
      min: Math.max(30, (345 / width) * 100),
      max: Math.min(70, ((width - 385) / width) * 100),
      width,
    }
  }
  const change = (element: HTMLElement, next: number) => {
    const { min, max } = limits(element)
    onChange(Math.max(Math.ceil(min), Math.min(Math.floor(max), Math.round(next))))
  }
  useEffect(() => {
    const element = ref.current
    if (!element?.parentElement) return
    const observer = new ResizeObserver(() => {
      if (!element.getClientRects().length) return
      const { min, max } = limits(element)
      setBounds((previous) =>
        previous.min === Math.ceil(min) && previous.max === Math.floor(max)
          ? previous
          : { min: Math.ceil(min), max: Math.floor(max) },
      )
      const clamped = Math.max(Math.ceil(min), Math.min(Math.floor(max), value))
      if (clamped !== value) onChange(clamped)
    })
    observer.observe(element.parentElement)
    return () => observer.disconnect()
  }, [value, onChange])
  return (
    <div
      ref={ref}
      className="pane-divider"
      role="separator"
      aria-label="Resize record pane"
      aria-orientation="vertical"
      aria-valuemin={bounds.min}
      aria-valuemax={bounds.max}
      aria-valuenow={value}
      aria-valuetext={`${value}% results width`}
      tabIndex={0}
      onPointerDown={(e) => {
        e.preventDefault()
        e.currentTarget.setPointerCapture(e.pointerId)
      }}
      onPointerMove={(e) => {
        if (!e.currentTarget.hasPointerCapture(e.pointerId)) return
        const rect = e.currentTarget.parentElement!.getBoundingClientRect()
        change(e.currentTarget, ((e.clientX - rect.left) / rect.width) * 100)
      }}
      onPointerUp={(e) => {
        if (e.currentTarget.hasPointerCapture(e.pointerId))
          e.currentTarget.releasePointerCapture(e.pointerId)
      }}
      onKeyDown={(e) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
        e.preventDefault()
        const { min, max } = limits(e.currentTarget)
        change(
          e.currentTarget,
          e.key === 'Home' ? min : e.key === 'End' ? max : value + (e.key === 'ArrowLeft' ? -2 : 2),
        )
      }}
    >
      <GripVertical size={14} />
    </div>
  )
}

export function ResearchPage({
  state,
  data,
  awards,
  loading,
  error,
  onBack,
  onRetry,
  onHome,
  nested = false,
}: {
  state: ResearchState
  data: Dataset
  awards: Signal[]
  loading: boolean
  error: string
  onBack: () => void
  onRetry: () => void
  onHome: () => void
  nested?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const signal = state.signal
  const text = useSignalText(signal)
  const [supplier, setSupplier] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [visibleAwards, setVisibleAwards] = useState(12)
  const [visibleHistory, setVisibleHistory] = useState(50)
  const buyer = useBuyerHistory(signal, state.kind === 'buyer')
  useEffect(() => {
    const el = ref.current
    const previous = state.opener
    el?.showModal()
    el?.querySelector<HTMLElement>('.research-back')?.focus()
    return () => {
      el?.close()
      if (previous.isConnected) previous.focus({ preventScroll: true })
      if (document.activeElement !== previous) {
        const restore =
          document.querySelector<HTMLElement>(
            `[data-signal-id="${CSS.escape(signal.id)}"] .row-select`,
          ) || document.querySelector<HTMLElement>('.signal-feed')
        restore?.focus({ preventScroll: true })
      }
    }
  }, [])
  const related = (
    state.kind === 'related' ? relatedAwards(signal, awards, Number.MAX_SAFE_INTEGER) : []
  )
    .map((match) => ({
      award: match.signal,
      reason:
        match.relationship === 'shared_capability'
          ? match.capabilityIds
              .map((id) => data.capabilities.find((c) => c.id === id)?.label || id)
              .join(' · ')
          : match.reason,
    }))
    .filter(
      ({ award }) =>
        (!supplier ||
          [award.incumbent_supplier, ...(award.winners || []).map((w) => w.name)]
            .join(' ')
            .toLowerCase()
            .includes(supplier.toLowerCase())) &&
        (!from || (!!award.award_date && award.award_date.slice(0, 10) >= from)) &&
        (!to || (!!award.award_date && award.award_date.slice(0, 10) <= to)),
    )
  const history = buyer.records
  const supplierSignals =
    state.kind === 'supplier' && state.supplier
      ? supplierAwards(signal, state.supplier, awards)
      : []
  const won =
    state.supplierRecord && state.supplier
      ? historySupplierAwards(
          state.supplierRecord,
          state.supplier,
          state.supplierRecords || [],
          awards,
        )
      : supplierSignals.map((award) => awardHistoryRecord(award))
  const visibleBuyerHistory = history.slice(0, visibleHistory)
  const buyerSources = visibleBuyerHistory.flatMap(historySources)
  const selectedSources = distinctSources([
    signal.primary_source_url,
    ...(signal.lots || []).map((lot) => lot.source_url),
    ...(signal.procedure_history || []).flatMap(historySources),
  ])
  return (
    <dialog
      ref={ref}
      className="research-page"
      aria-label={
        state.kind === 'buyer'
          ? 'Buyer history'
          : state.kind === 'supplier'
            ? 'Supplier history'
            : 'Opportunity research'
      }
      onCancel={(e) => {
        e.preventDefault()
        onBack()
      }}
    >
      <header className="research-page-header">
        <button className="research-back" onClick={onBack}>
          <ArrowLeft size={18} />
          {nested ? 'Back' : 'Back to results'}
        </button>
        <BrandSignature onHome={onHome} />
      </header>
      <div className="research-page-body">
        {state.kind === 'supplier' ? (
          <>
            <div className="research-hero">
              <h1>{state.supplier?.name}</h1>
            </div>
            <ResearchSurface className="supplier-timeline">
              <div className="surface-heading">
                <h2>Awarded contracts</h2>
                <span>
                  {loading ? 'Loading…' : `${won.length} ${won.length === 1 ? 'award' : 'awards'}`}
                </span>
              </div>
              {loading ? (
                <div className="research-empty" role="status">
                  Loading awarded contracts…
                </div>
              ) : error ? (
                <div className="research-empty" role="alert">
                  <p>{error}</p>
                  <button className="button secondary" onClick={onRetry}>
                    Try again
                  </button>
                </div>
              ) : (
                <>
                  <HistoryTimeline
                    records={won.slice(0, visibleHistory)}
                    signals={state.supplierRecord ? awards : supplierSignals}
                    origin={signal}
                    supplierRecords={won}
                  />
                  {visibleHistory < won.length && (
                    <button
                      className="button secondary research-load-more"
                      onClick={() => setVisibleHistory((n) => n + 50)}
                    >
                      Show more awards · {visibleHistory} of {won.length}
                    </button>
                  )}
                </>
              )}
            </ResearchSurface>
          </>
        ) : state.kind === 'buyer' ? (
          <>
            <div className="research-hero">
              <h1>{text.buyerName}</h1>
              {signal.agency_name && (
                <p className="muted">
                  {signal.agency_name}
                  {signal.department_name ? ` · ${signal.department_name}` : ''}
                </p>
              )}
            </div>
            <div className="buyer-research-grid">
              <ResearchSurface>
                <div className="surface-heading">
                  <h2>Contracts & notices</h2>
                  <span>{buyer.count} collected</span>
                </div>
                {buyer.loading ? (
                  <div className="research-empty" role="status">
                    Loading buyer history…
                  </div>
                ) : buyer.error ? (
                  <div className="research-empty" role="alert">
                    <p>{buyer.error}</p>
                    <button className="button secondary" onClick={buyer.retry}>
                      Try again
                    </button>
                  </div>
                ) : history.length ? (
                  <>
                    <HistoryTimeline
                      records={visibleBuyerHistory}
                      supplierRecords={history}
                      origin={signal}
                      excludedSources={[signal.primary_source_url]}
                    />
                    {visibleHistory < history.length && (
                      <button
                        className="button secondary research-load-more"
                        onClick={() => setVisibleHistory((n) => n + 50)}
                      >
                        Show more history · {Math.min(visibleHistory, history.length)} of{' '}
                        {history.length}
                      </button>
                    )}
                  </>
                ) : (
                  <div className="research-empty">
                    <Building2 size={30} />
                    <h3>No earlier history linked</h3>
                    <p>Check the buyer’s procurement source for other contracts.</p>
                  </div>
                )}
              </ResearchSurface>
              <aside className="buyer-context">
                <ResearchSurface>
                  <h2>{text.title}</h2>
                  <LotSummary record={signal} />
                  <p>{deadlineFact(signal).value}</p>
                  <ProcurementHistory
                    signal={signal}
                    showLotSummary={false}
                    excludedSources={buyerSources}
                  />
                  <SourceLink href={signal.primary_source_url} />
                </ResearchSurface>
                {!!signal.contacts?.length && (
                  <ResearchSurface>
                    <h2>Published contacts</h2>
                    {signal.contacts.map((contact, i) => (
                      <div className="published-contact" key={i}>
                        <strong>{contact.name || 'Contact'}</strong>
                        {contact.role && <p>{contact.role}</p>}
                        {contact.email && <p>{contact.email}</p>}
                      </div>
                    ))}
                    <SourceLinks
                      urls={signal.contacts.map((contact) => contact.source_url)}
                      excluded={[...selectedSources, ...buyerSources]}
                    />
                  </ResearchSurface>
                )}
              </aside>
            </div>
          </>
        ) : (
          <>
            <div className="research-hero">
              <h1>Context</h1>
            </div>
            <div className="research-split">
              <ResearchSurface className="research-current">
                <div className="research-current-content">
                  <h2>{text.title}</h2>
                  <p className="muted">
                    <BuyerLink signal={signal} />
                  </p>
                  <dl className="research-key-facts">
                    <div>
                      <dt>{valueFact(signal).label}</dt>
                      <dd>{valueFact(signal).value}</dd>
                    </div>
                    <div>
                      <dt>{deadlineFact(signal).label}</dt>
                      <dd>{deadlineFact(signal).value}</dd>
                    </div>
                  </dl>
                  <CapabilityTags signal={signal} data={data} />
                  <div className="research-description">
                    {text.description
                      .split(/\n\s*\n/)
                      .filter(Boolean)
                      .map((paragraph, index) => (
                        <p key={index}>{paragraph}</p>
                      ))}
                  </div>
                  <SourceLink href={signal.primary_source_url} />
                </div>
              </ResearchSurface>
              <ResearchSurface className="research-awards">
                <div className="surface-heading">
                  <h2>Related awards</h2>
                  <span>{related.length} matches</span>
                </div>
                <div className="research-award-filters">
                  <label>
                    Supplier
                    <input
                      value={supplier}
                      onChange={(e) => setSupplier(e.target.value)}
                      placeholder="Search awarded suppliers"
                    />
                  </label>
                  <label>
                    Awarded from
                    <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
                  </label>
                  <label>
                    To
                    <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
                  </label>
                </div>
                {loading ? (
                  <div className="research-empty" role="status">
                    Loading awarded contracts…
                  </div>
                ) : error ? (
                  <div className="research-empty" role="alert">
                    <p>{error}</p>
                    <button className="button secondary" onClick={onRetry}>
                      Try again
                    </button>
                  </div>
                ) : related.length ? (
                  <>
                    {related.slice(0, visibleAwards).map(({ award, reason }, index) => (
                      <RelatedAwardCard
                        key={award.id}
                        award={award}
                        reason={reason}
                        excludedSources={[
                          signal.primary_source_url,
                          ...related
                            .slice(0, index)
                            .map(({ award: previous }) => previous.primary_source_url),
                        ]}
                      />
                    ))}
                    {visibleAwards < related.length && (
                      <button
                        className="button secondary research-load-more"
                        onClick={() => setVisibleAwards((n) => n + 12)}
                      >
                        Show more awards · {Math.min(visibleAwards, related.length)} of{' '}
                        {related.length}
                      </button>
                    )}
                  </>
                ) : (
                  <div className="research-empty">
                    <Search size={28} />
                    <h3>No matching awards found</h3>
                    <p>
                      Try a broader supplier or date range. History is limited to collected award
                      notices.
                    </p>
                    {(supplier || from || to) && (
                      <button
                        className="button secondary"
                        onClick={() => {
                          setSupplier('')
                          setFrom('')
                          setTo('')
                        }}
                      >
                        Clear award filters
                      </button>
                    )}
                  </div>
                )}
              </ResearchSurface>
            </div>
          </>
        )}
      </div>
    </dialog>
  )
}
