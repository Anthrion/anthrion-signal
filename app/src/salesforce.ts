import type { DisplayLanguage, Signal } from './types'
import {
  amountLabels,
  countryLabels,
  responseDeadline,
  safeURL,
  selectedResponseDeadlineEvent,
  typeLabels,
} from './lib'
import { deadlinePresentation } from './publicFacts'
import { selectedGuidance } from './RecommendedApproach'

export interface SalesforceSandboxConfig {
  origin: string
  recordTypeId: string
}
type DisplayText = { title: string; description: string }
const source = 'Anthrion Signal'
const publicApp = 'https://anthrion.github.io/anthrion-signal/'
const activeCurrencies = new Set(['GBP', 'EUR', 'SEK', 'USD'])
// Public routing metadata only. Authentication and saving remain inside Salesforce.
export const salesforceSandbox: SalesforceSandboxConfig = {
  origin: 'https://anthrion--aitender.sandbox.lightning.force.com',
  recordTypeId: '012ag0000009JjNAAU',
}
const marketForCountry: Record<string, string> = {
  GB: 'UKI',
  IE: 'UKI',
  US: 'USA',
  DE: 'DACH',
  AT: 'DACH',
  CH: 'DACH',
  SE: 'NORD',
  FI: 'NORD',
  DK: 'NORD',
  NO: 'NORD',
  IS: 'NORD',
  ES: 'IBERIA',
  PT: 'IBERIA',
  IT: 'ITALIA',
  GR: 'GREECE',
}

export function salesforceSandboxConfig(
  origin?: string,
  recordTypeId?: string,
): SalesforceSandboxConfig | null {
  if (!origin || !recordTypeId || !/^012[a-zA-Z0-9]{12}(?:[a-zA-Z0-9]{3})?$/.test(recordTypeId))
    return null
  try {
    const url = new URL(origin)
    if (
      url.protocol !== 'https:' ||
      !/^[a-z0-9-]+\.sandbox\.lightning\.force\.com$/.test(url.hostname) ||
      url.port ||
      url.username ||
      url.password ||
      url.pathname !== '/' ||
      url.search ||
      url.hash
    )
      return null
    return { origin: url.origin, recordTypeId }
  } catch {
    return null
  }
}

// Bound text conservatively in UTF-16 units without splitting a surrogate pair.
function prefix(value: string, max: number) {
  const part = value.slice(0, max)
  return /[\uD800-\uDBFF]$/.test(part) ? part.slice(0, -1) : part
}
function short(value: string, max: number) {
  return value.length <= max ? value : `${prefix(value, max - 1).trimEnd()}…`
}
function identifiedName(label: string, id: string) {
  const suffix = ` · ${id}`
  return `${short(label, 80 - suffix.length)}${suffix}`
}
function excerpt(value: string, max: number) {
  return value.length <= max
    ? value
    : `${prefix(value, max).trimEnd()}…\n[Excerpt; full text in Anthrion Signal.]`
}
function contractAmount(signal: Signal) {
  const minimum = signal.amount?.minimum ?? signal.value_min
  const maximum = signal.amount?.maximum ?? signal.value_max
  const currency = signal.amount?.currency ?? signal.currency
  const values = [minimum, maximum].filter(
    (value): value is number => typeof value === 'number' && Number.isFinite(value),
  )
  const distinct = [...new Set(values)]
  return `${amountLabels[signal.amount?.kind || 'unknown'] || 'Published amount'}: ${distinct.length ? distinct.map((value) => value.toLocaleString('en-GB', { maximumFractionDigits: 20 })).join('–') + ' ' + (currency || '(currency not published)') : 'Not published'}`
}
function leadName(signal: Signal, title: string) {
  const values = [
    ...new Set(
      [
        signal.amount?.minimum ?? signal.value_min,
        signal.amount?.maximum ?? signal.value_max,
      ].filter((value): value is number => typeof value === 'number' && Number.isFinite(value)),
    ),
  ]
  const currency = signal.amount?.currency ?? signal.currency
  const symbol =
    ({ GBP: '£', EUR: '€', USD: '$', CAD: 'CA$', AUD: 'A$' } as Record<string, string>)[
      currency || ''
    ] || (currency ? `${currency} ` : '')
  const kind = signal.amount?.kind
  const qualifier =
    (
      {
        framework_ceiling: 'Ceiling ',
        grant_range: 'Grant ',
        programme_funding: 'Funding ',
        annual_spend: 'Annual ',
        award: 'Award ',
      } as Record<string, string>
    )[kind || ''] || ''
  const amount = values.length
    ? `${qualifier}${values.map((value) => symbol + value.toLocaleString('en-GB', { useGrouping: false, maximumFractionDigits: 20 })).join('–')}${currency ? '' : ' (currency unknown)'}`
    : 'Value not published'
  // Preserve all three useful parts within the existing unique Text(80) field.
  const price = amount.length <= 40 ? amount : 'Value in description'
  const buyer = signal.buyer_name?.trim() || 'Buyer not published'
  const project = title.trim() || 'Untitled project'
  if (`${project}, ${price}, ${buyer}`.length <= 80) return `${project}, ${price}, ${buyer}`
  const remaining = 80 - price.length - 4
  const buyerLength = Math.min(
    buyer.length,
    Math.max(18, remaining - project.length),
    Math.floor(remaining / 2),
  )
  return `${short(project, remaining - buyerLength)}, ${price}, ${short(buyer, buyerLength)}`
}
function encodeURL(config: SalesforceSandboxConfig, fields: Record<string, string>) {
  const url = new URL('/lightning/o/Lead/new', config.origin)
  url.searchParams.set('recordTypeId', config.recordTypeId)
  const wellFormed = (value: string) =>
    value.replace(
      /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/g,
      '\uFFFD',
    )
  url.searchParams.set(
    'defaultFieldValues',
    Object.entries(fields)
      .map(([key, value]) => `${key}=${encodeURIComponent(wellFormed(value))}`)
      .join(','),
  )
  return url.href
}

