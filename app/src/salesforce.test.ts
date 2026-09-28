import { describe, expect, test } from 'vitest'
import { datasetFixture } from '../tests/fixtures/dataset'
import { salesforcePrefill, salesforceSandboxConfig } from './salesforce'
import type { Signal } from './types'

const now = Date.parse('2026-09-24T12:00:00Z')
const config = salesforceSandboxConfig(
  'https://example--test.sandbox.lightning.force.com',
  '012000000000001AAA',
)!
const base = {
  ...datasetFixture().signals[0],
  id: 'sig_1234567890abcdef1234',
  countries: ['GB'],
  deadline_at: '2026-12-01T12:00:00+01:00',
}
const make = (overrides: Partial<Signal> = {}) => ({ ...base, ...overrides })
const draft = (s: Signal) => salesforcePrefill(s, config, s, 'en', now)
const decode = (href: string) =>
  Object.fromEntries(
    new URL(href).searchParams
      .get('defaultFieldValues')!
      .split(',')
      .map((pair) => {
        const index = pair.indexOf('=')
        return [pair.slice(0, index), decodeURIComponent(pair.slice(index + 1))]
      }),
  )

describe('Salesforce sandbox prefill', () => {
  test('uses the tender record type, source and separate stable identity value without inventing financial facts', () => {
    const record = make({
      buyer_name: 'Example Council',
      value_max: 123456.78,
      currency: 'GBP',
      amount: {
        kind: 'framework_ceiling',
        maximum: 123456.78,
        currency: 'GBP',
        source_label: 'Ceiling',
        source_url: 'https://example.com',
      },
    })
    const result = draft(record)!
    expect(new URL(result.href).searchParams.get('recordTypeId')).toBe(config.recordTypeId)
    expect(result.fields).toMatchObject({
      FirstName: 'AI tender',
      LastName: `Example Council · ${record.id}`,
      Company: 'Example Council',
      LeadSource: 'Anthrion Signal',
      Status: 'New',
      Market__c: 'UKI',
      CurrencyIsoCode: 'GBP',
      Industry__c: 'Technology',
      Sector__c: 'Software and Services',
      Anthrion_Signal_ID__c: record.id,
    })
    expect(result.fields).not.toHaveProperty('AnnualRevenue')
    expect(result.fields).not.toHaveProperty('Country')
    expect(result.fields.Description).toContain('Framework ceiling: 123,456.78 GBP')
    expect(result.fields.Lead_Name__c).toContain('Ceiling £123456.78')
    expect(result.fields.Description.indexOf('Framework ceiling:')).toBeLessThan(
      result.fields.Description.indexOf('Notice type:'),
    )
    expect(result.fields.Description).toContain('2026-12-01T12:00:00+01:00')
    expect(new URL(result.fields.Anthrion_Signal_URL__c).searchParams.get('signal')).toBe(record.id)
    expect(result.fields).not.toHaveProperty('RecordTypeId')
  })
  test('round trips multilingual punctuation, embedded parameter-like content and line breaks', () => {
    const record = make({
      title: 'München, Québec & = 100% + # portal',
      description: 'Line one\nCompany=Other,LeadSource=Override & # % \uD800',
      buyer_name: 'R&D, "Civic"',
    })
    const result = draft(record)!
    expect(decode(result.href)).toEqual({
      ...result.fields,
      Description: result.fields.Description.replace('\uD800', '\uFFFD'),
    })
    expect(decode(result.href).LeadSource).toBe('Anthrion Signal')
  })
  test('bounds Salesforce names, keeps the ID only in its field and contact fallback, and retains full facts', () => {
    const record = make({
      buyer_name: 'Long buyer '.repeat(40),
      title: '😀Technical title '.repeat(40),
    })
    const result = draft(record)!
    for (const key of ['LastName', 'Lead_Name__c']) {
      expect(result.fields[key].length).toBeLessThanOrEqual(80)
    }
    expect(result.fields.LastName.endsWith(record.id)).toBe(true)
    expect(result.fields.Lead_Name__c).not.toContain(record.id)
    expect(result.fields.Lead_Name__c).toContain('Long buyer')
    expect(result.fields.Title.length).toBeLessThanOrEqual(128)
    expect(result.fields.Company.length).toBeLessThanOrEqual(255)
    expect(result.fields.Description).toContain(record.title)
    expect(result.fields.Description).toContain(record.buyer_name)
  })
  test('uses the project, actual amount and buyer in Lead Name, retaining unknowns and ranges faithfully', () => {
    const record = make({
      title: 'Workflow management system',
      buyer_name: 'WM5G LIMITED',
      value_min: null,
      value_max: 450000,
      currency: 'USD',
    })
    expect(draft(record)!.fields).toMatchObject({
      Lead_Name__c: 'Workflow management system, $450000, WM5G LIMITED',
      Title: 'Workflow management system',
    })
    expect(
      draft(
        make({
          title: 'CRM',
          buyer_name: 'Council',
          value_min: 0,
          value_max: 250000,
          currency: 'GBP',
        }),
      )!.fields.Lead_Name__c,
    ).toBe('CRM, £0–£250000, Council')
    expect(
      draft(make({ title: 'CRM', buyer_name: 'Council', value_min: null, value_max: null }))!.fields
        .Lead_Name__c,
    ).toBe('CRM, Value not published, Council')
    expect(
      draft(make({ title: 'CRM', buyer_name: 'Council', value_max: 250000, currency: null }))!
        .fields.Lead_Name__c,
    ).toContain('currency unknown')
  })
  test('keeps lifecycle visibility in the site, while validating draft identity and full detail', () => {
    for (const overrides of [
      { signal_type: 'AWARD' },
      { status: 'awarded' },
      { status: 'withdrawn' },
      { status: 'cancelled' },
      { deadline_at: '2026-01-01' },
    ])
      expect(draft(make(overrides))).not.toBeNull()
    expect(draft(make({ is_summary: true }))).toBeNull()
    expect(draft(make({ id: 'bad,OwnerId=attacker' }))).toBeNull()
  })
  test('accepts only sandbox Lightning origins and valid Lead record types', () => {
    for (const origin of [
      'https://example.lightning.force.com',
      'https://example--test.sandbox.lightning.force.com.evil.test',
      'https://u:p@example--test.sandbox.lightning.force.com',
      'http://example--test.sandbox.lightning.force.com',
      'https://example--test.sandbox.lightning.force.com/path',
    ])
      expect(salesforceSandboxConfig(origin, config.recordTypeId)).toBeNull()
    expect(salesforceSandboxConfig(config.origin, 'invalid')).toBeNull()
    expect(salesforcePrefill(make(), null)).toBeNull()
  })
  test('preserves a single published contact name without guessing cultural name structure; ambiguous contacts stay in the brief', () => {
    const contact = {
      name: 'María del Carmen García',
      email: 'procurement@example.org',
      role: 'Procurement officer',
      source_url: 'https://example.org',
    }
    expect(draft(make({ contacts: [contact] }))!.fields).toMatchObject({
      FirstName: '',
      LastName: contact.name,
      Email: contact.email,
      Title: base.title,
    })
    const multiple = draft(
      make({ contacts: [contact, { ...contact, name: 'Another person' }] }),
    )!.fields
    expect(multiple.FirstName).toBe('AI tender')
    expect(multiple).not.toHaveProperty('Email')
    expect(multiple.Description).toContain('Another person')
    expect(multiple.Description).toContain(contact.role)
  })
  test('does not invent source URLs, company headquarters or currency conversions', () => {
    const result = draft(
      make({
        countries: ['CA'],
        currency: 'CAD',
        primary_source_url: 'javascript:alert(1)',
        value_max: 100000,
      }),
    )!.fields
    expect(result.Market__c).toBe('New Markets')
    expect(result.CurrencyIsoCode).toBe('USD')
    expect(result).not.toHaveProperty('Tender_Currency__c')
    expect(result).not.toHaveProperty('Procurement_Publication__c')
    expect(result).not.toHaveProperty('Company_HQ_Country__c')
    expect(result.Description).toContain('100,000 CAD')
    expect(result.Description).toContain('Published CAD amounts have not been converted.')
    expect(result.Lead_Name__c).toContain('CA$100000')
    for (const currency of ['GBP', 'EUR', 'SEK', 'USD']) {
      const fields = draft(make({ currency }))!.fields
      expect(fields.CurrencyIsoCode).toBe(currency)
      expect(fields).not.toHaveProperty('Tender_Currency__c')
    }
    expect(draft(make({ currency: null }))!.fields.CurrencyIsoCode).toBe('USD')
    expect(draft(make({ countries: ['GB', 'DE'] }))!.fields).not.toHaveProperty('Market__c')
    expect(draft(make({ countries: ['SE'] }))!.fields.Market__c).toBe('NORD')
    expect(draft(make({ currency: null }))!.fields).not.toHaveProperty('Tender_Currency__c')
  })
  test('reuses Original guidance and the displayed translation, preserving lots and problems', () => {
    const reviewed_guidance = {
      source_hash: 'hash',
      complexity: 4,
      problem_level: 2,
      original_language: 'de',
      approach: [{ text: 'Use Service Cloud.', lot_id: 'LOT-0001' }],
      problems: [{ text: 'Third-party ownership.' }],
      localized: {
        de: {
          approach: [{ text: 'Service Cloud einsetzen.', lot_id: 'LOT-0001' }],
          problems: [{ text: 'Rechte Dritter.' }],
        },
      },
    }
    const record = make({ countries: ['DE'], source_language: 'de', reviewed_guidance })
    const result = salesforcePrefill(
      record,
      config,
      { title: 'Deutscher Titel', description: 'Beschreibung' },
      'original',
      now,
    )!
    expect(result.fields.Technology__c).toBe(
      'Recommended approach:\nLot 0001: Service Cloud einsetzen.',
    )
    expect(result.fields.Description).toContain('Rechte Dritter.')
    expect(result.fields.Description).toContain('Deutscher Titel')
    expect(draft(record)!.fields.Technology__c).toContain('Use Service Cloud.')
  })
  test('keeps date-only precision and labels text excerpts; never silently cuts guidance', () => {
    const result = draft(
      make({
        description: 'Beschreibung '.repeat(3000),
        deadlines: [
          {
            kind: 'tender',
            date: '2026-12-02',
            precision: 'date',
            status: 'current',
            source_url: 'https://example.org',
            source_text: 'Tenders due 2 December 2026',
          },
        ],
      }),
    )!
    expect(result.fields.Description).toContain('Cutoff time not published')
    expect(result.fields.Description).toContain('[Excerpt; full text in Anthrion Signal.]')
    expect(result.href.length).toBeLessThanOrEqual(14000)
    const record = make({
      reviewed_guidance: {
        source_hash: 'hash',
        complexity: 4,
        problem_level: 1,
        approach: [{ text: '中'.repeat(10000) }],
        problems: [],
      },
    })
    expect(draft(record)).toBeNull()
  })
})
