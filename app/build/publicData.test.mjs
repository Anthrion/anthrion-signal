import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync, gunzipSync } from 'node:zlib'
import { afterEach, expect, test } from 'vitest'
import { build, resolveConfig } from 'vite'
import { copyPublicAssets, publicContentHash, SITE_LIMIT_BYTES } from './publicData.mjs'
const temporary = []
function sorted(value) {
  if (Array.isArray(value)) return value.map(sorted)
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sorted(item)]),
    )
  return value
}
async function json(path, value) {
  const body = JSON.stringify(sorted(value), null, 2) + '\n'
  await mkdir(dirname(path), { recursive: true })
  await writeFile(path, body)
  return body
}
async function directory() {
  const root = await mkdtemp(join(tmpdir(), 'signal-public-build-'))
  temporary.push(root)
  const publicDir = join(root, 'public')
  const outDir = join(root, 'dist')
  await mkdir(publicDir)
  await mkdir(outDir)
  await writeFile(join(outDir, 'index.html'), '<html>Built application</html>')
  return { root, publicDir, outDir }
}
async function page(publicDir, prefix, value) {
  const body = JSON.stringify(sorted(value), null, 2) + '\n'
  const path = `${prefix}-${publicContentHash(body).slice(0, 16)}.json`
  await mkdir(dirname(join(publicDir, 'data', path)), { recursive: true })
  await writeFile(join(publicDir, 'data', path), body)
  return path
}
async function historyPage(publicDir, records) {
  const body = JSON.stringify(sorted({ schema_version: '1.0', records }))
  const path = `history/abc-${publicContentHash(body).slice(0, 16)}.json.gz`
  await mkdir(dirname(join(publicDir, 'data', path)), { recursive: true })
  await writeFile(join(publicDir, 'data', path), gzipSync(body))
  return path
}
async function snapshot(root) {
  const result = {}
  const walk = async (directory) => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name)
      if (entry.isDirectory()) await walk(path)
      else
        result[relative(root, path)] = createHash('sha256')
          .update(await readFile(path))
          .digest('hex')
    }
  }
  await walk(root)
  return result
}
async function fixture() {
  const paths = await directory()
  const buyerId = `buyer_${'1'.repeat(20)}`
  const buyer = {
    schema_version: '1.0',
    buyer_id: buyerId,
    records: [{ signal_id: 'sig_current' }, { signal_id: 'sig_award' }, { signal_id: 'sig_older' }],
  }
  const buyerUrl = await page(paths.publicDir, `buyers/${buyerId}`, buyer)
  const signal = {
    id: 'sig_current',
    title: 'CRM delivery',
    description: 'Complete original source text',
    buyer_id: buyerId,
    buyer_history_ref: { url: buyerUrl, count: 3 },
  }
  const award = { ...signal, id: 'sig_award', title: 'Previous CRM award' }
  const recordUrl = await page(paths.publicDir, 'records/sig_current', {
    schema_version: '1.0',
    signal,
  })
  const awardRecordUrl = await page(paths.publicDir, 'records/sig_award', {
    schema_version: '1.0',
    signal: award,
  })
  const currentUrl = await page(paths.publicDir, 'current/GB', {
    schema_version: '1.0',
    signals: [{ ...signal, description: '', search_text: signal.description }],
  })
  const awardUrl = await page(paths.publicDir, 'awards/GB', {
    schema_version: '1.0',
    signals: [award],
  })
  const orphanUrl = await page(paths.publicDir, 'records/sig_orphan', {
    schema_version: '1.0',
    signal: { id: 'sig_orphan' },
  })
  const current = {
    schema_version: '2.0',
    generated_at: '2026-09-18T20:00:00Z',
    signals: [signal],
    translations: {},
    award_history: { GB: { url: awardUrl, count: 1 } },
    current_feed: {
      version: '1.0',
      markets: { GB: { url: currentUrl, count: 1 } },
      records: {
        sig_current: { url: recordUrl, view: 'opportunities' },
        sig_award: { url: awardRecordUrl, view: 'awards' },
      },
    },
  }
  const roots = async () => {
    await json(join(paths.publicDir, 'data/current.json'), current)
    await json(join(paths.publicDir, 'data/manifest.json'), {
      ...current,
      signals: [],
      translations: {},
    })
  }
  await roots()
  await writeFile(join(paths.publicDir, 'brand.svg'), '<svg>Brand asset</svg>')
  await writeFile(join(paths.publicDir, 'data/not-published.json'), '{"retained":"unreferenced"}')
  return {
    ...paths,
    current,
    signal,
    buyer,
    buyerUrl,
    recordUrl,
    awardRecordUrl,
    currentUrl,
    awardUrl,
    orphanUrl,
    roots,
  }
}
afterEach(async () => {
  for (const path of temporary.splice(0)) {
    const absolute = resolve(path)
    if (
      dirname(absolute) !== resolve(tmpdir()) ||
      !basename(absolute).startsWith('signal-public-build-')
    )
      throw new Error('Refusing cleanup outside the exact test temporary directories')
    await rm(absolute, { recursive: true, force: true })
  }
})
test('content hashing preserves Python numeric lexemes, Unicode and quoted punctuation', () => {
  const source = String.raw`{
    "amount": 1200.0,
    "description": "Échéance: \"CRM\", AI",
    "values": [1e-07, null, true]
  }`
  expect(JSON.parse(source).amount).toBe(1200)
  expect(publicContentHash(source)).toBe(
    '011589d420650effab8c23d43298e8d641aa153da3cebc35cb47c22b38ce22ff',
  )
})
test('linked history details are copied but cannot authorize unrelated retained records', async () => {
  const source = await fixture()
  const olderUrl = await page(source.publicDir, 'records/sig_older', {
    schema_version: '1.0',
    signal: { ...source.signal, id: 'sig_older' },
  })
  source.current.current_feed.records.sig_older = { url: olderUrl, view: 'history' }
  await source.roots()
  await copyPublicAssets(source)
  expect(JSON.parse(await readFile(join(source.outDir, 'data', olderUrl), 'utf8')).signal.id).toBe(
    'sig_older',
  )
  const bad = await fixture()
  bad.current.current_feed.records.sig_orphan = { url: bad.orphanUrl, view: 'history' }
  await bad.roots()
  await expect(copyPublicAssets(bad)).rejects.toThrow('unlinked')
})
test('compressed history keeps its source bytes and rejects extra records hidden in a shared bucket', async () => {
  const source = await fixture()
  const records = { sig_older: { signal: { ...source.signal, id: 'sig_older' } } }
  const path = await historyPage(source.publicDir, records)
  source.current.current_feed.records.sig_older = { url: path, view: 'history' }
  await source.roots()
  await copyPublicAssets(source)
  expect(JSON.parse(gunzipSync(await readFile(join(source.outDir, 'data', path))))).toEqual({
    schema_version: '1.0',
    records,
  })
  const bad = await fixture()
  const extra = await historyPage(bad.publicDir, {
    ...records,
    sig_hidden: { signal: { id: 'sig_hidden' } },
  })
  bad.current.current_feed.records.sig_older = { url: extra, view: 'history' }
  await bad.roots()
  await expect(copyPublicAssets(bad)).rejects.toThrow('outside its manifest')
})
test('a production copy preserves the whole referenced graph, history and non-data assets without changing public files', async () => {
  const source = await fixture()
  const before = await snapshot(source.publicDir)
  const result = await copyPublicAssets(source)
  expect(await snapshot(source.publicDir)).toEqual(before)
  expect(result.dataFiles).toBe(7)
  expect(await readFile(join(source.outDir, 'brand.svg'), 'utf8')).toBe('<svg>Brand asset</svg>')
  expect(await readFile(join(source.outDir, 'index.html'), 'utf8')).toBe(
    '<html>Built application</html>',
  )
  for (const path of [
    'current.json',
    'manifest.json',
    source.recordUrl,
    source.awardRecordUrl,
    source.currentUrl,
    source.awardUrl,
    source.buyerUrl,
  ])
    expect(await readFile(join(source.outDir, 'data', path))).toEqual(
      await readFile(join(source.publicDir, 'data', path)),
    )
  expect(
    JSON.parse(await readFile(join(source.outDir, 'data', source.buyerUrl), 'utf8')).records,
  ).toHaveLength(3)
  await expect(readFile(join(source.outDir, 'data', source.orphanUrl))).rejects.toThrow()
  await expect(readFile(join(source.outDir, 'data/not-published.json'))).rejects.toThrow()
})
test('the production limit includes bundled assets and fails without publishing root manifests', async () => {
  const source = await fixture()
  await writeFile(join(source.outDir, 'large-bundle.js'), Buffer.alloc(512))
  expect(SITE_LIMIT_BYTES).toBe(950 * 1024 * 1024)
  const limitBytes =
    (await readFile(join(source.publicDir, 'data/current.json'))).length +
    (await readFile(join(source.publicDir, 'data/manifest.json'))).length +
    512
  await expect(copyPublicAssets({ ...source, limitBytes })).rejects.toThrow(/build limit/)
  await expect(readFile(join(source.outDir, 'data/manifest.json'))).rejects.toThrow()
  expect(await readFile(join(source.publicDir, 'data/manifest.json'))).toBeTruthy()
})
test('missing and altered content-addressed files fail closed', async () => {
  const missing = await fixture()
  await rm(join(missing.publicDir, 'data', missing.recordUrl))
  await expect(copyPublicAssets(missing)).rejects.toThrow()
  await expect(readFile(join(missing.outDir, 'data/manifest.json'))).rejects.toThrow()
  const changed = await fixture()
  await json(join(changed.publicDir, 'data', changed.recordUrl), {
    schema_version: '1.0',
    signal: { ...changed.signal, title: 'Changed source' },
  })
  await expect(copyPublicAssets(changed)).rejects.toThrow(/hash or schema mismatch/)
})
test('unsafe dependency paths and source/output overlap are rejected', async () => {
  const source = await fixture()
  const feed = source.current.current_feed
  feed.records = {
    sig_current: { url: '../outside.json' },
    sig_award: { url: source.awardRecordUrl },
  }
  await source.roots()
  await expect(copyPublicAssets(source)).rejects.toThrow(/Unsafe records data path/)
  await expect(
    copyPublicAssets({ ...source, outDir: join(source.publicDir, 'dist') }),
  ).rejects.toThrow(/separate/)
})
test('a manifest captured during an unfinished export is rejected', async () => {
  const source = await fixture()
  await json(join(source.publicDir, 'data/manifest.json'), {
    ...source.current,
    generated_at: 'newer',
    signals: [],
    translations: {},
  })
  await expect(copyPublicAssets(source)).rejects.toThrow(/different publications/)
})
test('a valid hash cannot conceal a missing buyer-history row or a wrong record identity', async () => {
  const source = await fixture()
  const shortBuyer = await page(source.publicDir, `buyers/${source.buyer.buyer_id}`, {
    ...source.buyer,
    records: source.buyer.records.slice(0, 1),
  })
  source.signal.buyer_history_ref.url = shortBuyer
  const updatedRecord = await page(source.publicDir, 'records/sig_current', {
    schema_version: '1.0',
    signal: source.signal,
  })
  const feed = source.current.current_feed
  feed.records.sig_current = { url: updatedRecord, view: 'opportunities' }
  await source.roots()
  await expect(copyPublicAssets(source)).rejects.toThrow(/Buyer history identity or count mismatch/)
  const wrong = await fixture()
  const wrongRecord = await page(wrong.publicDir, 'records/sig_current', {
    schema_version: '1.0',
    signal: { ...wrong.signal, id: 'sig_wrong' },
  })
  wrong.current.current_feed.records.sig_current = {
    url: wrongRecord,
    view: 'opportunities',
  }
  await wrong.roots()
  await expect(copyPublicAssets(wrong)).rejects.toThrow(/identity mismatch/)
})
test('legacy current-only fixtures remain buildable, including an empty optional feed', async () => {
  const source = await directory()
  await json(join(source.publicDir, 'data/current.json'), {
    schema_version: '2.0',
    signals: [],
    current_feed: {},
    award_history: {},
  })
  await writeFile(join(source.publicDir, 'favicon.svg'), '<svg/>')
  const result = await copyPublicAssets(source)
  expect(result.dataFiles).toBe(1)
  expect(await readFile(join(source.outDir, 'favicon.svg'), 'utf8')).toBe('<svg/>')
})
test('two market references to one immutable shard copy that file only once', async () => {
  const source = await fixture()
  const markets = source.current.current_feed.markets
  markets.ALIAS = markets.GB
  await source.roots()
  expect((await copyPublicAssets(source)).dataFiles).toBe(7)
})
test('symlinked data directories cannot import files from outside the public tree', async () => {
  const source = await directory()
  const outside = join(source.root, 'outside')
  await mkdir(outside)
  await json(join(outside, 'current.json'), { signals: [] })
  await symlink(outside, join(source.publicDir, 'data'), 'junction')
  await expect(copyPublicAssets(source)).rejects.toThrow(/must not be links/)
})

