import { isAvailableOpportunity, isHistoricalAward, searchText } from './lib'
import type { EnglishText, Signal } from './types'
import { samePublishedBuyer } from './research'

// Procurement boilerplate cannot establish subject similarity. Corpus frequency
// additionally downweights locally common terms; original and cached English text
// share an index, independent of the user's display-language choice.
const stop = new Set(
  `the and for with from this that these those shall will must may not are was were has have been being its their our your into within through which where when who all any each other such than then also more including include required requirement requirements contract contracts contracting tender tenders notice notices procurement bid bids bidder bidders supply supplier suppliers service services provision provide providing provided project projects framework agreement agreements lot lots award awarded published authority procedure public request information date time year years month months system systems software solution solutions delivery implementation management scope document documents please following accordance technical support terms conditions price value company limited de des du le les la un une et en pour dans par sur aux au avec est sont ou ce cette ses se il der die das den dem des und zur zum von mit fur auf ein eine einer einem ist sind oder werden wird im zu es el los las del por para con que una uno di per della delle degli che con il lo gli da dei het van een voor aan met op bij door om te het den til som og och att av med en ett som ja tai on sekä at der som`.split(
    /\s+/,
  ),
)
const tokens = (value: string) =>
  searchText(value)
    .match(/[\p{L}][\p{L}\p{N}]{2,}/gu)
    ?.filter((token) => !stop.has(token) && token.length < 45) || []
const searchable = (signal: Signal, english?: EnglishText) =>
  [
    signal.title,
    signal.description || signal.search_text || '',
    english?.title,
    english?.description,
  ]
    .filter(Boolean)
    .join('\n')
type Document = { signal: Signal; terms: Map<string, number>; title: Set<string> }
export type RelatedMatch = {
  signal: Signal
  relationship: 'same_procedure' | 'same_buyer' | 'shared_capability' | 'similar_text'
  capabilityIds: string[]
  terms: string[]
  score: number
}

export function createRelatedIndex(
  records: Signal[],
  translations: Record<string, EnglishText> = {},
) {
  const documents = new Map<string, Document>()
  const postings = new Map<string, Set<string>>()
  for (const signal of records) {
    if (documents.has(signal.id)) continue
    const terms = new Map<string, number>()
    for (const token of tokens(searchable(signal, translations[signal.id])))
      terms.set(token, Math.min(3, (terms.get(token) || 0) + 1))
    documents.set(signal.id, {
      signal,
      terms,
      title: new Set(tokens([signal.title, translations[signal.id]?.title].join(' '))),
    })
    for (const term of terms.keys()) {
      if (!postings.has(term)) postings.set(term, new Set())
      postings.get(term)!.add(signal.id)
    }
  }
  const idf = (term: string) => Math.log(1 + documents.size / (1 + (postings.get(term)?.size || 0)))
  const norms = new Map<string, number>()
  for (const [id, doc] of documents)
    norms.set(
      id,
      Math.sqrt(
        [...doc.terms].reduce(
          (sum, [term, count]) =>
            sum + (idf(term) * (1 + Math.log(count) + (doc.title.has(term) ? 2 : 0))) ** 2,
          0,
        ),
      ),
    )
  return (
    record: Signal,
    kind: 'signals' | 'awards',
    now: number,
    limit = Infinity,
  ): RelatedMatch[] => {
    const query = documents.get(record.id) || {
      signal: record,
      terms: new Map(tokens(searchable(record, translations[record.id])).map((t) => [t, 1])),
      title: new Set(tokens(record.title)),
    }
    const norm =
      norms.get(record.id) ||
      Math.sqrt(
        [...query.terms].reduce(
          (sum, [term, count]) =>
            sum + (idf(term) * (1 + Math.log(count) + (query.title.has(term) ? 2 : 0))) ** 2,
          0,
        ),
      )
    const similarities = new Map<string, { dot: number; terms: string[] }>()
    for (const [term, count] of query.terms) {
      const matches = postings.get(term)
      if (!matches || (documents.size >= 10 && matches.size / documents.size > 0.45)) continue
      const weight = idf(term) * (1 + Math.log(count) + (query.title.has(term) ? 2 : 0))
      for (const id of matches) {
        const doc = documents.get(id)!
        const entry = similarities.get(id) || { dot: 0, terms: [] }
        entry.dot +=
          weight * idf(term) * (1 + Math.log(doc.terms.get(term)!) + (doc.title.has(term) ? 2 : 0))
        entry.terms.push(term)
        similarities.set(id, entry)
      }
    }
    const result: RelatedMatch[] = []
    for (const [id, doc] of documents) {
      const signal = doc.signal
      if (
        id === record.id ||
        !(kind === 'awards' ? isHistoricalAward(signal, now) : isAvailableOpportunity(signal, now))
      )
        continue
      const sameCountry = record.countries.some((country) => signal.countries.includes(country))
      const capabilityIds = signal.matched_capabilities.filter((id) =>
        record.matched_capabilities.includes(id),
      )
      const similarity = similarities.get(id)
      const textScore = (similarity?.dot || 0) / (norm * (norms.get(id) || 1) || 1)
      const shared = similarity?.terms || []
      const meaningful = shared.length >= 2 && textScore >= 0.035
      const procedure = !!record.procedure_id && record.procedure_id === signal.procedure_id
      const buyer = samePublishedBuyer(record, signal)
      if (!procedure && !buyer && !(sameCountry && capabilityIds.length) && !meaningful) continue
      const relationship = procedure
        ? 'same_procedure'
        : buyer
          ? 'same_buyer'
          : sameCountry && capabilityIds.length
            ? 'shared_capability'
            : 'similar_text'
      result.push({
        signal,
        relationship,
        capabilityIds,
        terms: shared.sort((a, b) => idf(b) - idf(a)).slice(0, 3),
        score:
          (procedure ? 8 : buyer ? 4 : 0) +
          Math.min(2, capabilityIds.length * 0.5) +
          textScore * 3 +
          (sameCountry ? 0.1 : 0),
      })
    }
    return result
      .sort(
        (a, b) =>
          b.score - a.score ||
          (b.signal.award_date || b.signal.published_at || '').localeCompare(
            a.signal.award_date || a.signal.published_at || '',
          ) ||
          a.signal.id.localeCompare(b.signal.id),
      )
      .slice(0, limit)
  }
}
