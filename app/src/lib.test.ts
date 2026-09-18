import { describe, expect, test } from 'vitest'
import type { Signal } from './types'
import {
  csv,
  defaults,
  filterSignals,
  isLive,
  safeURL,
  deadlineCaption,
  matchesMarket,
  marketIsEnabled,
  amount,
  currencyOptions,
  matchesSearch,
  lifecycleState,
  isAwardIntelligence,
  isAvailableOpportunity,
  isHistoricalAward,
  isAddedToday,
  normaliseFilters,
  priorityTier,
  responseDeadline,
  displayBuyer,
  gmailDraftURL,
  googleCalendarURL,
} from './lib'
const now = Date.parse('2026-09-09T12:00:00Z')
const signal = {
  id: 'one',
  title: 'Salesforce platform',
  description: 'CRM implementation',
  buyer_name: 'Buyer',
  countries: ['GB'],
  regions: ['Scotland'],
  categories: ['Public services'],
  cpv_codes: ['72200000'],
  provenance: [{ source: 'find_tender' }],
  matched_capabilities: ['salesforce'],
  recommendation: 'PURSUE',
  fit_score: 88,
  confidence_score: 82,
  analysis: {
    version: '2.0',
    summary: 'CRM implementation',
    requirements: [],
    requirements_completeness: 'SUMMARY',
    eligibility_checks: [],
  },
  value_max: 400000,
  currency: 'GBP',
  source_urls: [],
  primary_source_url: 'https://example.gov.uk/notice',
  signal_type: 'LIVE_TENDER',
  procurement_stage: 'tender',
  status: 'active',
  deadline_at: '2026-09-20T12:00:00Z',
  first_seen_at: '2026-09-08T14:00:00Z',
  last_material_update: '2026-09-08T14:00:00Z',
} as unknown as Signal
describe('team workflows', () => {
  test('Google Calendar drafts preserve the deadline instant and selected record, without inviting anyone', () => {
    const record = { ...signal, deadline_at: '2026-09-20T12:00:00+01:00' }
    const title = 'CRM & service / café + €'
    const url = new URL(
      googleCalendarURL(record, 'https://anthrion.github.io/anthrion-signal/?q=other&signal=old', {
        title,
        buyerName: 'Public buyer',
      })!,
    )
    expect(url.origin + url.pathname).toBe('https://calendar.google.com/calendar/r/eventedit')
    expect(url.searchParams.get('text')).toBe(`Deadline for tender: ${title}`)
    expect(url.searchParams.get('dates')).toBe('20260920T110000Z/20260920T111500Z')
    expect(url.searchParams.get('details')).toContain('20 Sept 2026, 11:00 UTC')
    expect(url.searchParams.get('details')).toContain('signal=one')
    expect(url.searchParams.get('details')).toContain(`Source notice: ${record.primary_source_url}`)
    expect(url.searchParams.get('details')).not.toContain('signal=old')
    expect(url.searchParams.has('add')).toBe(false)
  })

  test('date-only deadlines make one all-day entry, while missing or uncertain deadlines have no calendar link', () => {
    const appURL = 'https://anthrion.github.io/anthrion-signal/'
    const url = new URL(googleCalendarURL({ ...signal, deadline_at: '2026-12-31' }, appURL)!)
    expect(url.searchParams.get('dates')).toBe('20261231/20270101')
    expect(url.searchParams.get('details')).toContain('Deadline: 31 Dec 2026\n')
    for (const deadline of [null, 'invalid', '2026-02-30', '2026-09-20T12:00:00']) {
      expect(googleCalendarURL({ ...signal, deadline_at: deadline }, appURL)).toBeNull()
    }
  })

  test('Gmail drafts preserve displayed text and link to the selected record without unrelated filters', () => {
    const record = { ...signal, id: 'nordic & 2', countries: ['FI'] }
    const title = 'CRM & service / Henkilöstö + €'
    const url = new URL(
      gmailDraftURL(
        record,
        'https://anthrion.github.io/anthrion-signal/?q=other&signal=old&view=closing#old',
        { title, buyerName: 'Kunta (Municipality)' },
      ),
    )
    expect(url.origin + url.pathname).toBe('https://mail.google.com/mail/')
    expect(url.searchParams.get('su')).toBe(`Anthrion Signal: ${title}`)
    expect(url.searchParams.has('to')).toBe(false)
    const body = url.searchParams.get('body')!
    expect(body).toContain('Buyer: Kunta (Municipality)')
    expect(body).toContain('Value: £400,000')
    expect(body).toContain('Deadline: 20 Sept 2026')
    expect(body).toContain(`Source notice: ${record.primary_source_url}`)
    const link = new URL(
      body
        .split('\n')
        .find((line) => line.startsWith('View in Anthrion Signal: '))!
        .slice('View in Anthrion Signal: '.length),
    )
    expect(link.origin + link.pathname).toBe('https://anthrion.github.io/anthrion-signal/')
    expect(Object.fromEntries(link.searchParams)).toEqual({
      view: 'all',
      market: 'NORDICS',
      signal: record.id,
    })
    expect(link.hash).toBe('')
    expect(body).not.toContain(record.description)
  })

  test('Gmail drafts retain missing facts without including unsafe source links', () => {
    const url = new URL(
      gmailDraftURL(
        {
          ...signal,
          deadline_at: null,
          value_max: null,
          buyer_name: '',
          primary_source_url: 'javascript:alert(1)',
        },
        'https://anthrion.github.io/anthrion-signal/',
      ),
    )
    const body = url.searchParams.get('body')!
    expect(body).toContain('Buyer: Not published')
    expect(body).toContain('Value: Value not published')
    expect(body).toContain('Deadline: Not published')
    expect(body).not.toContain('Source notice:')
    expect(body).not.toContain('javascript:')
  })

  test('English buyer renderings supplement the exact official name without stale or duplicate aliases', () => {
    const original = { ...signal, buyer_name: 'Stadtverwaltung Berlin' }
    const english = {
      source_hash: 'test',
      version: 'test',
      title: 'Platform',
      description: '',
      buyer_original: original.buyer_name,
      buyer_name: 'Berlin City Administration',
    }
    expect(displayBuyer(original, english)).toBe(
      'Stadtverwaltung Berlin (Berlin City Administration)',
    )
    expect(displayBuyer(original)).toBe(original.buyer_name)
    expect(displayBuyer(original, { ...english, buyer_name: original.buyer_name })).toBe(
      original.buyer_name,
    )
    expect(displayBuyer(original, { ...english, buyer_original: 'Other buyer' })).toBe(
      original.buyer_name,
    )
    expect(matchesSearch(original, 'Berlin City Administration', [], english)).toBe(true)
    expect(
      filterSignals(
        [original],
        { ...defaults, view: 'all', buyer: 'City Administration' },
        [],
        now,
        [],
        { one: english },
      ),
    ).toEqual([original])
  })
  test('direct awards and restricted routes stay unavailable, while a remaining open lot survives', () => {
    expect(isAvailableOpportunity({ ...signal, notice_type: 'veat' }, now)).toBe(false)
    for (const status of ['restricted', 'not_listed', 'unverified'])
      expect(isAvailableOpportunity({ ...signal, status }, now)).toBe(false)
    const lots = {
      ...signal,
      deadline_at: '2025-01-01',
      response_deadlines: ['2025-01-01', '2027-01-01'],
    }
    expect(isAvailableOpportunity(lots, now)).toBe(true)
    expect(responseDeadline(lots, now)).toBe('2027-01-01')
    expect(deadlineCaption(lots, now)).not.toContain('Closed')
  })
  test('Added today uses collection time and the London calendar day, not a rolling day or publication time', () => {
    const now = Date.parse('2026-09-11T23:30:00Z')
    expect(isAddedToday({ ...signal, first_seen_at: '2026-09-11T23:00:00Z' }, now)).toBe(true)
    expect(isAddedToday({ ...signal, first_seen_at: '2026-09-11T22:59:59Z' }, now)).toBe(false)
    expect(isAddedToday({ ...signal, first_seen_at: '2026-09-12T00:00:00Z' }, now)).toBe(false)
    expect(isAddedToday({ ...signal, first_seen_at: 'invalid' }, now)).toBe(false)
    const today = {
      ...signal,
      id: 'newly-collected',
      first_seen_at: '2026-09-11T23:01:00Z',
      published_at: '2026-08-01',
    }
    const updated = {
      ...signal,
      first_seen_at: '2026-09-10',
      published_at: '2026-09-12',
      last_material_update: '2026-09-12',
    }
    expect(
      filterSignals([updated, today], { ...defaults, view: 'today' }, [], now).map((s) => s.id),
    ).toEqual(['newly-collected'])
    expect(
      isAddedToday(
        { ...signal, first_seen_at: '2026-12-10T23:59:00Z' },
        Date.parse('2026-12-11T00:01:00Z'),
      ),
    ).toBe(false)
  })
  test('removed refiner and updates URLs migrate to supported views', () => {
    expect(normaliseFilters({ view: 'updates' }).view).toBe('today')
    expect(normaliseFilters({ view: 'frameworks' })).toMatchObject({
      view: 'all',
      type: 'FRAMEWORK',
    })
    expect(normaliseFilters({ view: 'funding' }).view).toBe('all')
  })
  test('published values sort both ways and ranges work across markets without conversion', () => {
    expect(amount(300, null)).toBe('300 (currency not published)')
    const us = [
      { ...signal, id: 'small', countries: ['US'], value_max: 100, currency: 'USD' },
      { ...signal, id: 'foreign', countries: ['US'], value_max: 100000, currency: 'GBP' },
      { ...signal, id: 'large', countries: ['US'], value_max: 900, currency: 'USD' },
      { ...signal, id: 'unknown', countries: ['US'], value_max: null, currency: 'USD' },
      { ...signal, id: 'zero', countries: ['US'], value_max: 0, currency: 'USD' },
    ]
    const filters = { ...defaults, view: 'all', market: 'US', sort: 'value' }
    expect(filterSignals(us, filters, [], now).map((s) => s.id)).toEqual([
      'foreign',
      'large',
      'small',
      'zero',
      'unknown',
    ])
    expect(filterSignals(us, { ...filters, minValue: '500' }, [], now).map((s) => s.id)).toEqual([
      'foreign',
      'large',
    ])
    expect(filterSignals(us, { ...filters, currency: 'GBP' }, [], now).map((s) => s.id)).toEqual([
      'foreign',
    ])
    expect(filterSignals(us, { ...filters, sort: 'value-low' }, [], now).map((s) => s.id)).toEqual([
      'zero',
      'small',
      'large',
      'foreign',
      'unknown',
    ])
    const range = { ...filters, minValue: '500', maxValue: '1000' }
    expect(filterSignals(us, range, [], now).map((s) => s.id)).toEqual(['large'])
    const nordic = us.map((s) => ({ ...s, countries: ['NO'], currency: 'NOK' }))
    expect(
      filterSignals(nordic, { ...range, market: 'NORDICS' }, [], now).map((s) => s.id),
    ).toEqual(['large'])
    expect(currencyOptions(us).map((option) => option.value)).toEqual(
      expect.arrayContaining(['GBP', 'USD', 'EUR', 'SEK', 'NOK', 'DKK', 'ISK', 'JPY']),
    )
  })
  test('English search never changes source eligibility or priority', () => {
    const source = {
      ...signal,
      title: 'Kundenplattform',
      description: 'Implementierung und Betrieb',
    }
    const translations = {
      [source.id]: {
        title: 'Customer platform',
        description: 'Implementation and operation',
        source_hash: 'fixture',
        version: 'en-procurement-2',
      },
    }
    expect(
      filterSignals([source], { ...defaults, q: 'customer platform' }, [], now, [], translations),
    ).toEqual([source])
    expect(
      filterSignals([source], { ...defaults, q: 'Kundenplattform' }, [], now, [], translations),
    ).toEqual([source])
    expect(
      filterSignals(
        [{ ...source, status: 'awarded' }],
        { ...defaults, q: 'customer platform' },
        [],
        now,
        [],
        translations,
      ),
    ).toEqual([])
  })
  test('market selection scopes each country, all markets and the Nordic region', () => {
    expect(matchesMarket(signal, 'GB')).toBe(true)
    expect(matchesMarket(signal, 'US')).toBe(false)
    expect(matchesMarket(signal, '')).toBe(true)
    const nordic = ['SE', 'FI', 'DK', 'NO', 'IS'].map((country) => ({
      ...signal,
      id: country,
      countries: [country],
    }))
    expect(
      filterSignals([signal, ...nordic], { ...defaults, market: 'NORDICS' }, [], now),
    ).toHaveLength(5)
    expect(filterSignals([signal, ...nordic], { ...defaults, market: 'NO' }, [], now)).toHaveLength(
      1,
    )
    expect(marketIsEnabled('NORDICS', { GB: { enabled: true }, SE: { enabled: false } })).toBe(
      false,
    )
    expect(marketIsEnabled('NORDICS', { FI: { enabled: true } })).toBe(true)
  })
  test('same-day deadlines show hours and already passed deadlines show closed', () => {
    expect(deadlineCaption({ ...signal, deadline_at: '2026-09-09T11:59:00Z' }, now)).toMatch(
      /^Closed/,
    )
    expect(deadlineCaption({ ...signal, deadline_at: '2026-09-09T14:00:00Z' }, now)).toContain(
      '2h left',
    )
  })
  test('expired or cancelled tenders are not live', () => {
    expect(isLive(signal, now)).toBe(true)
    expect(isLive({ ...signal, status: 'cancelled' }, now)).toBe(false)
    expect(isLive({ ...signal, deadline_at: '2026-09-01' }, now)).toBe(false)
    expect(isLive({ ...signal, deadline_at: '2026-09-09T11:59:00Z' }, now)).toBe(false)
  })
  test('postponed notices cannot appear available through a stale placeholder deadline', () => {
    const postponed = { ...signal, status: 'postponed', deadline_at: '2039-09-09T12:00:00Z' }
    expect(isLive(postponed, now)).toBe(false)
    expect(isAvailableOpportunity(postponed, now)).toBe(false)
    expect(filterSignals([postponed], { ...defaults, view: 'all' }, [], now)).toEqual([])
  })
  test('closing this week only includes live, known deadlines in the next seven days', () => {
    const candidates = [
      { ...signal, id: 'today', deadline_at: '2026-09-09T13:00:00Z' },
      { ...signal, id: 'week', deadline_at: '2026-09-16T12:00:00Z' },
      { ...signal, id: 'later', deadline_at: '2026-09-17T12:00:00Z' },
      { ...signal, id: 'unknown', deadline_at: null },
      { ...signal, id: 'closed', deadline_at: '2026-09-09T11:00:00Z' },
      { ...signal, id: 'cancelled', status: 'cancelled', deadline_at: '2026-09-10T12:00:00Z' },
    ]
    expect(
      filterSignals(candidates, { ...defaults, view: 'closing' }, [], now).map((s) => s.id),
    ).toEqual(['today', 'week'])
  })
  test('combines source filters without requiring a model assessment', () => {
    expect(
      filterSignals(
        [signal],
        {
          ...defaults,
          source: 'find_tender',
          score: '82',
          capability: 'salesforce',
          cpv: '722',
          region: 'scot',
          deadline: '14',
        },
        [],
        now,
      ),
    ).toHaveLength(1)
    expect(
      filterSignals([{ ...signal, fit_score: null }], { ...defaults, score: '1' }, [], now),
    ).toHaveLength(1)
    expect(filterSignals([signal], { ...defaults, q: 'unrelated' }, [], now)).toHaveLength(0)
    expect(filterSignals([signal], { ...defaults, view: 'saved' }, ['one'], now)).toHaveLength(1)
  })
  test('CSV neutralises spreadsheet formulas and preserves quotes', () => {
    const result = csv([{ ...signal, title: '=HYPERLINK("bad")' }])
    expect(result).toContain("'=")
    expect(result).toContain('""bad""')
  })
  test('untrusted links cannot execute script', () => {
    expect(safeURL('javascript:alert(1)')).toBe('#')
    expect(safeURL('https://user:password@example.com')).toBe('#')
    expect(safeURL(signal.primary_source_url)).toBe(signal.primary_source_url)
  })
  test('live opportunities do not depend on legacy fit or keyword scores', () => {
    expect(filterSignals([{ ...signal, fit_score: 68 }], defaults, [], now)).toHaveLength(1)
    expect(
      filterSignals([{ ...signal, fit_score: null, prefilter_score: 18 }], defaults, [], now),
    ).toHaveLength(1)
    expect(
      filterSignals([{ ...signal, fit_score: null, prefilter_score: 65 }], defaults, [], now),
    ).toHaveLength(1)
    expect(
      filterSignals(
        [{ ...signal, deadline_at: '2026-09-09T11:59:00Z' }],
        { ...defaults, deadline: '7', view: 'all' },
        [],
        now,
      ),
    ).toHaveLength(0)
  })
  test('unknown, expired engagement and excluded scope cannot enter current views', () => {
    expect(lifecycleState({ ...signal, status: 'unknown', deadline_at: null }, now)).toBe('UNKNOWN')
    expect(
      filterSignals([{ ...signal, status: 'unknown', deadline_at: null }], defaults, [], now),
    ).toHaveLength(0)
    expect(
      filterSignals(
        [{ ...signal, signal_type: 'RFI', deadline_at: '2026-09-08' }],
        { ...defaults, view: 'early' },
        [],
        now,
      ),
    ).toHaveLength(0)
    expect(
      filterSignals(
        [{ ...signal, exclusion_reasons: ['Permanent employee vacancy'] }],
        { ...defaults, view: 'live' },
        [],
        now,
      ),
    ).toHaveLength(0)
    expect(
      filterSignals(
        [{ ...signal, exclusion_reasons: ['Permanent employee vacancy'] }],
        { ...defaults, view: 'saved' },
        ['one'],
        now,
      ),
    ).toHaveLength(0)
  })
  test('search uses source text and multilingual aliases, not old model suggestions', () => {
    const unrelated = {
      ...signal,
      title: 'Annual maintenance',
      description: 'Maintain chairs',
      analysis: null,
    }
    expect(matchesSearch(unrelated, 'AI')).toBe(false)
    expect(matchesSearch({ ...unrelated, title: 'Intégration applicative' }, 'integration')).toBe(
      true,
    )
    expect(
      matchesSearch(
        {
          ...signal,
          analysis: {
            ...signal.analysis!,
            solution_suggestion: 'A MuleSoft API layer could connect the systems.',
          },
        },
        'MuleSoft',
      ),
    ).toBe(false)
    expect(
      matchesSearch(
        {
          ...signal,
          title: 'Kundenplattform',
          description: '',
          analysis: null,
          discovery_families: ['crm'],
        },
        'customer relationship management',
        [
          {
            id: 'crm',
            label: 'CRM',
            family: 'CRM',
            search_terms: ['customer relationship management'],
          },
        ],
      ),
    ).toBe(true)
  })
  test('every refiner keeps CRM and combined CRM/AI before pure AI, with recency inside each group', () => {
    const rows = [
      { ...signal, id: 'ai-new', delivery_priority: 'ai', published_at: '2026-09-09' },
      { ...signal, id: 'crm-old', delivery_priority: 'platform', published_at: '2026-09-02' },
      {
        ...signal,
        id: 'crm-ai',
        delivery_priority: 'platform',
        discovery_families: ['crm', 'ai'],
        published_at: '2026-09-08',
      },
      { ...signal, id: 'other', delivery_priority: 'other', published_at: '2026-09-09' },
      { ...signal, id: 'ai-old', delivery_priority: 'ai', published_at: '2026-09-01' },
    ] as Signal[]
    for (const [view, signalType] of [
      ['all', 'LIVE_TENDER'],
      ['live', 'LIVE_TENDER'],
      ['closing', 'LIVE_TENDER'],
      ['early', 'RFI'],
      ['frameworks', 'FRAMEWORK'],
      ['funding', 'FUNDING'],
      ['saved', 'LIVE_TENDER'],
      ['today', 'LIVE_TENDER'],
    ]) {
      const typed = rows.map((s) => ({
        ...s,
        signal_type: signalType,
        deadline_at: '2026-09-12',
        first_seen_at: '2026-09-09',
      }))
      expect(
        filterSignals(
          typed,
          { ...defaults, view },
          rows.map((s) => s.id),
          now,
        ).map((s) => s.id),
      ).toEqual(['crm-ai', 'crm-old', 'ai-new', 'ai-old', 'other'])
    }
    expect(priorityTier({ ...signal, discovery_families: ['crm', 'ai'] })).toBe(0)
    expect(priorityTier({ ...signal, discovery_families: ['ai'] })).toBe(1)
    expect(
      priorityTier({ ...signal, delivery_priority: 'ai', discovery_families: ['ai', 'analytics'] }),
    ).toBe(1)
  })
  test('deadline retains priority groups but explicit values sort globally', () => {
    const rows = [
      {
        ...signal,
        id: 'ai',
        delivery_priority: 'ai',
        value_max: 900000,
        deadline_at: '2026-09-10',
      },
      {
        ...signal,
        id: 'crm-later',
        delivery_priority: 'platform',
        value_max: 100000,
        deadline_at: '2026-09-15',
      },
      {
        ...signal,
        id: 'crm-soon',
        delivery_priority: 'platform',
        value_max: 500000,
        deadline_at: '2026-09-12',
      },
    ] as Signal[]
    expect(
      filterSignals(rows, { ...defaults, sort: 'deadline' }, [], now).map((s) => s.id),
    ).toEqual(['crm-soon', 'crm-later', 'ai'])
    const withMissing = [...rows, { ...rows[0], id: 'unknown', value_max: null }]
    expect(
      filterSignals(withMissing, { ...defaults, sort: 'value' }, [], now).map((s) => s.id),
    ).toEqual(['ai', 'crm-soon', 'crm-later', 'unknown'])
    expect(
      filterSignals(withMissing, { ...defaults, sort: 'value-low' }, [], now).map((s) => s.id),
    ).toEqual(['crm-later', 'crm-soon', 'ai', 'unknown'])
  })
  test('capability sorting is alphabetical by displayed labels, with untagged records last', () => {
    const rows = [
      { ...signal, id: 'crm', matched_capabilities: ['crm'], delivery_priority: 'platform' },
      { ...signal, id: 'unknown', matched_capabilities: [] },
      { ...signal, id: 'ai', matched_capabilities: ['ai'], delivery_priority: 'ai' },
    ] as Signal[]
    expect(
      filterSignals(rows, { ...defaults, sort: 'capability' }, [], now, [
        { id: 'crm', label: 'CRM & customer platforms', family: 'CRM' },
        { id: 'ai', label: 'AI agents & assistants', family: 'AI' },
      ]).map((s) => s.id),
    ).toEqual(['ai', 'crm', 'unknown'])
  })
  test('old saved views and shared score filters migrate without hiding valid records', () => {
    expect(
      normaliseFilters({
        view: 'top',
        sort: 'fit',
        score: '90',
        confidence: '80',
        recommendation: 'PURSUE',
      }),
    ).toMatchObject({ view: 'all', sort: 'recent', score: '', confidence: '', recommendation: '' })
    expect(normaliseFilters({ view: 'pipeline' }).view).toBe('early')
    expect(normaliseFilters({ type: 'AWARD' }).type).toBe('')
    const header = csv([signal]).split('\n')[0]
    expect(header).not.toMatch(/Fit|Confidence|Recommendation|solution/i)
  })
  test('early and future includes planning signals without inventing a live procurement', () => {
    const rows = [
      { ...signal, id: 'rfi', signal_type: 'RFI' },
      { ...signal, id: 'future', signal_type: 'PIPELINE', procurement_stage: 'planning' },
      signal,
    ]
    expect(filterSignals(rows, { ...defaults, view: 'early' }, [], now).map((s) => s.id)).toEqual([
      'rfi',
      'future',
    ])
    expect(filterSignals(rows, { ...defaults, view: 'live' }, [], now).map((s) => s.id)).toEqual([
      'one',
    ])
  })
  test('recent publication and material update sorts remain distinct', () => {
    const rows = [
      {
        ...signal,
        id: 'published',
        published_at: '2026-09-09',
        last_material_update: '2026-09-07',
      },
      {
        ...signal,
        id: 'updated',
        published_at: '2026-09-01',
        last_material_update: '2026-09-08',
        updated_at: '2026-09-10',
      },
    ]
    expect(filterSignals(rows, { ...defaults, sort: 'recent' }, [], now)[0].id).toBe('published')
    expect(filterSignals(rows, { ...defaults, sort: 'updated' }, [], now)[0].id).toBe('updated')
  })
  test('awards and inferred renewals stay out of opportunity views, including saved and search', () => {
    const excluded = [
      { ...signal, id: 'type', signal_type: 'AWARD' },
      { ...signal, id: 'status', status: 'awarded' },
      { ...signal, id: 'state', lifecycle_state: 'AWARDED' },
      { ...signal, id: 'renewal', signal_type: 'RENEWAL_SIGNAL', related_signal_id: 'type' },
      { ...signal, id: 'inferred', signal_type: 'RENEWAL_SIGNAL', status: 'inferred' },
    ] as Signal[]
    for (const row of excluded) expect(isAwardIntelligence(row)).toBe(true)
    expect(isAwardIntelligence(signal)).toBe(false)
    expect(isAwardIntelligence({ ...signal, signal_type: 'RENEWAL_SIGNAL' })).toBe(false)
    for (const view of [
      'all',
      'top',
      'live',
      'early',
      'closing',
      'pipeline',
      'renewals',
      'frameworks',
      'funding',
      'updates',
    ]) {
      expect(
        filterSignals(
          excluded,
          { ...defaults, view },
          excluded.map((s) => s.id),
          now,
        ),
      ).toEqual([])
    }
    expect(filterSignals(excluded, { ...defaults, view: 'all', q: 'Salesforce' }, [], now)).toEqual(
      [],
    )
    expect(
      filterSignals(excluded, { ...defaults, view: 'awards' }, [], now)
        .map((s) => s.id)
        .sort(),
    ).toEqual(['state', 'status', 'type'])
    expect(
      filterSignals(excluded, { ...defaults, view: 'saved' }, ['type', 'renewal'], now).map(
        (s) => s.id,
      ),
    ).toEqual(['type'])
  })
  test('Awarded uses platform then standalone AI ordering and supports historical search', () => {
    const award = {
      ...signal,
      signal_type: 'AWARD',
      status: 'complete',
      deadline_at: '2020-01-01',
      updated_at: '2026-09-01T12:00:00Z',
    }
    const records: Signal[] = [
      { ...award, id: 'other', delivery_priority: 'other', matched_capabilities: [] },
      {
        ...award,
        id: 'ai',
        delivery_priority: 'ai',
        matched_capabilities: ['ai'],
        updated_at: '2026-09-08T12:00:00Z',
      },
      { ...award, id: 'crm', delivery_priority: 'platform' },
      {
        ...award,
        id: 'new-crm',
        delivery_priority: 'platform',
        updated_at: '2026-09-02T12:00:00Z',
      },
      signal,
    ]
    const filters = { ...defaults, view: 'awards' }
    expect(filterSignals(records, filters, [], now).map((s) => s.id)).toEqual([
      'new-crm',
      'crm',
      'ai',
      'other',
    ])
    expect(filterSignals(records, { ...filters, q: 'missing' }, [], now)).toEqual([])
    expect(
      filterSignals(records, { ...filters, capability: 'ai' }, [], now).map((s) => s.id),
    ).toEqual(['ai'])
    expect(normaliseFilters({ sort: 'awarded', type: 'LIVE_TENDER', deadline: '7' })).toMatchObject(
      { view: 'awards', sort: 'recent', type: '', deadline: '' },
    )
    expect(normaliseFilters({ view: 'awards' }).view).toBe('awards')
    expect(googleCalendarURL(award, 'https://example.org/')).toBe(null)
    expect(
      new URL(gmailDraftURL(award, 'https://example.org/')).searchParams.get('body'),
    ).toContain('view=awards')
  })
  test('uncertain digital call-offs stay reviewable without being presented as live', () => {
    const uncertain = {
      ...signal,
      source: 'digital_outcomes',
      lifecycle_state: 'UNKNOWN',
      deadline_at: null,
    }
    expect(filterSignals([uncertain], { ...defaults, view: 'all' }, [], now)).toEqual([uncertain])
    expect(filterSignals([uncertain], { ...defaults, view: 'live' }, [], now)).toEqual([])
  })
  test('a date-only UK call-off remains live throughout its stated closing day', () => {
    const dated = { ...signal, source: 'digital_outcomes', deadline_at: '2026-09-24' }
    expect(isLive(dated, Date.parse('2026-09-24T21:00:00Z'))).toBe(true)
    expect(isLive(dated, Date.parse('2026-09-24T23:00:00Z'))).toBe(false)
    expect(dated.deadline_at).toBe('2026-09-24')
  })
  test('cancelled, unsuccessful, pending and inferred awards cannot enter history', () => {
    const award = { ...signal, signal_type: 'AWARD' }
    for (const patch of [
      { status: 'cancelled' },
      { status: 'unsuccessful' },
      { status: 'withdrawn' },
      { award_statuses: ['pending'] },
      { award_statuses: ['cancelled'] },
      { signal_type: 'RENEWAL_SIGNAL' },
      { title: 'CANCELLED CRM procurement' },
      { notice_type: 'UK5' },
      { notice_type: 'veat' },
      { exclusion_reasons: ['Physical supplies'] },
    ])
      expect(isHistoricalAward({ ...award, ...patch }, now)).toBe(false)
  })
  test('unavailable records never return through saved, search or other views', () => {
    const blocked = [
      { ...signal, status: 'closed' },
      { ...signal, status: 'cancelled' },
      { ...signal, status: 'withdrawn' },
      { ...signal, deadline_at: '2026-09-08' },
      { ...signal, exclusion_reasons: ['Incompatible scope'] },
      {
        ...signal,
        analysis: { ...signal.analysis!, eligibility_checks: [{ status: 'CONFIRMED_BLOCKER' }] },
      },
    ] as Signal[]
    for (const row of blocked) expect(isAvailableOpportunity(row, now)).toBe(false)
    for (const view of ['all', 'live', 'saved', 'updates', 'top'])
      expect(filterSignals(blocked, { ...defaults, view }, ['one'], now)).toEqual([])
    expect(isAvailableOpportunity({ ...signal, status: 'unknown', deadline_at: null }, now)).toBe(
      true,
    )
    expect(isAvailableOpportunity({ ...signal, signal_type: 'PIPELINE' }, now)).toBe(true)
  })
})

describe('market grouping', () => {
  const inCountry = (country: string) => ({ ...signal, countries: [country] }) as Signal
  test('routes a saved Germany link to the DACH selector', () => {
    expect(normaliseFilters({ market: 'DE' }).market).toBe('DACH')
  })
  test('matches every DACH and Benelux country without crossing between them', () => {
    for (const c of ['DE', 'AT', 'CH']) expect(matchesMarket(inCountry(c), 'DACH')).toBe(true)
    for (const c of ['BE', 'NL', 'LU']) expect(matchesMarket(inCountry(c), 'BENELUX')).toBe(true)
    expect(matchesMarket(inCountry('NL'), 'DACH')).toBe(false)
    expect(matchesMarket(inCountry('FR'), 'BENELUX')).toBe(false)
  })
  test('enables a group when any of its countries is configured', () => {
    expect(marketIsEnabled('DACH', { CH: { enabled: true } })).toBe(true)
    expect(marketIsEnabled('BENELUX', { LU: { enabled: false } })).toBe(false)
  })
})
