import { test, expect, type Locator, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { Dataset, Signal } from '../src/types'
import {
  recordDataset,
  recordTitle as title,
  recordDescription as description,
} from './fixtures/record'

async function fixture(page: Page, overrides: Partial<Signal> = {}) {
  const dataset: Dataset = await (await page.request.get('./data/current.json')).json()
  await page.route('**/data/current.json', (route) =>
    route.fulfill({ json: recordDataset(dataset, overrides) }),
  )
}

async function preview(page: Page) {
  await page.goto('./?view=live')
  await expect(page.locator('.row-select').first()).toBeVisible()
  if (page.viewportSize()!.width <= 900) await page.locator('.row-select').first().click()
  const panel = page.locator('.console-detail:visible')
  await expect(panel).toBeVisible()
  return panel
}

async function dockInViewport(page: Page, panel: Locator) {
  const dock = panel.locator('.record-action-dock')
  const viewport = page.viewportSize()!
  for (const control of [dock, dock.locator('button'), dock.locator('a')]) {
    const box = (await control.boundingBox())!
    expect(box.x).toBeGreaterThanOrEqual(0)
    expect(box.y).toBeGreaterThanOrEqual(0)
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1)
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 1)
  }
  return dock.boundingBox()
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-09-11T12:00:00Z'))
})

test('selected design presents compact source facts before untruncated text', async ({
  page,
}, info) => {
  await fixture(page)
  const panel = await preview(page)
  await expect(panel.locator('.inspector-facts dt')).toHaveText([
    'Notice type',
    'Value',
    'Deadline',
  ])
  await expect(panel.locator('.inspector-capabilities')).toContainText('Case management & service')
  await expect(panel.locator('.inspector-summary p')).toHaveText(description.split('\n\n'))
  expect(
    await panel
      .locator('.inspector-summary p')
      .first()
      .evaluate((el) => getComputedStyle(el).webkitLineClamp),
  ).toBe('none')
  const facts = (await panel.locator('.inspector-facts').boundingBox())!
  const capabilities = (await panel.locator('.inspector-capabilities').boundingBox())!
  const prose = (await panel.locator('.inspector-summary').boundingBox())!
  const integrations = panel.getByRole('group', { name: 'Record integrations' })
  const buttons = integrations.locator('button, a')
  const overview = (await panel.locator('.inspector-overview').boundingBox())!
  const integrationBounds = (await integrations.boundingBox())!
  expect(
    Math.abs(
      integrationBounds.y + integrationBounds.height / 2 - (overview.y + overview.height / 2),
    ),
  ).toBeLessThan(1)
  let previousBottom = facts.y
  for (const button of await buttons.all()) {
    const box = (await button.boundingBox())!
    expect(box.width).toBeGreaterThanOrEqual(44)
    expect(box.height).toBeGreaterThanOrEqual(44)
    expect(box.x).toBeGreaterThanOrEqual(facts.x + facts.width)
    expect(box.y).toBeGreaterThanOrEqual(previousBottom)
    previousBottom = box.y + box.height
    expect(
      await button
        .locator('img')
        .evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0),
    ).toBe(true)
  }
  expect(prose.y).toBeGreaterThanOrEqual(previousBottom)
  expect(capabilities.y).toBeGreaterThanOrEqual(facts.y + facts.height - 1)
  expect(prose.y).toBeGreaterThanOrEqual(capabilities.y + capabilities.height)
  await dockInViewport(page, panel)
  await page.screenshot({ path: `../artifacts/record-panel-${info.project.name}.png` })
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  expect(results.violations).toEqual([])
})

