import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { Dataset, HistoryRecord, Signal } from '../src/types'
import { recordDataset } from './fixtures/record'

const hash = 'abcdef0123456789'
const source = 'https://example.com/notices/customer-platform'
const title = 'Customer services platform and casework transformation'
const quote =
  'Implement Salesforce and integrate customer casework with the existing finance platform.'
const metadata = {
  schema_version: '2.0',
  generated_at: '2026-09-18T12:00:00Z',
  data_updated_at: '2026-09-18T12:00:00Z',
  profile_version: '1',
  scoring_version: '1',
  signals: [],
  translations: {},
  sources: [
    {
      id: 'find_a_tender',
      name: 'Find a Tender',
      enabled: true,
      status: 'healthy',
      website: 'https://example.com',
      last_attempt: null,
      last_success: null,
      records: 2,
      message: null,
    },
  ],
  capabilities: [
    {
      id: 'salesforce',
      label: 'Salesforce platform',
      family: 'CRM & platforms',
      search_terms: ['salesforce', 'kundenplattform'],
    },
    {
      id: 'service',
      label: 'Case management & service',
      family: 'Service transformation',
      search_terms: ['case management', 'fallmanagement'],
    },
  ],
  evidence_catalog: {},
  markets: { GB: { name: 'United Kingdom', enabled: true }, FR: { name: 'France', enabled: true } },
  run: {
    sources_attempted: 1,
    sources_succeeded: 1,
    raw_records: 2,
    new_signals: 2,
    material_updates: 0,
  },
} satisfies Dataset

