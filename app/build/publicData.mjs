import { createHash } from 'node:crypto'
import { lstat, mkdir, readdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path'
export const SITE_LIMIT_BYTES = 950 * 1024 * 1024
const patterns = {
  current: /^current\/[A-Z]+-[a-f0-9]{16}\.json$/,
  awards: /^awards\/[A-Z]+-[a-f0-9]{16}\.json$/,
  records: /^records\/[A-Za-z0-9_-]{1,100}-[a-f0-9]{16}\.json$/,
  buyers: /^buyers\/buyer_[a-f0-9]{20}-[a-f0-9]{16}\.json$/,
}
function object(value, context) {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error(`Invalid public data object: ${context}`)
  return value
}
function rows(value, context) {
  if (!Array.isArray(value)) throw new Error(`Invalid public data array: ${context}`)
  return value.map((entry) => object(entry, context))
}
function pointer(value, context) {
  const entry = object(value, context)
  if (
    typeof entry.url !== 'string' ||
    !Number.isSafeInteger(entry.count) ||
    Number(entry.count) < 0
  )
    throw new Error(`Invalid public data reference: ${context}`)
  return { url: entry.url, count: Number(entry.count) }
}
function ident(value) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]{1,100}$/.test(value))
    throw new Error('Invalid public record identity')
  return value
}
function sameIds(left, right) {
  return left.size === right.size && [...left].every((value) => right.has(value))
}
function structure(value) {
  if (Array.isArray(value)) return `[${value.map(structure).join(',')}]`
  if (value && typeof value === 'object')
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${structure(value[key])}`)
      .join(',')}}`
  return JSON.stringify(value)
}
/** Match Python json.dumps(sort_keys=True) without rounding its numeric tokens.
 * Exported JSON already has sorted keys. Only insignificant whitespace differs
 * between its indented bytes and the canonical content used in hashed filenames.
 */
export function publicContentHash(source) {
  const hash = createHash('sha256')
  let quoted = false
  let escaped = false
  let start = 0
  let parts = []
  const append = (part) => {
    if (part) parts.push(part)
    if (parts.length >= 4096) {
      hash.update(parts.join(''))
      parts = []
    }
  }
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index]
    if (quoted) {
      if (escaped) escaped = false
      else if (character === '\\') escaped = true
      else if (character === '"') quoted = false
    } else if (character === '"') quoted = true
    else if (' \n\r\t'.includes(character)) {
      append(source.slice(start, index))
      start = index + 1
    } else if (character === ',' || character === ':') {
      append(source.slice(start, index + 1))
      append(' ')
      start = index + 1
    }
  }
  append(source.slice(start))
  hash.update(parts.join(''))
  return hash.digest('hex')
}
function inside(parent, child) {
  const part = relative(parent, child)
  return part === '' || (!isAbsolute(part) && part !== '..' && !part.startsWith(`..${sep}`))
}
async function existingFiles(directory) {
  const info = await lstat(directory).catch((error) => {
    if (error.code === 'ENOENT') return null
    throw error
  })
  if (!info) return []
  if (info.isSymbolicLink() || !info.isDirectory())
    throw new Error(`Public build directories must not be links: ${directory}`)
  const result = []
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isSymbolicLink()) throw new Error(`Public build assets must not be links: ${path}`)
    if (entry.isDirectory()) result.push(...(await existingFiles(path)))
    else if (entry.isFile()) result.push({ path, size: (await lstat(path)).size })
    else throw new Error(`Unsupported public build asset: ${path}`)
  }
  return result
}
async function boundedEach(values, action) {
  let next = 0
  let failure
  const workers = Array.from({ length: Math.min(8, values.length) }, async () => {
    while (next < values.length && !failure) {
      const value = values[next++]
      try {
        await action(value)
      } catch (error) {
        failure = error
      }
    }
  })
  await Promise.all(workers)
  if (failure) throw failure
}
/** Copy one coherent publication into a fresh production output directory.
 * Source files are never deleted or rewritten. Root manifests are copied last.
 */
