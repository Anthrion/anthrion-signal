import type { Dataset } from '../../src/types'
import { recordDataset } from './record'

/** Small source-shaped data for interactions; @data tests use the actual export. */
export function datasetFixture(): Dataset {
  const now = new Date().toISOString()
  const metadata: Dataset = {
    schema_version: '2.0',
    generated_at: now,
    data_updated_at: now,
    profile_version: 'fixture',
    scoring_version: 'fixture',
    signals: [],
    translations: {},
    evidence_catalog: {},
    sources: [
      {
        id: 'find_a_tender',
        name: 'Find a Tender',
        enabled: true,
        status: 'healthy',
        website: 'https://example.com',
        last_attempt: now,
        last_success: now,
        records: 50,
        message: null,
      },
      {
        id: 'usaspending',
        name: 'USAspending',
        enabled: false,
        status: 'disabled',
        website: 'https://example.com',
        last_attempt: null,
        last_success: null,
        records: 0,
        message: null,
      },
    ],
    capabilities: [
      { id: 'salesforce', label: 'Salesforce platform', family: 'CRM & platforms' },
      { id: 'crm', label: 'CRM & customer platforms', family: 'CRM & platforms' },
      { id: 'service', label: 'Case management & service', family: 'Service transformation' },
      { id: 'portals', label: 'Portals & self-service', family: 'CRM & platforms' },
      { id: 'analytics', label: 'Analytics & insight', family: 'Data & intelligence' },
      { id: 'ai', label: 'AI agents & assistants', family: 'Data & intelligence' },
    ],
    markets: {},
    run: {
      sources_attempted: 1,
      sources_succeeded: 1,
      raw_records: 50,
      new_signals: 50,
      material_updates: 0,
    },
  }
  const seed = recordDataset(metadata).signals[0]
  const countries = [
    'GB',
    'US',
    'IT',
    'DE',
    'AT',
    'CH',
    'SE',
    'FI',
    'DK',
    'NO',
    'IS',
    'ES',
    'GR',
    'BE',
    'NL',
    'LU',
    'FR',
  ]
  const signals = countries.flatMap((country) =>
    Array.from({ length: country === 'GB' ? 32 : 2 }, (_, i) => ({
      ...seed,
      id: `sample-${country}-${i}`,
      title:
        i === 0
          ? `CRM implementation and customer service platform for ${country}`
          : i === 1
            ? 'Customer services platform, integration, migration and implementation across multiple public service departments with reporting, accessible self-service and ongoing operational support'
            : `Customer platform implementation ${country} ${i}`,
      description: `${seed.description}\n\nCRM implementation, integration and reporting.`,
      buyer_name: `Example authority ${country} ${i % 3}`,
      countries: [country],
      signal_type: 'LIVE_TENDER' as const,
      framework: null,
      matched_capabilities: ['crm', 'service'],
      published_at: new Date(Date.now() - i * 3600000).toISOString(),
      first_seen_at: now,
      last_seen_at: now,
      last_material_update: now,
      deadline_at: '2099-01-01T12:00:00Z',
      response_deadlines: [],
      deadlines: [],
      value_min: null,
      value_max: i % 2 ? 100000 + i * 1000 : null,
      currency: country === 'US' ? 'USD' : country === 'GB' ? 'GBP' : 'EUR',
      primary_source_url: `https://example.com/notices/${country}/${i}`,
      source_urls: [`https://example.com/notices/${country}/${i}`],
    })),
  )
  return {
    ...metadata,
    markets: Object.fromEntries(countries.map((code) => [code, { name: code, enabled: true }])),
    signals,
  }
}