test('Vite uses the verified copier only for production and keeps ordinary public files in development', async () => {
  const source = await fixture()
  const options = {
    configFile: fileURLToPath(new URL('../vite.config.ts', import.meta.url)),
    root: source.root,
    build: { outDir: source.outDir },
    logLevel: 'silent',
  }
  const production = await resolveConfig(options, 'build')
  expect(production.publicDir.replaceAll('\\', '/')).toBe(source.publicDir.replaceAll('\\', '/'))
  expect(production.build.copyPublicDir).toBe(false)
  const plugin = production.plugins.find((item) => item.name === 'anthrion-published-data')
  expect(typeof plugin.writeBundle).toBe('function')
  await plugin.writeBundle.call({ info: () => undefined })
  expect(await readFile(join(source.outDir, 'data/manifest.json'))).toBeTruthy()
  const development = await resolveConfig(options, 'serve')
  expect(development.publicDir.replaceAll('\\', '/')).toBe(source.publicDir.replaceAll('\\', '/'))
  expect(development.plugins.some((item) => item.name === 'anthrion-published-data')).toBe(false)
})

test('a production build rewrites public font and brand URLs for the site base without copying orphan data', async () => {
  const source = await fixture()
  await mkdir(join(source.publicDir, 'fonts'))
  await writeFile(join(source.publicDir, 'fonts/test.woff2'), Buffer.from([0, 1, 2, 3]))
  await writeFile(
    join(source.root, 'index.html'),
    '<!doctype html><html><head><link rel="stylesheet" href="/styles.css"></head><body>Brand</body></html>',
  )
  await writeFile(
    join(source.root, 'styles.css'),
    "@font-face { font-family: Brand; src: url('/fonts/test.woff2') } body { background: url('/brand.svg') }",
  )
  await build({
    configFile: fileURLToPath(new URL('../vite.config.ts', import.meta.url)),
    root: source.root,
    base: '/proof-prefix/',
    build: { outDir: source.outDir, minify: false },
    logLevel: 'silent',
  })
  const stylesheet = (await readdir(join(source.outDir, 'assets'))).find((name) =>
    name.endsWith('.css'),
  )
  expect(stylesheet).toBeTruthy()
  const css = await readFile(join(source.outDir, 'assets', stylesheet), 'utf8')
  expect(css).toMatch(/url\(["']?\/proof-prefix\/fonts\/test\.woff2/)
  expect(css).toMatch(/url\(["']?\/proof-prefix\/brand\.svg/)
  expect(await readFile(join(source.outDir, 'fonts/test.woff2'))).toEqual(Buffer.from([0, 1, 2, 3]))
  expect(await readFile(join(source.outDir, 'brand.svg'), 'utf8')).toBe('<svg>Brand asset</svg>')
  await expect(readFile(join(source.outDir, 'data', source.orphanUrl))).rejects.toThrow()
  await expect(readFile(join(source.outDir, 'data/not-published.json'))).rejects.toThrow()
})
