import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowLeft,
  ArrowUpRight,
  Building2,
  ChevronDown,
  FileText,
  GripVertical,
  Search,
  X,
} from 'lucide-react'
import type { CapabilityEvidence, Dataset, Filters, HistoryRecord, Signal } from './types'
import {
  amount,
  date,
  defaults,
  responseDeadline,
  safeURL,
  selectedResponseDeadlineEvent,
} from './lib'
import {
  amountLabels,
  amountPresentation,
  deadlinePresentation,
  deadlineEventCalendarURL,
} from './publicFacts'
import { relatedAwards } from './research'
import { useBuyerHistory } from './useBuyerHistory'
import { useSignalText } from './Translation'
import type { usePersonalWorkspace } from './personalWorkspace'

type Personal = ReturnType<typeof usePersonalWorkspace>
type ResearchState = { kind: 'buyer' | 'related'; signal: Signal }
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
      onClick={() => open({ kind: 'related', signal })}
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
      onClick={() => open({ kind: 'buyer', signal })}
      aria-label={`View buyer history for ${text.buyerName}`}
    >
      {text.buyerName}
      <ArrowUpRight size={13} aria-hidden="true" />
    </button>
  )
}
export function SourceLink({
  href,
  children = 'View source',
}: {
  href: string
  children?: ReactNode
}) {
  return (
    <a className="evidence-source" href={safeURL(href)} target="_blank" rel="noopener noreferrer">
      {children}
      <ArrowUpRight size={13} aria-hidden="true" />
    </a>
  )
}

function EvidencePassage({ evidence }: { evidence: CapabilityEvidence }) {
  return (
    <>
      <div className="evidence-language">
        {evidence.basis === 'english_translation'
          ? 'English translation'
          : `Original passage${evidence.language && evidence.language !== 'und' ? ` · ${evidence.language}` : ''}`}
      </div>
      <blockquote>{evidence.quote}</blockquote>
      {evidence.original_quote && evidence.original_quote !== evidence.quote && (
        <details>
          <summary>Original passage</summary>
          <blockquote>{evidence.original_quote}</blockquote>
        </details>
      )}
      {evidence.translated_quote && evidence.translated_quote !== evidence.quote && (
        <details>
          <summary>English translation</summary>
          <blockquote>{evidence.translated_quote}</blockquote>
        </details>
      )}
    </>
  )
}

function RelatedAwardCard({ award, reason }: { award: Signal; reason: string }) {
  const text = useSignalText(award)
  const financial = valueFact(award)
  return (
    <article className="related-award">
      <div className="award-reason">{reason}</div>
      <h3>
        <SourceLink href={award.primary_source_url}>{text.title}</SourceLink>
      </h3>
      <p className="muted">{text.buyerName}</p>
      <p className="award-winner">
        {award.winners?.map((winner) => winner.name).join(', ') ||
          award.incumbent_supplier ||
          'Supplier not published'}
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
    </article>
  )
}

