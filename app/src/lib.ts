import type { Dataset, Filters, Signal } from './types'
import { dateOnlyEnd, deadlineEventValue, validCalendarDate } from './deadlineMath'

export const defaults: Filters = {
  q: '',
  searchMode: 'capability',
  match: 'all',
  view: 'live',
  sort: 'recent',
  market: 'GB',
  score: '',
  confidence: '',
  source: '',
  type: '',
  recommendation: '',
  capability: '',
  sector: '',
  buyer: '',
  supplier: '',
  awardFrom: '',
  awardTo: '',
  amountType: '',
  region: '',
  cpv: '',
  minValue: '',
  maxValue: '',
  currency: '',
  deadline: '',
  change: '',
}
export const markets = [
  { id: 'GB', name: 'United Kingdom', short: 'UK', countries: ['GB'], region: 'Europe' },
  {
    id: 'NORTHAMERICA',
    name: 'North America',
    short: 'NA',
    countries: ['US', 'CA'],
    region: 'North America',
  },
  { id: 'US', name: 'United States', short: 'US', countries: ['US'], region: 'North America' },
  { id: 'CA', name: 'Canada', short: 'CA', countries: ['CA'], region: 'North America' },
  { id: 'IT', name: 'Italy', short: 'IT', countries: ['IT'], region: 'Europe' },
  {
    id: 'NORDICS',
    name: 'Nordics',
    short: 'NO',
    countries: ['SE', 'FI', 'DK', 'NO', 'IS'],
    region: 'Northern Europe',
  },
  {
    id: 'DACH',
    name: 'DACH',
    short: 'DACH',
    countries: ['DE', 'AT', 'CH'],
    region: 'Central Europe',
  },
  { id: 'DE', name: 'Germany', short: 'DE', countries: ['DE'], region: 'Europe' },
  { id: 'ES', name: 'Spain', short: 'ES', countries: ['ES'], region: 'Europe' },
  { id: 'GR', name: 'Greece', short: 'GR', countries: ['GR'], region: 'Europe' },
  {
    id: 'BENELUX',
    name: 'Benelux',
    short: 'BNL',
    countries: ['BE', 'NL', 'LU'],
    region: 'Western Europe',
  },
  ...(
    [
      ['FR', 'France'],
      ['BE', 'Belgium'],
      ['IE', 'Ireland'],
      ['NL', 'Netherlands'],
      ['CH', 'Switzerland'],
      ['AT', 'Austria'],
      ['PT', 'Portugal'],
      ['PL', 'Poland'],
      ['EE', 'Estonia'],
      ['LV', 'Latvia'],
      ['LT', 'Lithuania'],
      ['CZ', 'Czechia'],
      ['RO', 'Romania'],
      ['BG', 'Bulgaria'],
      ['HR', 'Croatia'],
      ['HU', 'Hungary'],
      ['LU', 'Luxembourg'],
      ['CY', 'Cyprus'],
      ['MT', 'Malta'],
      ['SI', 'Slovenia'],
      ['SK', 'Slovakia'],
      ['SE', 'Sweden'],
      ['FI', 'Finland'],
      ['DK', 'Denmark'],
      ['NO', 'Norway'],
      ['IS', 'Iceland'],
    ] as const
  ).map(([id, name]) => ({ id, name, short: id, countries: [id], region: 'Europe' })),
] as const

export const marketGroups: Record<string, readonly string[]> = {
  NORTHAMERICA: ['US', 'CA'],
  NORDICS: ['SE', 'FI', 'DK', 'NO', 'IS'],
  BENELUX: ['BE', 'NL', 'LU'],
  DACH: ['DE', 'AT', 'CH'],
}
export function countryLabels(signal: Pick<Signal, 'countries'>) {
  return [...new Set(signal.countries)]
    .map(
      (id) =>
        markets.find((market) => market.id === id && market.countries.length === 1)?.name || id,
    )
    .join(' · ')
}
export function isCombinedMarket(market: string) {
  return (
    !market ||
    market === 'ALL' ||
    (markets.find((item) => item.id === market)?.countries.length || 0) > 1
  )
}
/** Country IDs remain supported in existing links and source facts. */
export function defaultMarketGroup(id: string) {
  return ['BENELUX', 'DACH'].find((group) => marketGroups[group].includes(id)) || id
}

