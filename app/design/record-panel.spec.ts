import { test, expect } from '@playwright/test'
import { datasetFixture } from '../tests/fixtures/dataset'
import { recordDataset } from '../tests/fixtures/record'

test('capture the record panel for design review', async ({ page }) => {
  const data = recordDataset(datasetFixture())
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.clock.setFixedTime(new Date('2026-09-11T12:00:00Z'))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 1600, height: 1352 })
  await page.goto('./?view=live')
  await expect(page.locator('.console-inspector')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page
    .locator('.console-inspector')
    .screenshot({ path: '../artifacts/record-panel-design.png' })
})
