import type { DeadlineEvent, Signal } from './types'
import { date, googleCalendarURL } from './lib'
import { deadlineEventValue } from './deadlineMath'
export { amountLabels, amountPresentation } from './lib'
export const deadlineLabels: Record<string, string> = {
  questions: 'Questions due',
  expression_of_interest: 'Expressions of interest due',
  application: 'Applications due',
  invited_submission: 'Invited submissions due',
  tender: 'Tenders due',
  unknown: 'Response due',
}
export function deadlinePresentation(event: DeadlineEvent) {
  const time = event.time?.replace(/^(\d{2}:\d{2}):00$/, '$1')
  const timezone =
    event.timezone && /^[+-]\d{2}(?::?\d{2})?$/.test(event.timezone)
      ? `UTC${event.timezone}`
      : event.timezone
  const local = `${date(event.date)}${time ? `, ${time}${timezone ? ` ${timezone}` : ' (timezone not published)'}` : ''}`
  let value = local
  if (event.precision === 'instant' && event.instant && !event.time) {
    try {
      value =
        new Intl.DateTimeFormat('en-GB', {
          dateStyle: 'medium',
          timeStyle: 'short',
          timeZone: event.timezone || 'UTC',
        }).format(new Date(event.instant)) + ` ${event.timezone || 'UTC'}`
    } catch {
      /* Keep the source date if the zone cannot be rendered. */
    }
  }
  return {
    label: deadlineLabels[event.kind] || 'Response due',
    value,
    precision: event.precision === 'date' ? 'Cutoff time not published' : '',
    status: event.status,
    sourceURL: event.source_url,
  }
}
export function deadlineEventCalendarURL(
  signal: Signal,
  event: DeadlineEvent,
  appURL: string,
  text = { title: signal.title, buyerName: signal.buyer_name },
) {
  if (event.status !== 'current') return null
  const value = deadlineEventValue(event)
  if (!value || (event.precision !== 'date' && /^\d{4}-\d{2}-\d{2}$/.test(value))) return null
  const calendar = googleCalendarURL(
    { ...signal, deadlines: [], response_deadlines: [], deadline_at: value },
    appURL,
    text,
  )
  if (!calendar) return null
  const url = new URL(calendar)
  url.searchParams.set('text', `${deadlineLabels[event.kind] || 'Deadline'}: ${text.title}`)
  const shown = deadlinePresentation(event)
  url.searchParams.set(
    'details',
    `${shown.label}: ${shown.value}${shown.precision ? `\n${shown.precision}` : ''}\n${url.searchParams.get('details') || ''}`,
  )
  return url.href
}
