import { safeURL } from './lib'
import type { HistoryRecord, Signal } from './types'

export function sourceKey(value: string) {
  const safe = safeURL(value)
  if (safe === '#') return ''
  const url = new URL(safe)
  url.hash = ''
  url.searchParams.sort()
  return url.href
}

export function distinctSources(urls: (string | null | undefined)[], excluded: string[] = []) {
  const seen = new Set(excluded.map(sourceKey).filter(Boolean))
  return urls.filter((url): url is string => {
    const key = url ? sourceKey(url) : ''
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

type Lot = NonNullable<Signal['lots']>[number]
const lotLabel = (value: string) =>
  value
    .toLowerCase()
    .replace(/\blots?\b/g, '')
    .replace(/[^\p{L}\p{N}]/gu, '')
    .replace(/^0+(?=\d)/, '')
export function descriptiveLotText(value: string | undefined, id: string) {
  return !!value?.trim() && lotLabel(value) !== lotLabel(id)
}
export function meaningfulLots(lots: Lot[] = []) {
  return lots.filter(
    (lot) =>
      descriptiveLotText(lot.title, lot.id) ||
      descriptiveLotText(lot.description, lot.id) ||
      !!lot.deadline_at ||
      lot.value_min != null ||
      lot.value_max != null ||
      ['cancelled', 'canceled', 'withdrawn', 'awarded', 'unsuccessful'].includes(
        lot.status.toLowerCase(),
      ),
  )
}
export function lotIds(record: Pick<Signal, 'lot_ids' | 'lots'> | HistoryRecord) {
  return [
    ...new Set(
      [...(record.lot_ids || []), ...(record.lots || []).map((lot) => lot.id)].filter(Boolean),
    ),
  ]
}
export function historySources(record: HistoryRecord) {
  return distinctSources([
    record.source_url,
    record.amount?.source_url,
    ...(record.lots || []).map((lot) => lot.source_url),
    ...(record.winners || []).map((winner) => winner.source_url),
  ])
}