export const allMarkets = {
  id: '',
  name: 'All markets',
  short: 'All',
  countries: [] as string[],
  region: '',
}
export const defaultMarketOptions = [allMarkets, ...markets]

export function matchesMarket(signal: Signal, market: string) {
  if (!market || market === 'ALL') return true
  const countries: readonly string[] = markets.find((m) => m.id === market)?.countries || [market]
  return signal.countries.some((country) => countries.includes(country))
}

export function marketIsEnabled(market: string, configured: Record<string, { enabled: boolean }>) {
  if (!market || market === 'ALL') return Object.values(configured).some((m) => m.enabled)
  const countries: readonly string[] = markets.find((m) => m.id === market)?.countries || [market]
  return countries.some((country) => configured[country]?.enabled)
}
export const typeLabels: Record<string, string> = {
  LIVE_TENDER: 'Live tender',
  EARLY_MARKET_ENGAGEMENT: 'Early engagement',
  PIPELINE: 'Pipeline',
  FUTURE_OPPORTUNITY: 'Future opportunity',
  FRAMEWORK: 'Framework',
  RFI: 'Request for information',
  RFP: 'Request for proposal',
  RENEWAL_SIGNAL: 'Renewal signal',
  AWARD: 'Contract award',
  STRATEGIC_INTENT: 'Strategic intent',
  FUNDING: 'Funding',
  PARTNERSHIP: 'Partnership',
}
export const recommendationLabels: Record<string, string> = {
  PURSUE: 'Pursue',
  ENGAGE_NOW: 'Engage now',
  WATCH: 'Watch',
  PARTNER: 'Partner',
  FUNDING: 'Explore funding',
  REVIEW: 'Review',
  LOW_PRIORITY: 'Low priority',
}
export const date = (value: string | null, options?: Intl.DateTimeFormatOptions) =>
  value && Number.isFinite(Date.parse(value))
    ? new Intl.DateTimeFormat('en-GB', {
        ...(options || { day: 'numeric', month: 'short', year: 'numeric' }),
        ...(/^\d{4}-\d{2}-\d{2}$/.test(value) ? { timeZone: 'UTC' } : {}),
      }).format(new Date(value))
    : 'Not published'
