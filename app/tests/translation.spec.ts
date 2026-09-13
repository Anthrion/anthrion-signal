import { test, expect } from '@playwright/test'
import type { Dataset } from '../src/types'

test('English is default; original text, search, hides and refresh retain their own state', async ({
  page,
}) => {
  const data: Dataset = await (await page.request.get('./data/current.json')).json()
  const now = new Date().toISOString()
  data.signals = [
    {
      ...data.signals[0],
      id: 'translated-lead',
      title: 'Kundenplattform und Integration',
      description: 'Gesucht wird die Implementierung einer Kundenplattform.',
      countries: ['DE'],
      status: 'active',
      signal_type: 'LIVE_TENDER',
      procurement_stage: 'tender',
      lifecycle_state: 'OPEN',
      delivery_priority: 'platform',
      exclusion_reasons: [],
      deadline_at: '2099-01-01T00:00:00Z',
      published_at: now,
      first_seen_at: now,
      last_material_update: now,
    },
  ]
  data.translations = {
    'translated-lead': {
      source_hash: 'fixture',
      version: 'en-procurement-2',
      title: 'Customer platform and integration',
      description: 'Implementation of a customer platform is required.',
    },
  }
  const apiRequests: string[] = []
  page.on('request', (request) => {
    if (/generativelanguage|translate.googleapis/.test(request.url()))
      apiRequests.push(request.url())
  })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto('./?market=DE&view=all')
  await expect(page.getByRole('combobox', { name: 'Record language' })).toHaveValue('en')
  await expect(page.locator('.row-title')).toHaveText('Customer platform and integration')
  await page.getByRole('combobox', { name: 'Record language' }).selectOption('original')
  await expect(page.locator('.row-title')).toHaveText('Kundenplattform und Integration')
  await page.reload()
  await expect(page.getByRole('combobox', { name: 'Record language' })).toHaveValue('original')
  await page.locator('.workspace-search input').fill('customer platform')
  await expect(page.locator('.row-title')).toHaveText('Kundenplattform und Integration')
  await page.getByRole('combobox', { name: 'Record language' }).selectOption('en')
  await page.locator('.workspace-search input').fill('Kundenplattform')
  await expect(page.locator('.row-title')).toHaveText('Customer platform and integration')
  await page.locator('.row-select').click()
  const panel =
    page.viewportSize()!.width > 900
      ? page.locator('#selected-opportunity')
      : page.getByRole('dialog')
  await expect(panel).toContainText('Implementation of a customer platform is required.')
  if (page.viewportSize()!.width <= 900)
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page
    .locator('.signal-row')
    .getByRole('checkbox', { name: 'Hide Customer platform and integration' })
    .click()
  await page.getByRole('combobox', { name: 'Record language' }).selectOption('original')
  await page.reload()
  await expect(page.locator('.row-title')).toHaveCount(0)
  expect(
    await page.evaluate(() => JSON.parse(localStorage.getItem('anthrion-hidden-v1') || '[]')),
  ).toContain('translated-lead')
  expect(apiRequests).toEqual([])
})

test('pending translations retain the original opportunity and compact market controls fit', async ({
  page,
}) => {
  const data: Dataset = await (await page.request.get('./data/current.json')).json()
  data.translations = {}
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto('./?view=all')
  await expect(page.locator('.row-title').first()).toBeVisible()
  const bounds = await page.locator('.language-control').boundingBox()
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `test-results/translation-${test.info().project.name}.png` })
})