async function fixture(page: Page, changeRecord?: (record: Signal) => void) {
  const dataset = recordDataset(metadata, {
    id: 'panel-a',
    title,
    buyer_name: 'Northbridge Council',
    buyer_id: 'buyer_northbridge',
    buyer_identity_basis: 'identifier',
    procedure_id: 'proc-2026',
    primary_source_url: source,
    description: `${quote}\n\nThe authority seeks a delivery partner for configuration, migration and support. Framework membership must be confirmed before bidding.`,
    deadline_at: '2026-11-20',
    response_deadlines: [],
    signal_type: 'LIVE_TENDER',
    matched_capabilities: ['salesforce', 'service'],
    amount: {
      kind: 'estimated_contract',
      minimum: 250000,
      maximum: 750000,
      currency: 'GBP',
      source_label: 'Estimated contract range',
      source_url: source,
    },
    deadlines: [
      {
        kind: 'questions',
        date: '2026-11-06',
        precision: 'date',
        source_text: 'Questions due 6 November',
        source_url: source,
        status: 'current',
      },
      {
        kind: 'tender',
        date: '2026-11-20',
        time: '14:00',
        timezone: 'Europe/London',
        precision: 'local_time',
        source_text: '20 November at 14:00 London',
        source_url: source,
        status: 'current',
      },
    ],
    capability_evidence: [
      {
        capability: 'salesforce',
        phrase: 'salesforce',
        strength: 'explicit',
        basis: 'original',
        field: 'description',
        quote,
        source_url: source,
        language: 'en',
        context: 'delivery',
        source_hash: 'source-v1',
        translated_quote:
          'Implement Salesforce and connect customer casework with the finance platform.',
      },
      {
        capability: 'service',
        phrase: 'casework',
        strength: 'needs',
        basis: 'original',
        field: 'description',
        quote,
        source_url: source,
        language: 'en',
        context: 'delivery',
        source_hash: 'source-v1',
      },
    ],
    delivery_role: { kind: 'direct_supplier', evidence: [] },
    participation_requirements: [
      {
        id: 'framework',
        requirement: 'Framework membership',
        status: 'needs_checking',
        source_quote: 'Framework membership must be confirmed before bidding.',
        source_url: source,
        company_evidence: null,
      },
    ],
    buyer_history_ref: {
      url: `buyers/buyer_northbridge-${hash}.json`,
      count: 55,
      identity_basis: 'identifier',
    },
    documents: [
      {
        title: 'Service specification',
        url: 'https://example.com/specification.pdf',
        kind: 'specification',
        status: 'cached',
        revision: '2',
        retrieved_at: '2026-09-18T12:00:00Z',
        page_count: 18,
        content_hash: 'revision-two',
        pages: [
          {
            page: 7,
            text: 'The supplier shall implement the case management workflow and preserve audit records.',
          },
        ],
        previous_revisions: [
          { content_hash: 'revision-one', revision: '1', retrieved_at: '2026-09-10T10:00:00Z' },
        ],
      },
    ],
    lots: [
      {
        id: '2',
        title: 'Customer platform implementation',
        description: 'Configuration and integration of the casework platform.',
        status: 'active',
        source_url: source,
      },
    ],
  })
  const record = dataset.signals[0]
  changeRecord?.(record)
  const summary = {
    ...record,
    is_summary: true,
    description: '',
    documents: [],
    capability_evidence: [],
    participation_requirements: [],
    search_text: `${record.title} ${record.description}`,
  }
  const other = {
    ...dataset.signals[1],
    deadline_at: '2026-11-20',
    countries: ['FR'],
    title: 'Portail citoyen',
    buyer_id: 'buyer_other',
    matched_capabilities: ['service'],
    amount: undefined,
    deadlines: [],
    search_text: 'Portail citoyen customer platform',
  }
  const manifest: Dataset = {
    ...metadata,
    current_feed: {
      version: '1.0',
      markets: {
        GB: { url: `current/GB-${hash}.json`, count: 1 },
        FR: { url: `current/FR-${hash}.json`, count: 1 },
      },
      records: {
        [record.id]: {
          url: `records/panel-a-${hash}.json`,
          markets: ['GB'],
          view: 'opportunities',
        },
        [other.id]: { url: `records/panel-b-${hash}.json`, markets: ['FR'], view: 'opportunities' },
      },
    },
    award_history: { GB: { url: `awards/GB-${hash}.json`, count: 2 } },
  }
  const awards: Signal[] = [
    {
      ...record,
      id: 'award-a',
      title: 'Customer platform implementation 2024',
      status: 'awarded',
      signal_type: 'AWARD',
      lifecycle_state: 'AWARDED',
      award_statuses: ['active'],
      related_signal_id: null,
      award_date: '2024-05-12',
      incumbent_supplier: 'Example Delivery Ltd',
      winners: [
        { name: 'Example Delivery Ltd', identifiers: [], lot_ids: ['2'], source_url: source },
      ],
      procedure_id: 'proc-2024',
      amount: {
        kind: 'award',
        maximum: 450000,
        minimum: null,
        currency: 'GBP',
        source_label: 'Award',
        source_url: source,
      },
    },
    {
      ...record,
      id: 'award-b',
      buyer_id: 'buyer_other',
      title: 'Case management renewal',
      status: 'awarded',
      signal_type: 'AWARD',
      lifecycle_state: 'AWARDED',
      award_statuses: ['active'],
      related_signal_id: null,
      award_date: '2025-03-12',
      incumbent_supplier: 'Another Supplier Ltd',
      procedure_id: 'proc-other',
    },
  ]
  const history: HistoryRecord[] = Array.from({ length: 55 }, (_, i) => ({
    signal_id: `history-${i}`,
    source: record.source,
    countries: record.countries,
    buyer_id: record.buyer_id,
    buyer_name: record.buyer_name,
    signal_type: 'AWARD',
    award_statuses: ['active'],
    procedure_id: `history-proc-${i}`,
    title: `Council digital service ${i + 1}`,
    status: 'awarded',
    source_url: `${source}?notice=${i}`,
    lot_ids: ['2'],
    published_at: '2024-05-11',
    award_date: '2024-05-12',
    supplier: `Winner ${i + 1} Ltd`,
    amount: {
      kind: 'award',
      maximum: 250000,
      minimum: null,
      currency: 'GBP',
      source_label: 'Award value',
      source_url: source,
    },
    contract_start: '2024-06-01',
    contract_end: '2027-06-01',
    lots: record.lots,
  }))
  history[1] = {
    ...history[1],
    supplier: '',
    winners: [],
    lots: [],
    lot_ids: [],
    amount: undefined,
    contract_start: undefined,
    contract_end: undefined,
  }
  await page.route('**/data/**', (route) => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/manifest.json')) return route.fulfill({ json: manifest })
    if (path.includes('/current/GB-'))
      return route.fulfill({ json: { schema_version: '1.0', signals: [summary] } })
    if (path.includes('/current/FR-'))
      return route.fulfill({ json: { schema_version: '1.0', signals: [other] } })
    if (path.includes('/records/panel-a-'))
      return route.fulfill({ json: { schema_version: '1.0', signal: record } })
    if (path.includes('/records/panel-b-'))
      return route.fulfill({ json: { schema_version: '1.0', signal: other } })
    if (path.includes('/awards/GB-'))
      return route.fulfill({ json: { schema_version: '1.0', signals: awards } })
    if (path.includes('/buyers/'))
      return route.fulfill({
        json: {
          schema_version: '1.0',
          buyer_id: record.buyer_id,
          buyer_name: record.buyer_name,
          identity_basis: 'identifier',
          records: history,
        },
      })
    return route.fulfill({ status: 404 })
  })
  return { record, manifest, history }
}
async function openRecord(page: Page) {
  await page.goto('./')
  await expect(page.locator('.row-select').first()).toBeVisible()
  if (page.viewportSize()!.width <= 900) await page.locator('.row-select').first().click()
  const panel = page.locator('.console-detail:visible')
  await expect(panel.getByRole('heading', { name: title })).toBeVisible()
  return panel
}
test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-09-18T12:00:00Z'))
  await fixture(page)
})