export const amount = (value: number | null, currency: string | null, compact = true) => {
  if (value === null) return 'Value not published'
  if (!currency) return `${value.toLocaleString('en-GB')} (currency not published)`
  try {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: currency || 'GBP',
      notation: compact ? 'compact' : 'standard',
      maximumFractionDigits: compact ? 1 : 0,
    }).format(value)
  } catch {
    return `${value.toLocaleString('en-GB')} ${currency || ''}`
  }
}
export const amountLabels: Record<string, string> = {
  estimated_contract: 'Estimated contract value',
  framework_ceiling: 'Framework ceiling',
  grant_range: 'Published grant range',
  programme_funding: 'Programme funding',
  award: 'Award value',
  annual_spend: 'Annual spend',
  unknown: 'Published amount',
}
export function amountPresentation(signal: Signal, compact = true) {
  const fact = signal.amount
  const minimum = fact?.minimum ?? signal.value_min
  const maximum = fact?.maximum ?? signal.value_max
  const currency = fact?.currency ?? signal.currency
  const value =
    minimum !== null &&
    minimum !== undefined &&
    maximum !== null &&
    maximum !== undefined &&
    minimum !== maximum
      ? `${amount(minimum, currency, compact)}–${amount(maximum, currency, compact)}`
      : amount(maximum ?? minimum ?? null, currency, compact)
  return {
    label: amountLabels[fact?.kind || 'unknown'] || 'Published amount',
    value,
    sourceLabel: fact?.source_label || '',
    sourceURL: fact?.source_url || signal.primary_source_url,
  }
}
export function currencyOptions(signals: Signal[]) {
  const currencies = new Set(['GBP', 'USD', 'EUR', 'DKK', 'NOK', 'SEK', 'ISK'])
  if (typeof Intl.supportedValuesOf === 'function') {
    for (const currency of Intl.supportedValuesOf('currency')) currencies.add(currency)
  }
  for (const signal of signals) {
    if (signal.currency && /^[A-Z]{3}$/.test(signal.currency)) currencies.add(signal.currency)
  }
  const names = new Intl.DisplayNames('en-GB', { type: 'currency' })
  return [...currencies]
    .map((currency) => ({ value: currency, label: names.of(currency) || currency }))
    .sort((a, b) => a.label.localeCompare(b.label, 'en-GB') || a.value.localeCompare(b.value))
}
export function responseDeadline(s: Signal, now = Date.now()) {
  const dates = responseValues(s)
    .filter((value) => Number.isFinite(Date.parse(value)))
    .sort((a, b) => Date.parse(a) - Date.parse(b))
  return (
    dates.find((value) => deadlineInstant(value, s) > now) ||
    dates.at(-1) ||
    (s.deadlines?.length ? null : s.deadline_at)
  )
}
function responseEvents(s: Signal) {
  const current = (s.deadlines || []).filter(
    (event) =>
      event.status === 'current' && !['questions', 'invited_submission'].includes(event.kind),
  )
  const initial = current.filter((event) =>
    ['expression_of_interest', 'application'].includes(event.kind),
  )
  return initial.length ? initial : current
}
export function selectedResponseDeadlineEvent(s: Signal, now = Date.now()) {
  const value = responseDeadline(s, now)
  return value ? responseEvents(s).find((event) => deadlineEventValue(event) === value) : undefined
}
function responseValues(s: Signal): string[] {
  if (s.deadlines?.length) {
    return responseEvents(s)
      .map(deadlineEventValue)
      .filter((value): value is string => !!value)
  }
  return s.response_deadlines?.length ? s.response_deadlines : s.deadline_at ? [s.deadline_at] : []
}
function deadlineInstant(value: string, signal: Signal) {
  const instant = Date.parse(value)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(instant)) return instant
  const event = signal.deadlines?.find((d) => d.date === value && d.status === 'current')
  return dateOnlyEnd(
    value,
    event?.timezone || (signal.source === 'digital_outcomes' ? 'Europe/London' : undefined),
  )
}
export const daysLeft = (s: Signal, now = Date.now()) => {
  const deadline = responseDeadline(s, now)
  return deadline ? Math.ceil((deadlineInstant(deadline, s) - now) / 86400000) : null
}
export function deadlineCaption(s: Signal, now = Date.now()) {
  const deadline = responseDeadline(s, now)
  if (!deadline)
    return s.procurement_stage === 'planning' ? 'Early-stage opportunity' : 'Deadline not published'
  const remaining = deadlineInstant(deadline, s) - now
  const label = date(deadline, { day: 'numeric', month: 'short' })
  if (/^\d{4}-\d{2}-\d{2}$/.test(deadline) && remaining > 0) return label
  if (remaining <= 0) return `Closed ${label}`
  if (remaining < 3600000) return `${label} · ${Math.ceil(remaining / 60000)}m left`
  if (remaining < 86400000) return `${label} · ${Math.ceil(remaining / 3600000)}h left`
  return `${label}${remaining <= 14 * 86400000 ? ` · ${Math.ceil(remaining / 86400000)}d left` : ''}`
}
export function lifecycleState(s: Signal, now = Date.now()) {
  if (/^(CANCELLED|CANCELED|AVLYST|KESKEYTETTY|PERUTTU)\b/.test(s.title.trim())) return 'CLOSED'
  if (['veat', 'dir-awa-pre'].includes(s.notice_type?.toLowerCase() || '')) return 'CLOSED'
  if (['cancelled', 'canceled', 'unsuccessful'].includes(s.status)) return 'CANCELLED'
  if (s.status === 'withdrawn') return 'WITHDRAWN'
  if (s.signal_type === 'AWARD' || s.status === 'awarded' || s.lifecycle_state === 'AWARDED')
    return 'AWARDED'
  if (
    ['closed', 'complete', 'completed', 'terminated', 'not_listed', 'restricted'].includes(s.status)
  )
    return 'CLOSED'
  if (s.status === 'postponed') return 'UNKNOWN'
  const deadlines = responseValues(s)
    .map((value) => deadlineInstant(value, s))
    .filter(Number.isFinite)
  const finalDeadline = deadlines.length ? Math.max(...deadlines) : NaN
  if (s.status === 'expired' || finalDeadline <= now) return 'EXPIRED'
  if (s.source === 'digital_outcomes' && s.lifecycle_state === 'UNKNOWN') return 'UNKNOWN'
  if (s.signal_type === 'RENEWAL_SIGNAL') return 'FUTURE'
  if (['EARLY_MARKET_ENGAGEMENT', 'RFI'].includes(s.signal_type)) {
    return s.deadline_at ||
      s.status === 'active' ||
      now - Date.parse(s.last_material_update || s.published_at || '') <= 90 * 86400000
      ? 'EARLY_ENGAGEMENT'
      : 'UNKNOWN'
  }
  if (
    ['PIPELINE', 'FUTURE_OPPORTUNITY', 'STRATEGIC_INTENT'].includes(s.signal_type) ||
    s.procurement_stage === 'planning'
  )
    return 'FUTURE'
  if (['active', 'open'].includes(s.status) || s.deadline_at) return 'OPEN'
  return 'UNKNOWN'
}
export const lifecycleLabels: Record<string, string> = {
  OPEN: 'Open',
  EARLY_ENGAGEMENT: 'Early engagement',
  FUTURE: 'Future',
  AWARDED: 'Awarded',
  CLOSED: 'Closed',
  EXPIRED: 'Expired',
  CANCELLED: 'Cancelled',
  WITHDRAWN: 'Withdrawn',
  UNKNOWN: 'Status to confirm',
}
export function isAwardIntelligence(s: Signal) {
  return (
    s.signal_type === 'AWARD' ||
    s.status.toLowerCase() === 'awarded' ||
    s.lifecycle_state === 'AWARDED' ||
    (s.signal_type === 'RENEWAL_SIGNAL' &&
      !!(s.related_signal_id || s.status === 'inferred' || s.renewal_basis))
  )
}
export function isAvailableOpportunity(s: Signal, now = Date.now()) {
  return (
    !isAwardIntelligence(s) &&
    !['postponed', 'unverified'].includes(s.status) &&
    !['AWARDED', 'CLOSED', 'EXPIRED', 'CANCELLED', 'WITHDRAWN'].includes(lifecycleState(s, now)) &&
    !s.exclusion_reasons?.length &&
    !s.analysis?.eligibility_checks?.some((check) => check.status === 'CONFIRMED_BLOCKER')
  )
}
export const isLive = (s: Signal, now = Date.now()) =>
  !s.exclusion_reasons?.length && lifecycleState(s, now) === 'OPEN'
