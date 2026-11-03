import { expect, test, type Page } from '@playwright/test'
import { datasetFixture } from './fixtures/dataset'
import { defaults } from '../src/lib'
import type { Signal } from '../src/types'

const shared = { q: 'Kept', buyer: 'Chosen buyer', currency: 'GBP', minValue: '100' }

async function fixture(page: Page) {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-10-01T12:00:00Z'))
  const data = datasetFixture()
  const base: Signal = {
    ...data.signals[0],
    buyer_name: shared.buyer,
    countries: ['GB'],
    currency: 'GBP',
    value_max: 200,
    first_seen_at: '2026-10-01T10:00:00Z',
    deadline_at: '2026-10-06T12:00:00Z',
    framework: null,
  }
  const live = { ...base, signal_type: 'LIVE_TENDER', lifecycle_state: 'OPEN' }
  const early = {
    ...base,
    signal_type: 'RFI',
    lifecycle_state: 'EARLY_ENGAGEMENT',
    procurement_stage: 'planning',
  }
  data.signals = [live, early].flatMap((record, i) =>
    ['old', 'new'].map((age, j) => ({
      ...record,
      id: `kept-${i}-${age}`,
      title: `Kept ${i === 0 ? 'live' : 'pre-market'} ${age}`,
      published_at: `2026-09-${27 + i + j * 2}T12:00:00Z`,
    })),
  )
  data.signals.push(
    { ...live, id: 'other-buyer', title: 'Kept other buyer', buyer_name: 'Other buyer' },
    { ...live, id: 'other-currency', title: 'Kept other currency', currency: 'EUR' },
    { ...live, id: 'lower-value', title: 'Kept lower value', value_max: 50 },
    { ...live, id: 'outside-deadline', title: 'Kept later deadline', deadline_at: '2026-11-01' },
  )
  const awards = ['Example Ltd', 'Other supplier'].map((supplier, i) => ({
    ...base,
    id: `kept-award-${i}`,
    title: `Kept award ${i}`,
    signal_type: 'AWARD',
    lifecycle_state: 'AWARDED',
    procurement_stage: 'award',
    status: 'complete',
    award_date: '2026-08-01',
    deadline_at: '2025-01-01',
    first_seen_at: '2025-01-01',
    incumbent_supplier: supplier,
  }))
  const awardPath = 'awards/GB-0123456789abcdef.json'
  data.award_history = { GB: { url: awardPath, count: awards.length } }
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.route(`**/data/${awardPath}`, (route) =>
    route.fulfill({ json: { schema_version: '1.0', signals: awards } }),
  )
}

async function selectRefiner(page: Page, label: string) {
  const item = page
    .locator('.discovery-card, .compact-refiners > button')
    .filter({ hasText: label })
  const position = page.getByRole('button', { name: `Show ${label}`, exact: true })
  await position.or(item).filter({ visible: true }).last().click()
  await item.click()
  await expect(item).toHaveAttribute('aria-pressed', 'true')
}

async function expectPreferences(page: Page, preferences: Record<string, string>) {
  await expect
    .poll(() => ({ ...defaults, ...Object.fromEntries(new URL(page.url()).searchParams) }))
    .toMatchObject(preferences)
}