test('default summary selection loads full evidence and precise commercial facts', async ({
  page,
}, info) => {
  const requests: string[] = []
  page.on('request', (request) => requests.push(request.url()))
  const panel = await openRecord(page)
  await expect(panel.locator('.inspector-facts')).toContainText('Estimated contract value')
  await expect(panel.locator('.inspector-facts')).toContainText('14:00 Europe/London')
  if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
    await page.screenshot({ path: `../artifacts/research-overview-${info.project.name}.png` })
  await expect(panel.locator('.capability-tags')).toContainText('Salesforce platform')
  await expect(
    panel.locator('.capability-tags button, .evidence-sheet, .decision-brief, .original-notice'),
  ).toHaveCount(0)
  await expect(panel.locator('.inspector-summary')).toContainText(quote)
  await expect(page.locator('.row-numbers')).not.toContainText(['Estimated contract value'])
  expect(requests.some((url) => url.includes('/records/panel-a-'))).toBe(true)
  expect(requests.some((url) => url.includes('/current/FR-'))).toBe(false)
  await expect(page.getByRole('button', { name: /Mark working/ })).toHaveCount(0)
  if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
    await page.screenshot({
      path: `../artifacts/research-record-${info.project.name}.png`,
      fullPage: false,
    })
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([])
})

test('simplified record keeps the same response stage as its calendar', async ({ page }) => {
  await fixture(page, (record) => {
    const original = 'Implementieren Sie Salesforce und integrieren Sie die Kundenfallbearbeitung.'
    record.capability_evidence = [
      {
        ...record.capability_evidence![0],
        basis: 'english_translation',
        language: 'de',
        original_quote: original,
        translated_quote: quote,
      },
    ]
    record.deadlines = [
      { ...record.deadlines![1], kind: 'invited_submission', date: '2026-12-20' },
      { ...record.deadlines![1], kind: 'tender', date: '2026-11-20' },
      { ...record.deadlines![1], kind: 'expression_of_interest', date: '2026-10-05' },
    ]
  })
  const panel = await openRecord(page)
  await expect(panel.locator('.inspector-facts')).toContainText('Expressions of interest due')
  await expect(panel.locator('.inspector-facts')).toContainText('5 Oct 2026')
  await expect(
    panel.getByRole('link', {
      name: 'Add deadline to Google Calendar (opens a new tab)',
      exact: true,
    }),
  ).toHaveAttribute('href', /20261005T130000Z/)
  await expect(panel.locator('.decision-brief, .evidence-sheet')).toHaveCount(0)
})

