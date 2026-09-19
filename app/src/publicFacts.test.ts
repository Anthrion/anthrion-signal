import { describe, expect, test } from 'vitest'
import type { Dataset, DeadlineEvent, Signal } from './types'
import { recordDataset } from '../tests/fixtures/record'
import { dateOnlyEnd, deadlineEventValue, zonedDateTimeInstant } from './deadlineMath'
import { amountPresentation, deadlineEventCalendarURL, deadlinePresentation } from './publicFacts'
import { lifecycleState, responseDeadline, selectedResponseDeadlineEvent } from './lib'
import { relatedAwards, samePublishedBuyer } from './research'

const signal = recordDataset({} as Dataset).signals[0]
const deadline: DeadlineEvent = {
  kind: 'application',
  date: '2026-10-19',
  precision: 'date',
  source_text: 'Applications close 19 October',
  source_url: 'https://example.gov/deadline',
  status: 'current',
}
describe('published financial and deadline facts', () => {
  test('grant floors and ceilings remain a labelled range; missing values remain unknown', () => {
    expect(
      amountPresentation(
        {
          ...signal,
          amount: {
            kind: 'grant_range',
            minimum: 250000,
            maximum: 200000000,
            currency: 'USD',
            source_label: 'Award floor / ceiling',
            source_url: signal.primary_source_url,
          },
        },
        false,
      ),
    ).toMatchObject({ label: 'Published grant range', value: 'US$250,000–US$200,000,000' })
    expect(amountPresentation({ ...signal, value_min: null, value_max: null }).value).toBe(
      'Value not published',
    )
  })
  test('date-only notices are not closed at an invented midnight and calendar entries stay all-day', () => {
    const row = { ...signal, deadline_at: '2026-10-19', deadlines: [deadline] }
    expect(lifecycleState(row, Date.parse('2026-10-19T18:00:00Z'))).toBe('OPEN')
    expect(lifecycleState(row, Date.parse('2026-10-20T12:00:00Z'))).toBe('EXPIRED')
    const url = new URL(deadlineEventCalendarURL(row, deadline, 'https://example.test/')!)
    expect(url.searchParams.get('dates')).toBe('20261019/20261020')
    expect(url.searchParams.get('details')).toContain('Cutoff time not published')
    expect(deadlinePresentation(deadline).precision).toBe('Cutoff time not published')
  })
  test('named time zones handle daylight-saving changes and reject ambiguous or nonexistent local times', () => {
    expect(
      new Date(zonedDateTimeInstant('2026-07-10', '23:59', 'America/New_York')!).toISOString(),
    ).toBe('2026-07-11T03:59:00.000Z')
    expect(
      new Date(zonedDateTimeInstant('2026-12-10', '23:59', 'America/New_York')!).toISOString(),
    ).toBe('2026-12-11T04:59:00.000Z')
    expect(zonedDateTimeInstant('2026-11-01', '01:30', 'America/New_York')).toBeNull()
    expect(zonedDateTimeInstant('2026-03-08', '02:30', 'America/New_York')).toBeNull()
    expect(dateOnlyEnd('2026-07-10', 'Europe/London')).toBe(Date.parse('2026-07-10T22:59:59.999Z'))
  })
  test('published time labels omit only zero seconds and identify numeric UTC offsets', () => {
    const event: DeadlineEvent = {
      ...deadline,
      precision: 'instant',
      instant: '2026-10-19T08:00:00Z',
      time: '10:00:00',
      timezone: '+02:00',
    }
    expect(deadlinePresentation(event).value).toContain('10:00 UTC+02:00')
    expect(
      deadlinePresentation({ ...event, time: '10:00:31', timezone: '-04:30' }).value,
    ).toContain('10:00:31 UTC-04:30')
    expect(deadlinePresentation({ ...event, timezone: 'Europe/London' }).value).toContain(
      '10:00 Europe/London',
    )
    expect(deadlinePresentation({ ...event, timezone: undefined }).value).toContain(
      '10:00 (timezone not published)',
    )
    const calendar = new URL(deadlineEventCalendarURL(signal, event, 'https://example.test/')!)
    expect(calendar.searchParams.get('dates')).toBe('20261019T080000Z/20261019T081500Z')
    expect(event.time).toBe('10:00:00')
  })
  test('questions and invited submissions cannot extend the initial participation window', () => {
    const events: DeadlineEvent[] = [
      deadline,
      { ...deadline, kind: 'questions', date: '2026-10-01' },
      { ...deadline, kind: 'invited_submission', date: '2026-12-01' },
      { ...deadline, kind: 'tender', date: '2026-11-01' },
    ]
    const row = { ...signal, deadlines: events }
    expect(responseDeadline(row, Date.parse('2026-10-10'))).toBe('2026-10-19')
    expect(lifecycleState(row, Date.parse('2026-10-21'))).toBe('EXPIRED')
    expect(responseDeadline({ ...row, deadlines: [{ ...deadline, kind: 'questions' }] })).toBeNull()
  })
  test('the displayed response event follows stage priority and the next remaining lot regardless of source order', () => {
    const now = Date.parse('2026-10-21T12:00:00Z')
    const initial = { ...deadline, kind: 'expression_of_interest' as const }
    const tender = { ...deadline, kind: 'tender' as const, date: '2026-11-01' }
    const invited = { ...deadline, kind: 'invited_submission' as const, date: '2026-12-01' }
    const row = { ...signal, deadlines: [invited, tender, initial] }
    expect(selectedResponseDeadlineEvent(row, now)).toBe(initial)
    expect(deadlineEventValue(selectedResponseDeadlineEvent(row, now)!)).toBe(
      responseDeadline(row, now),
    )
    const remainingLot = { ...tender, date: '2026-10-26', lot_id: 'B' }
    const pastLot = { ...tender, date: '2026-10-19', lot_id: 'A' }
    expect(
      selectedResponseDeadlineEvent({ ...signal, deadlines: [tender, pastLot, remainingLot] }, now),
    ).toBe(remainingLot)
    expect(
      selectedResponseDeadlineEvent(
        { ...signal, deadlines: [{ ...deadline, kind: 'questions' }] },
        now,
      ),
    ).toBeUndefined()
    expect(
      selectedResponseDeadlineEvent(
        { ...signal, deadlines: [{ ...deadline, status: 'conflicting' }] },
        now,
      ),
    ).toBeUndefined()
    expect(selectedResponseDeadlineEvent({ ...signal, deadlines: [] }, now)).toBeUndefined()
  })
  test('extensions replace superseded events and conflicted dates do not produce calendar claims', () => {
    const extended = { ...deadline, date: '2026-11-01' }
    expect(
      responseDeadline(
        { ...signal, deadlines: [{ ...deadline, status: 'superseded' }, extended] },
        Date.parse('2026-10-10'),
      ),
    ).toBe('2026-11-01')
    expect(
      deadlineEventCalendarURL(
        signal,
        { ...deadline, status: 'conflicting' },
        'https://example.test/',
      ),
    ).toBeNull()
    expect(
      deadlineEventValue({
        ...deadline,
        precision: 'local_time',
        time: '01:30',
        timezone: 'America/New_York',
        date: '2026-11-01',
      }),
    ).toBe('2026-11-01')
  })
})
describe('transparent award relationships', () => {
  const award = (patch: Partial<Signal>): Signal => ({
    ...signal,
    id: 'award',
    status: 'awarded',
    signal_type: 'AWARD',
    lifecycle_state: 'AWARDED',
    ...patch,
  })
  test('similar names never merge identities; matching capabilities are a separate research relationship', () => {
    const current = {
      ...signal,
      buyer_id: 'buyer-one',
      buyer_name: 'Council of North City',
      countries: ['GB'],
    }
    const different = award({
      buyer_id: 'buyer-two',
      buyer_name: 'North City Council',
      matched_capabilities: current.matched_capabilities,
    })
    expect(samePublishedBuyer(current, different)).toBe(false)
    expect(relatedAwards(current, [different])[0].relationship).toBe('shared_capability')
  })
  test('explicit procedure identity outranks buyer identity, with duplicate notices deduplicated', () => {
    const current = {
      ...signal,
      procedure_id: 'ocid-one',
      buyer_id: 'buyer-one',
      buyer_identity_basis: 'identifier' as const,
    }
    const procedure = award({
      id: 'procedure',
      procedure_id: 'ocid-one',
      buyer_id: 'buyer-one',
      buyer_identity_basis: 'identifier',
    })
    const buyer = award({ id: 'buyer', buyer_id: 'buyer-one', buyer_identity_basis: 'identifier' })
    expect(
      relatedAwards(current, [buyer, procedure, procedure]).map((r) => r.relationship),
    ).toEqual(['same_procedure', 'same_buyer'])
  })
})