test('@pr refiner switches preserve the chosen sort, search and shared filters', async ({
  page,
}) => {
  await fixture(page)
  const preferences = { ...shared, deadline: '7' }
  await page.goto(`./?${new URLSearchParams({ ...preferences, view: 'all' })}`)
  await expect(page.locator('.signal-row')).toHaveCount(4)
  await page.getByRole('button', { name: 'Sort opportunities: Best match' }).click()
  await page.getByRole('menuitemradio', { name: 'Most recent', exact: true }).click()
  for (const [label, count] of [
    ['Live Opportunities', 2],
    ['Pre-market', 2],
    ['Closing Soon', 2],
    ['Added today', 4],
    ['All Signals', 4],
  ] as const) {
    await selectRefiner(page, label)
    await expect(
      page.getByRole('button', { name: 'Sort opportunities: Most recent' }),
    ).toBeVisible()
    await expectPreferences(page, { ...preferences, sort: 'recent' })
    await expect(page.locator('.signal-row')).toHaveCount(count)
    await expect(page.locator('.row-title').first()).toContainText('new')
  }
  await page.reload()
  await expect(page.getByRole('button', { name: 'Sort opportunities: Most recent' })).toBeVisible()
  await page.goto('./')
  await expectPreferences(page, { ...preferences, sort: 'recent' })
  await expect(page.locator('.signal-row')).toHaveCount(4)
  await page.getByRole('button', { name: 'Sort opportunities: Most recent' }).click()
  await page.getByRole('menuitemradio', { name: 'Highest value', exact: true }).click()
  await selectRefiner(page, 'Closing Soon')
  await expect(
    page.getByRole('button', { name: 'Sort opportunities: Highest value' }),
  ).toBeVisible()
  await expectPreferences(page, { ...preferences, sort: 'value' })
  await page.getByRole('button', { name: 'Sort opportunities: Highest value' }).click()
  await page.getByRole('menuitemradio', { name: 'Best match', exact: true }).click()
  await selectRefiner(page, 'Pre-market')
  await expect(page.getByRole('button', { name: 'Sort opportunities: Best match' })).toBeVisible()
  await expectPreferences(page, preferences)
  await expect(page.locator('.signal-row')).toHaveCount(2)
})

test('@pr Awarded retains opportunity preferences and restores its own filters after switching back', async ({
  page,
}) => {
  await fixture(page)
  const preferences = {
    ...shared,
    type: 'LIVE_TENDER',
    deadline: '7',
    change: 'new',
    sort: 'value',
  }
  await page.goto(`./?${new URLSearchParams({ ...preferences, view: 'all' })}`)
  await expect(page.locator('.signal-row')).toHaveCount(2)
  await selectRefiner(page, 'Awarded')
  await expect(page.locator('.signal-row')).toHaveCount(2)
  await expect(page.getByRole('button', { name: 'Sorted by Latest awards' })).toBeDisabled()
  await expectPreferences(page, { ...preferences, view: 'awards' })
  await expect(page.getByRole('button', { name: 'Remove Notice filter' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Remove Deadline filter' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Remove Change filter' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Filters', exact: true }).click()
  await page.getByLabel('Awarded supplier', { exact: true }).fill('Example Ltd')
  await page.getByLabel('Awarded from', { exact: true }).fill('2026-01-01')
  await page.getByLabel('Awarded to', { exact: true }).fill('2026-12-31')
  await page.getByRole('button', { name: 'Close panel' }).click()
  const awardPreferences = {
    supplier: 'Example Ltd',
    awardFrom: '2026-01-01',
    awardTo: '2026-12-31',
  }
  await expect(page.locator('.signal-row')).toHaveCount(1)
  await selectRefiner(page, 'Pre-market')
  await expect(page.getByText('No matching signals', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Remove Notice filter' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Remove Supplier filter' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Filters', exact: true }).click()
  await expect(page.getByLabel('Notice type', { exact: true })).toHaveValue('LIVE_TENDER')
  await expect(page.getByRole('radio', { name: '7 days', exact: true })).toBeChecked()
  await expect(page.getByLabel('Freshness', { exact: true })).toHaveValue('new')
  await page.getByRole('button', { name: 'Close panel' }).click()
  await selectRefiner(page, 'Live Opportunities')
  await expect(
    page.getByRole('button', { name: 'Sort opportunities: Highest value' }),
  ).toBeVisible()
  await expect(page.locator('.signal-row')).toHaveCount(2)
  await expectPreferences(page, { ...preferences, ...awardPreferences, view: 'live' })
  await selectRefiner(page, 'Awarded')
  await page.reload()
  await expect(page.locator('.signal-row')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Remove Supplier filter' })).toBeVisible()
  await expectPreferences(page, { ...preferences, ...awardPreferences, view: 'awards' })
  await selectRefiner(page, 'Live Opportunities')
  await expect(page.locator('.signal-row')).toHaveCount(2)
  await expect(
    page.getByRole('button', { name: 'Sort opportunities: Highest value' }),
  ).toBeVisible()
})