export const hasAwardOutcome = (s: Signal, now = Date.now()) =>
  s.signal_type !== 'RENEWAL_SIGNAL' &&
  !s.related_signal_id &&
  (!s.award_statuses?.length || s.award_statuses.includes('active')) &&
  s.notice_type?.toUpperCase() !== 'UK5' &&
  lifecycleState(s, now) === 'AWARDED'
export const isHistoricalAward = (s: Signal, now = Date.now()) =>
  !s.exclusion_reasons?.length && hasAwardOutcome(s, now)
export const isEarly = (s: Signal, now = Date.now()) =>
  !s.exclusion_reasons?.length && lifecycleState(s, now) === 'EARLY_ENGAGEMENT'

export function searchText(value: string) {
  const folded = value
    .replace(/[\u0080-\uffff]+/g, (part) => part.normalize('NFKD').replace(/\p{M}/gu, ''))
    .toLocaleLowerCase()
  // Apply Unicode classification only to non-ASCII runs. One curly quote must
  // not force the slower Unicode expression over an entire English notice.
  return folded
    .replace(/[\u0080-\uffff]+/g, (part) => part.replace(/[^\p{L}\p{N}]+/gu, ' '))
    .replace(/[^a-z0-9\u0080-\uffff]+/g, ' ')
    .trim()
}

export interface SearchIntent {
  mode?: string
  match?: string
}

export function explainSearch(
  s: Signal,
  query: string,
  capabilities: Dataset['capabilities'] = [],
  english?: NonNullable<Dataset['translations']>[string],
  intent: SearchIntent = {},
) {
  return prepareSearch(query, capabilities, intent)(s, english)
}

