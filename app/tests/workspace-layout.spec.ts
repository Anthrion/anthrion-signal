import { datasetFixture } from './fixtures/dataset'
import { test, expect, type Locator, type Page } from '@playwright/test'
import { recordDataset } from './fixtures/record'

async function contained(child: Locator, parent: Locator) {
  const bounds = (await parent.boundingBox())!
  const box = (await child.boundingBox())!
  expect(box.x).toBeGreaterThanOrEqual(bounds.x - 1)
  expect(box.y).toBeGreaterThanOrEqual(bounds.y - 1)
  expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width + 1)
  expect(box.y + box.height).toBeLessThanOrEqual(bounds.y + bounds.height + 1)
  return box
}

async function ready(page: Page) {
  await page.goto('./?view=all')
  await expect(page.locator('.row-select').first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

test.beforeEach(async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-09-11T12:00:00Z'))
  const dataset = datasetFixture()
  await page.route('**/data/current.json', (route) =>
    route.fulfill({ json: recordDataset(dataset) }),
  )
})

test('the header owns search, filters and sort without colliding with brand or saved controls', async ({
  page,
}, info) => {
  const widths =
    info.project.name === 'desktop'
      ? [901, 997, 1100, 1101, 1139, 1220, 1484, 1920]
      : [320, 360, 390, 620, 621, 768, 900]
  for (const width of widths) {
    await page.setViewportSize({ width, height: 920 })
    await ready(page)
    const header = page.locator('.workspace-header')
    const search = header.getByRole('search')
    await expect(search.getByRole('textbox', { name: 'Search opportunities' })).toBeVisible()
    await expect(search.getByRole('button', { name: 'Filters', exact: true })).toBeVisible()
    await expect(search.getByRole('button', { name: /Sort opportunities:/ })).toBeVisible()
    await expect(page.locator('.console-toolbar')).toHaveCount(0)
    await expect(page.locator('.feed-heading')).toHaveCSS('clip-path', 'inset(50%)')
    expect((await page.locator('.feed-heading').boundingBox())!.height).toBe(1)
    const boxes = []
    for (const selector of [
      '.workspace-brand',
      '.workspace-search',
      '.workspace-nav',
      '.workspace-tools',
    ])
      boxes.push(await contained(header.locator(selector), header))
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i],
          b = boxes[j]
        const intersectionWidth = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)
        const intersectionHeight = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y)
        expect(intersectionWidth > 1 && intersectionHeight > 1).toBe(false)
      }
    }
    if (width > 900) {
      expect(boxes[1].x).toBeGreaterThan(boxes[0].x + boxes[0].width)
      expect(boxes[1].x + boxes[1].width).toBeLessThan(boxes[2].x)
      expect(boxes[0].y + boxes[0].height).toBeLessThanOrEqual(66)
    }
    for (const control of [
      search.locator('.search-box'),
      search.getByRole('button', { name: 'Filters', exact: true }),
      search.locator('.sort-trigger'),
    ])
      await contained(control, search)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
})

test('export is centred beside the six refiners and remains clear of carousel navigation', async ({
  page,
}, info) => {
  const desktop = info.project.name === 'desktop'
  // Six glass cards fit a wide desktop; a narrower one scrolls them with arrows, and phones use
  // a row of chips.
  const layouts = desktop
    ? [
        { width: 1484, arrows: 0 },
        { width: 1100, arrows: 2 },
      ]
    : [{ width: 320, arrows: 0 }]
  const exportButton = page.getByRole('button', { name: 'Export signals', exact: true })
  for (const { width, arrows } of layouts) {
    await page.setViewportSize({ width, height: 920 })
    await ready(page)
    await expect(
      page.locator(desktop ? '.discovery-card' : '.compact-refiners button'),
    ).toHaveCount(6)
    await expect(page.locator('.carousel-arrow')).toHaveCount(arrows)
    const exportBox = await contained(exportButton, page.locator('.discovery-band'))
    // Phone chips scroll edge to edge through their padding; their content stops before export.
    const refiners = await page
      .locator(desktop ? '.discovery-viewport' : '.compact-refiners')
      .evaluate((el) => {
        const box = el.getBoundingClientRect()
        return {
          middle: box.top + box.height / 2,
          end: box.right - parseFloat(getComputedStyle(el).paddingRight),
        }
      })
    expect(
      Math.abs(exportBox.y + exportBox.height / 2 - refiners.middle),
      `centred at ${width}px`,
    ).toBeLessThan(1)
    expect(exportBox.x).toBeGreaterThan(refiners.end)
    for (const arrow of await page.locator('.carousel-arrow').all()) {
      const box = (await arrow.boundingBox())!
      expect(box.x + box.width).toBeLessThanOrEqual(exportBox.x)
    }
  }
  await page.getByRole('textbox', { name: 'Search opportunities' }).fill('Vanguard')
  await expect(page.locator('.row-select').first()).toBeVisible()
  const download = page.waitForEvent('download')
  await exportButton.click()
  expect((await download).suggestedFilename()).toMatch(/\.csv$/)
  // Hidden records are a lens in the header now; with none hidden there is nothing to export.
  const hidden = page.getByRole('button', { name: 'Hidden, 0', exact: true })
  await hidden.click()
  await expect(hidden).toHaveAttribute('aria-pressed', 'true')
  await expect(exportButton).toBeDisabled()
  await expect(page.getByText('No hidden signals', { exact: true })).toBeVisible()
})