export function CapabilityEvidenceList({ signal, data }: { signal: Signal; data: Dataset }) {
  const [active, setActive] = useState('')
  useEffect(() => setActive(''), [signal.id])
  const rows = (signal.capability_evidence || []).filter((e) => e.capability === active)
  return (
    <div className="capability-evidence-block">
      <div className="capability-buttons" aria-label="Capability evidence">
        {signal.matched_capabilities.map((id) => (
          <button
            key={id}
            aria-expanded={active === id}
            onClick={() => setActive(active === id ? '' : id)}
          >
            {data.capabilities.find((c) => c.id === id)?.label || id}
            <ChevronDown size={12} aria-hidden="true" />
          </button>
        ))}
        {!signal.matched_capabilities.length && <span className="muted">Not specified</span>}
      </div>
      {active && (
        <section
          className="evidence-sheet"
          aria-label={`${data.capabilities.find((c) => c.id === active)?.label || active} evidence`}
        >
          <div className="evidence-sheet-heading">
            <strong>Source evidence</strong>
            <button aria-label="Close capability evidence" onClick={() => setActive('')}>
              <X size={16} />
            </button>
          </div>
          {rows.length ? (
            rows.map((e, i) => (
              <article className="evidence-entry" key={`${e.source_hash}-${i}`}>
                <span className={`evidence-context context-${e.context}`}>
                  {{
                    delivery: 'Delivery requirement',
                    existing_system: 'Existing system',
                    uncertain: 'Context to review',
                  }[e.context] || 'Source passage'}
                </span>
                <EvidencePassage evidence={e} />
                <SourceLink href={e.source_url || signal.primary_source_url} />
              </article>
            ))
          ) : (
            <p className="muted">
              A supporting passage is not available in this record.{' '}
              <SourceLink href={signal.primary_source_url}>Read the source notice</SourceLink>
            </p>
          )}
        </section>
      )}
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

export function DecisionBrief({ signal, compact = false }: { signal: Signal; compact?: boolean }) {
  const scope =
    signal.delivery_role?.evidence?.find((e) => e.context === 'delivery') ||
    signal.capability_evidence?.find((e) => e.context === 'delivery')
  const role = signal.delivery_role?.kind || 'unknown'
  const requirements = signal.participation_requirements || []
  return (
    <section
      className={`decision-brief ${compact ? 'brief-compact' : ''}`}
      aria-label="Decision brief"
    >
      <div className="section-eyebrow">At a glance</div>
      <h3>
        {
          {
            direct_supplier: 'Supplier procurement',
            advertised_component: 'Advertised component',
            funded_project: 'Funding for a complete project',
            unknown: 'Participation route unconfirmed',
          }[role]
        }
      </h3>
      {scope ? (
        <>
          <EvidencePassage evidence={scope} />
          <SourceLink href={scope.source_url || signal.primary_source_url}>
            Published delivery scope
          </SourceLink>
        </>
      ) : (
        <p className="muted">
          Review the published scope to confirm the work and participation route.
        </p>
      )}
      <details className="participation-checks" open={!compact && requirements.length > 0}>
        <summary>
          <span>Participation checks</span>
          <span className="check-count">{requirements.length || '—'} to review</span>
        </summary>
        <p className="qualification-note">Technical relevance does not confirm eligibility.</p>
        {requirements.length ? (
          requirements.map((r) => (
            <div className="participation-row" key={r.id}>
              <strong>{r.requirement}</strong>
              <span className="needs-checking">Needs checking</span>
              {r.source_quote &&
                r.source_quote.trim() !== r.requirement.trim() &&
                (r.translated_quote ? (
                  <details className="requirement-translation">
                    <summary>Original source text</summary>
                    <blockquote>{r.source_quote}</blockquote>
                  </details>
                ) : (
                  <blockquote>{r.source_quote}</blockquote>
                ))}
              {r.translated_quote && r.translated_quote.trim() !== r.requirement.trim() && (
                <details className="requirement-translation">
                  <summary>English translation</summary>
                  <blockquote>{r.translated_quote}</blockquote>
                </details>
              )}
              <SourceLink href={r.source_url} />
            </div>
          ))
        ) : (
          <p className="muted">
            No specific prerequisites are available in this record. Check the notice for
            eligibility, framework membership and required evidence.
          </p>
        )}
      </details>
    </section>
  )
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
              <SourceLink href={event.source_url} />
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

export function SourceDocuments({ signal }: { signal: Signal }) {
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
      {signal.documents.map((doc) => (
        <article className="source-document" key={doc.url}>
          <div className="document-title">
            <FileText size={18} />
            <SourceLink href={doc.url}>{doc.title}</SourceLink>
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

export function ProcurementHistory({ signal }: { signal: Signal }) {
  return (
    <div className="procurement-history">
      {!!signal.lots?.length && (
        <>
          <h3>Published lots</h3>
          <div className="lot-grid">
            {signal.lots.map((lot) => (
              <article key={lot.id}>
                <span className="section-eyebrow">
                  Lot {lot.id} · {lot.status.replaceAll('_', ' ')}
                </span>
                <h4>{lot.title || `Lot ${lot.id}`}</h4>
                {lot.description && <p>{lot.description}</p>}
                <SourceLink href={lot.source_url} />
                {lot.deadline_at && <small>Deadline {date(lot.deadline_at)}</small>}
              </article>
            ))}
          </div>
        </>
      )}
      {!!signal.procedure_history?.length && (
        <>
          <h3>Procurement history</h3>
          <HistoryTimeline records={signal.procedure_history} />
        </>
      )}
    </div>
  )
}
function HistoryTimeline({ records }: { records: HistoryRecord[] }) {
  return (
    <ol className="research-timeline">
      {[...records]
        .sort((a, b) =>
          (b.award_date || b.published_at || '').localeCompare(
            a.award_date || a.published_at || '',
          ),
        )
        .map((record, index) => (
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
                <SourceLink href={record.source_url}>{record.title}</SourceLink>
              </h3>
              {!!(record.supplier || record.winners?.length) && (
                <p className="award-winner">
                  Awarded supplier:{' '}
                  <strong>
                    {record.winners?.map((winner) => winner.name).join(', ') || record.supplier}
                  </strong>
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
              {!!record.lot_ids?.length && (
                <p className="muted">Lots {record.lot_ids.join(', ')}</p>
              )}
              {!!(
                record.contract_start ||
                record.contract_end ||
                record.extension_end ||
                record.lots?.length
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
                  {record.lots?.map((lot) => (
                    <div className="history-lot" key={lot.id}>
                      <strong>
                        Lot {lot.id}: {lot.title}
                      </strong>
                      <span>{lot.status.replaceAll('_', ' ')}</span>
                      {lot.description && <p>{lot.description}</p>}
                      <SourceLink href={lot.source_url} />
                    </div>
                  ))}
                </details>
              )}
            </div>
          </li>
        ))}
    </ol>
  )
}

export function SearchWorkspace({
  filters,
  update,
  showHidden,
  onRestore,
  personal,
  data,
  count,
}: {
  filters: Filters
  update: (patch: Partial<Filters>) => void
  showHidden: boolean
  onRestore: (filters: Filters, showHidden: boolean) => void
  personal: Personal
  data: Dataset | null
  count: number
}) {
  const [saveOpen, setSaveOpen] = useState(false)
  const [name, setName] = useState('')
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
      <details
        className="saved-view-menu"
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.open = false
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.currentTarget.open = false
            e.currentTarget.querySelector('summary')?.focus()
          }
        }}
      >
        <summary>
          Saved views
          <ChevronDown size={13} />
        </summary>
        <div className="saved-view-popover">
          <strong>Your working views</strong>
          {personal.savedViews.length ? (
            personal.savedViews.map((view) => (
              <div className="saved-view-row" key={view.id}>
                <button
                  onClick={(e) => {
                    onRestore(view.filters, view.showHidden ?? false)
                    e.currentTarget.closest('details')?.removeAttribute('open')
                  }}
                >
                  {view.name}
                </button>
                <button
                  aria-label={`Delete saved view ${view.name}`}
                  onClick={() => personal.removeView(view.id)}
                >
                  <X size={14} />
                </button>
              </div>
            ))
          ) : (
            <p className="muted">Save a search and its filters for next time.</p>
          )}
          <button
            className="text-action"
            onClick={(e) => {
              e.currentTarget.closest('details')?.removeAttribute('open')
              setSaveOpen(true)
            }}
          >
            Save this view
          </button>
        </div>
      </details>
      {saveOpen && (
        <form
          className="save-view-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (personal.saveView(name, filters, showHidden)) {
              setSaveOpen(false)
              setName('')
            }
          }}
        >
          <label>
            Name this view
            <input
              aria-label="Saved view name"
              autoFocus
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
              placeholder="UK CRM closing soon"
              required
            />
          </label>
          <button className="button primary" type="submit">
            Save
          </button>
          <button type="button" aria-label="Cancel saving view" onClick={() => setSaveOpen(false)}>
            <X size={17} />
          </button>
        </form>
      )}
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
}: {
  state: ResearchState
  data: Dataset
  awards: Signal[]
  loading: boolean
  error: string
  onBack: () => void
  onRetry: () => void
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
    const previous = document.activeElement as HTMLElement | null
    el?.showModal()
    el?.querySelector<HTMLElement>('.research-back')?.focus()
    return () => {
      el?.close()
      const restore = previous?.isConnected
        ? previous
        : document.querySelector<HTMLElement>(
            `[data-signal-id="${CSS.escape(signal.id)}"] .row-select`,
          ) || document.querySelector<HTMLElement>('.signal-feed')
      restore?.focus({ preventScroll: true })
    }
  }, [])
  const related = relatedAwards(signal, awards, Number.MAX_SAFE_INTEGER)
    .map((match) => ({
      award: match.signal,
      reason:
        match.relationship === 'shared_capability'
          ? `${match.reason}: ${match.capabilityIds.map((id) => data.capabilities.find((c) => c.id === id)?.label || id).join(', ')}`
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
  return (
    <dialog
      ref={ref}
      className="research-page"
      aria-label={state.kind === 'buyer' ? 'Buyer history' : 'Opportunity research'}
      onCancel={(e) => {
        e.preventDefault()
        onBack()
      }}
    >
      <header className="research-page-header">
        <button className="research-back" onClick={onBack}>
          <ArrowLeft size={18} />
          Back to results
        </button>
        <span className="research-brand">
          Anthrion <em>signal</em>
        </span>
        <SourceLink href={signal.primary_source_url}>Open source notice</SourceLink>
      </header>
      <div className="research-page-body">
        {state.kind === 'buyer' ? (
          <>
            <div className="research-hero">
              <span className="section-eyebrow">Buyer intelligence</span>
              <h1>{text.buyerName}</h1>
              <p>Known procurement history from collected source notices.</p>
              {signal.agency_name && (
                <p className="muted">
                  {signal.agency_name}
                  {signal.department_name ? ` · ${signal.department_name}` : ''}
                </p>
              )}
            </div>
            <div className="buyer-research-grid">
              <section className="research-surface">
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
                    <HistoryTimeline records={history.slice(0, visibleHistory)} />
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
                    <SourceLink href={signal.primary_source_url} />
                  </div>
                )}
              </section>
              <aside className="buyer-context">
                <section className="research-surface">
                  <div className="section-eyebrow">Selected procurement</div>
                  <h2>{text.title}</h2>
                  <p>{deadlineFact(signal).value}</p>
                  <SourceLink href={signal.primary_source_url} />
                  <ProcurementHistory signal={signal} />
                </section>
                {!!signal.contacts?.length && (
                  <section className="research-surface">
                    <h2>Published contacts</h2>
                    {signal.contacts.map((contact, i) => (
                      <div className="published-contact" key={i}>
                        <strong>{contact.name || 'Contact'}</strong>
                        {contact.role && <p>{contact.role}</p>}
                        {contact.email && <p>{contact.email}</p>}
                        <SourceLink href={contact.source_url} />
                      </div>
                    ))}
                  </section>
                )}
              </aside>
            </div>
          </>
        ) : (
          <>
            <div className="research-hero">
              <span className="section-eyebrow">Opportunity research</span>
              <h1>See the opportunity in context.</h1>
              <p>Compare the current requirement with published awards and their suppliers.</p>
            </div>
            <div className="research-split">
              <section className="research-surface research-current">
                <div className="section-eyebrow">Selected opportunity</div>
                <h2>{text.title}</h2>
                <p className="muted">{text.buyerName}</p>
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
                <DecisionBrief signal={signal} />
                <CapabilityEvidenceList signal={signal} data={data} />
                <details className="original-notice">
                  <summary>Read original notice text</summary>
                  <p>{signal.description}</p>
                </details>
                <SourceLink href={signal.primary_source_url} />
              </section>
              <section className="research-surface research-awards">
                <div className="surface-heading">
                  <h2>Related awards</h2>
                  <span>{related.length} matches</span>
                </div>
                <p className="research-relation-note">
                  Each match states its connection. A shared buyer or capability does not mean the
                  same contract.
                </p>
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
                    {related.slice(0, visibleAwards).map(({ award, reason }) => (
                      <RelatedAwardCard key={award.id} award={award} reason={reason} />
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
              </section>
            </div>
          </>
        )}
      </div>
    </dialog>
  )
}
