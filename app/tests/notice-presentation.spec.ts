import { test, expect } from '@playwright/test'
import { datasetFixture } from './fixtures/dataset'
import { recordDataset } from './fixtures/record'

test.beforeEach(async ({ page }) => {
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.setFixedTime(new Date('2026-09-11T12:00:00Z'))
})

test('@pr tidy lot descriptions retain English/original switching and the lot facts', async ({
  page,
}) => {
  const data = recordDataset(datasetFixture(), {
    source: 'germany',
    description: 'Originaler Leistungsumfang. Lot LOT-51: None. None',
    lot_ids: ['LOT-51'],
    lots: [
      {
        id: 'LOT-51',
        title: '',
        description: '',
        status: 'active',
        source_url: 'https://example.com/tender/a',
      },
    ],
  })
  data.translations = {
    'panel-a': {
      source_hash: 'fixture',
      version: 'en-procurement-2',
      title: data.signals[0].title,
      description: 'English delivery scope. Lot LOT-51: None. None',
    },
  }
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto('./?view=all&signal=panel-a')
  const record = page.locator('.console-detail:visible')
  await expect(record.locator('.inspector-summary')).toContainText('English delivery scope.')
  await expect(record.locator('.inspector-summary')).not.toContainText('None')
  await expect(record.locator('.record-facts').first()).toContainText('LOT-51')
  await record.getByRole('button', { name: 'Original', exact: true }).click()
  await expect(record.locator('.inspector-summary')).toContainText('Originaler Leistungsumfang.')
  await expect(record.locator('.inspector-summary')).not.toContainText('None')
  await record.getByRole('button', { name: 'English', exact: true }).click()
  await expect(record.locator('.inspector-summary')).toContainText('English delivery scope.')
})

test('@pr TED publication days do not create a source update in the redesigned detail view', async ({
  page,
}) => {
  const data = recordDataset(datasetFixture(), {
    source: 'ted',
    published_at: '2026-07-02',
    updated_at: '2026-07-01T22:00:00Z',
    last_material_update: '2026-07-01T22:00:00Z',
    provenance: [],
  })
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
  await page.goto('./?view=all&signal=panel-a')
  const record = page.locator('.console-detail:visible')
  await expect(record.locator('.record-facts').first()).toContainText('2 Jul 2026')
  await record.locator('.record-history > summary').click()
  await expect(record.getByText('Updated at source', { exact: true })).toHaveCount(0)
  await expect(record.getByText('Material update', { exact: true })).toHaveCount(0)
})
