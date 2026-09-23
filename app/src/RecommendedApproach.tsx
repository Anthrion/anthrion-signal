import type { Signal } from './types'
import { isAvailableOpportunity } from './lib'
import { useTranslations } from './Translation'

const countries = new Set(['GB', 'US', 'CA', 'DE', 'AT', 'CH'])
const languageAliases: Record<string, string> = {
  eng: 'en',
  deu: 'de',
  ger: 'de',
  fra: 'fr',
  fre: 'fr',
  ita: 'it',
  spa: 'es',
  por: 'pt',
  nld: 'nl',
  dut: 'nl',
  dan: 'da',
  swe: 'sv',
  nor: 'no',
  nob: 'nb',
  nno: 'nn',
  fin: 'fi',
  isl: 'is',
  ice: 'is',
  ell: 'el',
  gre: 'el',
  pol: 'pl',
  ces: 'cs',
  cze: 'cs',
  slk: 'sk',
  slo: 'sk',
  slv: 'sl',
  hrv: 'hr',
  hun: 'hu',
  ron: 'ro',
  rum: 'ro',
  bul: 'bg',
  est: 'et',
  lav: 'lv',
  lit: 'lt',
  gle: 'ga',
  cym: 'cy',
  wel: 'cy',
  gla: 'gd',
  mlt: 'mt',
  ltz: 'lb',
  roh: 'rm',
  cat: 'ca',
  eus: 'eu',
  baq: 'eu',
  sqi: 'sq',
  alb: 'sq',
  mkd: 'mk',
  mac: 'mk',
  bos: 'bs',
  srp: 'sr',
  ukr: 'uk',
  rus: 'ru',
  tur: 'tr',
  ara: 'ar',
  zho: 'zh',
  chi: 'zh',
  jpn: 'ja',
  kor: 'ko',
  hin: 'hi',
  heb: 'he',
}
function languageCode(value?: string | null) {
  const language = value?.trim().toLowerCase().replaceAll('_', '-').split('-')[0] || ''
  return /^[a-z]{2}$/.test(language) ? language : languageAliases[language]
}

type Points = NonNullable<Signal['reviewed_guidance']>['approach']
function aligned(localized: Points, english: Points) {
  return (
    Array.isArray(localized) &&
    localized.length === english.length &&
    localized.every(
      (point, index) =>
        typeof point?.text === 'string' &&
        !!point.text.trim() &&
        (point.lot_id || null) === (english[index].lot_id || null),
    )
  )
}

export function RecommendedApproach({ signal }: { signal: Signal }) {
  const { language } = useTranslations()
  const guidance = signal.reviewed_guidance
  if (
    !guidance ||
    !signal.countries.some((country) => countries.has(country)) ||
    !isAvailableOpportunity(signal)
  )
    return null
  const originalLanguage =
    languageCode(guidance.original_language) || languageCode(signal.source_language)
  const candidate =
    language === 'original' && originalLanguage && originalLanguage !== 'en'
      ? guidance.localized?.[originalLanguage]
      : undefined
  const localized =
    candidate &&
    aligned(candidate.approach, guidance.approach) &&
    aligned(candidate.problems, guidance.problems)
      ? candidate
      : undefined
  const display = localized || guidance
  const paragraphs = (points: Points) =>
    points.map((point, index) => (
      <p key={index} lang={localized ? originalLanguage : 'en'}>
        {point.lot_id && <strong>Lot {point.lot_id.replace(/^LOT[- ]?/i, '')}: </strong>}
        {point.text}
      </p>
    ))
  return (
    <section className="recommended-approach" aria-label="Recommended approach">
      <h3>Recommended approach:</h3>
      {paragraphs(display.approach)}
      {!!display.problems.length && (
        <div className="approach-problems">
          <h3>Problems:</h3>
          {paragraphs(display.problems)}
        </div>
      )}
    </section>
  )
}
