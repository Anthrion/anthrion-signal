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
for (const word of `application applications standard maintenance consultant consultants estimated quantity
  digital digitale digitaal government council municipality municipal ministry department organisation organization
  gemeente gemeenten gemeentelijke overheid gemeinde stadt verwaltung behörde kommune kommun kommunal
  opdracht opdrachten opdrachtgever opdrachtnemer overeenkomst overeenkomsten aanbesteding aanbestedingen
  levering leveringen leveren dienst diensten dienstverlening onderhoud standaard algemene betreft tevens
  medewerker medewerkers projectleider aanpak aantal geraamd geraamde omvang waarde exclusief bestaat
  aanvang gedurende jaarlijks inclusief onderstaande nadere bedoeld beschreven eisen voorwaarden
  auftrag aufträge auftraggeber auftragnehmer ausschreibung vergabe angebot angebote leistung leistungen
  lieferung bereitstellung rahmenvereinbarung gegenstand anforderungen leistungsbeschreibung vertrag verträge
  marché marchés prestation prestations fourniture fournitures titulaire acheteur contrat contrats
  notamment montant estimé estimée objet cadre durée conditions exigences
  appalto appalti fornitura forniture servizio servizi contratto contratti offerta offerte importo durata
  applicatie applicaties anwendung anwendungen applicazione applicazioni`.split(/\s+/))
  stop.add(searchText(word))
const tokens = (value: string) => {
  const text = searchText(value)
  const result: string[] = []
  for (const word of text.split(' ')) {
    if (word.length < 3 || stop.has(word)) continue
    const token = /[^a-z0-9]/.test(word)
      ? word.match(/[\p{L}][\p{L}\p{N}]{2,}/u)?.[0]
      : word.match(/[a-z][a-z0-9]{2,}/)?.[0]
    if (token && token.length < 45 && !stop.has(token)) result.push(token)
  }
  return result
}
const searchable = (signal: Signal, english?: EnglishText) =>
  [
    signal.title,
    signal.description || signal.search_text || '',
    english?.title,
    english?.description,
  ]
    .filter(Boolean)
    .join('\n')
type Document = { signal: Signal; terms: Map<number, number>; title: Set<number>; norm: number }
type Posting = { text: string; documents: number[]; frequency: number }
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
  const documents: Document[] = []
  const byId = new Map<string, Document>()
  const vocabulary = new Map<string, number>()
  const postings: Posting[] = []
  const termId = (text: string) => {
    const known = vocabulary.get(text)
    if (known !== undefined) return known
    const id = postings.length
    vocabulary.set(text, id)
    postings.push({ text, documents: [], frequency: Math.log(1 + documents.length) })
    return id
  }
  const normOf = (terms: Map<number, number>) => {
    let sum = 0
    for (const [term, factor] of terms) sum += (postings[term].frequency * factor) ** 2
    return Math.sqrt(sum)
  }
  for (const signal of records) {
    if (byId.has(signal.id)) continue
    const english = translations[signal.id]
    const terms = new Map<number, number>()
    for (const token of tokens(searchable(signal, english))) {
      const id = termId(token)
      terms.set(id, Math.min(3, (terms.get(id) || 0) + 1))
    }
    const title = new Set(tokens([signal.title, english?.title].join(' ')).map(termId))
    for (const [term, count] of terms) {
      terms.set(term, 1 + Math.log(count) + (title.has(term) ? 2 : 0))
      postings[term].documents.push(documents.length)
    }
    const document = { signal, terms, title, norm: 0 }
    documents.push(document)
    byId.set(signal.id, document)
  }
  // Store each word and source identity once. Numeric postings avoid millions
  // of repeated strings and Set entries without discarding any matching terms.
  for (const posting of postings)
    posting.frequency = Math.log(1 + documents.length / (1 + posting.documents.length))
  for (const document of documents) document.norm = normOf(document.terms)
  const find = (
    record: Signal,
    kind: 'signals' | 'awards' | 'both',
    now: number,
    limit = Infinity,
  ): RelatedMatch[] => {
    const fallbackTitle = byId.has(record.id)
      ? undefined
      : new Set(tokens(record.title).map(termId))
    const query = byId.get(record.id) || {
      signal: record,
      terms: new Map(
        tokens(searchable(record, translations[record.id]))
          .map(termId)
          .map((t) => [t, 1 + (fallbackTitle!.has(t) ? 2 : 0)]),
      ),
      title: fallbackTitle!,
      norm: 0,
    }
    const norm = query.norm || normOf(query.terms)
    const similarities = new Map<number, { dot: number; terms: number[] }>()
    for (const [term, factor] of query.terms) {
      const { documents: matches, frequency } = postings[term]
      if (documents.length >= 10 && matches.length / documents.length > 0.45) continue
      const weight = frequency * factor
      for (const id of matches) {
        const doc = documents[id]
        const entry = similarities.get(id) || { dot: 0, terms: [] }
        entry.dot += weight * frequency * doc.terms.get(term)!
        entry.terms.push(term)
        similarities.set(id, entry)
      }
    }
    const result: RelatedMatch[] = []
    for (const [id, doc] of documents.entries()) {
      const signal = doc.signal
      if (
        signal.id === record.id ||
        !(kind === 'awards'
          ? isHistoricalAward(signal, now)
          : kind === 'signals'
            ? isAvailableOpportunity(signal, now)
            : isHistoricalAward(signal, now) || isAvailableOpportunity(signal, now))
      )
        continue
      const sameCountry = record.countries.some((country) => signal.countries.includes(country))
      const capabilityIds = signal.matched_capabilities.filter((id) =>
        record.matched_capabilities.includes(id),
      )
      const similarity = similarities.get(id)
      const textScore = (similarity?.dot || 0) / (norm * (doc.norm || 1) || 1)
      const shared = similarity?.terms || []
      const titleConnection = shared.some((term) => query.title.has(term) || doc.title.has(term))
      const meaningful =
        shared.length >= 2 && textScore >= 0.035 && (titleConnection || textScore >= 0.12)
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
        terms: shared
          .sort((a, b) => postings[b].frequency - postings[a].frequency)
          .slice(0, 3)
          .map((id) => postings[id].text),
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
  // Both columns use the same corpus, query vector and ranking. Calculate those
  // once, then split the ordered result without capping either column.
  return Object.assign(find, {
    both(record: Signal, now: number) {
      const matches = find(record, 'both', now)
      return {
        signals: matches.filter(({ signal }) => isAvailableOpportunity(signal, now)),
        awards: matches.filter(({ signal }) => isHistoricalAward(signal, now)),
      }
    },
  })
}
