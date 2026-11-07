import { useEffect, useRef, useState } from 'react'
import { BoundedCache, fetchJSON, safeDataPath } from './dataClient'
import type { HistoryRecord, Signal } from './types'

interface BuyerPage {
  schema_version: string
  buyer_id: string
  buyer_name: string
  identity_basis: string
  records: HistoryRecord[]
}
export function validBuyerPage(value: unknown, buyerId: string): value is BuyerPage {
  const page = value as BuyerPage | null
  return (
    !!page &&
    page.schema_version === '1.0' &&
    page.buyer_id === buyerId &&
    Array.isArray(page.records) &&
    page.records.every(
      (record) =>
        !!record &&
        ['signal_id', 'title', 'status', 'source_url'].every(
          (key) => typeof record[key as keyof HistoryRecord] === 'string',
        ) &&
        Array.isArray(record.lot_ids),
    )
  )
}
export function buyerPage(value: unknown, buyerId: string): BuyerPage | null {
  const bucket = value as { schema_version?: string; buyers?: Record<string, unknown> } | null
  const page = bucket?.schema_version === '1.0' && bucket.buyers ? bucket.buyers[buyerId] : value
  return validBuyerPage(page, buyerId) ? page : null
}
export function useBuyerHistory(signal: Signal | null | undefined, active = true) {
  const cache = useRef(new BoundedCache<unknown>(10, 16 * 1024 * 1024))
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ key: string; records: HistoryRecord[]; error: string }>({
    key: '',
    records: [],
    error: '',
  })
  const path = active ? signal?.buyer_history_ref?.url || '' : ''
  const buyerId = signal?.buyer_id || ''
  const key = `${buyerId}|${path}`
  const expectedCount = signal?.buyer_history_ref?.count
  useEffect(() => {
    if (!active || !path || !buyerId) return
    const controller = new AbortController()
    const load = async () => {
      try {
        safeDataPath(path, 'buyers')
        const cached = cache.current.get(path)
        const value = cached ?? (await fetchJSON(path, controller.signal))
        const page = buyerPage(value, buyerId)
        if (!page) throw new Error('Invalid buyer history')
        if (!cached && !controller.signal.aborted) cache.current.set(path, value)
        if (expectedCount !== undefined && page.records.length !== expectedCount)
          throw new Error('Incomplete buyer history')
        if (!controller.signal.aborted) setResult({ key, records: page.records, error: '' })
      } catch {
        if (!controller.signal.aborted)
          setResult({
            key,
            records: [],
            error: 'The buyer history is temporarily unavailable. Refresh the feed and try again.',
          })
      }
    }
    void load()
    return () => controller.abort()
  }, [active, path, buyerId, key, expectedCount, attempt])
  const current = result.key === key
  return {
    records: !active ? [] : path ? (current ? result.records : []) : signal?.buyer_history || [],
    loading: active && !!path && !!buyerId && !current,
    error:
      path && !buyerId
        ? 'The buyer identity could not be verified.'
        : path && current
          ? result.error
          : '',
    count: signal?.buyer_history_ref?.count ?? signal?.buyer_history?.length ?? 0,
    identityBasis:
      signal?.buyer_history_ref?.identity_basis || signal?.buyer_identity_basis || 'unknown',
    retry: () => {
      setResult({ key: '', records: [], error: '' })
      setAttempt((v) => v + 1)
    },
  }
}
