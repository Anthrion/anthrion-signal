"""Dates explicitly published in UK Digital Outcomes application timelines.

This is deliberately source-specific: numeric dates are day/month/year and
specified clock times use Europe/London. A date without a time stays date-only;
we never manufacture a clock time or infer a missing year. Initial submission
stages take priority over invitation-only final tenders.
"""
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .utils import parse_date

MONTHS = {name.lower(): index for index, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
MONTHS.update({name[:3]: index for name, index in list(MONTHS.items())})
MONTHS['sept'] = 9
DATE = re.compile(r"\b(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:\s+(?P<month>[A-Za-z]+)\s+|/(?P<numeric>\d{1,2})/)(?P<year>20\d{2})\b", re.I)
TIME = re.compile(r"\b(?:(?P<hour>\d{1,2})(?::(?P<minute>\d{2})\s*(?P<meridian>am|pm)?|\s*(?P<short>am|pm))|(?P<noon>noon|midday))\b", re.I)
LABEL = re.compile(
    r"\b(?:application closing date|tender submission deadline|closing date|"
    r"deadline for (?:applications|responses|tenders|(?:receipt of )?(?:stage\s*1\s*)?bids)|"
    r"(?:stage\s*1\s+)?(?:bids?|applications?|conditions of participation|CoP)\s+(?:submission\s+)?deadline|"
    r"(?:submission|receipt) of (?:stage\s*1\s+)?(?:bids|applications|conditions of participation|CoP))\b", re.I)


def _date(text, match):
    month = int(match['numeric']) if match['numeric'] else MONTHS.get(match['month'].lower())
    if not month:
        return None
    try:
        value = datetime(int(match['year']), month, int(match['day']))
        # Clock may precede the date in a table, or immediately follow it.
        before, after = text[:match.start()], text[match.end():]
        clock = TIME.search(before) or TIME.match(after.lstrip(' ,;()-').removeprefix('at ').strip())
        if not clock:
            return value.date().isoformat()
        hour, minute = (12, 0) if clock['noon'] else (int(clock['hour']), int(clock['minute'] or 0))
        meridian = (clock['meridian'] or clock['short'] or '').lower()
        if meridian:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if meridian == 'pm' else 0)
        return value.replace(hour=hour, minute=minute, tzinfo=ZoneInfo('Europe/London')).isoformat()
    except ValueError:
        return None


def digital_deadline(text):
    # Later tender phases invite shortlisted suppliers, not new applicants.
    text = re.split(r"\b(?:tender phase\s*[-–:]?\s*stage\s*2\b|stage\s*2\s+(?:tender submission|bids?))", text, maxsplit=1, flags=re.I)[0]
    candidates = []
    for label in LABEL.finditer(text):
        # Don't cross another timeline row, sentence or section looking for a date.
        tail = re.split(r"\b(?:clarification|buyer responses|contract award|latest start|stage\s*2|evaluation)\b|[!?]", text[label.end():label.end() + 95], maxsplit=1, flags=re.I)[0]
        match = DATE.search(tail)
        if match:
            value = _date(tail, match)
            if value:
                candidates.append(value)
        else:
            # Date-first timelines, e.g. '09 Sep 2026 - Deadline for Submission of Bids'.
            prefix = text[max(0, label.start() - 65):label.start()]
            dates = list(DATE.finditer(prefix))
            if dates and re.fullmatch(r"\s*[-–:]?\s*(?:Deadline for\s+)?", prefix[dates[-1].end():], re.I):
                value = _date(prefix, dates[-1])
                if value:
                    candidates.append(value)
    # The service also renders the closing date before its label in the header.
    for match in DATE.finditer(text):
        if re.match(r"\s+Application closing date\b", text[match.end():], re.I):
            value = _date(match.group(), DATE.search(match.group()))
            if value:
                candidates.append(value)
    # Prefer an explicitly timed entry when the header repeats its date only.
    by_day = {}
    for value in candidates:
        key = value[:10]
        if key not in by_day or len(value) > len(by_day[key]):
            by_day[key] = value
    return by_day[min(by_day)] if by_day else None


def digital_window_uncertain(text, deadline, now):
    """An old planned start is not an invented deadline or evidence of an open bid."""
    start = re.search(r"\bLatest start date\s+(20\d{2}-\d{2}-\d{2})\b", text, re.I)
    if deadline or not start:
        return False
    try:
        return datetime.strptime(start[1], '%Y-%m-%d').date() < now.date()
    except ValueError:
        return False


def digital_deadline_instant(value):
    # Date-only UK closing dates remain usable throughout that calendar day.
    # This comparison boundary is never added to the published source facts.
    parsed = parse_date(value)
    if parsed and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return datetime.combine(parsed.date(), time.max, tzinfo=ZoneInfo('Europe/London'))
    return parsed


def response_deadline_instant(value, source_timezone=None):
    """Comparison only: never publish an invented cutoff for an untimed date.

    Unknown timezones stay reviewable through the last timezone's calendar day.
    Source-local timed values without an offset also cannot establish an instant.
    """
    parsed = parse_date(value)
    if not parsed:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[+-]\d{2}:\d{2})?", value) or not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
        zone = ZoneInfo(source_timezone) if source_timezone else timezone(timedelta(hours=-12))
        day = datetime.strptime(value[:10], "%Y-%m-%d").date()
        return datetime.combine(day, time.max, tzinfo=zone)
    return parsed
