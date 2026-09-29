import { datasetFixture } from './fixtures/dataset'
import { test, expect, type Locator, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { Dataset, Signal } from '../src/types'
import {
  recordDataset,
  recordTitle as title,
  recordDescription as description,
} from './fixtures/record'

async function fixture(page: Page, overrides: Partial<Signal> = {}) {
  const dataset: Dataset = datasetFixture()
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
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-09-11T12:00:00Z'))
})

test('selected design presents compact source facts before untruncated text in one scroll, with Brief reading as a menu preference', async ({
  page,
}, info) => {
  await fixture(page)
  const panel = await preview(page)
  const paragraphs = description.split('\n\n')
  await expect(panel.locator('.inspector-facts dt')).toHaveText([
    'Notice type',
    'Published amount',
    'Deadline',
  ])
  await expect(panel.locator('.inspector-capabilities')).toContainText('Case management & service')
  // Full text is the default Reading preference: the whole description, with nothing to expand.
  await expect(panel.locator('.inspector-summary p')).toHaveText(paragraphs)
  await expect(panel.getByRole('button', { name: 'Full text', exact: true })).toHaveCount(0)
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
  expect(
    await buttons.evaluateAll((controls) => controls.map((el) => el.getAttribute('aria-label'))),
  ).toEqual([
    'Salesforce prefill unavailable',
    'Share this opportunity in Gmail (opens a new tab)',
    'Slack (coming soon)',
    'Copy link to this opportunity',
  ])
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
  }
  // The three services show their logos; Copy link is a drawn icon.
  const logos = integrations.locator('img')
  await expect(logos).toHaveCount(3)
  for (const logo of await logos.all())
    await expect
      .poll(() => logo.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0))
      .toBe(true)
  await expect(
    integrations.getByRole('button', { name: 'Copy link to this opportunity' }).locator('svg'),
  ).toBeVisible()
  expect(prose.y).toBeGreaterThanOrEqual(previousBottom)
  expect(capabilities.y).toBeGreaterThanOrEqual(facts.y + facts.height - 1)
  expect(prose.y).toBeGreaterThanOrEqual(capabilities.y + capabilities.height)
  // One complete record: the source history follows the description in the same scroll.
  const history = panel.locator('.inspector-scroll .record-history')
  await expect(history.locator('summary')).toHaveText('Source history')
  expect((await history.boundingBox())!.y).toBeGreaterThanOrEqual(prose.y + prose.height)
  await dockInViewport(page, panel)
  if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
    await page.screenshot({ path: `../artifacts/record-panel-${info.project.name}.png` })
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  expect(results.violations).toEqual([])
  // Brief reading is chosen in the workspace menu and persists: the record opens with the first
  // passage, and Full text restores the complete description.
  if (page.viewportSize()!.width <= 900)
    await page.getByRole('button', { name: 'Close panel' }).click()
  await page.getByRole('button', { name: 'Workspace menu', exact: true }).click()
  const menu = page.getByRole('dialog', { name: 'Workspace' })
  await menu
    .getByRole('radiogroup', { name: 'Reading' })
    .getByRole('radio', { name: 'Brief' })
    .click()
  await menu.getByRole('button', { name: 'Close workspace menu' }).click()
  const brief = await preview(page)
  await expect(brief.locator('.inspector-summary p')).toHaveText([paragraphs[0]])
  await brief.getByRole('button', { name: 'Full text', exact: true }).click()
  await expect(brief.locator('.inspector-summary p')).toHaveText(paragraphs)
})

test('@pr Gmail opens an unsent draft for the current record and its link reopens that record', async ({
  page,
}) => {
  const shareTitle = 'CRM & service / café + €'
  await fixture(page, { title: shareTitle })
  const panel = await preview(page)
  await expect(
    panel.getByRole('button', { name: 'Salesforce prefill unavailable', exact: true }),
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
      .getByRole('link', {
        name: 'Share this opportunity in Gmail (opens a new tab)',
        exact: true,
      })
      .getAttribute('href'))!,
  )
  expect(nextURL.searchParams.get('su')).toBe('Anthrion Signal: Customer platform implementation')
  expect(nextURL.searchParams.get('body')).toContain('signal=panel-b')
  expect(nextURL.searchParams.get('body')).toContain('Source notice: https://example.com/tender/b')
  expect(nextURL.searchParams.get('body')).not.toContain('signal=panel-a')
})

