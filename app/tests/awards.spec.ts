import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { Dataset, Signal } from '../src/types'
import { recordDataset } from './fixtures/record'
import { isHistoricalAward, markets, matchesMarket, priorityTier } from '../src/lib'

const gbPath = 'awards/GB-0123456789abcdef.json'
const nordicPath = 'awards/NORDICS-fedcba9876543210.json'

async function fixture(page: Page, fail: boolean | 'malformed' = false) {
  const original: Dataset = await (await page.request.get('./data/current.json')).json()
  const data = recordDataset(original, { deadline_at: '2099-10-01' })
  const base: Signal = {
    ...data.signals[0],
    signal_type: 'AWARD',
    status: 'complete',
    lifecycle_state: 'AWARDED',
    deadline_at: '2024-01-01',
    updated_at: '2025-04-01T12:00:00Z',
    incumbent_supplier: 'Example Delivery Ltd',
    procurement_stage: 'award',
  }
  const awards: Signal[] = [
    {
      ...base,
      id: 'ai-award',
      title: 'AI support assistant',
      delivery_priority: 'ai',
      matched_capabilities: ['ai'],
      updated_at: '2026-08-01T12:00:00Z',
    },
    {
      ...base,
      id: 'crm-award',
      title: 'Customer platform implementation',
      delivery_priority: 'platform',
      matched_capabilities: ['crm'],
    },
    {
      ...base,
      id: 'other-award',
      title: 'Digital engineering',
      delivery_priority: 'other',
      matched_capabilities: [],
    },
    { ...base, id: 'cancelled-award', title: 'Cancelled award', status: 'cancelled' },
  ]
  data.award_history = { GB: { url: gbPath, count: 4 }, NORDICS: { url: nordicPath, count: 1 } }
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  let requests = 0
  await page.route(`**/data/${gbPath}`, (route) => {
    requests++
    return fail && requests === 1
      ? fail === 'malformed'
        ? route.fulfill({ json: { schema_version: '1.0', signals: [{ id: 'broken' }] } })
        : route.fulfill({ status: 503 })
      : route.fulfill({ json: { schema_version: '1.0', signals: awards } })
  })
  await page.route(`**/data/${nordicPath}`, (route) =>
    route.fulfill({
      json: {
        schema_version: '1.0',
        signals: [{ ...base, id: 'se-award', title: 'Kundplattform', countries: ['SE'] }],
        translations: {
          'se-award': {
            source_hash: 'fixture',
            version: 'fixture',
            title: 'Nordic customer platform',
            description: 'Implementation of CRM software.',
          },
        },
      },
    }),
  )
  return { requests: () => requests }
}

test.beforeEach(async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-09-18T12:00:00Z'))
})

