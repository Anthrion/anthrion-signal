import { expect, test } from '@playwright/test'
import { datasetFixture } from './fixtures/dataset'
import type { Signal } from '../src/types'

test('@pr Best match is the default, ranks lazy evidence and preserves explicit sort choices', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const fixture = datasetFixture()
  const base = fixture.signals.find((s) => s.countries.includes('GB'))!
  const hash = '0123456789abcdef'
  const rows: Signal[] = [
    {
      ...base,
      id: 'ranking-code',
      title: 'Shared software purchase',
      published_at: '2026-09-30',
      capability_evidence: [],
    },
    {
      ...base,
      id: 'ranking-need',
      title: 'Shared case management system',
      published_at: '2026-09-29',
      capability_evidence: [
        {
          capability: 'service',
          strength: 'needs',
          field: 'title',
          context: 'uncertain',
          phrase: 'case management',
          basis: 'original',
          language: 'en',
          quote: 'Shared case management system',
          source_url: base.primary_source_url,
          source_hash: 'test',
        },
      ],
    },
    {
      ...base,
      id: 'ranking-named',
      title: 'Shared Salesforce implementation',
      published_at: '2026-09-28',
      capability_evidence: [
        {
          capability: 'salesforce',
          strength: 'explicit',
          field: 'title',
          context: 'delivery',
          phrase: 'Salesforce',
          basis: 'original',
          language: 'en',
          quote: 'Shared Salesforce implementation',
          source_url: base.primary_source_url,
          source_hash: 'test',
        },
      ],
    },
  ].map((s) => ({
    ...s,
    countries: ['GB'],
    description: 'Shared software delivery.',
    status: 'active',
    signal_type: 'LIVE_TENDER',
    lifecycle_state: 'OPEN',
    procurement_stage: 'tender',
    delivery_priority: 'platform',
    deadline_at: '2099-10-01',
    response_deadlines: [],
    deadlines: [],
    exclusion_reasons: [],
  }))
  const summaries = rows.map(({ capability_evidence, lots: _lots, ...s }) => ({
    ...s,
    description: '',
    documents: [],
    changes: [],
    is_summary: true,
    search_text: `${s.title} ${s.description}`,
    ranking_evidence: capability_evidence?.map(({ capability, strength, field, context }) => ({
      capability,
      strength,
      field,
      context,
    })),
  }))
  const manifest = {
    ...fixture,
    signals: [],
    translations: {},
    award_history: {},
    current_feed: {
      version: '1.0',
      markets: { GB: { url: `current/GB-${hash}.json`, count: rows.length } },
      records: Object.fromEntries(
        rows.map((s) => [
          s.id,
          { url: `records/${s.id}-${hash}.json`, markets: ['GB'], view: 'opportunities' },
        ]),
      ),
    },
  }
  await page.route('**/data/manifest.json', (route) => route.fulfill({ json: manifest }))
  await page.route(`**/data/current/GB-${hash}.json`, (route) =>
    route.fulfill({ json: { schema_version: '1.0', signals: summaries, translations: {} } }),
  )
  await page.route('**/data/records/ranking-*.json', (route) => {
    const signal = rows.find((s) => route.request().url().includes(`${s.id}-${hash}`))!
    return route.fulfill({ json: { schema_version: '1.0', signal } })
  })
  await page.goto('./?view=all&market=GB&q=Shared')
  await expect(page.locator('.signal-row')).toHaveCount(3)
  await expect(page.getByRole('button', { name: 'Sort opportunities: Best match' })).toBeVisible()
  await expect(page.locator('.signal-row').first()).toContainText(
    'Shared Salesforce implementation',
  )
  await page.getByRole('button', { name: 'Sort opportunities: Best match' }).click()
  await page.getByRole('menuitemradio', { name: 'Most recent', exact: true }).click()
  await expect(page.locator('.signal-row').first()).toContainText('Shared software purchase')
  await expect(page.locator('.signal-row')).toHaveCount(3)
  await expect.poll(() => new URL(page.url()).searchParams.get('sort')).toBe('recent')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Sort opportunities: Most recent' })).toBeVisible()
  await expect(page.locator('.signal-row').first()).toContainText('Shared software purchase')
  await page.getByRole('button', { name: 'Sort opportunities: Most recent' }).click()
  await page.getByRole('menuitemradio', { name: 'Best match', exact: true }).click()
  await expect(page.locator('.signal-row').first()).toContainText(
    'Shared Salesforce implementation',
  )
  await expect.poll(() => new URL(page.url()).searchParams.has('sort')).toBe(false)
  await page.reload()
  await expect(page.getByRole('button', { name: 'Sort opportunities: Best match' })).toBeVisible()
  await expect(page.locator('.signal-row').first()).toContainText(
    'Shared Salesforce implementation',
  )
  await expect(page.locator('.signal-row')).toHaveCount(3)
})