test('Gmail opens an unsent draft for the current record and its link reopens that record', async ({
  page,
}) => {
  const shareTitle = 'CRM & service / café + €'
  await fixture(page, { title: shareTitle })
  const panel = await preview(page)
  await expect(
    panel.getByRole('button', { name: 'Salesforce (coming soon)', exact: true }),
  ).toBeDisabled()
  await expect(
    panel.getByRole('button', { name: 'Slack (coming soon)', exact: true }),
  ).toBeDisabled()
  await page
    .context()
    .route('https://mail.google.com/**', (route) => route.fulfill({ body: 'Gmail compose' }))
  const opened = page.waitForEvent('popup')
  await panel
    .getByRole('link', { name: 'Share this opportunity in Gmail (opens a new tab)', exact: true })
    .click()
  const draft = await opened
  await expect(draft).toHaveURL(/^https:\/\/mail\.google\.com\/mail\//)
  const composeURL = new URL(draft.url())
  expect(composeURL.searchParams.get('su')).toBe(`Anthrion Signal: ${shareTitle}`)
  expect(composeURL.searchParams.has('to')).toBe(false)
  const body = composeURL.searchParams.get('body')!
  expect(body).toContain('VANGUARD LEARNING TRUST')
  expect(body).toContain('Source notice: https://example.com/tender/a')
  const recordURL = body
    .split('\n')
    .find((line) => line.startsWith('View in Anthrion Signal: '))!
    .slice('View in Anthrion Signal: '.length)
  await draft.close()
  await page.goto(recordURL)
  await expect(page.locator('.console-detail:visible .inspector-heading h2')).toHaveText(shareTitle)
  if (page.viewportSize()!.width <= 900)
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page.locator('.row-select').nth(1).click()
  const next = page.locator('.console-detail:visible')
  const nextURL = new URL(
    (await next
      .getByRole('link', { name: 'Share this opportunity in Gmail (opens a new tab)', exact: true })
      .getAttribute('href'))!,
  )
  expect(nextURL.searchParams.get('su')).toBe('Anthrion Signal: Customer platform implementation')
  expect(nextURL.searchParams.get('body')).toContain('signal=panel-b')
  expect(nextURL.searchParams.get('body')).toContain('Source notice: https://example.com/tender/b')
  expect(nextURL.searchParams.get('body')).not.toContain('signal=panel-a')
})

test('long records keep the dock visible before and after scrolling at compact and short sizes', async ({
  page,
}, info) => {
  await fixture(page, {
    title: `${title} ${title}`,
    buyer_name:
      'A public buyer with a long organisation name and multiple participating departments',
    description: Array.from(
      { length: 45 },
      (_, index) => `Paragraph ${index + 1}. ${description}`,
    ).join('\n\n'),
  })
  const sizes =
    info.project.name === 'desktop'
      ? [
          [997, 600],
          [980, 480],
          [1440, 400],
          [1139, 920],
          [1440, 720],
        ]
      : [
          [320, 568],
          [390, 844],
          [844, 390],
        ]
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width, height })
    const panel = await preview(page)
    const before = await dockInViewport(page, panel)
    const scroller = panel.locator('.inspector-scroll')
    await scroller.focus()
    await page.keyboard.press('PageDown')
    await expect.poll(() => scroller.evaluate((el) => el.scrollTop)).toBeGreaterThan(0)
    await scroller.evaluate((el) => el.scrollTo(0, el.scrollHeight))
    await expect(panel.locator('.inspector-summary p').last()).toBeInViewport()
    expect(await dockInViewport(page, panel)).toEqual(before)
    const last = (await panel.locator('.inspector-summary p').last().boundingBox())!
    expect(last.y + last.height).toBeLessThanOrEqual(before!.y)
    await expect(panel.getByRole('button', { name: 'Full details', exact: true })).toBeEnabled()
    await page.screenshot({ path: `../artifacts/record-panel-long-${width}x${height}.png` })
    await panel.getByRole('button', { name: 'Full details', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dockInViewport(page, dialog)
    await dialog.locator('.detail-content').evaluate((el) => el.scrollTo(0, el.scrollHeight))
    await dockInViewport(page, dialog)
    await dialog.getByRole('button', { name: 'Back to record' }).click()
    if (width <= 900) await expect(page.locator('.console-detail:visible')).toBeVisible()
    else await expect(dialog).toHaveCount(0)
  }
})

