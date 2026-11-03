import { useEffect, useMemo, useRef, useState } from 'react'
import type { EnglishText, Signal } from './types'
import type { RelatedMatch } from './relatedSearch'

type Result = { signals: RelatedMatch[]; awards: RelatedMatch[]; loading: boolean; error: string }
type MatchId = Omit<RelatedMatch, 'signal'> & { id: string }
const fields = [
  'id',
  'title',
  'description',
  'search_text',
  'buyer_name',
  'buyer_id',
  'buyer_identity_basis',
  'source',
  'countries',
  'matched_capabilities',
  'procedure_id',
  'signal_type',
  'status',
  'notice_type',
  'lifecycle_state',
  'exclusion_reasons',
  'related_signal_id',
  'award_statuses',
  'deadline_at',
  'response_deadlines',
  'deadlines',
  'last_material_update',
  'published_at',
  'award_date',
  'procurement_stage',
  'renewal_basis',
  'analysis',
] as const

export function useRelatedMatches(
  records: Signal[],
  translations: Record<string, EnglishText> | undefined,
  selectedId: string,
  now: number,
  enabled: boolean,
) {
  const worker = useRef<Worker | null>(null)
  const requestedTime = useRef(now)
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<Result>({
    signals: [],
    awards: [],
    loading: false,
    error: '',
  })
  const byId = useMemo(() => new Map(records.map((signal) => [signal.id, signal])), [records])
  useEffect(() => {
    if (!enabled) return
    let active = true
    setResult((previous) => ({ ...previous, loading: true, error: '' }))
    const failed = () => {
      if (active)
        setResult({
          signals: [],
          awards: [],
          loading: false,
          error: 'Related records could not be loaded.',
        })
    }
    try {
      const instance = new Worker(new URL('./relatedSearch.worker.ts', import.meta.url), {
        type: 'module',
      })
      worker.current = instance
      instance.onmessage = (event: MessageEvent<{ signals: MatchId[]; awards: MatchId[] }>) => {
        if (!active) return
        const restore = (values: MatchId[]) =>
          values.flatMap(({ id, ...match }) =>
            byId.has(id) ? [{ ...match, signal: byId.get(id)! }] : [],
          )
        setResult({
          signals: restore(event.data.signals),
          awards: restore(event.data.awards),
          loading: false,
          error: '',
        })
      }
      instance.onerror = failed
      instance.onmessageerror = failed
      // Preserve complete matching text, but avoid copying document/history trees
      // into a worker. Results carry identities back to the full source records.
      instance.postMessage({
        records: records.map((signal) => {
          const projected: Record<string, unknown> = {}
          for (const field of fields) projected[field] = signal[field]
          projected.analysis = signal.analysis && {
            eligibility_checks: signal.analysis.eligibility_checks?.map(({ status }) => ({
              status,
            })),
          }
          return projected
        }),
        translations: Object.fromEntries(
          records.flatMap((signal) => {
            const english = translations?.[signal.id]
            return english
              ? [[signal.id, { title: english.title, description: english.description }]]
              : []
          }),
        ),
        selectedId,
        now,
      })
      requestedTime.current = now
    } catch {
      failed()
    }
    return () => {
      active = false
      worker.current?.terminate()
      worker.current = null
    }
  }, [records, byId, translations, selectedId, enabled, attempt])
  useEffect(() => {
    if (worker.current && requestedTime.current !== now) {
      worker.current.postMessage({ now })
      requestedTime.current = now
    }
  }, [now])
  return { ...result, retry: () => setAttempt((value) => value + 1) }
}
