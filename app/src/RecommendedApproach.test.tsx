import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { RecommendedApproach } from './RecommendedApproach'
import { TranslationProvider } from './Translation'
import type { DisplayLanguage, Signal } from './types'

const signal = {
  title: 'Case management implementation',
  countries: ['GB'],
  status: 'active',
  signal_type: 'LIVE_TENDER',
  lifecycle_state: 'OPEN',
  deadline_at: null,
  response_deadlines: [],
  reviewed_guidance: {
    source_hash: 'source',
    approach: [{ text: 'Build the published case workflow.', lot_id: 'LOT-0002' }],
    problems: [],
    complexity: 6,
    problem_level: 1,
  },
} as unknown as Signal

function render(record = signal, language: DisplayLanguage = 'en') {
  return renderToStaticMarkup(
    <TranslationProvider language={language} translations={{}}>
      <RecommendedApproach signal={record} />
    </TranslationProvider>,
  )
}

test('guidance shows relevant lots and only real problems, keeping ratings out of the interface', () => {
  const html = renderToStaticMarkup(<RecommendedApproach signal={signal} />)
  expect(html).toContain('Recommended approach:')
  expect(html).toContain('Lot 0002:')
  expect(html).not.toContain('Problems:')
  expect(html).not.toMatch(/complexity|problem_level/)
  const changed = {
    ...signal,
    reviewed_guidance: {
      ...signal.reviewed_guidance!,
      problems: [{ text: 'Migration includes 10 million legacy rows.' }],
    },
  }
  expect(renderToStaticMarkup(<RecommendedApproach signal={changed} />)).toContain('Problems:')
})

test('historical, unavailable, excluded, unsupported and unreviewed records do not acquire recommendations', () => {
  for (const changed of [
    { signal_type: 'AWARD', lifecycle_state: 'AWARDED' },
    { status: 'cancelled', lifecycle_state: 'CANCELLED' },
    { deadline_at: '2020-01-01T00:00:00Z' },
    { exclusion_reasons: ['Reviewed unrelated scope'] },
    { countries: ['FR'] },
    { countries: [] },
    { reviewed_guidance: undefined },
  ]) {
    expect(
      renderToStaticMarkup(<RecommendedApproach signal={{ ...signal, ...changed } as Signal} />),
    ).toBe('')
  }
})

test.each(['GB', 'US', 'CA', 'DE', 'AT', 'CH'])(
  'current %s records can show reviewed guidance',
  (country) => {
    expect(render({ ...signal, countries: [country] })).toContain(
      'Build the published case workflow.',
    )
  },
)

const german = {
  ...signal,
  countries: ['DE'],
  source_language: 'und',
  reviewed_guidance: {
    ...signal.reviewed_guidance!,
    original_language: 'de',
    problems: [{ text: 'The source requires a named certification.', lot_id: 'LOT-0002' }],
    localized: {
      de: {
        approach: [
          {
            text: 'Die veröffentlichten Fallprozesse mit Salesforce umsetzen.',
            lot_id: 'LOT-0002',
          },
        ],
        problems: [
          { text: 'Die Ausschreibung verlangt eine benannte Zertifizierung.', lot_id: 'LOT-0002' },
        ],
      },
    },
  },
}

test('Original uses reviewed language metadata for unknown source language and switches both sections together', () => {
  const before = JSON.stringify(german)
  const english = render(german)
  expect(english).toContain('Build the published case workflow.')
  expect(english).toContain('The source requires a named certification.')
  expect(english).not.toContain('Die veröffentlichten')
  const original = render(german, 'original')
  expect(original).toContain('Die veröffentlichten Fallprozesse')
  expect(original).toContain('Die Ausschreibung verlangt')
  expect(original).toContain('lang="de"')
  expect(original).toContain('Lot 0002:')
  expect(original).not.toContain('Build the published')
  expect(original).not.toContain('The source requires')
  expect(original).not.toMatch(/complexity|problem_level/)
  expect(JSON.stringify(german)).toBe(before)
})

test.each(['de', 'deu', 'ger', 'de-DE', 'DE_at'])(
  'Original resolves known source-language alias %s when reviewed metadata is absent',
  (source_language) => {
    const record = {
      ...german,
      source_language,
      reviewed_guidance: { ...german.reviewed_guidance, original_language: undefined },
    }
    expect(render(record, 'original')).toContain('Die veröffentlichten Fallprozesse')
  },
)

test.each([
  ['CA', 'fra', 'fr', 'Configurer les processus de dossier avec Salesforce.'],
  ['CH', 'ita', 'it', 'Configurare i processi di gestione dei casi con Salesforce.'],
])(
  'Original supports %s source-language content without a translation request',
  (country, source_language, code, text) => {
    const record = {
      ...signal,
      countries: [country],
      source_language,
      reviewed_guidance: {
        ...signal.reviewed_guidance!,
        localized: { [code]: { approach: [{ text, lot_id: 'LOT-0002' }], problems: [] } },
      },
    }
    expect(render(record, 'original')).toContain(text)
    expect(render(record, 'en')).toContain('Build the published case workflow.')
  },
)

test('missing, unbound or misaligned localization falls back to the full English guidance', () => {
  const localized = german.reviewed_guidance.localized.de
  const cases: NonNullable<Signal['reviewed_guidance']>[] = [
    { ...german.reviewed_guidance, localized: {} },
    { ...german.reviewed_guidance, original_language: undefined },
    { ...german.reviewed_guidance, original_language: 'en' },
    { ...german.reviewed_guidance, localized: { fr: localized } },
    { ...german.reviewed_guidance, localized: { de: { ...localized, approach: [] } } },
    { ...german.reviewed_guidance, localized: { de: { ...localized, problems: [] } } },
    {
      ...german.reviewed_guidance,
      localized: {
        de: { ...localized, approach: [{ ...localized.approach[0], lot_id: 'LOT-0003' }] },
      },
    },
  ]
  for (const guidance of cases) {
    const html = render({ ...german, reviewed_guidance: guidance }, 'original')
    expect(html).toContain('Build the published case workflow.')
    expect(html).toContain('The source requires a named certification.')
    expect(html).not.toContain('Die veröffentlichten')
  }
})