export async function copyPublicAssets(options) {
  const publicDir = resolve(options.publicDir)
  const outDir = resolve(options.outDir)
  const limit = options.limitBytes ?? SITE_LIMIT_BYTES
  if (!Number.isSafeInteger(limit) || limit <= 0) throw new Error('Invalid site size limit')
  if (inside(publicDir, outDir) || inside(outDir, publicDir))
    throw new Error('Production output must be separate from public source files')
  const output = await existingFiles(outDir)
  const occupied = new Set(output.map((file) => relative(outDir, file.path)))
  let bytes = output.reduce((sum, file) => sum + file.size, 0)
  let files = output.length
  let dataFiles = 0
  const reserve = (size) => {
    if (bytes + size > limit)
      throw new Error(
        `Published site exceeds the ${Math.floor(limit / 1024 / 1024)} MiB build limit ` +
          `(${bytes + size} bytes required). Preserve history by reducing duplication or changing storage before publishing.`,
      )
    bytes += size
  }
  reserve(0)
  const checkedDirectories = new Set()
  const safeRead = async (path) => {
    const part = relative(publicDir, path)
    if (!inside(publicDir, path)) throw new Error('Public asset escaped its source directory')
    let directory = publicDir
    for (const component of ['', ...part.split(sep).slice(0, -1)]) {
      if (component) directory = join(directory, component)
      if (checkedDirectories.has(directory)) continue
      const info = await lstat(directory)
      if (info.isSymbolicLink() || !info.isDirectory())
        throw new Error(`Public source directories must not be links: ${directory}`)
      checkedDirectories.add(directory)
    }
    const info = await lstat(path)
    if (info.isSymbolicLink() || !info.isFile())
      throw new Error(`Public source assets must be regular files: ${path}`)
    if (info.size > limit) throw new Error(`Public asset exceeds the site size limit: ${path}`)
    return readFile(path)
  }
  const write = async (name, body, reserved = false) => {
    const destination = join(outDir, name)
    if (!inside(outDir, destination) || occupied.has(name))
      throw new Error(`Public asset would overwrite another build file: ${name}`)
    occupied.add(name)
    if (!reserved) reserve(body.length)
    await mkdir(dirname(destination), { recursive: true })
    await writeFile(destination, body, { flag: 'wx' })
    files += 1
    if (name.startsWith(`data${sep}`)) dataFiles += 1
  }
  const parse = (body, context) => object(JSON.parse(body.toString('utf8')), context)
  const currentBytes = await safeRead(join(publicDir, 'data', 'current.json'))
  const current = parse(currentBytes, 'current.json')
  reserve(currentBytes.length)
  let manifestBytes
  let manifest
  try {
    manifestBytes = await safeRead(join(publicDir, 'data', 'manifest.json'))
    manifest = parse(manifestBytes, 'manifest.json')
    reserve(manifestBytes.length)
  } catch (error) {
    if (error.code !== 'ENOENT') throw error
  }
  const hasFeed =
    current.current_feed && Object.keys(object(current.current_feed, 'current feed')).length > 0
  if (hasFeed && !manifest) throw new Error('Current feed is missing its completed root manifest')
  if (manifest && structure(manifest) !== structure({ ...current, signals: [], translations: {} }))
    throw new Error(
      'Public manifest and current.json are from different publications; finish export before building',
    )
  const buyerReferences = new Map()
  const buyersOf = (signal) => {
    if (!signal.buyer_history_ref) return
    const reference = pointer(signal.buyer_history_ref, 'buyer history')
    if (!patterns.buyers.test(reference.url)) throw new Error('Unsafe buyer history path')
    const previous = buyerReferences.get(reference.url)
    if (previous && (previous.buyerId !== signal.buyer_id || previous.count !== reference.count))
      throw new Error('Conflicting buyer history references')
    buyerReferences.set(reference.url, { buyerId: signal.buyer_id, count: reference.count })
  }
  const currentRows = rows(current.signals, 'current signals')
  const currentIds = new Set(currentRows.map((signal) => ident(signal.id)))
  if (currentIds.size !== currentRows.length) throw new Error('Duplicate current record identity')
  currentRows.forEach(buyersOf)
  const copiedPages = new Set()
  const loadPage = async (path, kind) => {
    if (!patterns[kind].test(path)) throw new Error(`Unsafe ${kind} data path: ${path}`)
    const body = await safeRead(join(publicDir, 'data', path))
    const page = parse(body, path)
    if (
      page.schema_version !== '1.0' ||
      !path.endsWith(`${publicContentHash(body.toString('utf8')).slice(0, 16)}.json`)
    )
      throw new Error(`Public content hash or schema mismatch: ${path}`)
    if (!copiedPages.has(path)) {
      copiedPages.add(path)
      await write(join('data', path), body)
    }
    return page
  }
  const awardIds = new Set()
  for (const value of Object.values(object(current.award_history ?? {}, 'award history'))) {
    const reference = pointer(value, 'award market')
    const page = await loadPage(reference.url, 'awards')
    const signals = rows(page.signals, reference.url)
    if (signals.length !== reference.count) throw new Error('Award market count mismatch')
    for (const signal of signals) {
      awardIds.add(ident(signal.id))
      buyersOf(signal)
    }
  }
  if (hasFeed) {
    const feed = object(current.current_feed, 'current feed')
    if (feed.version !== '1.0') throw new Error('Unsupported current feed version')
    const indexedIds = new Set()
    for (const value of Object.values(object(feed.markets, 'current markets'))) {
      const reference = pointer(value, 'current market')
      const page = await loadPage(reference.url, 'current')
      const signals = rows(page.signals, reference.url)
      if (signals.length !== reference.count) throw new Error('Current market count mismatch')
      for (const signal of signals) {
        indexedIds.add(ident(signal.id))
        buyersOf(signal)
      }
    }
    if (!sameIds(indexedIds, currentIds)) throw new Error('Current indexes omit or add records')
    const records = object(feed.records, 'record details')
    if (!sameIds(new Set(Object.keys(records)), new Set([...currentIds, ...awardIds])))
      throw new Error('Record manifest does not cover exactly the published records')
    await boundedEach(Object.entries(records), async ([id, value]) => {
      const reference = object(value, id)
      if (typeof reference.url !== 'string') throw new Error('Invalid record detail reference')
      const page = await loadPage(reference.url, 'records')
      const signal = object(page.signal, reference.url)
      if (ident(signal.id) !== id) throw new Error('Record detail identity mismatch')
      if (
        (reference.view !== undefined &&
          reference.view !== (currentIds.has(id) ? 'opportunities' : 'awards')) ||
        !reference.url.startsWith(`records/${id}-`)
      )
        throw new Error('Record detail reference does not match its identity or view')
      buyersOf(signal)
    })
  }
  await boundedEach([...buyerReferences], async ([path, reference]) => {
    const page = await loadPage(path, 'buyers')
    const records = rows(page.records, path)
    if (
      page.buyer_id !== reference.buyerId ||
      records.length !== reference.count ||
      !path.startsWith(`buyers/${page.buyer_id}-`)
    )
      throw new Error('Buyer history identity or count mismatch')
  })
  for (const entry of await readdir(publicDir, { withFileTypes: true })) {
    if (entry.name === 'data') continue
    const path = join(publicDir, entry.name)
    const assets = entry.isDirectory() ? await existingFiles(path) : [{ path }]
    for (const asset of assets) {
      await write(relative(publicDir, asset.path), await safeRead(asset.path))
    }
  }
  await write(join('data', 'current.json'), currentBytes, true)
  if (manifestBytes) await write(join('data', 'manifest.json'), manifestBytes, true)
  return { files, dataFiles, bytes }
}