test('record actions open Google Calendar while save and hide remain in the results list', async ({
  page,
}) => {
  await fixture(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('./?view=live')
  const firstRow = page.locator('[data-signal-id="panel-a"]')
  await firstRow.getByRole('button', { name: 'Save opportunity in this browser' }).click()
  await expect(
    firstRow.getByRole('button', { name: 'Unsave opportunity', exact: true }),
  ).toBeVisible()
  const panel = await preview(page)
  await expect(panel.getByRole('button', { name: /save.*opportunity/i })).toHaveCount(0)
  await expect(panel.getByRole('checkbox')).toHaveCount(0)
  await page
    .context()
    .route('https://calendar.google.com/**', (route) =>
      route.fulfill({ body: 'Google Calendar event editor' }),
    )
  const calendarButton = panel.getByRole('link', {
    name: 'Add deadline to Google Calendar (opens a new tab)',
    exact: true,
  })
  const calendarBox = (await calendarButton.boundingBox())!
  const originalIcon = (await panel.locator('.inspector-facts dd > svg').first().boundingBox())!
  expect(calendarBox.width).toBe(originalIcon.width)
  expect(calendarBox.height).toBe(originalIcon.height)
  const deadline = panel.locator('.inspector-deadline')
  expect(calendarBox.x).toBe((await deadline.boundingBox())!.x)
  expect(calendarBox.x + calendarBox.width).toBeLessThan(
    (await deadline.locator('span').boundingBox())!.x,
  )
  expect(await calendarButton.evaluate((el) => getComputedStyle(el).borderWidth)).toBe('0px')
  const calendarOpened = page.waitForEvent('popup')
  await calendarButton.click()
  const calendar = await calendarOpened
  await expect(calendar).toHaveURL(/^https:\/\/calendar\.google\.com\/calendar\/r\/eventedit/)
  const calendarURL = new URL(calendar.url())
  expect(calendarURL.searchParams.get('text')).toBe(`Deadline for tender: ${title}`)
  expect(calendarURL.searchParams.get('dates')).toBe('20260914T110000Z/20260914T111500Z')
  expect(calendarURL.searchParams.get('details')).toContain(
    'Source notice: https://example.com/tender/a',
  )
  await calendar.close()
  await page
    .context()
    .route('https://example.com/tender/**', (route) => route.fulfill({ body: 'Source notice' }))
  const opened = page.waitForEvent('popup')
  await panel.getByRole('link', { name: 'Open source notice' }).click()
  const source = await opened
  await expect(source).toHaveURL('https://example.com/tender/a')
  await source.close()
  await panel.getByRole('button', { name: 'Full details', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('button', { name: /save.*opportunity|^Saved$/i })).toHaveCount(0)
  await expect(
    dialog.getByRole('link', {
      name: 'Add deadline to Google Calendar (opens a new tab)',
      exact: true,
    }),
  ).toHaveAttribute('href', calendarURL.href)
  await dialog.getByRole('tab', { name: 'Sources & timeline' }).click()
  await expect(dialog.getByRole('tabpanel')).toContainText('Source provenance')
  await dockInViewport(page, dialog)
  await dialog.getByRole('button', { name: 'Back to record' }).click()
  if (page.viewportSize()!.width <= 900)
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page.locator('.row-select').nth(1).click()
  const next = page.locator('.console-detail:visible')
  await expect(next.locator('.inspector-heading h2')).toHaveText('Customer platform implementation')
  await expect.poll(() => next.locator('.inspector-scroll').evaluate((el) => el.scrollTop)).toBe(0)
  await expect(next.getByRole('link', { name: 'Open source notice' })).toHaveAttribute(
    'href',
    'https://example.com/tender/b',
  )
  if (page.viewportSize()!.width <= 900)
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page
    .locator('[data-signal-id="panel-b"]')
    .getByRole('checkbox', { name: 'Hide Customer platform implementation', exact: true })
    .click()
  await expect(page.locator('[data-signal-id="panel-b"]')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('missing descriptions, capabilities and deadlines retain usable dock controls', async ({
  page,
}) => {
  await fixture(page, { description: '  \n ', deadline_at: null, matched_capabilities: [] })
  const panel = await preview(page)
  await expect(panel.locator('.inspector-facts')).toContainText('Deadline not published')
  await expect(
    panel.getByRole('link', {
      name: 'Add deadline to Google Calendar (opens a new tab)',
      exact: true,
    }),
  ).toHaveCount(0)
  await expect(panel.locator('.inspector-capabilities')).toContainText('Not specified')
  await expect(panel.locator('.inspector-summary')).toContainText('No description was published')
  await dockInViewport(page, panel)
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([])
})

test('capture the selected panel at its natural design dimensions', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', 'Reference is a desktop component')
  await fixture(page)
  await page.setViewportSize({ width: 1600, height: 1352 })
  await preview(page)
  await page.evaluate(() => document.fonts.ready)
  await page
    .locator('.console-inspector')
    .screenshot({ path: '../artifacts/record-panel-design.png' })
})