test('document revisions and page-linked evidence remain source traceable', async ({ page }) => {
  await fixture(page, (record) => {
    record.provenance = [{ ...record.provenance[0], url: source }]
    record.documents.push({ title: 'Notice listing', url: source, kind: 'notice' })
  })
  const panel = await openRecord(page)
  await panel.getByRole('button', { name: 'Full details', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Opportunity intelligence' })
  await dialog.getByRole('tab', { name: 'Sources & timeline' }).click()
  await expect(dialog.locator('.source-document').first()).toContainText('Revision 2')
  await dialog.getByText('Read page evidence', { exact: true }).click()
  await expect(dialog.getByRole('link', { name: 'Page 7' })).toHaveAttribute(
    'href',
    'https://example.com/specification.pdf#page=7',
  )
  await expect(dialog.locator('.document-pages')).toContainText('preserve audit records')
  await expect(dialog.locator(`a[href="${source}"]`)).toHaveCount(1)
})

test('buyer page loads all collected history and restores the prior working view', async ({
  page,
}, info) => {
  const panel = await openRecord(page)
  await panel.getByRole('button', { name: 'View buyer history for Northbridge Council' }).click()
  const research = page.getByRole('dialog', { name: 'Buyer history' })
  await expect(research.locator('.research-hero')).toContainText('Northbridge Council')
  await expect(research.locator('.surface-heading').first()).toContainText('55 collected')
  await expect(research.locator('.research-timeline > li')).toHaveCount(50)
  await research.getByRole('button', { name: /Show more history/ }).click()
  await expect(research.locator('.research-timeline > li')).toHaveCount(55)
  const sparseRecord = research.locator('.research-timeline > li').nth(1)
  await expect(sparseRecord.locator('.award-winner, .history-contract')).toHaveCount(0)
  expect(await sparseRecord.innerText()).not.toMatch(/(?:^|\n)0(?:\n|$)/)
  await research.getByText('Contract & lot details').first().click()
  await expect(research.locator('.history-contract').first()).toContainText('2027')
  if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
    await page.screenshot({
      path: `../artifacts/research-buyer-${info.project.name}.png`,
      fullPage: false,
    })
  await research.getByRole('button', { name: 'Back to results' }).click()
  await expect(page.locator('.row-select').first()).toBeVisible()
  if (info.project.name === 'mobile')
    await expect(page.locator('.row-select').first()).toBeFocused()
  await expect(page.getByRole('button', { name: 'United Kingdom', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('buyer history links retained supplier awards outside the main feed and returns to the clicked row', async ({
  page,
}) => {
  const { history } = await fixture(page)
  history[52].supplier = history[0].supplier
  history[52].award_date = '2023-05-12'
  const panel = await openRecord(page)
  await panel.getByRole('button', { name: 'View buyer history for Northbridge Council' }).click()
  const buyer = page.getByRole('dialog', { name: 'Buyer history' })
  const company = buyer.getByRole('button', {
    name: 'View awarded contracts for Winner 1 Ltd',
    exact: true,
  })
  await expect(company).toHaveCount(1)
  await company.click()
  const supplier = page.getByRole('dialog', { name: 'Supplier history' })
  await expect(supplier.locator('.research-timeline > li')).toHaveCount(2)
  await expect(supplier.locator('.research-timeline')).toContainText('Council digital service 1')
  await expect(supplier.locator('.research-timeline')).toContainText('Council digital service 53')
  await expect(supplier.locator('.research-surface > .metal-edge')).toHaveCount(1)
  await expect(supplier.locator(`a[href="${source}?notice=0"]`)).toHaveCount(1)
  await supplier.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(company).toBeFocused()
  await expect(buyer.locator('.research-surface > .metal-edge')).toHaveCount(2)
})

test('label-only lots and repeated listing links collapse while separate historical sources remain', async ({
  page,
}) => {
  const { record, history } = await fixture(page)
  record.lot_ids = ['LOT-0001', 'LOT-0002']
  record.lots = record.lot_ids.map((id, i) => ({
    id,
    title: `Lot ${i + 1}`,
    description: '',
    status: 'unknown',
    source_url: `${source}#lot-${i + 1}`,
  }))
  record.procedure_history = [
    {
      signal_id: record.id,
      title,
      status: 'active',
      source_url: `${source}#history`,
      lot_ids: record.lot_ids,
      lots: record.lots,
    },
    {
      signal_id: record.id,
      title: '',
      status: 'unknown',
      source_url: 'https://other.example.org/notice/12',
      lot_ids: [],
    },
  ]
  history.splice(0, history.length, record.procedure_history[0], {
    ...history[0],
    lots: record.lots,
  })
  record.buyer_history_ref!.count = 2
  const panel = await openRecord(page)
  await panel.getByRole('button', { name: 'View buyer history for Northbridge Council' }).click()
  const buyer = page.getByRole('dialog', { name: 'Buyer history' })
  const selected = buyer.locator('.buyer-context > .research-surface').first()
  await expect(selected.locator('.lot-summary')).toHaveText('Lots LOT-0001 · LOT-0002')
  await expect(selected.locator('.lot-grid, .research-timeline')).toHaveCount(0)
  await expect(buyer.getByRole('heading', { name: 'Published lots', exact: true })).toHaveCount(0)
  await expect(buyer.locator(`a[href="${source}"]`)).toHaveCount(1)
  await expect(buyer.locator(`a[href="${source}?notice=0"]`)).toHaveCount(1)
  await expect(selected.locator('a[href="https://other.example.org/notice/12"]')).toHaveCount(1)
  await expect(buyer.locator('.research-page-header .glass-source-button')).toHaveCount(0)
  await expect(buyer.locator('.research-surface > .metal-edge')).toHaveCount(2)
})

test('title research compares source-linked awards with explicit relationship and filters', async ({
  page,
}, info) => {
  const panel = await openRecord(page)
  await panel.getByRole('button', { name: title, exact: true }).click()
  const research = page.getByRole('dialog', { name: 'Opportunity research' })
  await expect(research.locator('.related-award')).toHaveCount(2)
  await expect(research.locator('.related-award').first()).toContainText(
    'Same published buyer identifier',
  )
  await expect(research.locator('.related-award').last().locator('.award-reason')).toHaveText(
    'Salesforce platform · Case management & service',
  )
  await research.getByLabel('Supplier', { exact: true }).fill('Example Delivery')
  await expect(research.locator('.related-award')).toHaveCount(1)
  await research.getByLabel('Awarded from').fill('2025-01-01')
  await expect(research.getByText('No matching awards found')).toBeVisible()
  await research.getByRole('button', { name: 'Clear award filters' }).click()
  if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
    await page.screenshot({
      path: `../artifacts/research-comparison-${info.project.name}.png`,
      fullPage: false,
    })
})

test('last view remembers search and matching while shared URLs and UK startup stay predictable', async ({
  page,
}) => {
  await page.goto('./')
  await page.getByRole('textbox', { name: 'Search opportunities' }).fill('kundenplattform')
  await expect(page.locator('.row-select')).toHaveCount(1)
  await page.getByRole('combobox', { name: 'Search mode' }).selectOption('exact')
  await expect(page.getByText('No matching signals', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Search mode' }).selectOption('capability')
  await page.goto('./')
  await expect(page.getByRole('textbox', { name: 'Search opportunities' })).toHaveValue(
    'kundenplattform',
  )
  await expect(page.getByRole('button', { name: 'United Kingdom', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByText('Saved views', { exact: true })).toHaveCount(0)
  await page.goto('./?market=FR&view=all')
  await expect(page.getByRole('textbox', { name: 'Search opportunities' })).toHaveValue('')
  await expect(page.getByRole('button', { name: 'France', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.goto('./')
  await expect(page.getByRole('button', { name: 'United Kingdom', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('All leads UK; groups and individual countries can be pinned together and moved', async ({
  page,
}) => {
  await page.goto('./')
  await expect(page.locator('.market-tabs > button').nth(0)).toHaveAttribute(
    'aria-label',
    'All markets',
  )
  await expect(page.locator('.market-tabs > button').nth(1)).toHaveAttribute(
    'aria-label',
    'United Kingdom',
  )
  await expect(page.getByRole('button', { name: 'France', exact: true })).toBeAttached()
  await expect(page.getByRole('button', { name: 'Benelux', exact: true })).toBeAttached()
  await page.getByRole('button', { name: 'Organize markets' }).click()
  const organizer = page.getByRole('dialog', { name: 'Organize markets' })
  await expect(
    organizer.getByRole('checkbox', { name: 'Pin All markets', exact: true }),
  ).toBeChecked()
  for (const country of [
    'Germany',
    'Austria',
    'Switzerland',
    'Belgium',
    'Netherlands',
    'Luxembourg',
  ])
    await expect(
      organizer.getByRole('checkbox', { name: `Pin ${country}`, exact: true }),
    ).toHaveCount(1)
  await organizer.getByRole('checkbox', { name: 'Pin Belgium', exact: true }).check()
  await organizer.getByRole('checkbox', { name: 'Pin Germany', exact: true }).check()
  await organizer
    .getByRole('button', { name: 'Reorder All markets', exact: true })
    .press('ArrowDown')
  await organizer.getByRole('button', { name: 'Done', exact: true }).click()
  await page.reload()
  await expect(page.locator('.market-tabs > button').nth(0)).toHaveAttribute(
    'aria-label',
    'United Kingdom',
  )
  await expect(page.locator('.market-tabs > button').nth(1)).toHaveAttribute(
    'aria-label',
    'All markets',
  )
  for (const market of ['Belgium', 'Germany', 'DACH', 'Benelux'])
    await expect(page.getByRole('button', { name: market, exact: true })).toBeAttached()
  await page.getByRole('button', { name: 'All markets', exact: true }).click()
  await expect(page.locator('.row-select')).toHaveCount(2)
})

test('market dragging previews the drop and saves order without changing pins or selection', async ({
  page,
}, info) => {
  await page.goto('./')
  await page.getByRole('button', { name: 'Organize markets' }).click()
  const organizer = page.getByRole('dialog', { name: 'Organize markets' })
  const handle = organizer.getByRole('button', { name: 'Reorder All markets', exact: true })
  const from = (await handle.boundingBox())!
  const to = (await organizer.locator('[data-market-id="IT"]').boundingBox())!
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(from.x + from.width / 2, to.y + to.height - 3, { steps: 12 })
  await expect(organizer.locator('[data-market-id="NORDICS"]')).toHaveAttribute(
    'data-drop-before',
    'true',
  )
  await expect(organizer.locator('.market-drag-preview')).toContainText('All markets')
  if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
    await page.screenshot({ path: `../artifacts/market-drag-${info.project.name}.png` })
  await page.mouse.up()
  await expect(organizer.locator('.market-drag-preview')).toHaveCount(0)
  await expect(organizer.getByRole('listitem').nth(3)).toHaveAttribute('data-market-id', '')
  await expect(
    organizer.getByRole('checkbox', { name: 'Pin All markets', exact: true }),
  ).toBeChecked()
  await organizer.getByRole('button', { name: 'Done', exact: true }).click()
  await expect(page.getByRole('button', { name: 'United Kingdom', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.reload()
  await expect(page.locator('.market-tabs > button').nth(3)).toHaveAttribute(
    'aria-label',
    'All markets',
  )
  await expect(page.getByRole('button', { name: 'United Kingdom', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('market drag scrolls the list and Escape cancels without saving or closing the picker', async ({
  page,
}) => {
  await page.goto('./')
  await page.getByRole('button', { name: 'Organize markets' }).click()
  const organizer = page.getByRole('dialog', { name: 'Organize markets' })
  const list = organizer.getByRole('list', { name: 'Market order' })
  const handle = organizer.getByRole('button', { name: 'Reorder All markets', exact: true })
  const from = (await handle.boundingBox())!
  const bounds = (await list.boundingBox())!
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(from.x + from.width / 2, bounds.y + bounds.height - 2, { steps: 10 })
  await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(200)
  await page.keyboard.press('Escape')
  await page.mouse.up()
  await expect(organizer).toBeVisible()
  await expect(organizer.locator('.market-drag-preview')).toHaveCount(0)
  await expect(organizer.getByRole('listitem').first()).toHaveAttribute('data-market-id', '')
  await handle.press('End')
  await expect(organizer.getByRole('listitem').last()).toHaveAttribute('data-market-id', '')
  await expect(handle).toBeFocused()
  await handle.press('Home')
  await expect(organizer.getByRole('listitem').first()).toHaveAttribute('data-market-id', '')
  await expect(handle).toBeFocused()
  const result = await new AxeBuilder({ page }).include('.market-organizer').analyze()
  expect(result.violations).toEqual([])
})

test('touch can reorder a market and a cancelled touch leaves the order intact', async ({
  page,
  browserName,
}, info) => {
  test.skip(
    browserName !== 'chromium' || info.project.name !== 'mobile',
    'Chromium mobile touch protocol check',
  )
  await page.goto('./')
  await page.getByRole('button', { name: 'Organize markets' }).click()
  const organizer = page.getByRole('dialog', { name: 'Organize markets' })
  const touch = await page.context().newCDPSession(page)
  const from = (await organizer
    .getByRole('button', { name: 'Reorder All markets', exact: true })
    .boundingBox())!
  const to = (await organizer.locator('[data-market-id="GB"]').boundingBox())!
  const x = from.x + from.width / 2
  const y = from.y + from.height / 2
  const end = to.y + to.height - 3
  await touch.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] })
  await touch.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: end }] })
  await expect(organizer.locator('.market-drag-preview')).toBeVisible()
  await touch.send('Input.dispatchTouchEvent', { type: 'touchCancel', touchPoints: [] })
  await expect(organizer.locator('.market-drag-preview')).toHaveCount(0)
  await expect(organizer.getByRole('listitem').first()).toHaveAttribute('data-market-id', '')
  await touch.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] })
  await touch.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: end }] })
  await expect(organizer.locator('[data-market-id="US"]')).toHaveAttribute(
    'data-drop-before',
    'true',
  )
  await touch.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await expect(organizer.getByRole('listitem').nth(1)).toHaveAttribute('data-market-id', '')
  await expect(
    organizer.getByRole('checkbox', { name: 'Pin All markets', exact: true }),
  ).toBeChecked()
  await touch.detach()
})

test('All and grouped markets can be unpinned and remain selectable from More', async ({
  page,
}) => {
  await page.goto('./')
  await page.getByRole('button', { name: 'Organize markets' }).click()
  const organizer = page.getByRole('dialog', { name: 'Organize markets' })
  for (const name of ['All markets', 'Benelux', 'France'])
    await organizer.getByRole('checkbox', { name: `Pin ${name}`, exact: true }).uncheck()
  await organizer.getByRole('button', { name: 'Done', exact: true }).click()
  await page.reload()
  await expect(
    page.locator('.market-tabs').getByRole('button', { name: 'All markets', exact: true }),
  ).toHaveCount(0)
  await page.locator('.more-markets-trigger').click()
  const menu = page.getByRole('menu', { name: 'More markets' })
  for (const name of ['All markets', 'Benelux', 'France', 'Belgium'])
    await expect(menu.getByRole('menuitemradio', { name, exact: true })).toBeAttached()
  await menu.getByRole('menuitemradio', { name: 'All markets', exact: true }).click()
  await expect(page.locator('.row-select')).toHaveCount(2)
  await expect(page.locator('.more-markets-trigger')).toContainText('All markets')
})

test('nested buyer and supplier timelines return to the same Context filters and focus', async ({
  page,
}) => {
  const panel = await openRecord(page)
  await panel.getByRole('button', { name: title, exact: true }).click()
  const context = page.getByRole('dialog', { name: 'Opportunity research' })
  await expect(context.getByRole('heading', { name: 'Context', exact: true })).toBeVisible()
  await expect(context.locator('.research-current > .metal-edge')).toHaveCount(1)
  await expect(context.locator('.research-surface > .metal-edge')).toHaveCount(2)
  await expect(context.locator('.decision-brief, .original-notice, .evidence-sheet')).toHaveCount(0)
  await expect(context.locator('.research-description')).toContainText(quote)
  await expect(context.locator('.workspace-brand img')).toHaveAttribute('src', /anthrion-logo.svg$/)
  await context.getByLabel('Supplier', { exact: true }).fill('Example Delivery')
  const winner = context.getByRole('button', {
    name: 'View awarded contracts for Example Delivery Ltd',
  })
  await winner.click()
  const supplier = page.getByRole('dialog', { name: 'Supplier history' })
  await expect(
    supplier.getByRole('heading', { name: 'Example Delivery Ltd', exact: true }),
  ).toBeVisible()
  await expect(supplier.locator('.research-timeline > li')).toHaveCount(1)
  await supplier.getByRole('button', { name: 'View buyer history for Northbridge Council' }).click()
  const buyer = page.getByRole('dialog', { name: 'Buyer history' })
  await expect(buyer.locator('.surface-heading').first()).toContainText('55 collected')
  await buyer.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(supplier).toBeVisible()
  await supplier.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(context.getByLabel('Supplier', { exact: true })).toHaveValue('Example Delivery')
  await expect(winner).toBeFocused()
  await expect(context.locator('.related-award')).toHaveCount(1)
  await context
    .locator('.related-award')
    .getByRole('button', { name: 'View buyer history for Northbridge Council' })
    .click()
  await expect(buyer).toBeVisible()
})

test('awarded supplier links work from the main record and its full details', async ({ page }) => {
  await page.goto('./?view=awards')
  await page
    .locator('.row-select')
    .filter({ hasText: 'Customer platform implementation 2024' })
    .click()
  const panel = page.locator('.console-detail:visible')
  await panel
    .getByRole('button', { name: 'View awarded contracts for Example Delivery Ltd' })
    .click()
  await expect(
    page.getByRole('dialog', { name: 'Supplier history' }).locator('.research-timeline > li'),
  ).toHaveCount(1)
})

test('slow details stay in a loading state before source research can open', async ({
  page,
}, info) => {
  let release = () => {}
  const pending = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/data/records/panel-a-*', async (route) => {
    await pending
    await route.fallback()
  })
  await page.goto('./')
  await expect(page.locator('.row-select').first()).toBeVisible()
  if (info.project.name === 'mobile') await page.locator('.row-select').first().click()
  const record =
    info.project.name === 'mobile'
      ? page.getByRole('dialog', { name: 'Opportunity intelligence' })
      : page.locator('.console-inspector')
  await expect(record.getByText('Loading full record…')).toBeVisible()
  await expect(record.getByRole('button', { name: title, exact: true })).toHaveCount(0)
  release()
  await expect(record.getByRole('button', { name: title, exact: true })).toBeVisible()
  await record.getByRole('button', { name: 'View buyer history for Northbridge Council' }).click()
  await expect(
    page.getByRole('dialog', { name: 'Buyer history' }).locator('.surface-heading').first(),
  ).toContainText('55 collected')
})

test('an open research page updates source and translation together after a delayed revision', async ({
  page,
}) => {
  const { record, manifest } = await fixture(page)
  const panel = await openRecord(page)
  await panel.getByRole('button', { name: title, exact: true }).click()
  const research = page.getByRole('dialog', { name: 'Opportunity research' })
  await expect(research.locator('.research-current h2')).toHaveText(title)
  const revised = {
    ...record,
    title: 'Original title revision two',
    description: 'Version two original source description.',
    capability_evidence: [
      {
        ...record.capability_evidence![0],
        quote: 'Version two source scope.',
        source_hash: 'source-v2',
      },
    ],
  }
  const english = {
    source_hash: 'source-v2',
    version: 'v2',
    title: 'Updated English title',
    description: 'Updated English description',
  }
  const nextHash = 'fedcba9876543210'
  await page.route('**/data/manifest.json', (route) =>
    route.fulfill({
      json: {
        ...manifest,
        current_feed: {
          ...manifest.current_feed,
          markets: {
            ...manifest.current_feed!.markets,
            GB: { url: `current/GB-${nextHash}.json`, count: 1 },
          },
          records: {
            ...manifest.current_feed!.records,
            [record.id]: {
              url: `records/${record.id}-${nextHash}.json`,
              markets: ['GB'],
              view: 'opportunities',
            },
          },
        },
      },
    }),
  )
  await page.route(`**/data/current/GB-${nextHash}.json`, (route) =>
    route.fulfill({
      json: {
        schema_version: '1.0',
        signals: [
          { ...revised, is_summary: true, description: '', search_text: revised.description },
        ],
        translations: { [record.id]: english },
      },
    }),
  )
  let release = () => {}
  const pending = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(`**/data/records/${record.id}-${nextHash}.json`, async (route) => {
    await pending
    await route.fulfill({ json: { schema_version: '1.0', signal: revised, translation: english } })
  })
  await page.evaluate(() =>
    document.querySelector<HTMLButtonElement>('[aria-label="Check for updates"]')!.click(),
  )
  await expect(page.locator('.console-inspector')).toContainText('Loading full record…')
  await expect(research.locator('.research-current h2')).toHaveText(title)
  await expect(research.locator('.research-description')).toContainText(quote)
  release()
  await expect(research.locator('.research-current h2')).toHaveText(english.title)
  await expect(research.locator('.research-description')).toContainText(english.description)
  await expect(research.locator('.original-notice')).toHaveCount(0)
})

test('direct record links load the requested country before choosing a default row', async ({
  page,
}) => {
  await page.goto('./?signal=panel-b')
  await expect(page.locator('.console-detail:visible h2')).toHaveText('Portail citoyen')
  await expect(page).toHaveURL(/market=FR/)
  await expect(page.getByRole('button', { name: 'France', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(
    page.getByText('This opportunity is no longer available', { exact: true }),
  ).toHaveCount(0)
})

test('More markets exposes individual countries with hover and keyboard navigation', async ({
  page,
}) => {
  await page.goto('./')
  const trigger = page.locator('.more-markets-trigger')
  await trigger.focus()
  await trigger.press('ArrowDown')
  const menu = page.getByRole('menu', { name: 'More markets' })
  await expect(menu).toBeVisible()
  await expect(menu.getByRole('menuitemradio', { name: 'Benelux', exact: true })).toHaveCount(0)
  await expect(
    menu.getByRole('menuitemradio', {
      name: /^(Germany|Austria|Switzerland|Belgium|Netherlands|Luxembourg)$/,
    }),
  ).toHaveCount(6)
  await page.keyboard.press('End')
  await expect(menu.getByRole('menuitemradio').last()).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(menu).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await trigger.hover()
  await expect(menu).toBeVisible()
})

test('record separator supports keyboard resizing, persistence and compact reading', async ({
  page,
}, info) => {
  test.skip(info.project.name !== 'desktop', 'Desktop has resizable side-by-side panes.')
  await openRecord(page)
  const separator = page.getByRole('separator', { name: 'Resize record pane' })
  await separator.focus()
  await separator.press('ArrowLeft')
  await expect(separator).toHaveAttribute('aria-valuenow', '48')
  await page.getByRole('button', { name: 'Compact reading mode', exact: true }).click()
  await expect(page.locator('.compact-refiners')).toBeVisible()
  await page.reload()
  await expect(separator).toHaveAttribute('aria-valuenow', '48')
  await expect(page.locator('.compact-refiners')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const handle = (await separator.boundingBox())!
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2)
  await page.mouse.down()
  await page.mouse.move(handle.x + 85, handle.y + handle.height / 2)
  await page.mouse.up()
  await expect
    .poll(async () => Number(await separator.getAttribute('aria-valuenow')))
    .toBeGreaterThan(48)
  await separator.press('End')
  await page.setViewportSize({ width: 950, height: 760 })
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true)
  await expect(page.locator('.console-inspector')).toBeVisible()
  await page.setViewportSize({ width: 720, height: 525 })
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true)
})

test('long source records retain readable widths and dock actions in compact and 200%-equivalent viewports', async ({
  page,
}, info) => {
  test.skip(info.project.name !== 'desktop', 'Reflow is exercised once from a desktop workspace.')
  await fixture(page, (record) => {
    record.title = `${title} with regional departments, shared services and cross-agency integration`
    record.buyer_name =
      'Landesbetrieb für Informationstechnik und Digitalisierung der regionalen öffentlichen Verwaltung'
    record.description = Array.from({ length: 8 }, () => record.description).join('\n\n')
  })
  for (const [width, height] of [
    [1280, 720],
    [901, 600],
    [720, 450],
  ]) {
    await page.setViewportSize({ width, height })
    await page.goto('./')
    await expect(page.locator('.row-select').first()).toBeVisible()
    const compact = page.getByRole('button', { name: 'Compact reading mode', exact: true })
    if (await compact.count()) await compact.click()
    expect((await page.locator('.discovery-band').boundingBox())!.height).toBeLessThan(90)
    if (width <= 900) await page.locator('.row-select').first().click()
    const panel = page.locator('.console-detail:visible')
    await expect(panel).toBeVisible()
    const dock = panel.locator('.record-action-dock')
    await expect(dock.getByRole('button', { name: 'Full details', exact: true })).toBeInViewport()
    await expect(
      dock.getByRole('link', { name: 'Open source notice', exact: true }),
    ).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    if (process.env.SIGNAL_CAPTURE_DESIGN === 'true')
      await page.screenshot({ path: `../artifacts/research-long-${width}x${height}.png` })
  }
})
