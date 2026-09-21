import { datasetFixture } from './fixtures/dataset'
import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  const data = datasetFixture()
  await page.route('**/data/manifest.json', (route) => route.fulfill({ status: 404 }))
  await page.route('**/data/current.json', (route) => route.fulfill({ json: data }))
})

test('@pr production policy permits the app and blocks injected scripts and off-origin requests', async ({
  page,
}) => {
  test.skip(
    process.env.SIGNAL_TEST_PREVIEW !== 'true',
    'CSP is installed only in production builds',
  )
  const violations: string[] = []
  const pageErrors: string[] = []
  await page.exposeFunction('recordPolicyViolation', (directive: string) =>
    violations.push(directive),
  )
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) => {
      ;(
        window as unknown as { recordPolicyViolation: (directive: string) => void }
      ).recordPolicyViolation(event.effectiveDirective)
    })
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.goto('./?view=all')
  await expect(page.locator('.signal-row').first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.locator('.row-select').first().click()
  await expect(page.locator('.console-detail:visible')).toBeVisible()
  await expect(page.locator('meta[http-equiv="Content-Security-Policy"]')).toHaveAttribute(
    'content',
    /script-src 'self'/,
  )
  expect(pageErrors).toEqual([])
  expect(violations).toEqual([])

  let externalRequests = 0
  await page.route('https://csp-test.invalid/**', async (route) => {
    externalRequests += 1
    await route.fulfill({ body: '' })
  })
  const blocked = await page.evaluate(async () => {
    const script = document.createElement('script')
    script.textContent = 'window.__injectedByPolicyTest = true'
    document.head.appendChild(script)
    try {
      await fetch('https://csp-test.invalid/probe')
      return false
    } catch {
      return !(window as unknown as { __injectedByPolicyTest?: boolean }).__injectedByPolicyTest
    }
  })
  expect(blocked).toBe(true)
  expect(externalRequests).toBe(0)
  await expect.poll(() => violations).toContain('script-src-elem')
  await expect.poll(() => violations).toContain('connect-src')
})
