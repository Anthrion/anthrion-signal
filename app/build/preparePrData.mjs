// Reuse the browser suite's small fixture for PR compilation. Never touch retained data,
// create a verification receipt, or replace an existing public export.
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

if (process.env.GITHUB_EVENT_NAME !== 'pull_request')
  throw new Error('This fixture is only for pull-request checks, never publication.')
const root = dirname(dirname(fileURLToPath(import.meta.url)))
const server = await createServer({
  root,
  configFile: false,
  envFile: false,
  appType: 'custom',
  logLevel: 'error',
  optimizeDeps: { noDiscovery: true, include: [] },
  server: { middlewareMode: true, hmr: false, watch: null },
})
try {
  const { datasetFixture } = await server.ssrLoadModule('/tests/fixtures/dataset.ts')
  const data = datasetFixture()
  await mkdir(join(root, 'public/data'), { recursive: true })
  await writeFile(join(root, 'public/data/current.json'), JSON.stringify(data), { flag: 'wx' })
  console.log(`Prepared ${data.signals.length} fixture records for PR checks.`)
} finally {
  await server.close()
}
