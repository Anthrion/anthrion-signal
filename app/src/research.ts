import { isHistoricalAward, searchText } from './lib'
import type { HistoryRecord, Signal } from './types'

export interface RelatedAward {
  signal: Signal
  relationship: 'same_procedure' | 'same_buyer' | 'same_buyer_name' | 'shared_capability'
  reason: string
  capabilityIds: string[]
}
export function samePublishedBuyer(left: Signal, right: Signal) {
  if (left.buyer_id && right.buyer_id) return left.buyer_id === right.buyer_id
  return (
    !!left.buyer_name &&
    !!right.buyer_name &&
    left.source === right.source &&
    searchText(left.buyer_name) === searchText(right.buyer_name) &&
    left.countries.some((country) => right.countries.includes(country))
  )
}
export function relatedAwards(record: Signal, awards: Signal[], limit = 12): RelatedAward[] {
  const unique = [...new Map(awards.map((s) => [s.id, s])).values()]
  const related: RelatedAward[] = []
  for (const signal of unique) {
    if (record.id === signal.id || !isHistoricalAward(signal)) continue
    const capabilityIds = signal.matched_capabilities.filter((id) =>
      record.matched_capabilities.includes(id),
    )
    if (record.procedure_id && signal.procedure_id === record.procedure_id)
      related.push({
        signal,
        relationship: 'same_procedure',
        reason: 'Same published procurement identifier',
        capabilityIds,
      })
    else if (samePublishedBuyer(record, signal)) {
      const identified =
        !!record.buyer_id &&
        record.buyer_identity_basis === 'identifier' &&
        signal.buyer_identity_basis === 'identifier'
      related.push({
        signal,
        relationship: identified ? 'same_buyer' : 'same_buyer_name',
        reason: identified
          ? 'Same published buyer identifier'
          : 'Same published buyer name and source',
        capabilityIds,
      })
    } else if (
      capabilityIds.length &&
      record.countries.some((country) => signal.countries.includes(country))
    ) {
      related.push({
        signal,
        relationship: 'shared_capability',
        reason: 'Shared capability in this market',
        capabilityIds,
      })
    }
  }
  const priority = { same_procedure: 0, same_buyer: 1, same_buyer_name: 2, shared_capability: 3 }
  return related
    .sort(
      (a, b) =>
        priority[a.relationship] - priority[b.relationship] ||
        Date.parse(b.signal.award_date || b.signal.published_at || '') -
          Date.parse(a.signal.award_date || a.signal.published_at || '') ||
        a.signal.id.localeCompare(b.signal.id),
    )
    .slice(0, limit)
}
export function buyerTimeline(record: Signal, records: Signal[] = []): HistoryRecord[] {
  const published = record.buyer_history || []
  const fromRecords = [record, ...records]
    .filter((s) => samePublishedBuyer(record, s))
    .map((s): HistoryRecord => ({
      signal_id: s.id,
      procedure_id: s.procedure_id,
      title: s.title,
      signal_type: s.signal_type,
      published_at: s.published_at,
      award_date: s.award_date,
      supplier: s.incumbent_supplier,
      status: s.status,
      source_url: s.primary_source_url,
      lot_ids: s.lot_ids,
    }))
  return [
    ...new Map([...fromRecords, ...published].map((event) => [event.signal_id, event])).values(),
  ].sort(
    (a, b) =>
      Date.parse(b.award_date || b.published_at || '') -
        Date.parse(a.award_date || a.published_at || '') || a.signal_id.localeCompare(b.signal_id),
  )
}
