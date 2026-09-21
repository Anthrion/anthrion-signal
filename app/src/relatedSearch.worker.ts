import { createRelatedIndex } from './relatedSearch'
import type { EnglishText, Signal } from './types'

let find: ReturnType<typeof createRelatedIndex> | undefined
let selected: Signal | undefined
self.onmessage = (
  event: MessageEvent<{
    records?: Signal[]
    translations?: Record<string, EnglishText>
    selectedId?: string
    now: number
  }>,
) => {
  const { records, translations, selectedId, now } = event.data
  if (records) {
    find = createRelatedIndex(records, translations)
    selected = records.find((record) => record.id === selectedId)
  }
  if (!find || !selected) return
  const result = find.both(selected, now)
  const identities = (kind: 'signals' | 'awards') =>
    result[kind].map(({ signal, ...match }) => ({ id: signal.id, ...match }))
  self.postMessage({ signals: identities('signals'), awards: identities('awards') })
}
