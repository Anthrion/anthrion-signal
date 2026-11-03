import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createHash } from 'node:crypto'

// Optional local audit; intentionally outside the release test path.
// From app/: node --expose-gc scripts/benchmark-search.mjs [app-root] [output-json]
const root = resolve(process.argv[2] || '.')
const output = resolve(process.argv[3] || '../artifacts/search-benchmark.json')
mkdirSync(dirname(output), { recursive: true })
const { createServer } = await import(
  pathToFileURL(resolve(root, 'node_modules/vite/dist/node/index.js'))
)
const server = await createServer({
  root,
  server: { middlewareMode: true },
  appType: 'custom',
  optimizeDeps: { noDiscovery: true, include: [] },
})
try {
  const lib = await server.ssrLoadModule('/src/lib.ts')
  const { createRelatedIndex } = await server.ssrLoadModule('/src/relatedSearch.ts')
  const { selectMarketEntries } = await server.ssrLoadModule('/src/dataClient.ts')
  const json = (path) => JSON.parse(readFileSync(resolve(root, 'public/data', path)))
  const manifest = json('manifest.json')
  const report = {
    node: process.version,
    memory_measured: !!global.gc,
    generated_at: manifest.generated_at,
    search: [],
    related: [],
  }
  const digest = (value) => createHash('sha256').update(JSON.stringify(value)).digest('hex')
  const now = Date.parse(process.env.SIGNAL_BENCHMARK_NOW || '2026-09-21T14:00:00Z')
  for (const market of ['GB', '']) {
    const pages = selectMarketEntries(Object.entries(manifest.current_feed.markets), market).map(
      ([, p]) => json(p.url),
    )
    const signals = [
      ...new Map(pages.flatMap((p) => p.signals.map((s) => [s.id, s]))).values(),
    ].filter((s) => lib.isAvailableOpportunity(s, now))
    const translations = Object.assign({}, ...pages.map((p) => p.translations))
    const queries = [
      'salesforce',
      'crm',
      'customer platform',
      '"case management"',
      'portail',
      'digital citizen',
      'servicio',
      'data analytics',
      'xyzunmatched',
    ]
    for (let repeat = 0; repeat < 2; repeat++)
      for (const q of queries) {
        const t = performance.now()
        const found = lib.filterSignals(
          signals,
          { ...lib.defaults, market, view: 'all', q },
          [],
          now,
          manifest.capabilities,
          translations,
        )
        report.search.push({
          market: market || 'ALL',
          repeat,
          q,
          records: signals.length,
          ms: performance.now() - t,
          count: found.length,
          digest: digest(found.map((s) => s.id)),
        })
      }
    const awardPages = selectMarketEntries(Object.entries(manifest.award_history), market).map(
      ([, p]) => json(p.url),
    )
    const awards = [
      ...new Map(awardPages.flatMap((p) => p.signals.map((s) => [s.id, s]))).values(),
    ].filter((s) => lib.isHistoricalAward(s, now) && lib.matchesMarket(s, market))
    Object.assign(translations, ...awardPages.map((p) => p.translations))
    const records = [...signals, ...awards]
    global.gc?.()
    const heapBefore = process.memoryUsage().heapUsed
    const start = performance.now()
    const find = createRelatedIndex(records, translations)
    const buildMs = performance.now() - start
    global.gc?.()
    const indexHeapBytes = process.memoryUsage().heapUsed - heapBefore
    const selected = [
      signals.find((s) => s.id === 'sig_bb3dcf41bab4e99b59ef'),
      ...signals.filter((s) =>
        /salesforce|case management|citizen|portal|data analytics/i.test(s.title),
      ),
      signals[0],
    ]
      .filter(Boolean)
      .slice(0, 6)
    for (const record of selected) {
      const t = performance.now()
      const values = find.both
        ? find.both(record, now)
        : { signals: find(record, 'signals', now), awards: find(record, 'awards', now) }
      report.related.push({
        market: market || 'ALL',
        records: records.length,
        id: record.id,
        title: record.title,
        buildMs,
        indexHeapBytes,
        queryMs: performance.now() - t,
        signals: values.signals.length,
        awards: values.awards.length,
        digest: digest(
          Object.fromEntries(
            Object.entries(values).map(([k, v]) => [
              k,
              v.map(({ signal, ...m }) => ({ id: signal.id, ...m })),
            ]),
          ),
        ),
      })
    }
  }
  writeFileSync(output, JSON.stringify(report, null, 2))
  console.log(
    JSON.stringify({
      output,
      search: report.search.map(({ digest, ...v }) => v),
      related: report.related.map(({ digest, ...v }) => v),
    }),
  )
} finally {
  await server.close()
}
