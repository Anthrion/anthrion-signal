// Generates src/coverageGeometry.ts: projected, clipped and simplified country outlines.
// Boundaries: Natural Earth 1:50m Admin 0, public domain
// (https://www.naturalearthdata.com/about/terms-of-use/), redistributed by world-atlas (ISC).
//
// The tools are not app dependencies. Install them anywhere, then point this script at them:
//   npm install --prefix <dir> world-atlas@2.0.2 topojson-client@3.1.0 d3-geo@3.1.1
//   node build/generateCoverageMap.mjs <dir>
import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const tools = createRequire(join(resolve(process.argv[2] || '.'), 'package.json'))
const { feature } = tools('topojson-client')
const { geoAzimuthalEqualArea, geoConicEqualArea, geoPath } = await import(
  pathToFileURL(tools.resolve('d3-geo')).href
)
const OUT = join(dirname(fileURLToPath(import.meta.url)), '../src/coverageGeometry.ts')
const world = JSON.parse(readFileSync(tools.resolve('world-atlas/countries-50m.json'), 'utf8'))
const countries = feature(world, world.objects.countries).features

// ISO 3166-1 numeric -> alpha-2 for markets Signal can cover.
const NUMERIC = {
  826: 'GB',
  840: 'US',
  124: 'CA',
  380: 'IT',
  752: 'SE',
  246: 'FI',
  208: 'DK',
  578: 'NO',
  352: 'IS',
  276: 'DE',
  724: 'ES',
  300: 'GR',
  56: 'BE',
  528: 'NL',
  250: 'FR',
  756: 'CH',
  40: 'AT',
  372: 'IE',
  620: 'PT',
  616: 'PL',
  233: 'EE',
  428: 'LV',
  440: 'LT',
  203: 'CZ',
  642: 'RO',
  100: 'BG',
  191: 'HR',
  348: 'HU',
  442: 'LU',
  196: 'CY',
  470: 'MT',
  705: 'SI',
  703: 'SK',
}
const code = (f) => NUMERIC[Number(f.id)] || ''

const W = 372
const H = 300
const INSET = { x: W - 126, y: 4, width: 122, height: 90 }

// Europe: ETRS89-style Lambert azimuthal equal-area, centred on 10°E 52°N.
const europeExtent = {
  type: 'Feature',
  geometry: {
    type: 'MultiPoint',
    coordinates: [
      [-24.5, 63.5],
      [-24, 66.6],
      [-10.5, 51.5],
      [-9.6, 36.9],
      [-6, 35.6],
      [10, 34.6],
      [14.5, 35.6],
      [24, 34.7],
      [34.6, 34.4],
      [35.5, 35.2],
      [31, 71],
      [26, 71.2],
      [15, 71.2],
    ],
  },
}
const europe = geoAzimuthalEqualArea()
  .rotate([-10, -52])
  .fitExtent(
    [
      [6, 8],
      [W - 6, H - 6],
    ],
    europeExtent,
  )
  .clipExtent([
    [0, 0],
    [W, H],
  ])

// North America inset: conic equal-area, US + Canada.
const naExtent = {
  type: 'Feature',
  geometry: {
    type: 'MultiPoint',
    coordinates: [
      [-168, 66],
      [-125, 49],
      [-117, 32.5],
      [-97, 25.8],
      [-80, 25],
      [-67, 45],
      [-55, 52],
      [-62, 82.5],
      [-95, 80],
      [-141, 70],
    ],
  },
}
const pad = 7
const northAmerica = geoConicEqualArea()
  .parallels([33, 65])
  .rotate([100, 0])
  .fitExtent(
    [
      [INSET.x + pad, INSET.y + pad],
      [INSET.x + INSET.width - pad, INSET.y + INSET.height - pad],
    ],
    naExtent,
  )
  .clipExtent([
    [INSET.x + 1, INSET.y + 1],
    [INSET.x + INSET.width - 1, INSET.y + INSET.height - 1],
  ])

