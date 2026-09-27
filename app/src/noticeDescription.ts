import type { Signal } from './types'

const ocdsSources = new Set(['find_tender', 'contracts_finder', 'scotland', 'wales', 'germany'])
const digitalHeader =
  /^Beta This is a new service \S your feedback will help us to improve it\. Home Digital Outcomes opportunities Procurement details\s+/
const digitalFooter =
  /\s+Help You can contact us by email, phone or using the enquiry form \(opens in a new tab\) \. Email: info@(gca|crowncommercial)\.gov\.uk Telephone: 0345 410 2222 (GCA|CCS) customer services team is available Monday to Friday, 9am to 5pm\.$/

// Presentation only: canonical source text remains the evidence for reviews,
// translations, change detection and search. Never repair text with a broad
// replacement of "None", "Help", or a buyer's substantive search criteria.
export function noticeDescription(signal: Pick<Signal, 'source' | 'lots'>, text: string) {
  if (signal.source === 'digital_outcomes' && digitalHeader.test(text)) {
    return text.replace(digitalHeader, '').replace(digitalFooter, '')
  }
  if (!ocdsSources.has(signal.source) || !signal.lots?.length) return text

  // The old OCDS normaliser appended every lot, including null and empty fields.
  // Remove a suffix only when ALL its parts match the structured source facts.
  // Truncated, translated or subsequently combined text falls back unchanged.
  let body = text
  const cleaned: string[] = []
  for (const lot of [...signal.lots].reverse()) {
    const titles = lot.title ? [lot.title] : ['', 'None']
    const descriptions = lot.description ? [lot.description] : ['', 'None']
    const candidates = titles.flatMap((title) =>
      descriptions.map((description) =>
        `Lot ${lot.id}: ${title}. ${description}`.replace(/\s+/g, ' ').trim(),
      ),
    )
    const suffix = candidates.find((value) => body === value || body.endsWith(` ${value}`))
    if (!suffix) return text
    body = body.slice(0, -suffix.length).trimEnd()
    if (lot.title || lot.description) {
      cleaned.unshift(`Lot ${lot.id}: ${[lot.title, lot.description].filter(Boolean).join('. ')}`)
    }
  }
  // With no buyer prose or meaningful lot text, keep the available source text.
  return [body, ...cleaned].filter(Boolean).join(' ') || text
}