test('@pr Salesforce opens a reviewable sandbox draft with tender fields and follows Original in full details', async ({
  page,
}) => {
  const id = 'sig_1234567890abcdef1234'
  const data = recordDataset(datasetFixture(), {
    id,
    title: 'Système de workflow',
    buyer_name: 'WM5G LIMITED',
    description: 'Configurer le système.',
    countries: ['CA'],
    source_language: 'fr',
    value_max: 450000,
    currency: 'CAD',
    deadline_at: '2099-01-01',
    reviewed_guidance: {
      source_hash: 'fixture',
      complexity: 4,
      problem_level: 1,
      original_language: 'fr',
      approach: [{ text: 'Configure Service Cloud flows.' }],
      problems: [],
      localized: {
        fr: { approach: [{ text: 'Configurer les flux Service Cloud.' }], problems: [] },
      },
    },
  })
  data.translations = {
    [id]: {
      source_hash: 'fixture',
      version: 'en-procurement-2',
      title: 'Workflow management system',
      description: 'Configure the system.',
    },
  }
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto(`./?view=all&market=&signal=${id}`)
  const panel = page.locator('.console-detail:visible')
  const salesforce = panel.getByRole('link', {
    name: 'Review lead in Salesforce sandbox (opens a new tab)',
    exact: true,
  })
  await expect(salesforce).toBeVisible()
  await page
    .context()
    .route('https://anthrion--aitender.sandbox.lightning.force.com/**', (route) =>
      route.fulfill({ body: 'Unsaved Salesforce draft' }),
    )
  const opened = page.waitForEvent('popup')
  await salesforce.click()
  const popup = await opened
  await expect(popup).toHaveURL(
    /^https:\/\/anthrion--aitender\.sandbox\.lightning\.force\.com\/lightning\/o\/Lead\/new\?/,
  )
  function fields(href: string) {
    return Object.fromEntries(
      new URL(href).searchParams
        .get('defaultFieldValues')!
        .split(',')
        .map((pair) => {
          const split = pair.indexOf('=')
          return [pair.slice(0, split), decodeURIComponent(pair.slice(split + 1))]
        }),
    )
  }
  const draft = fields(popup.url())
  expect(draft).toMatchObject({
    Lead_Name__c: 'Workflow management system, WM5G LIMITED',
    Expected_Value__c: 'CA$450,000',
    Response_Deadline__c: '2099-01-01',
    FirstName: '',
    LastName: 'WM5G LIMITED',
    Title: 'Workflow management system',
    Industry__c: 'Technology',
    Sector__c: 'Software and Services',
    CurrencyIsoCode: 'USD',
    Anthrion_Signal_ID__c: id,
    Technology__c: 'Recommended approach:\nConfigure Service Cloud flows.',
  })
  expect(draft).not.toHaveProperty('Tender_Currency__c')
  expect(draft.Description).toContain('450,000 CAD')
  expect(draft.Description).toContain('Published CAD amounts have not been converted.')
  expect(draft.Description.indexOf('Published amount:')).toBeLessThan(
    draft.Description.indexOf('Notice type:'),
  )
  await popup.close()
  await panel.locator('.inspector-heading .research-title-link').click()
  const context = page.getByRole('dialog', { name: 'Opportunity research' })
  await context.getByRole('button', { name: 'Record language: English' }).click()
  await context.getByRole('menuitemradio', { name: 'Original', exact: true }).click()
  await context.locator('.research-current .record-title-link').click()
  const full = page.getByRole('dialog', { name: 'Full record', exact: true })
  const originalLink = full.getByRole('link', { name: /Review lead in Salesforce/ })
  await expect(originalLink).toBeVisible()
  const original = fields((await originalLink.getAttribute('href'))!)
  expect(original.Title).toBe('Système de workflow')
  expect(original.Technology__c).toContain('Configurer les flux Service Cloud.')
  expect(original.Anthrion_Signal_ID__c).toBe(id)
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
    const before = (await dockInViewport(page, panel))!
    const scroller = panel.locator('.inspector-scroll')
    await scroller.focus()
    await page.keyboard.press('PageDown')
    await expect.poll(() => scroller.evaluate((el) => el.scrollTop)).toBeGreaterThan(0)
    // The record is one scroll that ends with its source history, readable above the dock.
    await scroller.evaluate((el) => el.scrollTo(0, el.scrollHeight))
    const history = panel.locator('.record-history')
    await expect(history).toBeInViewport()
    expect(await dockInViewport(page, panel)).toEqual(before)
    const end = (await history.boundingBox())!
    expect(end.y + end.height).toBeLessThanOrEqual(before.y)
    // The dock names the source and when it was checked, and opens the source history in place.
    const source = panel
      .locator('.record-action-dock')
      .getByRole('button', { name: /^Find a Tender/ })
    await expect(source).toContainText(/Find a Tender\s*checked 11 Sept/)
    await expect(source).toBeEnabled()
    if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
      await page.screenshot({ path: `../artifacts/record-panel-long-${width}x${height}.png` })
    await source.click()
    await expect(history).toHaveAttribute('open', '')
    await expect(history.locator('.provenance-list')).toContainText('Reference panel-notice')
    await expect(page.getByRole('dialog')).toHaveCount(width <= 900 ? 1 : 0)
    expect(await dockInViewport(page, panel)).toEqual(before)
    await scroller.evaluate((el) => el.scrollTo(0, el.scrollHeight))
    const openedEnd = (await history.boundingBox())!
    expect(openedEnd.height).toBeGreaterThan(end.height)
    expect(openedEnd.y + openedEnd.height).toBeLessThanOrEqual(before.y)
    expect(await dockInViewport(page, panel)).toEqual(before)
  }
})

