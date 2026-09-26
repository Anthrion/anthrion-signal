import { describe, expect, test } from 'vitest'
import { pairPlaces } from './RollingNumber'

describe('rolling counts', () => {
  test('places pair from the right, so units stay units as a number changes length', () => {
    expect(pairPlaces('6,148', '762')).toEqual([
      { key: 4, from: '6', to: '' },
      { key: 3, from: ',', to: '' },
      { key: 2, from: '1', to: '7' },
      { key: 1, from: '4', to: '6' },
      { key: 0, from: '8', to: '2' },
    ])
    expect(pairPlaces('21', '9,506').map(({ from, to }) => `${from || '·'}${to || '·'}`)).toEqual([
      '·9',
      '·,',
      '·5',
      '20',
      '16',
    ])
  })

  test('an unchanged number keeps every place', () => {
    expect(pairPlaces('881', '881').every(({ from, to }) => from === to)).toBe(true)
  })
})