test('default reading stays clear and the Compact refiners preference gains space above the usable action dock', async ({
  page,
}, info) => {
  const desktop = info.project.name === 'desktop'
  await page.setViewportSize({ width: desktop ? 1484 : 390, height: desktop ? 920 : 844 })
  await ready(page)
  const band = page.locator('.discovery-band')
  if (!desktop) {
    // Phones always show the compact chip row; the Refiners preference is for wider screens.
    await expect(page.locator('.compact-refiners')).toBeVisible()
    await page.locator('.row-select').first().click()
  }
  const panel = page.locator('.console-detail:visible')
  const dock = panel.locator('.record-action-dock')
  if (desktop) {
    const standardReading = (await panel.locator('.inspector-scroll').boundingBox())!
    const standardDock = (await dock.boundingBox())!
    const cards = (await band.boundingBox())!
    expect(standardReading.height).toBeGreaterThanOrEqual(450)
    expect(standardReading.y).toBeGreaterThanOrEqual(cards.y + cards.height)
    expect(standardReading.y + standardReading.height).toBeLessThanOrEqual(standardDock.y + 1)
    await page.getByRole('button', { name: 'Workspace menu', exact: true }).click()
    const menu = page.getByRole('dialog', { name: 'Workspace' })
    const compact = menu
      .getByRole('radiogroup', { name: 'Refiners' })
      .getByRole('radio', { name: 'Compact' })
    await compact.click()
    await expect(compact).toHaveAttribute('aria-checked', 'true')
    await menu.getByRole('button', { name: 'Close workspace menu' }).click()
    await expect(menu).toHaveCount(0)
    await expect(page.locator('.compact-refiners')).toBeVisible()
    await expect(page.locator('.discovery-viewport')).toHaveCount(0)
    // The chip row is shorter than the cards, and the record takes all of the space it frees:
    // it keeps its distance below the refiners and still ends at the unchanged dock.
    const chips = (await band.boundingBox())!
    const reading = (await panel.locator('.inspector-scroll').boundingBox())!
    expect(reading.y - (chips.y + chips.height)).toBeCloseTo(
      standardReading.y - (cards.y + cards.height),
      0,
    )
    expect(reading.y + reading.height).toBeCloseTo(standardReading.y + standardReading.height, 0)
    expect(reading.height - standardReading.height).toBeGreaterThanOrEqual(40)
    expect(await dock.boundingBox()).toEqual(standardDock)
  }
  const before = (await dock.boundingBox())!
  // One row of 44px controls; the source button's second line (when it was checked) adds a little.
  expect(before.height).toBeLessThanOrEqual(61)
  expect(before.y + before.height).toBeLessThanOrEqual(page.viewportSize()!.height)
  if (desktop) {
    await expect(page.locator('.console-inspector')).toHaveCSS('border-top-left-radius', '6px')
    await expect(page.locator('.console-inspector')).toHaveCSS('border-bottom-left-radius', '6px')
    await expect(page.locator('.market-section')).toHaveCSS('height', '66px')
    await expect(panel.locator('.inspector-summary')).toHaveCSS('margin-top', '20px')
    await expect(panel.locator('.inspector-summary')).toHaveCSS('padding-left', '24px')
    await expect(panel.locator('.inspector-summary p').first()).toHaveCSS('font-size', '18px')
  }
  const heading = (await panel.locator('.inspector-heading').boundingBox())!
  const overview = (await panel.locator('.inspector-overview').boundingBox())!
  expect(overview.y - (heading.y + heading.height)).toBeCloseTo(12, 0)
  for (const button of [dock.getByRole('button'), dock.getByRole('link')]) {
    expect((await contained(button, dock)).height).toBeGreaterThanOrEqual(44)
  }
  // The record is one scroll: it ends with the source history, above the dock.
  await panel.locator('.inspector-scroll').evaluate((el) => el.scrollTo(0, el.scrollHeight))
  expect(await dock.boundingBox()).toEqual(before)
  const history = panel.locator('.record-history')
  await expect(history).toBeInViewport()
  const end = (await history.boundingBox())!
  expect(end.y + end.height).toBeLessThanOrEqual(before.y)
  // The dock's source button opens that history in place; the dock itself does not change.
  await dock.getByRole('button', { name: /^Find a Tender/ }).click()
  await expect(history).toHaveAttribute('open', '')
  await expect(history.locator('.provenance-list')).toContainText('Reference panel-notice')
  await expect(page.getByRole('dialog')).toHaveCount(desktop ? 0 : 1)
  expect(await dock.boundingBox()).toEqual(before)
})