// Compile the query and its capability aliases once for the whole feed. Neither
// language matching nor query parsing depends on the record being examined.
export function prepareSearch(
  query: string,
  capabilities: Dataset['capabilities'] = [],
  intent: SearchIntent = {},
) {
  const q = searchText(query)
  const terms =
    intent.match === 'phrase'
      ? [{ text: q, phrase: true }]
      : [...query.matchAll(/"([^"]+)"|(\S+)/gu)]
          .map((m) => ({ text: searchText(m[1] || m[2]), phrase: !!m[1] }))
          .filter((t) => t.text)
  const aliases = new Map<string, string[]>()
  if (q && intent.mode !== 'exact') {
    const requested = new Set([q, ...terms.map((term) => term.text)])
    for (const capability of capabilities) {
      const names = new Set(
        [capability.id, capability.label, ...(capability.search_terms || [])].map(searchText),
      )
      for (const name of names) {
        if (!requested.has(name)) continue
        const ids = aliases.get(name) || []
        ids.push(capability.id)
        aliases.set(name, ids)
      }
    }
  }
  return (s: Signal, english?: NonNullable<Dataset['translations']>[string]) => {
    if (!q) return { matched: true, basis: 'text' as const, capabilities: [] as string[] }
    const text = searchText(
      [
        s.title,
        s.description,
        english?.title,
        english?.description,
        s.buyer_name,
        translatedBuyer(s, english),
        s.search_text,
        s.ocid,
        ...(s.external_ids || []),
      ]
        .filter(Boolean)
        .join(' '),
    )
    const boundaryText = ` ${text} `
    const literal = (term: string, phrase = false) =>
      phrase || intent.mode === 'exact'
        ? boundaryText.includes(` ${term} `)
        : term.length <= 3
          ? !term.includes(' ') && boundaryText.includes(` ${term} `)
          : text.includes(term)
    const literalMatches = terms.map((term) => literal(term.text, term.phrase))
    const direct =
      intent.match === 'any' ? literalMatches.some(Boolean) : literalMatches.every(Boolean)
    if (direct) return { matched: true, basis: 'text' as const, capabilities: [] as string[] }
    const recordAliases = (term: string) =>
      (aliases.get(term) || []).filter(
        (id) => s.matched_capabilities.includes(id) || s.discovery_families?.includes(id),
      )
    const results = terms.map((term, index) => ({
      text: literalMatches[index],
      aliases: recordAliases(term.text),
    }))
    const wholeAliases = recordAliases(q)
    const expanded =
      intent.match === 'any'
        ? results.some((r) => r.text || r.aliases.length)
        : results.every((r) => r.text || r.aliases.length)
    return {
      matched: !!wholeAliases.length || expanded,
      basis: 'capability' as const,
      capabilities: [...new Set([...wholeAliases, ...results.flatMap((r) => r.aliases)])],
    }
  }
}

export function matchesSearch(
  s: Signal,
  query: string,
  capabilities: Dataset['capabilities'] = [],
  english?: NonNullable<Dataset['translations']>[string],
  intent: SearchIntent = {},
) {
  return explainSearch(s, query, capabilities, english, intent).matched
}
export function translatedBuyer(s: Signal, english?: NonNullable<Dataset['translations']>[string]) {
  return s.buyer_name && english?.buyer_original === s.buyer_name ? english.buyer_name || '' : ''
}

export function displayBuyer(s: Signal, english?: NonNullable<Dataset['translations']>[string]) {
  const official = s.buyer_name || 'Buyer not published'
  const translated = translatedBuyer(s, english).trim()
  return translated && !searchText(official).includes(searchText(translated))
    ? `${official} (${translated})`
    : official
}
export const isNew = (s: Signal, now = Date.now()) => now - Date.parse(s.first_seen_at) < 86400000
const collectionDay = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/London',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})
export function isAddedToday(s: Signal, now = Date.now()) {
  const collected = Date.parse(s.first_seen_at)
  return (
    Number.isFinite(collected) &&
    collected <= now &&
    collectionDay.format(collected) === collectionDay.format(now)
  )
}
// A calendar day is the source's own publication date, recorded at discovery; observed
// material changes are collection instants. Parsed as midnight UTC, a TED day can start up
// to two hours after its Brussels-midnight release was first collected.
export const isUpdated = (s: Signal, now = Date.now()) =>
  !isNew(s, now) &&
  !/^\d{4}-\d{2}-\d{2}$/.test(s.last_material_update) &&
  now - Date.parse(s.last_material_update) < 86400000
