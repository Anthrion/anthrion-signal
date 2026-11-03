// Generates public/assets/optical-glass-daylight.png, the light theme's glass, from the dark
// theme's optical-glass-material.png: node build/generateDaylightGlass.mjs
//
// The dark texture is light on black and is screened onto dark surfaces. Daylight needs the
// opposite reading: thick glass looks tinted where it is lit, so the texture's glow becomes a
// soft blue tint, its edges, bend and rim become fine deeper blue lines, and everything else is
// transparent. The image is half size; the stylesheet halves the border-image slices to match.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { deflateSync, inflateSync } from 'node:zlib'

const assets = join(dirname(fileURLToPath(import.meta.url)), '../public/assets')
const SOURCE = join(assets, 'optical-glass-material.png')
const OUT = join(assets, 'optical-glass-daylight.png')

// The dark texture's border-image slices (top, right, bottom, left), in source pixels.
const slices = [90, 64, 144, 64]
const tone = {
  floor: 0.1, // the dim body of the slab stays clear
  split: 0.14, // below: glow, rendered as tint; above: edges, rendered as lines
  peak: 0.85,
  glow: 0.5,
  line: 0.46,
  glowColour: [140, 208, 240],
  lineColour: [30, 125, 180],
  // A glow fades out before the inner edge of the frame, so the face shows no seam.
  seam: 11,
}

function readPng(file) {
  const bytes = readFileSync(file)
  let offset = 8
  let header
  const data = []
  while (offset < bytes.length) {
    const length = bytes.readUInt32BE(offset)
    const type = bytes.toString('latin1', offset + 4, offset + 8)
    const body = bytes.subarray(offset + 8, offset + 8 + length)
    if (type === 'IHDR') header = body
    if (type === 'IDAT') data.push(body)
    offset += 12 + length
  }
  const width = header.readUInt32BE(0)
  const height = header.readUInt32BE(4)
  if (header[8] !== 8 || header[9] !== 2 || header[12] !== 0)
    throw new Error('Expected an 8-bit RGB, non-interlaced PNG')
  const raw = inflateSync(Buffer.concat(data))
  const stride = width * 3
  const pixels = Buffer.alloc(stride * height)
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)]
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1))
    for (let x = 0; x < stride; x++) {
      const left = x >= 3 ? pixels[y * stride + x - 3] : 0
      const up = y ? pixels[(y - 1) * stride + x] : 0
      const corner = x >= 3 && y ? pixels[(y - 1) * stride + x - 3] : 0
      const predict = [0, left, up, (left + up) >> 1, paeth(left, up, corner)][filter]
      pixels[y * stride + x] = (line[x] + predict) & 255
    }
  }
  return { width, height, pixels }
}

function paeth(a, b, c) {
  const p = a + b - c
  const pa = Math.abs(p - a)
  const pb = Math.abs(p - b)
  const pc = Math.abs(p - c)
  return pa <= pb && pa <= pc ? a : pb <= pc ? b : c
}

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})
function crc32(buffer) {
  let c = 0xffffffff
  for (const byte of buffer) c = crcTable[(c ^ byte) & 255] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}
function chunk(type, body) {
  const out = Buffer.alloc(12 + body.length)
  out.writeUInt32BE(body.length, 0)
  out.write(type, 4, 'latin1')
  body.copy(out, 8)
  out.writeUInt32BE(crc32(out.subarray(4, 8 + body.length)), 8 + body.length)
  return out
}

function writePng(file, width, height, rgba) {
  const stride = width * 4
  const rows = []
  for (let y = 0; y < height; y++) {
    const line = rgba.subarray(y * stride, (y + 1) * stride)
    const previous = y ? rgba.subarray((y - 1) * stride, y * stride) : Buffer.alloc(stride)
    // Each row keeps whichever filter leaves the smallest residue, for a compact file.
    let best
    for (const filter of [0, 1, 2, 4]) {
      const row = Buffer.alloc(stride + 1)
      row[0] = filter
      let cost = 0
      for (let x = 0; x < stride; x++) {
        const left = x >= 4 ? line[x - 4] : 0
        const predict = [
          0,
          left,
          previous[x],
          0,
          paeth(left, previous[x], x >= 4 ? previous[x - 4] : 0),
        ][filter]
        row[x + 1] = (line[x] - predict) & 255
        cost += row[x + 1] < 128 ? row[x + 1] : 256 - row[x + 1]
      }
      if (!best || cost < best.cost) best = { row, cost }
    }
    rows.push(best.row)
  }
  const header = Buffer.alloc(13)
  header.writeUInt32BE(width, 0)
  header.writeUInt32BE(height, 4)
  header.set([8, 6, 0, 0, 0], 8)
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])
  const data = deflateSync(Buffer.concat(rows), { level: 9 })
  writeFileSync(
    file,
    Buffer.concat([
      signature,
      chunk('IHDR', header),
      chunk('IDAT', data),
      chunk('IEND', Buffer.alloc(0)),
    ]),
  )
}

const step = (edge0, edge1, value) => {
  const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)))
  return t * t * (3 - 2 * t)
}

const source = readPng(SOURCE)
const width = Math.floor(source.width / 2)
const height = Math.floor(source.height / 2)
const [top, right, bottom, left] = slices.map((slice) => slice / 2)
const rgba = Buffer.alloc(width * height * 4)
for (let y = 0; y < height; y++) {
  for (let x = 0; x < width; x++) {
    // Half size: each pixel averages a 2 x 2 block of the source.
    const colour = [0, 0, 0]
    for (const [dx, dy] of [
      [0, 0],
      [1, 0],
      [0, 1],
      [1, 1],
    ]) {
      const at = ((y * 2 + dy) * source.width + x * 2 + dx) * 3
      for (let k = 0; k < 3; k++) colour[k] += source.pixels[at + k] / 4
    }
    const luminance = (0.2126 * colour[0] + 0.7152 * colour[1] + 0.0722 * colour[2]) / 255
    const t = Math.min(1, Math.max(0, (luminance - tone.floor) / (1 - tone.floor)))
    const outside = Math.hypot(
      Math.max(left - x, 0, x - (width - right)),
      Math.max(top - y, 0, y - (height - bottom)),
    )
    const alpha =
      tone.glow * step(0, tone.split, t) * step(0, tone.seam, outside) +
      tone.line * step(tone.split, tone.peak, t)
    const blend = step(tone.split / 2, tone.peak * 0.8, t)
    const at = (y * width + x) * 4
    if (alpha < 1 / 255) continue
    for (let k = 0; k < 3; k++)
      rgba[at + k] = Math.round(
        tone.glowColour[k] + (tone.lineColour[k] - tone.glowColour[k]) * blend,
      )
    rgba[at + 3] = Math.round(Math.min(1, alpha) * 255)
  }
}
writePng(OUT, width, height, rgba)
console.log(`Wrote ${OUT} (${width} x ${height})`)
