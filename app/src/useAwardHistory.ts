import { useEffect, useMemo, useRef, useState } from 'react'
import type { Dataset, Signal, EnglishText } from './types'
import { isHistoricalAward } from './lib'

interface AwardPage {
  schema_version: string
  signals: Signal[]
  translations?: Record<string, EnglishText>
}
const empty = { signals: [] as Signal[], translations: {} as Record<string, EnglishText> }

export function useAwardHistory(data: Dataset | null, active: boolean, market: string) {
  const cache = useRef(new Map<string, AwardPage>())
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({ key: '', ...empty, error: '' })
  const paths = useMemo(
    () =>
      active
        ? Object.entries(data?.award_history || {})
            .filter(([id]) => !market || id === market)
            .map(([, page]) => page.url)
            .sort()
        : [],
    [active, data?.award_history, market],
  )
  const key = JSON.stringify(paths)
  useEffect(() => {
    if (!active || !data) return
    const controller = new AbortController()
    const load = async () => {
      try {
        const pages = await Promise.all(
          paths.map(async (path) => {
            if (!/^awards\/[A-Z]+-[a-f0-9]{16}\.json$/.test(path))
              throw new Error('Invalid award history path')
            const cached = cache.current.get(path)
            if (cached) return cached
            const response = await fetch(`${import.meta.env.BASE_URL}data/${path}`, {
              signal: controller.signal,
            })
            if (!response.ok) throw new Error('Award history unavailable')
            const page: AwardPage = await response.json()
            if (page.schema_version !== '1.0' || !Array.isArray(page.signals))
              throw new Error('Invalid award history')
            if (
              !page.signals.every(
                (s) =>
                  s &&
                  [
                    'id',
                    'title',
                    'description',
                    'status',
                    'source',
                    'signal_type',
                    'primary_source_url',
                  ].every((field) => typeof s[field as keyof Signal] === 'string') &&
                  [
                    'countries',
                    'matched_capabilities',
                    'provenance',
                    'categories',
                    'cpv_codes',
                    'regions',
                    'lot_ids',
                    'documents',
                    'changes',
                  ].every((field) => Array.isArray(s[field as keyof Signal])),
              )
            )
              throw new Error('Invalid award record')
            cache.current.set(path, page)
            return page
          }),
        )
        if (!controller.signal.aborted)
          setResult({
            key,
            error: '',
            signals: [
              ...new Map(
                pages
                  .flatMap((p) => p.signals)
                  .filter((s) => isHistoricalAward(s))
                  .map((s) => [s.id, s]),
              ).values(),
            ],
            translations: Object.assign({}, ...pages.map((p) => p.translations || {})),
          })
      } catch {
        if (!controller.signal.aborted) {
          paths.forEach((path) => cache.current.delete(path))
          setResult({ key, ...empty, error: 'Awarded records are temporarily unavailable.' })
        }
      }
    }
    void load()
    return () => controller.abort()
  }, [active, data, key, paths, attempt])
  const current = active && result.key === key
  const knownSignals = useMemo(
    () => [
      ...new Map(
        [...cache.current.values()]
          .flatMap((page) => page.signals)
          .filter((signal) => isHistoricalAward(signal))
          .map((signal) => [signal.id, signal]),
      ).values(),
    ],
    [result],
  )
  return {
    ...(current ? result : { ...empty, error: '' }),
    loading: active && !!data && !current,
    knownSignals,
    retry: () => {
      setResult({ key: '', ...empty, error: '' })
      setAttempt((v) => v + 1)
    },
  }
}