test('record actions open Google Calendar and the source history, an opened record can be saved, and hide stays in the results list', async ({
  page,
}) => {
  await fixture(page)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('./?view=live')
  const narrow = page.viewportSize()!.width <= 900
  const saved = () => page.evaluate(() => localStorage.getItem('anthrion-saved-v1'))
  const firstRow = page.locator('[data-signal-id="panel-a"]')
  await firstRow.getByRole('button', { name: 'Save opportunity in this browser' }).click()
  await expect(
    firstRow.getByRole('button', { name: 'Unsave opportunity', exact: true }),
  ).toBeVisible()
  const panel = await preview(page)
  // The opened record shares the results list's saved state and can change it.
  if (narrow) {
    const drawer = page.getByRole('dialog')
    await drawer.getByRole('button', { name: 'Unsave opportunity', exact: true }).click()
    await expect.poll(saved).toBe('[]')
    await drawer
      .getByRole('button', { name: 'Save opportunity in this browser', exact: true })
      .click()
    await expect(
      drawer.getByRole('button', { name: 'Unsave opportunity', exact: true }),
    ).toBeVisible()
  } else {
    // Beside the list, the selected record is saved with its row's button or the S shortcut.
    await page.keyboard.press('s')
    await expect(
      firstRow.getByRole('button', { name: 'Save opportunity in this browser', exact: true }),
    ).toBeVisible()
    await expect.poll(saved).toBe('[]')
    await page.keyboard.press('s')
    await expect(
      firstRow.getByRole('button', { name: 'Unsave opportunity', exact: true }),
    ).toBeVisible()
  }
  await expect.poll(saved).toBe('["panel-a"]')
  const record = narrow ? page.getByRole('dialog') : panel
  await expect(record.getByRole('button', { name: /^(Hide|Unhide) / })).toHaveCount(0)
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
  // The dock's source button opens the source history within the record and brings it into view.
  const history = panel.locator('.record-history')
  await expect(history).not.toHaveAttribute('open')
  await panel
    .locator('.record-action-dock')
    .getByRole('button', { name: /^Find a Tender/ })
    .click()
  await expect(history).toHaveAttribute('open', '')
  const provenance = history.locator('.provenance-list')
  await expect(provenance).toContainText('Find a Tender')
  await expect(provenance).toContainText('Reference panel-notice')
  await expect(provenance).toBeInViewport({ ratio: 1 })
  await dockInViewport(page, panel)
  if (narrow) {
    await page.getByRole('button', { name: 'Close panel' }).click()
    await expect(
      firstRow.getByRole('button', { name: 'Unsave opportunity', exact: true }),
    ).toBeVisible()
  }
  await page.locator('.row-select').nth(1).click()
  const next = page.locator('.console-detail:visible')
  await expect(next.locator('.inspector-heading h2')).toHaveText('Customer platform implementation')
  await expect.poll(() => next.locator('.inspector-scroll').evaluate((el) => el.scrollTop)).toBe(0)
  await expect(next.locator('.record-history')).not.toHaveAttribute('open')
  await expect(next.getByRole('link', { name: 'Open source notice' })).toHaveAttribute(
    'href',
    'https://example.com/tender/b',
  )
  if (narrow) await page.getByRole('button', { name: 'Close panel' }).click()
  await page
    .locator('[data-signal-id="panel-b"]')
    .getByRole('button', { name: 'Hide Customer platform implementation', exact: true })
    .click()
  await expect(page.locator('[data-signal-id="panel-b"]')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('@pr missing descriptions, capabilities and deadlines retain usable dock controls', async ({
  page,
}) => {
  await fixture(page, { description: '  \n ', deadline_at: null, matched_capabilities: [] })
  const panel = await preview(page)
  await expect(panel.locator('.inspector-facts')).toContainText('Not published')
  await expect(
    panel.getByRole('link', {
      name: 'Add deadline to Google Calendar (opens a new tab)',
      exact: true,
    }),
  ).toHaveCount(0)
  await expect(panel.locator('.inspector-capabilities')).toHaveCount(0)
  await expect(panel.locator('.inspector-summary')).toContainText('No description was published')
  await dockInViewport(page, panel)
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([])
})