test('Awarded is below Capability A-Z, lazy loads and preserves capability priority', async ({
  page,
}, info) => {
  const counter = await fixture(page)
  await page.goto('./?view=all')
  await expect(page.locator('.row-select').first()).toBeVisible()
  expect(counter.requests()).toBe(0)
  const liveCounts = await page.locator('.discovery-value').allTextContents()
  await page.getByRole('button', { name: 'Sort opportunities: Most recent' }).click()
  const labels = await page.getByRole('menuitemradio').allTextContents()
  expect(labels.indexOf('Awarded')).toBe(labels.indexOf('Capability A-Z') + 1)
  await page.getByRole('menuitemradio', { name: 'Awarded', exact: true }).click()
  await expect(page.locator('.row-title')).toHaveText([
    'Customer platform implementation',
    'AI support assistant',
    'Digital engineering',
  ])
  expect(counter.requests()).toBe(1)
  await expect(page).toHaveURL(/view=awards/)
  expect(await page.locator('.discovery-value').allTextContents()).toEqual(liveCounts)
  await page.locator('.row-select').first().click()
  const panel = page.locator('.console-detail:visible')
  await expect(panel).toContainText('Example Delivery Ltd')
  await expect(panel.locator('.inspector-facts dt')).toHaveText([
    'Notice type',
    'Published amount',
    'Award notice published',
  ])
  await expect(panel.getByRole('link', { name: /Add deadline/ })).toHaveCount(0)
  const gmail = new URL(
    (await panel
      .getByRole('link', { name: /Share this opportunity in Gmail/ })
      .getAttribute('href'))!,
  )
  expect(gmail.searchParams.get('body')).toContain('view=awards')
  await page.screenshot({ path: `../artifacts/awarded-${info.project.name}.png` })
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  // A menu sort choice returns to the normal feed. Mobile detail is closed first.
  if (info.project.name === 'mobile')
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page
    .locator('.signal-row')
    .first()
    .getByRole('button', { name: 'Save opportunity in this browser' })
    .click()
  await expect(page.getByRole('button', { name: /Saved opportunities/ })).toContainText('1')
  await page.getByRole('button', { name: /Saved opportunities/ }).click()
  await expect(page.locator('.row-title')).toHaveText(['Customer platform implementation'])
  await page.reload()
  await expect(page.locator('.row-title')).toHaveText(['Customer platform implementation'])
  await page.getByRole('button', { name: 'Sort opportunities: Most recent' }).click()
  await page.getByRole('menuitemradio', { name: 'Awarded', exact: true }).click()
  await page.getByRole('textbox', { name: 'Search opportunities' }).fill('AI support')
  await expect(page.locator('.row-title')).toHaveText(['AI support assistant'])
  await page.getByRole('button', { name: 'Clear search' }).click()
  await page.getByRole('button', { name: 'Sort opportunities: Awarded' }).click()
  await page.getByRole('menuitemradio', { name: 'Most recent', exact: true }).click()
  await expect(page).not.toHaveURL(/view=awards/)
  await expect(page.locator('.row-title')).toHaveCount(2)
})

test('award deep links survive reload and market changes', async ({ page }) => {
  await fixture(page)
  await page.goto('./?view=awards&market=NORDICS&signal=se-award')
  await expect(page.locator('.console-detail:visible h2')).toHaveText('Nordic customer platform')
  await page.reload()
  await expect(page.locator('.console-detail:visible h2')).toHaveText('Nordic customer platform')
  if (page.viewportSize()!.width <= 900)
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page
    .getByRole('navigation', { name: 'Markets' })
    .getByRole('button', { name: 'United Kingdom', exact: true })
    .click()
  await expect(page.locator('.row-title').first()).toHaveText('Customer platform implementation')
  await expect(page).toHaveURL(/view=awards/)
  await page.getByRole('textbox', { name: 'Search opportunities' }).fill('not-present')
  await expect(page.getByText('No matching signals', { exact: true })).toBeVisible()
})

for (const failure of [true, 'malformed'] as const)
  test(`history failure ${failure} is recoverable and never displayed as an empty successful result`, async ({
    page,
  }) => {
    await fixture(page, failure)
    await page.goto('./?view=awards')
    await expect(page.getByRole('alert')).toContainText(
      'Awarded records are temporarily unavailable',
    )
    await expect(page.getByText('No matching signals', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: 'Try again', exact: true }).click()
    await expect(page.locator('.row-title').first()).toHaveText('Customer platform implementation')
  })

test('published historical records match every market manifest and stay out of live data', async ({
  page,
}) => {
  test.setTimeout(180000)
  await page.unroute('**/data/manifest.json')
  const data: Dataset = await (await page.request.get('./data/current.json')).json()
  expect(data.signals.every((s) => !isHistoricalAward(s))).toBe(true)
  expect(Object.keys(data.award_history || {}).sort()).toEqual(markets.map((m) => m.id).sort())
  for (const [market, manifest] of Object.entries(data.award_history!)) {
    const response = await page.request.get(`./data/${manifest.url}`)
    expect(response.ok()).toBe(true)
    const payload: { signals: Signal[] } = await response.json()
    expect(payload.signals).toHaveLength(manifest.count)
    expect(payload.signals.every((s) => isHistoricalAward(s) && matchesMarket(s, market))).toBe(
      true,
    )
    await page.goto(`./?view=awards&market=${market}`)
    if (!manifest.count) continue
    await expect(page.locator('.row-select').first()).toBeVisible()
    const id = await page.locator('.row-motion').first().getAttribute('data-signal-id')
    const first = payload.signals.find((s) => s.id === id)!
    expect(first).toBeDefined()
    expect(priorityTier(first)).toBe(Math.min(...payload.signals.map(priorityTier)))
  }
})
