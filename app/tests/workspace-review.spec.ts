import { test, expect } from '@playwright/test'
import { datasetFixture } from './fixtures/dataset'
import { recordDataset } from './fixtures/record'

test.beforeEach(async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-09-11T12:00:00Z'))
})

test('@pr a single questions deadline remains available beyond the headline response date', async ({
  page,
}) => {
  const data = recordDataset(datasetFixture(), {
    deadlines: [
      {
        kind: 'questions',
        date: '2026-09-12',
        precision: 'date',
        source_text: '2026-09-12',
        source_url: 'https://example.com/questions',
        status: 'current',
      },
    ],
  })
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto('./?view=all&signal=panel-a')
  const record = page.locator('.console-detail:visible')
  await expect(record.getByRole('heading', { name: 'Key dates' })).toBeVisible()
  await expect(record.locator('.deadline-events')).toContainText('12 Sept 2026')
})

test('@pr typing shortcut letters in menus does not hide or save the selected record', async ({
  page,
}) => {
  await page.route('**/data/current.json', (route) =>
    route.fulfill({ json: recordDataset(datasetFixture()) }),
  )
  await page.goto('./?view=all')
  await expect(page.locator('.row-select').first()).toBeVisible()
  for (const trigger of ['Sort opportunities: Most recent', 'Search options']) {
    await page.getByRole('button', { name: trigger, exact: true }).click()
    await page.keyboard.press('h')
    await page.keyboard.press('s')
    const lists = await page.evaluate(() =>
      ['anthrion-hidden-v1', 'anthrion-saved-v1'].map((key) =>
        JSON.parse(localStorage.getItem(key) || '[]'),
      ),
    )
    expect(lists).toEqual([[], []])
    await page.keyboard.press('Escape')
  }
})

test('@pr award-only currencies, sectors and merged retired sources remain filterable', async ({
  page,
}) => {
  const data = recordDataset(datasetFixture())
  const award = {
    ...data.signals[0],
    id: 'historic-cad',
    signal_type: 'AWARD',
    lifecycle_state: 'AWARDED',
    status: 'complete',
    procurement_stage: 'award',
    award_date: '2025-01-01',
    currency: 'CAD',
    value_max: 250000,
    categories: ['Historic sector'],
    provenance: [{ ...data.signals[0].provenance[0], source: 'usaspending' }],
  }
  data.award_history = { GB: { url: 'awards/GB-0123456789abcdef.json', count: 1 } }
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.route('**/data/awards/GB-0123456789abcdef.json', (route) =>
    route.fulfill({ json: { schema_version: '1.0', signals: [award] } }),
  )
  await page.goto('./?view=awards')
  await expect(page.locator('.row-select')).toHaveCount(1)
  await page.getByRole('button', { name: 'Filters', exact: true }).click()
  await expect(
    page.getByLabel('Currency', { exact: true }).locator('option[value="CAD"]'),
  ).toHaveCount(1)
  await page.getByLabel('Currency', { exact: true }).selectOption('CAD')
  await page.getByText('More filters', { exact: true }).click()
  await page.getByLabel('Sector', { exact: true }).selectOption('Historic sector')
  await page.getByLabel('Source', { exact: true }).selectOption('usaspending')
  await page.getByRole('button', { name: 'Show 1 awards', exact: true }).click()
  await expect(page.locator('.row-select')).toHaveCount(1)
})
