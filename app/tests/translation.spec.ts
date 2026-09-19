import { test, expect } from '@playwright/test'
import type { Dataset } from '../src/types'
import type { Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
})

async function chooseLanguage(page: Page, label: 'English' | 'Original') {
  await page.getByRole('button', { name: /^Record language:/ }).click()
  await page.getByRole('menuitemradio', { name: label, exact: true }).click()
  await expect(page.getByRole('button', { name: `Record language: ${label}` })).toBeFocused()
}

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
      buyer_name: 'Stadtverwaltung Berlin',
      countries: ['DE'],
      status: 'active',
      signal_type: 'LIVE_TENDER',
      procurement_stage: 'tender',
      lifecycle_state: 'OPEN',
      delivery_priority: 'platform',
      exclusion_reasons: [],
      deadline_at: '2099-01-01T00:00:00Z',
      response_deadlines: [],
      deadlines: [],
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
      buyer_original: 'Stadtverwaltung Berlin',
      buyer_name: 'Berlin City Administration',
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
  await expect(page.getByRole('button', { name: 'Record language: English' })).toBeVisible()
  await expect(page.locator('.row-title')).toHaveText('Customer platform and integration')
  await expect(page.locator('.row-buyer')).toHaveText(
    'Stadtverwaltung Berlin (Berlin City Administration)',
  )
  await chooseLanguage(page, 'Original')
  await expect(page.locator('.row-buyer')).toHaveText('Stadtverwaltung Berlin')
  await expect(page.locator('.row-title')).toHaveText('Kundenplattform und Integration')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Record language: Original' })).toBeVisible()
  await page.locator('.workspace-search input').fill('customer platform')
  await expect(page.locator('.row-title')).toHaveText('Kundenplattform und Integration')
  await chooseLanguage(page, 'English')
  await page.locator('.workspace-search input').fill('Berlin City Administration')
  await expect(page.locator('.row-title')).toHaveText('Customer platform and integration')
  await page.locator('.workspace-search input').fill('Kundenplattform')
  await expect(page.locator('.row-title')).toHaveText('Customer platform and integration')
  await page.locator('.row-select').click()
  const panel =
    page.viewportSize()!.width > 900
      ? page.locator('#selected-opportunity')
      : page.getByRole('dialog')
  await expect(panel).toContainText('Implementation of a customer platform is required.')
  await expect(panel).toContainText('Stadtverwaltung Berlin (Berlin City Administration)')
  if (page.viewportSize()!.width <= 900)
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page
    .locator('.signal-row')
    .getByRole('checkbox', { name: 'Hide Customer platform and integration' })
    .click()
  await chooseLanguage(page, 'Original')
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
  await page.getByRole('button', { name: 'Record language: English' }).click()
  const menu = page.getByRole('menu', { name: 'Record language' })
  await expect(menu).toBeVisible()
  const menuBounds = await menu.boundingBox()
  expect(menuBounds!.x).toBeGreaterThanOrEqual(0)
  expect(menuBounds!.x + menuBounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.screenshot({
    path: `test-results/translation-${test.info().project.name}.png`,
    animations: 'disabled',
  })
})

test('glass language menu supports keyboard navigation, selection and dismissal', async ({
  page,
}) => {
  await page.goto('./?view=all')
  const trigger = page.getByRole('button', { name: /^Record language:/ })
  await trigger.focus()
  await page.keyboard.press('ArrowDown')
  const english = page.getByRole('menuitemradio', { name: 'English', exact: true })
  const original = page.getByRole('menuitemradio', { name: 'Original', exact: true })
  await expect(english).toBeFocused()
  await expect(english).toHaveAttribute('aria-checked', 'true')
  await page.keyboard.press('End')
  await expect(original).toBeFocused()
  await page.keyboard.press('Home')
  await expect(english).toBeFocused()
  await page.keyboard.press('o')
  await expect(original).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(trigger).toBeFocused()
  await expect(trigger).toHaveAccessibleName('Record language: Original')
  await trigger.click()
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await trigger.click()
  await page.locator('.workspace-search input').click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('.workspace-search input')).toBeFocused()
})
