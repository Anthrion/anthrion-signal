import { isHistoricalAward } from './lib'
import type { HistoryRecord, Signal } from './types'

export type PublishedSupplier = NonNullable<Signal['winners']>[number]
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

function identifiers(supplier: PublishedSupplier, signal: Signal) {
  return (supplier.identifiers || [])
    .filter((id) => id.trim() && !/^(?:ORG|TPO|WOR|supplier|winner)[-_ ]?\d+$/i.test(id))
    .map((id) =>
      globalRegistryId(id) ? id : JSON.stringify([signal.source, [...signal.countries].sort(), id]),
    )
}

export function supplierHistoryMarket(origin: Signal, supplier: PublishedSupplier) {
  // A name-only/scoped identity can match only within its origin country. Do not
  // download other markets that cannot produce a valid match. Registry IDs may
  // connect awards across countries and therefore require the full collected feed.
  return origin.countries.length === 1 && !(supplier.identifiers || []).some(globalRegistryId)
    ? origin.countries[0]
    : ''
}

export function samePublishedSupplier(
  selected: PublishedSupplier,
  origin: Signal,
  candidate: PublishedSupplier,
  record: Signal,
) {
  const left = identifiers(selected, origin)
  const right = identifiers(candidate, record)
  if (left.length && right.length) return left.some((id) => right.includes(id))
  // No fuzzy matching, inferred corporate groups, or splitting combined source labels.
  return (
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
    procedure_id: signal.procedure_id,
    title,
    signal_type: signal.signal_type,
    notice_type: signal.notice_type,
    published_at: signal.published_at,
    award_date: signal.award_date,
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
