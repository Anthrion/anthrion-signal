import { useCallback, useEffect, useRef, useState } from 'react'
import type { Dataset, EnglishText, Signal } from './types'
import { isAvailableOpportunity } from './lib'
import {
  BoundedCache,
  fetchJSON,
  isEnglishText,
  isSignal,
  loadCurrentDataset,
  safeDataPath,
} from './dataClient'
import type { DetailPage, SignalPage } from './dataClient'

export function resolveSignalSelection(
  data: Dataset | null,
  selected: Signal | string | null | undefined,
) {
  const id = typeof selected === 'string' ? selected : selected?.id || ''
  const summary = typeof selected === 'object' ? selected : data?.signals.find((s) => s.id === id)
  // Full legacy feeds and full award shards already contain the readable record.
  const path =
    summary && summary.is_summary !== true ? '' : data?.current_feed?.records[id]?.url || ''
  return { id, summary, path }
}

export function useSignalDetail(
  data: Dataset | null,
  selected: Signal | string | null | undefined,
) {
  const cache = useRef(new BoundedCache<DetailPage>(40, 16 * 1024 * 1024))
  const [attempt, setAttempt] = useState(0)
  const { id, summary, path } = resolveSignalSelection(data, selected)
  const key = `${id}|${path}`
  const [result, setResult] = useState<{
    key: string
    signal: Signal | null
    translation?: EnglishText
    error: string
  }>({ key: '', signal: null, error: '' })
  useEffect(() => {
    if (!id || !path) return
    const controller = new AbortController()
    const load = async () => {
      try {
        safeDataPath(path, 'records')
        let page = cache.current.get(path)
        if (!page) {
          const value = (await fetchJSON(path, controller.signal)) as DetailPage
          if (
            !value ||
            !['1.0', '2.0'].includes(value.schema_version) ||
            !isSignal(value.signal) ||
            value.signal.id !== id ||
            (value.translation !== undefined && !isEnglishText(value.translation))
          )
            throw new Error('Invalid detail')
          page = value
          if (!controller.signal.aborted) cache.current.set(path, page)
        }
        if (!controller.signal.aborted)
          setResult({ key, signal: page.signal, translation: page.translation, error: '' })
      } catch {
        if (!controller.signal.aborted)
          setResult({
            key,
            signal: null,
            error: 'The full record is temporarily unavailable. Refresh the feed and try again.',
          })
      }
    }
    void load()
    return () => controller.abort()
  }, [id, path, key, attempt])
  if (!path)
    return {
      signal: summary || null,
      translation: data?.translations?.[id],
      loading: false,
      error: id && !summary ? 'This record is not in the current feed.' : '',
      retry: () => setAttempt((v) => v + 1),
    }
  const current = result.key === key
  return {
    signal: current ? result.signal : null,
    translation: current ? result.translation : undefined,
    loading: !current,
    error: current ? result.error : '',
    retry: () => {
      setResult({ key: '', signal: null, error: '' })
      setAttempt((v) => v + 1)
    },
  }
}

export function useOpportunityData({
  market,
  selectedId = null,
}: {
  market: string
  selectedId?: string | null
}) {
  const cache = useRef(new BoundedCache<SignalPage>())
  const controller = useRef<AbortController | null>(null)
  const [result, setResult] = useState<{ market: string; data: Dataset | null; error: string }>({
    market,
    data: null,
    error: '',
  })
  const [loading, setLoading] = useState(true)
  const load = useCallback(async () => {
    controller.current?.abort()
    const active = new AbortController()
    controller.current = active
    setLoading(true)
    try {
      const data = await loadCurrentDataset(market, active.signal, cache.current)
      if (!active.signal.aborted)
        setResult({
          market,
          data: { ...data, signals: data.signals.filter((s) => isAvailableOpportunity(s)) },
          error: '',
        })
    } catch {
      if (!active.signal.aborted)
        setResult((previous) => ({
          market,
          data: previous.market === market ? previous.data : null,
          error: 'The latest opportunity feed is temporarily unavailable.',
        }))
    } finally {
      if (!active.signal.aborted) setLoading(false)
    }
  }, [market])
  useEffect(() => {
    void load()
    const interval = setInterval(() => {
      if (!document.hidden) void load()
    }, 5 * 60000)
    return () => {
      clearInterval(interval)
      controller.current?.abort()
    }
  }, [load])
  const data = result.market === market ? result.data : null
  const detail = useSignalDetail(data, selectedId)
  return {
    data,
    loading,
    error: result.market === market ? result.error : '',
    reload: load,
    selectedSignal: detail.signal,
    selectedTranslation: detail.translation,
    detailLoading: detail.loading,
    detailError: detail.error,
  }
}
