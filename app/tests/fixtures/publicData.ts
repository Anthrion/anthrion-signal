import type { APIRequestContext } from '@playwright/test'
import { gunzipSync } from 'node:zlib'

/** Read actual published bytes independently of the browser's data client. */
export async function publicJSON(request: APIRequestContext, path = 'current.json') {
  let response = await request.get(`./data/${path}`)
  if (path === 'current.json' && response.status() === 404) {
    path = 'current.json.gz'
    response = await request.get(`./data/${path}`)
  }
  if (!response.ok()) throw new Error(`Published data request failed: ${response.status()}`)
  const bytes = await response.body()
  // Vite's development fallback is HTML, whereas production returns 404.
  if (path === 'current.json' && bytes[0] === 60) return publicJSON(request, 'current.json.gz')
  return JSON.parse(
    (bytes[0] === 0x1f && bytes[1] === 0x8b
      ? gunzipSync(bytes, { maxOutputLength: 256 * 1024 * 1024 })
      : bytes
    ).toString('utf8'),
  )
}