// Record projected rings through d3's clipping pipeline.
function rings(projection, geometry) {
  const out = []
  let ring = null
  const context = {
    moveTo(x, y) {
      ring = [[x, y]]
      out.push(ring)
    },
    lineTo(x, y) {
      ring.push([x, y])
    },
    closePath() {},
    arc() {},
  }
  geoPath(projection, context)(geometry)
  return out
}
const area = (ring) => {
  let total = 0
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++)
    total += (ring[j][0] + ring[i][0]) * (ring[j][1] - ring[i][1])
  return Math.abs(total / 2)
}
// Visvalingam–Whyatt in pixel space.
function simplify(ring, minArea) {
  if (ring.length <= 4) return ring
  const points = ring.map((p) => [...p])
  const triangle = (a, b, c) =>
    Math.abs((a[0] - c[0]) * (b[1] - a[1]) - (a[0] - b[0]) * (c[1] - a[1])) / 2
  let changed = true
  while (changed && points.length > 4) {
    changed = false
    let best = -1
    let bestArea = Infinity
    for (let i = 1; i < points.length - 1; i++) {
      const value = triangle(points[i - 1], points[i], points[i + 1])
      if (value < bestArea) {
        bestArea = value
        best = i
      }
    }
    if (best > 0 && bestArea < minArea) {
      points.splice(best, 1)
      changed = true
    }
  }
  return points
}
function pathData(list, { minRing = 0.6, minTriangle = 0.18 } = {}) {
  const parts = []
  for (const raw of list) {
    if (raw.length < 3 || area(raw) < minRing) continue
    const ring = simplify(raw, minTriangle)
    const rounded = []
    for (const [x, y] of ring) {
      const point = [Math.round(x * 10) / 10, Math.round(y * 10) / 10]
      const last = rounded.at(-1)
      if (!last || last[0] !== point[0] || last[1] !== point[1]) rounded.push(point)
    }
    if (rounded.length < 3) continue
    parts.push(encode(rounded))
  }
  return parts.join('')
}
const num = (value) => {
  const text = String(Math.round(value * 10) / 10)
  return text.replace(/^(-?)0./, '$1.')
}
// Relative commands from rounded absolute points avoid cumulative drift.
function encode(points) {
  let out = 'M' + num(points[0][0]) + ',' + num(points[0][1]) + 'l'
  let previous = ''
  for (let i = 1; i < points.length; i++) {
    for (const value of [points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]]) {
      const text = num(value)
      // A separator is needed unless the next number starts with '-' or a second decimal point.
      const needs =
        previous && !(text.startsWith('-') || (text.startsWith('.') && previous.includes('.')))
      out += (needs ? ',' : '') + text
      previous = text
    }
  }
  return out + 'z'
}
function centroid(list) {
  let best = null
  for (const ring of list) {
    const a = area(ring)
    if (!best || a > best.a) best = { a, ring }
  }
  if (!best) return null
  const xs = best.ring.map((p) => p[0])
  const ys = best.ring.map((p) => p[1])
  return [
    Math.round(((Math.min(...xs) + Math.max(...xs)) / 2) * 10) / 10,
    Math.round(((Math.min(...ys) + Math.max(...ys)) / 2) * 10) / 10,
  ]
}

const covered = []
const context = []
const insetContext = []
const markers = {}
const TINY = new Set(['MT', 'LU', 'CY'])
for (const country of countries) {
  const id = code(country)
  const isNorthAmerica =
    ['US', 'CA'].includes(id) || ['484', '304', '192', '044', '666'].includes(String(country.id))
  const projection = ['US', 'CA'].includes(id) ? northAmerica : europe
  const projected = rings(projection, country.geometry)
  // Keep the inset free of European geometry and vice versa.
  const visible = projected.filter((ring) =>
    projection === europe
      ? !ring.every(([x, y]) => x > INSET.x - 1 && y < INSET.y + INSET.height + 1)
      : true,
  )
  if (id) {
    const d = pathData(visible, {
      minRing: TINY.has(id) ? 0.05 : 0.8,
      minTriangle: TINY.has(id) ? 0.02 : 0.3,
    })
    if (d) covered.push({ id, d })
    if (TINY.has(id)) markers[id] = centroid(visible)
  } else if (!isNorthAmerica || projection === europe) {
    const d = pathData(visible, { minRing: 2, minTriangle: 0.6 })
    if (d) context.push(d)
  }
  if (isNorthAmerica && !id) {
    const d = pathData(rings(northAmerica, country.geometry), { minRing: 1.5, minTriangle: 0.5 })
    if (d) insetContext.push(d)
  }
}
covered.sort((a, b) => a.id.localeCompare(b.id))

const body = `// Generated by app/build/generateCoverageMap.mjs. Do not edit by hand.
// Country boundaries: Natural Earth 1:50m Admin 0 (public domain,
// https://www.naturalearthdata.com/about/terms-of-use/) via world-atlas 2.0.2 (ISC).
// Europe: Lambert azimuthal equal-area (10°E, 52°N). Inset: conic equal-area North America.
export const coverageMap = {
  width: ${W},
  height: ${H},
  inset: ${JSON.stringify(INSET)},
  countries: ${JSON.stringify(covered)} as { id: string; d: string }[],
  context: ${JSON.stringify(context.join(''))},
  insetContext: ${JSON.stringify(insetContext.join(''))},
  markers: ${JSON.stringify(markers)} as Record<string, [number, number]>,
}
`
// Format with the repository's Prettier settings so regeneration keeps the format check clean.
const prettier = await import('prettier')
const formatted = await prettier.format(body, {
  ...(await prettier.resolveConfig(OUT)),
  filepath: OUT,
})
writeFileSync(OUT, formatted)
console.log(`Wrote ${covered.length} countries, ${formatted.length} bytes`)
