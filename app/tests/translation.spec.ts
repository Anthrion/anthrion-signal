import { datasetFixture } from './fixtures/dataset'
import { test, expect } from '@playwright/test'
import type { Dataset } from '../src/types'
import type { Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  const data = datasetFixture()
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
})

// The market row's English/Original switch: a radiogroup, one radio per language.
function languageOption(page: Page, label: 'English' | 'Original') {
  return page
    .getByRole('radiogroup', { name: 'Record language' })
    .getByRole('radio', { name: label, exact: true })
}

async function chooseLanguage(page: Page, label: 'English' | 'Original') {
  const option = languageOption(page, label)
  await option.click()
  await expect(option).toBeChecked()
  await expect(option).toBeFocused()
}

test('@pr English is default; original text, search, hides and refresh retain their own state', async ({
  page,
}) => {
  const data: Dataset = datasetFixture()
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
  await expect(languageOption(page, 'English')).toBeChecked()
  await expect(page.locator('.row-title')).toHaveText('Customer platform and integration')
  await expect(page.locator('.row-buyer')).toHaveText(
    'Stadtverwaltung Berlin (Berlin City Administration)',
  )
  await chooseLanguage(page, 'Original')
  await expect(page.locator('.row-buyer')).toHaveText('Stadtverwaltung Berlin')
  await expect(page.locator('.row-title')).toHaveText('Kundenplattform und Integration')
  await page.reload()
  await expect(languageOption(page, 'Original')).toBeChecked()
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
    .getByRole('button', { name: 'Hide Customer platform and integration', exact: true })
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
  const data: Dataset = datasetFixture()
  data.translations = {}
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto('./?view=all')
  // Without a cached translation the English view keeps the source wording.
  await expect(page.locator('.row-title').first()).toHaveText(data.signals[0].title)
  const control = page.getByRole('radiogroup', { name: 'Record language' })
  const bounds = await control.boundingBox()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  // The switch has no popup: both choices stay fully on screen in the compact market row.
  for (const label of ['English', 'Original'] as const)
    await expect(languageOption(page, label)).toBeInViewport({ ratio: 1 })
  if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
    await page.screenshot({
      path: `test-results/translation-${test.info().project.name}.png`,
      animations: 'disabled',
    })
})

test('record language switch supports arrow keys, Home, End, selection and roving focus', async ({
  page,
}) => {
  const data: Dataset = datasetFixture()
  data.signals[0] = { ...data.signals[0], title: 'Kundenplattform für das Vereinigte Königreich' }
  data.translations = {
    [data.signals[0].id]: {
      source_hash: 'fixture',
      version: 'en-procurement-2',
      title: 'Customer platform for the United Kingdom',
      description: data.signals[0].description,
    },
  }
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto('./?view=all')
  const english = languageOption(page, 'English')
  const original = languageOption(page, 'Original')
  const title = page.locator(`[data-signal-id="${data.signals[0].id}"] .row-title`)
  await expect(title).toHaveText('Customer platform for the United Kingdom')
  // One tab stop: the checked choice.
  await expect(english).toBeChecked()
  await expect(english).toHaveAttribute('tabindex', '0')
  await expect(original).toHaveAttribute('tabindex', '-1')
  await english.focus()
  await page.keyboard.press('ArrowRight')
  await expect(original).toBeChecked()
  await expect(original).toBeFocused()
  await expect(english).not.toBeChecked()
  await expect(original).toHaveAttribute('tabindex', '0')
  await expect(english).toHaveAttribute('tabindex', '-1')
  await expect(title).toHaveText('Kundenplattform für das Vereinigte Königreich')
  await page.keyboard.press('ArrowLeft')
  await expect(english).toBeChecked()
  await expect(english).toBeFocused()
  await expect(title).toHaveText('Customer platform for the United Kingdom')
  await page.keyboard.press('End')
  await expect(original).toBeChecked()
  await expect(original).toBeFocused()
  await page.keyboard.press('Home')
  await expect(english).toBeChecked()
  await expect(english).toBeFocused()
  // Up and down move the same way, wrapping at either end.
  await page.keyboard.press('ArrowUp')
  await expect(original).toBeChecked()
  await expect(original).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await expect(english).toBeChecked()
  await expect(english).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await expect(original).toBeChecked()
  await expect(original).toBeFocused()
  await expect(title).toHaveText('Kundenplattform für das Vereinigte Königreich')
  // Tab leaves the group; Shift+Tab returns to the checked choice, not the first one.
  await page.keyboard.press('Tab')
  await expect(original).not.toBeFocused()
  await expect(english).not.toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(original).toBeFocused()
  await page.reload()
  await expect(original).toBeChecked()
  await expect(title).toHaveText('Kundenplattform für das Vereinigte Königreich')
})

test('research page glass language menu supports keyboard navigation, selection and dismissal', async ({
  page,
}) => {
  await page.goto('./?view=all')
  if (page.viewportSize()!.width <= 900) await page.locator('.row-select').first().click()
  await page.locator('.console-detail:visible .inspector-heading .research-title-link').click()
  // Research pages keep the glass language menu in their header.
  const context = page.getByRole('dialog', { name: 'Opportunity research' })
  const trigger = context.getByRole('button', { name: /^Record language:/ })
  await trigger.focus()
  await page.keyboard.press('ArrowDown')
  const english = context.getByRole('menuitemradio', { name: 'English', exact: true })
  const original = context.getByRole('menuitemradio', { name: 'Original', exact: true })
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
  // Escape closes only the menu, not the research page.
  await expect(context).toBeVisible()
  await trigger.click()
  const search = context.getByRole('textbox', { name: 'Search related signals' })
  await search.click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(search).toBeFocused()
  // The page's choice is the workspace language, so the results' switch follows it.
  await context.getByRole('button', { name: 'Back to results', exact: true }).click()
  await expect(languageOption(page, 'Original')).toBeChecked()
})