export function normaliseFilters(value: Partial<Filters>): Filters {
  const result = Object.fromEntries(
    Object.entries(defaults).map(([key, fallback]) => [
      key,
      typeof value[key as keyof Filters] === 'string' ? value[key as keyof Filters] : fallback,
    ]),
  ) as unknown as Filters
  if (!['exact', 'capability'].includes(result.searchMode)) result.searchMode = defaults.searchMode
  if (!['all', 'any', 'phrase'].includes(result.match)) result.match = defaults.match
  if (result.market === 'ALL') result.market = ''
  if (marketGroups[result.market.toUpperCase()]) result.market = result.market.toUpperCase()
  for (const key of ['awardFrom', 'awardTo'] as const) {
    if (result[key] && !validCalendarDate(result[key])) result[key] = ''
  }
  if (['top', 'renewals', 'sources'].includes(result.view)) result.view = 'all'
  if (result.sort === 'awarded') {
    result.view = 'awards'
    result.sort = 'recent'
  }
  if (result.view === 'pipeline') result.view = 'early'
  if (result.view === 'updates') result.view = 'today'
  if (result.view === 'frameworks') {
    result.view = 'all'
    result.type ||= 'FRAMEWORK'
  }
  if (result.view === 'funding') result.view = 'all'
  if (['recommended', 'fit', 'confidence'].includes(result.sort)) result.sort = 'recent'
  if (!['all', 'live', 'early', 'closing', 'today', 'saved', 'awards'].includes(result.view))
    result.view = defaults.view
  if (!['recent', 'updated', 'deadline', 'value', 'value-low', 'capability'].includes(result.sort))
    result.sort = defaults.sort
  if (['AWARD', 'RENEWAL_SIGNAL'].includes(result.type)) result.type = ''
  if (result.view === 'awards') result.type = result.deadline = result.change = ''
  result.score = result.confidence = result.recommendation = ''
  return result
}
export function readFilters(): Filters {
  const params = new URLSearchParams(window.location.search)
  return normaliseFilters(Object.fromEntries(params))
}
const platformFamilies = new Set([
  'salesforce',
  'crm',
  'relationships',
  'service',
  'contact_centre',
  'portals',
  'sales_revenue',
  'marketing',
  'data',
  'integration',
  'analytics',
  'field_service',
  'transformation',
  'workflow',
  'managed',
  'industry',
  'external_integration',
  'collaboration',
])
const aiFamilies = new Set(['ai', 'genai', 'automation', 'knowledge'])
export function priorityTier(signal: Signal) {
  if (signal.delivery_priority) return { platform: 0, ai: 1, other: 2 }[signal.delivery_priority]
  const families = signal.discovery_families || signal.matched_capabilities
  if (families.some((id) => platformFamilies.has(id))) return 0
  return families.some((id) => aiFamilies.has(id)) ? 1 : 2
}
export function filterSignals(
  signals: Signal[],
  f: Filters,
  saved: string[] = [],
  now = Date.now(),
  capabilities: Dataset['capabilities'] = [],
  translations: Dataset['translations'] = {},
) {
  const currentViews = ['live', 'closing', 'early', 'pipeline', 'frameworks', 'funding']
  const search = prepareSearch(f.q, capabilities, { mode: f.searchMode, match: f.match })
  const result = signals.filter((s) => {
    if (
      f.view === 'awards'
        ? !isHistoricalAward(s, now)
        : !isAvailableOpportunity(s, now) && !(f.view === 'saved' && isHistoricalAward(s, now))
    )
      return false
    if (!matchesMarket(s, f.market)) return false
    const state = lifecycleState(s, now)
    if (
      currentViews.includes(f.view) &&
      (s.exclusion_reasons?.length || !['OPEN', 'EARLY_ENGAGEMENT', 'FUTURE'].includes(state))
    )
      return false
    switch (f.view) {
      case 'live':
        if (!isLive(s, now)) return false
        break
      case 'closing':
        if (!isLive(s, now) || daysLeft(s, now) === null || daysLeft(s, now)! > 7) return false
        break
      case 'early':
      case 'pipeline':
        if (!['EARLY_ENGAGEMENT', 'FUTURE'].includes(state)) return false
        break
      case 'frameworks':
        if (s.signal_type !== 'FRAMEWORK') return false
        break
      case 'funding':
        if (!['FUNDING', 'PARTNERSHIP'].includes(s.signal_type)) return false
        break
      case 'saved':
        if (!saved.includes(s.id)) return false
        break
      case 'today':
        if (!isAddedToday(s, now)) return false
        break
    }
    if (!search(s, translations[s.id]).matched) return false
    if (f.source && !s.provenance.some((p) => p.source === f.source)) return false
    if (f.type && s.signal_type !== f.type) return false
    if (f.capability && !s.matched_capabilities.includes(f.capability)) return false
    if (f.sector && !s.categories.includes(f.sector)) return false
    if (
      f.buyer &&
      !searchText([s.buyer_name, translatedBuyer(s, translations[s.id])].join(' ')).includes(
        searchText(f.buyer),
      )
    )
      return false
    if (f.region && !s.regions.some((r) => r.toLowerCase().includes(f.region.toLowerCase())))
      return false
    if (f.cpv && !s.cpv_codes.some((c) => c.startsWith(f.cpv))) return false
    if (f.minValue && (s.value_max === null || s.value_max < Number(f.minValue))) return false
    if (f.maxValue && (s.value_max === null || s.value_max > Number(f.maxValue))) return false
    if (
      f.deadline &&
      (!responseDeadline(s, now) ||
        daysLeft(s, now)! <= 0 ||
        daysLeft(s, now)! > Number(f.deadline))
    )
      return false
    if (f.currency && s.currency !== f.currency) return false
    if (f.amountType && s.amount?.kind !== f.amountType) return false
    if (
      f.supplier &&
      !searchText(
        [s.incumbent_supplier, ...(s.winners || []).map((w) => w.name)].join(' '),
      ).includes(searchText(f.supplier))
    )
      return false
    if (f.awardFrom && (!s.award_date || s.award_date.slice(0, 10) < f.awardFrom)) return false
    if (f.awardTo && (!s.award_date || s.award_date.slice(0, 10) > f.awardTo)) return false
    if (f.change === 'new' && !isNew(s, now)) return false
    if (f.change === 'updated' && !isUpdated(s, now)) return false
    return true
  })
  const capabilityNames = new Map(capabilities.map((c) => [c.id, c.label]))
  const capabilityKey = (s: Signal) =>
    [...new Set(s.matched_capabilities.map((id) => capabilityNames.get(id) || id))]
      .sort((a, b) => a.localeCompare(b, 'en-GB'))
      .join('\u0000')
  const capabilityKeys =
    f.sort === 'capability' ? new Map(result.map((s) => [s.id, capabilityKey(s)])) : null
  return result.sort((a, b) => {
    if (f.view === 'awards')
      return (
        priorityTier(a) - priorityTier(b) ||
        Date.parse(b.award_date || b.updated_at || b.published_at || b.first_seen_at) -
          Date.parse(a.award_date || a.updated_at || a.published_at || a.first_seen_at) ||
        a.id.localeCompare(b.id)
      )
    // An explicit value/capability sort takes precedence over the default delivery tiers.
    if (f.sort === 'value' || f.sort === 'value-low') {
      if (a.value_max === null) return b.value_max === null ? compareRecommended(a, b, now) : 1
      if (b.value_max === null) return -1
      return (
        (f.sort === 'value' ? b.value_max - a.value_max : a.value_max - b.value_max) ||
        compareRecommended(a, b, now)
      )
    }
    if (capabilityKeys) {
      const first = capabilityKeys.get(a.id) || ''
      const second = capabilityKeys.get(b.id) || ''
      if (!first || !second) return first ? -1 : second ? 1 : compareRecommended(a, b, now)
      return first.localeCompare(second, 'en-GB') || compareRecommended(a, b, now)
    }
    const priority = priorityTier(a) - priorityTier(b)
    if (priority) return priority
    switch (f.sort) {
      case 'recent':
        return (
          Date.parse(b.published_at || b.first_seen_at) -
          Date.parse(a.published_at || a.first_seen_at)
        )
      case 'updated':
        return (
          Date.parse(b.last_material_update || b.first_seen_at) -
          Date.parse(a.last_material_update || a.first_seen_at)
        )
      case 'deadline':
        return (
          (responseDeadline(a, now) ? Date.parse(responseDeadline(a, now)!) : Infinity) -
          (responseDeadline(b, now) ? Date.parse(responseDeadline(b, now)!) : Infinity)
        )
      default:
        return compareRecommended(a, b, now)
    }
  })
}
export function compareRecommended(a: Signal, b: Signal, now = Date.now()) {
  void now
  return (
    priorityTier(a) - priorityTier(b) ||
    Date.parse(b.published_at || b.first_seen_at) - Date.parse(a.published_at || a.first_seen_at) ||
    a.id.localeCompare(b.id)
  )
}
export function safeURL(value: string) {
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password
      ? value
      : '#'
  } catch {
    return '#'
  }
}
function recordShareText(
  signal: Signal,
  appURL: string,
  text = { title: signal.title, buyerName: signal.buyer_name },
) {
  const recordURL = new URL(appURL)
  recordURL.search = ''
  recordURL.hash = ''
  recordURL.searchParams.set('view', hasAwardOutcome(signal) ? 'awards' : 'all')
  recordURL.searchParams.set(
    'market',
    markets.find((market) => matchesMarket(signal, market.id))?.id || '',
  )
  recordURL.searchParams.set('signal', signal.id)
  const deadline = responseDeadline(signal)
  const sourceURL = safeURL(signal.primary_source_url)
  const financial = amountPresentation(signal, false)
  return [
    text.title,
    '',
    `Buyer: ${text.buyerName || 'Not published'}`,
    `Notice type: ${typeLabels[signal.signal_type] || signal.signal_type}`,
    `${signal.amount ? financial.label : 'Value'}: ${financial.value}`,
    hasAwardOutcome(signal)
      ? `Awarded: ${signal.award_date ? date(signal.award_date) : 'Date not published'}`
      : `Deadline: ${
          deadline
            ? date(deadline, {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
                timeZone: 'UTC',
                ...(/^\d{4}-\d{2}-\d{2}$/.test(deadline)
                  ? {}
                  : { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }),
              })
            : 'Not published'
        }`,
    '',
    `View in Anthrion Signal: ${recordURL.href}`,
    ...(sourceURL === '#' ? [] : [`Source notice: ${sourceURL}`]),
  ].join('\n')
}
export function gmailDraftURL(
  signal: Signal,
  appURL: string,
  text = { title: signal.title, buyerName: signal.buyer_name },
) {
  const gmailURL = new URL('https://mail.google.com/mail/')
  gmailURL.search = new URLSearchParams({
    view: 'cm',
    fs: '1',
    su: `Anthrion Signal: ${text.title}`,
    body: recordShareText(signal, appURL, text),
  }).toString()
  return gmailURL.href
}
export function googleCalendarURL(
  signal: Signal,
  appURL: string,
  text = { title: signal.title, buyerName: signal.buyer_name },
) {
  if (isAwardIntelligence(signal)) return null
  const deadline = responseDeadline(signal)
  if (!deadline || !Number.isFinite(Date.parse(deadline))) return null
  const start = new Date(deadline)
  const allDay = /^\d{4}-\d{2}-\d{2}$/.test(deadline)
  if (allDay && start.toISOString().slice(0, 10) !== deadline) return null
  if (!allDay && !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(deadline)) return null
  const end = new Date(start.getTime() + (allDay ? 86400000 : 15 * 60000))
  const format = (value: Date) =>
    allDay
      ? value.toISOString().slice(0, 10).replaceAll('-', '')
      : value
          .toISOString()
          .replace(/[-:]/g, '')
          .replace(/\.\d{3}/, '')
  const url = new URL('https://calendar.google.com/calendar/r/eventedit')
  url.search = new URLSearchParams({
    action: 'TEMPLATE',
    text: `Deadline for tender: ${text.title}`,
    dates: `${format(start)}/${format(end)}`,
    details: recordShareText(signal, appURL, text),
  }).toString()
  return url.href
}
export function csv(signals: Signal[]) {
  const escape = (value: unknown) =>
    '"' +
    String(value ?? '')
      .replace(/^[\s\x00-\x1f]*[=+@\-\t\r]/, "'$&")
      .replace(/"/g, '""') +
    '"'
  return [
    [
      'Title',
      'Buyer',
      'Type',
      'Lifecycle',
      'Value',
      'Currency',
      'Deadline',
      'Source URL',
      'Amount type',
      'Minimum value',
      'Amount source label',
      'Award date',
    ],
    ...signals.map((s) => [
      s.title,
      s.buyer_name,
      typeLabels[s.signal_type],
      lifecycleLabels[lifecycleState(s)],
      s.value_max,
      s.currency,
      responseDeadline(s),
      s.primary_source_url,
      s.amount?.kind || 'unknown',
      s.amount?.minimum ?? s.value_min,
      s.amount?.source_label || '',
      s.award_date || '',
    ]),
  ]
    .map((row) => row.map(escape).join(','))
    .join('\r\n')
}
export function download(name: string, body: string, mime: string) {
  const url = URL.createObjectURL(new Blob([body], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
