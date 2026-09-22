import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { RecommendedApproach } from './RecommendedApproach'
import type { Signal } from './types'

const signal = {
  title: 'Case management implementation',
  countries: ['GB'],
  status: 'active',
  signal_type: 'LIVE_TENDER',
  lifecycle_state: 'OPEN',
  deadline_at: null,
  response_deadlines: [],
  reviewed_guidance: {
    source_hash: 'source',
    approach: [{ text: 'Build the published case workflow.', lot_id: 'LOT-0002' }],
    problems: [],
    complexity: 6,
    problem_level: 1,
  },
} as unknown as Signal

test('guidance shows relevant lots and only real problems, keeping ratings out of the interface', () => {
  const html = renderToStaticMarkup(<RecommendedApproach signal={signal} />)
  expect(html).toContain('Recommended approach:')
  expect(html).toContain('Lot 0002:')
  expect(html).not.toContain('Problems:')
  expect(html).not.toMatch(/complexity|problem_level/)
  const changed = {
    ...signal,
    reviewed_guidance: {
      ...signal.reviewed_guidance!,
      problems: [{ text: 'Migration includes 10 million legacy rows.' }],
    },
  }
  expect(renderToStaticMarkup(<RecommendedApproach signal={changed} />)).toContain('Problems:')
})

test('historical, excluded, foreign and unreviewed records do not acquire recommendations', () => {
  for (const changed of [
    { signal_type: 'AWARD', lifecycle_state: 'AWARDED' },
    { exclusion_reasons: ['Reviewed unrelated scope'] },
    { countries: ['DE'] },
    { reviewed_guidance: undefined },
  ]) {
    expect(
      renderToStaticMarkup(<RecommendedApproach signal={{ ...signal, ...changed } as Signal} />),
    ).toBe('')
  }
})
