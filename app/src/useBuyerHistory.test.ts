import { expect, test } from 'vitest'
import { buyerPage } from './useBuyerHistory'

const history = (buyer_id: string) => ({
  schema_version: '1.0',
  buyer_id,
  buyer_name: buyer_id,
  identity_basis: 'source',
  records: [
    {
      signal_id: buyer_id,
      title: 'Original title',
      status: 'active',
      source_url: 'https://example.org',
      lot_ids: [],
    },
  ],
})

test('a shared buyer bundle selects each exact identity and retains legacy pages', () => {
  const first = history('buyer_first')
  const second = history('buyer_second')
  const bucket = { schema_version: '1.0', buyers: { buyer_first: first, buyer_second: second } }
  expect(buyerPage(bucket, 'buyer_first')).toEqual(first)
  expect(buyerPage(bucket, 'buyer_second')).toEqual(second)
  expect(buyerPage(bucket, 'absent')).toBeNull()
  expect(buyerPage(first, 'buyer_first')).toEqual(first)
  expect(buyerPage(first, 'buyer_second')).toBeNull()
  expect(buyerPage({ ...bucket, schema_version: 'unknown' }, 'buyer_first')).toBeNull()
})
