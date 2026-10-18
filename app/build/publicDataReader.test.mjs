import { expect, test, vi } from 'vitest'
import { gzipSync } from 'node:zlib'
import { publicJSON } from '../tests/fixtures/publicData.ts'

test.each([404, 200])(
  'published-data readers dispose the legacy response and gzip fallback (%s)',
  async (status) => {
    const legacy = {
      status: () => status,
      ok: () => status === 200,
      body: async () => Buffer.from('<html>'),
      dispose: vi.fn(async () => {}),
    }
    const compressed = {
      status: () => 200,
      ok: () => true,
      body: async () => gzipSync('{"title":"Québec"}'),
      dispose: vi.fn(async () => {}),
    }
    const get = vi.fn().mockResolvedValueOnce(legacy).mockResolvedValueOnce(compressed)
    expect(await publicJSON({ get })).toEqual({ title: 'Québec' })
    expect(legacy.dispose).toHaveBeenCalledOnce()
    expect(compressed.dispose).toHaveBeenCalledOnce()
  },
)

test.each([503, 200])(
  'published-data readers also release failed HTTP/JSON bodies (%s)',
  async (status) => {
    const response = {
      status: () => status,
      ok: () => status === 200,
      body: async () => Buffer.from('invalid JSON'),
      dispose: vi.fn(async () => {}),
    }
    await expect(publicJSON({ get: async () => response })).rejects.toThrow()
    expect(response.dispose).toHaveBeenCalledOnce()
  },
)
