import { useEffect, useMemo, useRef, useState } from 'react'
import type { Dataset, Signal, EnglishText } from './types'
import { isHistoricalAward, matchesMarket } from './lib'
import { BoundedCache, loadPages, mergeSignalPages, selectMarketEntries } from './dataClient'
import type { SignalPage } from './dataClient'

const empty = { signals: [] as Signal[], translations: {} as Record<string, EnglishText> }
export function awardMarketPaths(data: Dataset | null, market: string) {
  const manifest = data?.award_history || {}
  return [
    ...new Set(selectMarketEntries(Object.entries(manifest), market).map(([, p]) => p.url)),
  ].sort()
}
export function useAwardHistory(data: Dataset | null, active: boolean, market: string) {
  const cache = useRef(new BoundedCache<SignalPage>(12, 40 * 1024 * 1024))
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({ key: '', ...empty, error: '' })
  const paths = useMemo(() => awardMarketPaths(data, market), [data?.award_history, market])
  const counts = useMemo(
    () =>
      Object.fromEntries(
        Object.values(data?.award_history || {}).map((page) => [page.url, page.count]),
      ),
    [data?.award_history],
  )
  const key = JSON.stringify([market, paths.map((path) => [path, counts[path]])])
  useEffect(() => {
    if (!active || !data) return
    // The merged result already owns these records even when the shard LRU has
    // evicted some of them. Reopening Context need not download/parse them again.
    // Content-addressed paths AND manifest counts invalidate this reuse.
    if (result.key === key && !result.error) return
    const controller = new AbortController()
    const load = async () => {
      try {
        const pages = await loadPages(
          paths,
          'awards',
          controller.signal,
          cache.current,
          undefined,
          counts,
        )
        const merged = mergeSignalPages(pages)
        if (!controller.signal.aborted)
          setResult({
            key,
            error: '',
            ...merged,
            signals: merged.signals.filter((s) => isHistoricalAward(s) && matchesMarket(s, market)),
          })
      } catch {
        if (!controller.signal.aborted) {
          controller.abort()
          setResult({
            key,
            ...empty,
            error: 'Awarded records are temporarily unavailable. Refresh the feed and try again.',
          })
        }
      }
    }
    void load()
    return () => controller.abort()
  }, [active, data, key, paths, market, attempt])
  const current = active && result.key === key
  const knownSignals = useMemo(() => {
    const currentPaths = new Set(Object.values(data?.award_history || {}).map((p) => p.url))
    return [
      ...new Map(
        [...currentPaths]
          .flatMap((path) => cache.current.get(path)?.signals || [])
          .filter((s) => isHistoricalAward(s))
          .map((s) => [s.id, s]),
      ).values(),
    ]
  }, [data, result])
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
