import { isHistoricalAward } from './lib'
import type { Dataset, HistoryRecord, Signal } from './types'

export type PublishedSupplier = NonNullable<Signal['winners']>[number]
type SupplierScope = Pick<Signal, 'source' | 'countries'>
const globalRegistryId = (id: string) => /^(?:[A-Z]{2}-[A-Z0-9]+):/.test(id)
const exactName = (value: string) =>
  value.normalize('NFKC').trim().replace(/\s+/g, ' ').toLocaleLowerCase('en')

export function publishedSuppliers(signal: Signal): PublishedSupplier[] {
  if (!isHistoricalAward(signal)) return []
  const winners = signal.winners?.filter((winner) => winner.name?.trim()) || []
  return winners.length
    ? winners
    : signal.incumbent_supplier?.trim()
      ? [
          {
            name: signal.incumbent_supplier,
            identifiers: [],
            lot_ids: [],
            source_url: signal.primary_source_url,
          },
        ]
      : []
}

function identifiers(supplier: PublishedSupplier, signal: SupplierScope) {
  return (supplier.identifiers || [])
    .filter((id) => id.trim() && !/^(?:ORG|TPO|WOR|supplier|winner)[-_ ]?\d+$/i.test(id))
    .filter((id) => globalRegistryId(id) || (!!signal.source && signal.countries.length > 0))
    .map((id) =>
      globalRegistryId(id) ? id : JSON.stringify([signal.source, [...signal.countries].sort(), id]),
    )
}

export function supplierHistoryMarket(origin: SupplierScope, supplier: PublishedSupplier) {
  // A name-only/scoped identity can match only within its origin country. Do not
  // download other markets that cannot produce a valid match. Registry IDs may
  // connect awards across countries and therefore require the full collected feed.
  return origin.countries.length === 1 && !(supplier.identifiers || []).some(globalRegistryId)
    ? origin.countries[0]
    : ''
}

export function samePublishedSupplier(
  selected: PublishedSupplier,
  origin: SupplierScope,
  candidate: PublishedSupplier,
  record: SupplierScope,
) {
  const left = identifiers(selected, origin)
  const right = identifiers(candidate, record)
  if (left.length && right.length) return left.some((id) => right.includes(id))
  // No fuzzy matching, inferred corporate groups, or splitting combined source labels.
  return (
    !!origin.source &&
    origin.source === record.source &&
    origin.countries.some((country) => record.countries.includes(country)) &&
    exactName(selected.name) === exactName(candidate.name)
  )
}

export function supplierAwards(origin: Signal, supplier: PublishedSupplier, records: Signal[]) {
  return [...new Map([origin, ...records].map((record) => [record.id, record])).values()]
    .filter((record) =>
      publishedSuppliers(record).some((candidate) =>
        samePublishedSupplier(supplier, origin, candidate, record),
      ),
    )
    .sort(
      (a, b) =>
        (b.award_date || b.published_at || '').localeCompare(
          a.award_date || a.published_at || '',
        ) || a.id.localeCompare(b.id),
    )
}

export function awardHistoryRecord(signal: Signal, title = signal.title): HistoryRecord {
  return {
    signal_id: signal.id,
    source: signal.source,
    countries: signal.countries,
    buyer_name: signal.buyer_name,
    buyer_id: signal.buyer_id,
    procedure_id: signal.procedure_id,
    title,
    signal_type: signal.signal_type,
    notice_type: signal.notice_type,
    published_at: signal.published_at,
    award_date: signal.award_date,
    award_statuses: signal.award_statuses,
    supplier: signal.incumbent_supplier,
    status: signal.status,
    source_url: signal.primary_source_url,
    lot_ids: signal.lot_ids,
    amount: signal.amount,
    contract_start: signal.contract_start,
    contract_end: signal.contract_end,
    extension_end: signal.extension_end,
    winners: signal.winners,
    lots: signal.lots,
  }
}

export function historySuppliers(record: HistoryRecord): PublishedSupplier[] {
  const status = record.status.toLowerCase()
  const ended = ['cancelled', 'canceled', 'withdrawn', 'unsuccessful']
  if (
    ended.includes(status) ||
    /^(CANCELLED|CANCELED|AVLYST|KESKEYTETTY|PERUTTU)\b/.test(record.title.trim()) ||
    ['uk5', 'veat', 'dir-awa-pre'].includes(record.notice_type?.toLowerCase() || '') ||
    record.signal_type === 'RENEWAL_SIGNAL' ||
    (record.award_statuses?.length &&
      !record.award_statuses.some((value) => value.toLowerCase() === 'active')) ||
    (record.signal_type !== 'AWARD' && status !== 'awarded')
  )
    return []
  const winners = record.winners?.filter((winner) => winner.name?.trim()) || []
  return winners.length
    ? winners
    : record.supplier?.trim()
      ? [{ name: record.supplier, identifiers: [], lot_ids: [], source_url: record.source_url }]
      : []
}

export function historySupplierScope(record: HistoryRecord, data?: Dataset): SupplierScope {
  return {
    source: record.source || '',
    countries:
      record.countries ||
      data?.current_feed?.records[record.signal_id]?.markets.filter((id) =>
        /^[A-Z]{2}$/.test(id),
      ) ||
      [],
  }
}

export function historySupplierAwards(
  selected: HistoryRecord,
  supplier: PublishedSupplier,
  history: HistoryRecord[],
  awards: Signal[],
): HistoryRecord[] {
  const published = awards
    .filter((award) => publishedSuppliers(award).length)
    .map((award) => awardHistoryRecord(award))
  const origin = published.find((record) => record.signal_id === selected.signal_id) || selected
  // The clicked award is itself evidence even when it falls outside the opportunity
  // classifier. Do not fabricate a full Signal or borrow another notice's identity.
  return [
    ...new Map(
      [selected, ...history, ...published].map((record) => [record.signal_id, record]),
    ).values(),
  ]
    .filter((record) =>
      historySuppliers(record).some(
        (candidate) =>
          (record.signal_id === selected.signal_id &&
            exactName(supplier.name) === exactName(candidate.name)) ||
          samePublishedSupplier(
            supplier,
            historySupplierScope(origin),
            candidate,
            historySupplierScope(record),
          ),
      ),
    )
    .sort(
      (a, b) =>
        (b.award_date || b.published_at || '').localeCompare(
          a.award_date || a.published_at || '',
        ) || a.signal_id.localeCompare(b.signal_id),
    )
}
