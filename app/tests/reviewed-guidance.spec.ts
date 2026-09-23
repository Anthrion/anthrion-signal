import { expect, test, type Locator, type Page } from '@playwright/test'
import { datasetFixture } from './fixtures/dataset'

const englishApproach =
  'Configure Salesforce case workflows and connect the existing systems through published APIs.'
const englishProblem = 'The bidder must hold the published ISO 27001 certification.'
const examples = [
  {
    country: 'DE',
    sourceLanguage: 'und',
    originalLanguage: 'de',
    code: 'de',
    title: 'Kundenplattform und Integration',
    description:
      'Gesucht wird eine Kundenplattform mit Schnittstellen. Der Bieter muss ISO 27001 nachweisen.',
    approach:
      'Salesforce-Fallprozesse konfigurieren und die bestehenden Systeme über veröffentlichte APIs anbinden.',
    problem: 'Der Bieter muss die veröffentlichte Zertifizierung ISO 27001 nachweisen.',
  },
  {
    country: 'CA',
    sourceLanguage: 'fra',
    originalLanguage: undefined,
    code: 'fr',
    title: 'Plateforme de gestion des demandes',
    description:
      'Une plateforme avec des interfaces est requise. Le soumissionnaire doit détenir la certification ISO 27001.',
    approach:
      'Configurer les processus de dossier Salesforce et relier les systèmes existants par les API publiées.',
    problem: 'Le soumissionnaire doit détenir la certification ISO 27001 publiée.',
  },
]

async function chooseLanguage(scope: Locator, label: 'English' | 'Original') {
  await scope.getByRole('button', { name: /^Record language:/ }).click()
  await scope.getByRole('menuitemradio', { name: label, exact: true }).click()
}

async function inspector(page: Page) {
  if (page.viewportSize()!.width <= 900 && !new URL(page.url()).searchParams.has('signal'))
    await page.locator('.row-select').click()
  const panel = page.locator('.console-detail:visible')
  await expect(panel.locator('.recommended-approach')).toBeVisible()
  return panel
}

for (const example of examples) {
  test(`@pr ${example.country} guidance follows persisted English/Original in the inspector, full details and Context`, async ({
    page,
  }) => {
    const data = datasetFixture()
    data.signals = [
      {
        ...data.signals[0],
        id: 'reviewed-localized-lead',
        title: example.title,
        description: example.description,
        countries: [example.country],
        source_language: example.sourceLanguage,
        signal_type: 'LIVE_TENDER',
        lifecycle_state: 'OPEN',
        status: 'active',
        deadline_at: '2099-01-01T00:00:00Z',
        response_deadlines: [],
        deadlines: [],
        exclusion_reasons: [],
        lot_ids: ['LOT-0002'],
        reviewed_guidance: {
          source_hash: 'a'.repeat(64),
          approach: [{ text: englishApproach, lot_id: 'LOT-0002' }],
          problems: [{ text: englishProblem, lot_id: 'LOT-0002' }],
          complexity: 6,
          problem_level: 3,
          original_language: example.originalLanguage,
          localized: {
            [example.code]: {
              approach: [{ text: example.approach, lot_id: 'LOT-0002' }],
              problems: [{ text: example.problem, lot_id: 'LOT-0002' }],
            },
          },
        },
      },
    ]
    data.translations = {
      'reviewed-localized-lead': {
        source_hash: 'fixture',
        version: 'en-procurement-2',
        title: 'Customer platform and integration',
        description:
          'A customer platform with interfaces is required. The bidder must hold ISO 27001 certification.',
      },
    }
    const providerRequests: string[] = []
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    page.on('request', (request) => {
      if (/generativelanguage|translate\.googleapis/.test(request.url()))
        providerRequests.push(request.url())
    })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
    await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
    await page.goto(`./?market=${example.country}&view=all`)
    let panel = await inspector(page)
    await expect(panel.locator('.recommended-approach')).toContainText(englishApproach)
    await expect(panel.locator('.recommended-approach')).not.toContainText(example.approach)
    if (page.viewportSize()!.width <= 900)
      await page.getByRole('button', { name: 'Close panel' }).click()

    await chooseLanguage(page.locator('body'), 'Original')
    await page.reload()
    await expect(page.getByRole('button', { name: 'Record language: Original' })).toBeVisible()
    panel = await inspector(page)
    const checkOriginal = async (scope: Locator) => {
      const guidance = scope.locator('.recommended-approach')
      await expect(guidance).toContainText(example.approach)
      await expect(guidance).toContainText(example.problem)
      await expect(guidance).toContainText('Lot 0002:')
      await expect(guidance).not.toContainText(englishApproach)
      await expect(guidance.locator('p').first()).toHaveAttribute('lang', example.code)
    }
    await checkOriginal(panel)
    await panel.getByRole('button', { name: 'Full details', exact: true }).click()
    const details = page.getByRole('dialog', { name: 'Opportunity intelligence' })
    await checkOriginal(details)
    await details.getByRole('button', { name: 'Back to record' }).click()
    await panel.locator('.research-title-link').click()
    const context = page.getByRole('dialog', { name: 'Opportunity research' }).last()
    await checkOriginal(context.locator('.research-current'))
    await chooseLanguage(context, 'English')
    await expect(context.locator('.research-current .recommended-approach')).toContainText(
      englishApproach,
    )
    await expect(context.locator('.research-current .recommended-approach')).toContainText(
      englishProblem,
    )
    await expect(context.locator('.research-current .recommended-approach')).not.toContainText(
      example.approach,
    )
    await context.getByRole('button', { name: 'Back to results' }).click()
    await page.reload()
    await expect(page.getByRole('button', { name: 'Record language: English' })).toBeVisible()
    panel = await inspector(page)
    await expect(panel.locator('.recommended-approach')).toContainText(englishApproach)
    expect(providerRequests).toEqual([])
    expect(errors).toEqual([])
  })
}
