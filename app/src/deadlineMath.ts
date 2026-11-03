import type { DeadlineEvent } from './types'

export function validCalendarDate(value: string) {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value
  )
}
/** Resolve a named zone only when that wall time has one possible instant. */
export function zonedDateTimeInstant(day: string, time: string, zone: string): number | null {
  if (!validCalendarDate(day) || !/^\d{2}:\d{2}(?::\d{2})?$/.test(time)) return null
  const target = Date.parse(`${day}T${time.length === 5 ? `${time}:00` : time}Z`)
  if (!Number.isFinite(target)) return null
  try {
    const formatter = new Intl.DateTimeFormat('en-CA', {
      timeZone: zone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    })
    const wallTime = (instant: number) => {
      const p = Object.fromEntries(
        formatter.formatToParts(instant).map((part) => [part.type, part.value]),
      )
      return Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`)
    }
    const candidates = new Set<number>()
    for (const shift of [-86400000, 0, 86400000]) {
      const sample = target + shift
      const candidate = target - (wallTime(sample) - sample)
      if (wallTime(candidate) === target) candidates.add(candidate)
    }
    return candidates.size === 1 ? [...candidates][0] : null
  } catch {
    return null
  }
}
export function deadlineEventValue(event: DeadlineEvent): string | null {
  if (
    event.precision === 'instant' &&
    event.instant &&
    /(?:Z|[+-]\d{2}:?\d{2})$/i.test(event.instant) &&
    Number.isFinite(Date.parse(event.instant))
  )
    return event.instant
  if (event.precision === 'local_time' && event.time && event.timezone) {
    const instant = zonedDateTimeInstant(event.date, event.time, event.timezone)
    if (instant !== null) return new Date(instant).toISOString()
  }
  return validCalendarDate(event.date) ? event.date : null
}
export function dateOnlyEnd(day: string, zone?: string | null) {
  if (!validCalendarDate(day)) return NaN
  if (zone) {
    const end = zonedDateTimeInstant(day, '23:59:59', zone)
    if (end !== null) return end + 999
  }
  // Without a published zone the last possible local calendar day is conservative.
  return Date.parse(day) + 36 * 3600000 - 1
}
