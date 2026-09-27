import { expect, test } from 'vitest'
import { noticeDescription } from './noticeDescription'
import type { Signal } from './types'

const lot = (id: string, title = '', description = '') => ({
  id,
  title,
  description,
  status: 'active',
  source_url: 'https://example.gov/notice',
})
const source = { source: 'find_tender', lots: [lot('1'), lot('2', 'CRM', 'Configure Salesforce')] }

test('only an exact structured lot suffix is tidied; source facts are immutable', () => {
  const text = 'Scope is None of the above. Lot 1: None. None Lot 2: CRM. Configure Salesforce'
  const record = Object.freeze({ ...source, description: text })
  expect(noticeDescription(record, text)).toBe(
    'Scope is None of the above. Lot 2: CRM. Configure Salesforce',
  )
  expect(record.description).toBe(text)
  expect(
    noticeDescription({ source: 'find_tender', lots: [lot('1')] }, 'Buyer scope. Lot 1: .'),
  ).toBe('Buyer scope.')
  expect(
    noticeDescription(
      { source: 'find_tender', lots: [lot('1', '', 'Delivery scope')] },
      'Buyer scope. Lot 1: None. Delivery scope',
    ),
  ).toBe('Buyer scope. Lot 1: Delivery scope')
})

test('mismatched, truncated, translated and substantive None text survive', () => {
  for (const text of [
    'Lot 1: None. None This is buyer prose.',
    'Scope. Lot 1: None. None Lot 2: CRM. Configure',
    'Scope. Lot 1: None. None Lot 2: Different title. Configure Salesforce',
    'Umfang. Los 1: Kein. Kein Los 2: CRM. Salesforce konfigurieren',
  ])
    expect(noticeDescription(source, text)).toBe(text)
  const realNone = { source: 'find_tender', lots: [lot('1', 'None', 'None')] }
  expect(noticeDescription(realNone, 'Scope. Lot 1: None. None')).toBe('Scope. Lot 1: None. None')
  expect(noticeDescription({ source: 'ted', lots: [lot('1')] }, 'Scope. Lot 1: None. None')).toBe(
    'Scope. Lot 1: None. None',
  )
  expect(noticeDescription({ source: 'find_tender', lots: [lot('1')] }, 'Lot 1: None. None')).toBe(
    'Lot 1: None. None',
  )
})

test('lot identifiers are literal, never interpreted as a regular expression', () => {
  expect(
    noticeDescription({ source: 'germany', lots: [lot('[1].*')] }, 'Scope. Lot [1].*: None. None'),
  ).toBe('Scope.')
  expect(
    noticeDescription({ source: 'germany', lots: [lot('[1].*')] }, 'Scope. Lot 1ZZ: None. None'),
  ).toBe('Scope. Lot 1ZZ: None. None')
})

const header =
  'Beta This is a new service – your feedback will help us to improve it. Home Digital Outcomes opportunities Procurement details '
const footer =
  ' Help You can contact us by email, phone or using the enquiry form (opens in a new tab) . Email: info@gca.gov.uk Telephone: 0345 410 2222 GCA customer services team is available Monday to Friday, 9am to 5pm.'
const notice =
  'Example Council. Search criteria used: suppliers providing Salesforce. Support the help desk from 9am to 5pm.'

test('Digital Outcomes presentation drops exact GOV.UK chrome and preserves buyer criteria', () => {
  const record = { source: 'digital_outcomes' } as Signal
  expect(noticeDescription(record, header + notice + footer)).toBe(notice)
  expect(noticeDescription(record, header + notice)).toBe(notice)
  expect(noticeDescription(record, notice + footer)).toBe(notice + footer)
  expect(noticeDescription({ source: 'ted' }, header + notice + footer)).toBe(
    header + notice + footer,
  )
  expect(noticeDescription(record, header + notice + ' Help Contact the buyer by 5pm.')).toBe(
    notice + ' Help Contact the buyer by 5pm.',
  )
})