/** Creates only a draft URL. Salesforce remains responsible for review, validation and save. */
export function salesforcePrefill(
  signal: Signal,
  config: SalesforceSandboxConfig | null,
  text: DisplayText = signal,
  language: DisplayLanguage = 'en',
  now = Date.now(),
) {
  const checked = config && salesforceSandboxConfig(config.origin, config.recordTypeId)
  if (!checked || signal.is_summary || !/^sig_[a-f0-9]{20}$/.test(signal.id)) return null
  const recordURL = new URL(publicApp)
  recordURL.search = new URLSearchParams({ view: 'all', market: '', signal: signal.id }).toString()
  const fields: Record<string, string> = {
    FirstName: 'AI tender',
    LastName: identifiedName(signal.buyer_name || 'Buyer not published', signal.id),
    Lead_Name__c: leadName(signal, text.title),
    Title: short(text.title, 128),
    Industry__c: 'Technology',
    Sector__c: 'Software and Services',
    LeadSource: source,
    Status: 'New',
    Anthrion_Signal_ID__c: signal.id,
    Anthrion_Signal_URL__c: recordURL.href,
  }
  if (signal.buyer_name) fields.Company = short(signal.buyer_name, 255)
  // Country of performance is not necessarily the buyer's registered address or HQ.
  const mapped = new Set(
    signal.countries.map((country) => marketForCountry[country] || 'New Markets'),
  )
  if (mapped.size === 1) fields.Market__c = [...mapped][0]
  const currency = signal.amount?.currency ?? signal.currency
  if (currency && activeCurrencies.has(currency)) fields.CurrencyIsoCode = currency
  if (currency) fields.Tender_Currency__c = activeCurrencies.has(currency) ? currency : 'Other'
  const noticeURL = safeURL(signal.primary_source_url)
  if (noticeURL !== '#' && noticeURL.length <= 255) fields.Procurement_Publication__c = noticeURL
  const contacts = signal.contacts || []
  if (contacts.length === 1) {
    const contact = contacts[0]
    // The source supplies a full name, not structured given/family names. Preserve it intact.
    if (contact.name?.trim() && contact.name.trim().length <= 80) {
      fields.FirstName = ''
      fields.LastName = contact.name.trim()
    }
    if (
      contact.email &&
      /^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$/.test(contact.email) &&
      contact.email.length <= 80
    )
      fields.Email = contact.email
  }
  const guidance = selectedGuidance(signal, language, now)?.display
  const points = (items: { text: string; lot_id?: string | null }[]) =>
    items
      .map(
        (item) =>
          `${item.lot_id ? `Lot ${item.lot_id.replace(/^LOT[- ]?/i, '')}: ` : ''}${item.text}`,
      )
      .join('\n\n')
  const approach = guidance ? points(guidance.approach) : ''
  const problems = guidance?.problems.length ? points(guidance.problems) : ''
  const event = selectedResponseDeadlineEvent(signal, now)
  const deadline = event ? deadlinePresentation(event) : null
  const deadlineText = deadline
    ? `${deadline.label}: ${deadline.value}${deadline.precision ? ` (${deadline.precision})` : ''}`
    : `Response due: ${responseDeadline(signal, now) || 'Not published'}`
  const facts = [
    text.title,
    ...(text.title !== signal.title ? [`Original title: ${signal.title}`] : []),
    `Buyer: ${signal.buyer_name || 'Not published'}`,
    `Notice country: ${countryLabels(signal) || 'Not published'}`,
    contractAmount(signal),
    `Notice type: ${typeLabels[signal.signal_type] || signal.signal_type}`,
    deadlineText,
    ...(signal.lot_ids.length ? [`Lots: ${signal.lot_ids.join(', ')}`] : []),
    `Signal: ${recordURL.href}`,
    ...(noticeURL !== '#' ? [`Source notice: ${noticeURL}`] : []),
    ...(contacts.length
      ? [
          `Published contacts:\n${contacts.map((c) => [c.name, c.role, c.email].filter(Boolean).join(' · ')).join('\n')}`,
        ]
      : []),
    ...(problems ? [`Problems:\n${problems}`] : []),
  ].join('\n\n')
  // A bounded draft keeps the link usable. All excerpts are labelled and link to the full record.
  for (const budget of [1800, 1200, 600, 250, 0]) {
    fields.Description = `${facts}${text.description && budget ? `\n\nNotice text:\n${excerpt(text.description, budget)}` : text.description ? '\n\nFull notice text is available in Anthrion Signal.' : ''}`
    if (approach) fields.Technology__c = `Recommended approach:\n${approach}`
    const href = encodeURL(checked, fields)
    if (
      href.length <= 14000 &&
      fields.Description.length <= 32000 &&
      (!fields.Technology__c || fields.Technology__c.length <= 32000)
    )
      return { href, fields }
  }
  // Never silently discard the approach, problems or primary facts to squeeze them into a URL.
  return null
}
