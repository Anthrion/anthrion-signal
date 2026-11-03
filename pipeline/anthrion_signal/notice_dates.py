"""Dates explicitly published in source-specific application windows.

Digital Outcomes numeric dates are day/month/year and specified clock times
use Europe/London. The Find a Tender prose fallback retains unknown timezones.
A date without a time stays date-only; we never manufacture a clock time or
infer a missing year. Initial submission stages precede invitation-only tenders.
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
MONTH_FIRST_DATE = re.compile(r"\b(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<year>20\d{2})\b", re.I)
TIME = re.compile(r"\b(?:(?P<hour>\d{1,2})(?::(?P<minute>\d{2})\s*(?P<meridian>am|pm)?|\s*(?P<short>am|pm))|(?P<noon>noon|midday))\b", re.I)
LABEL = re.compile(
    r"\b(?:application closing date|tender submission deadline|closing date|"
    r"deadline for (?:applications|responses|tenders|(?:receipt of )?(?:stage\s*1\s*)?bids)|"
    r"(?:stage\s*1\s+)?(?:bids?|applications?|conditions of participation|CoP)\s+(?:submission\s+)?deadline|"
    r"(?:submission|receipt) of (?:stage\s*1\s+)?(?:bids|applications|conditions of participation|CoP))\b", re.I)


def _date(text, match):
    numeric = match.groupdict().get('numeric')
    month = int(numeric) if numeric else MONTHS.get(match['month'].lower())
    if not month:
        return None
    try:
        value = datetime(int(match['year']), month, int(match['day']))
        # Clock may precede the date in a table, or immediately follow it.
        before, after = text[:match.start()], text[match.end():]
        clock = TIME.search(before) or TIME.match(re.sub(r'^at\s+', '', after.lstrip(' ,;()-'), flags=re.I).strip())
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
    """Unresolved response timelines and old starts do not confirm an open bid."""
    if deadline:
        return False
    # A yearless/TBC submission row must not become OPEN merely because a later
    # project start has a year. Only inspect the source's actual timeline section.
    timeline = re.search(r"(?:^|\n|\b\d+\.\s*)Timeline\b(?P<body>.*?)(?=\b\d+\.\s*(?:Contracted out service|How to apply)\b|$)", text, re.I | re.S)
    if timeline and LABEL.search(timeline['body']):
        return True
    start = re.search(r"\bLatest start date\s+(20\d{2}-\d{2}-\d{2})\b", text, re.I)
    if not start:
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


def _zoned_local_instant(day, clock, zone):
    """Resolve only one real wall-clock instant, including DST folds and gaps."""
    try:
        local = datetime.fromisoformat(f"{day}T{clock}")
        candidates = {local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
                      for fold in (0, 1)}
        candidates = {candidate for candidate in candidates
                      if candidate.astimezone(zone).replace(tzinfo=None) == local}
        return next(iter(candidates)) if len(candidates) == 1 else None
    except ValueError:
        return None


def deadline_event_instant(event):
    """Comparison boundary for a source fact; never rewrite its published precision."""
    if event.precision == "instant" and event.instant and re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", event.instant):
        instant = parse_date(event.instant)
        if instant:
            return instant
    try:
        zone = ZoneInfo(event.timezone) if event.timezone else None
    except (KeyError, ValueError):
        zone = None
    if event.precision == "local_time" and event.time and zone:
        instant = _zoned_local_instant(event.date, event.time, zone)
        if instant:
            return instant
    if zone:
        end = _zoned_local_instant(event.date, "23:59:59", zone)
        if end:
            return end + timedelta(microseconds=999999)
    return response_deadline_instant(event.date)


def signal_response_deadline(signal):
    """Use current public-entry stages and retain any still-open response lot."""
    if signal.deadlines:
        current = [event for event in signal.deadlines if event.status == "current"
                   and event.kind not in {"questions", "invited_submission"}]
        initial = [event for event in current if event.kind in {"application", "expression_of_interest"}]
        values = [deadline_event_instant(event) for event in (initial or current)]
    else:
        values = [response_deadline_instant(value)
                  for value in (signal.response_deadlines or [signal.deadline_at])]
    return max((value for value in values if value), default=None)


def engagement_notice_deadline(signal):
    """Lifecycle-only fallback for explicit Find a Tender engagement closures.

    Do not mine general milestones or lot prose, infer years/timezones, overwrite
    source facts, or let prose compete with structured response windows.
    """
    if signal.source != 'find_tender' or signal.signal_type not in {'EARLY_MARKET_ENGAGEMENT', 'RFI'}:
        return None
    if signal_response_deadline(signal) or any(response_deadline_instant(value) for value in (
            signal.deadline_at, *signal.response_deadlines, *(lot.deadline_at for lot in signal.lots)) if value):
        return None
    # Explicitly disputed/withdrawn facts are not absence of data. An old prose
    # sentence must not revive a superseded or conflicting date.
    if any(event.kind not in {'questions', 'invited_submission'} for event in signal.deadlines):
        return None
    text = re.split(r'\bLot\s+[A-Za-z0-9][\w.-]*\s*:', signal.description, maxsplit=1, flags=re.I)[0]
    if re.search(r'\b(?:previous|original|historical|superseded|withdrawn|cancelled|canceled|draft)\s+(?:notice|engagement|closing date|response deadline)\b', text, re.I):
        return None
    if re.search(r'\b(?:new|revised|extended|superseded|postponed)\s+(?:response\s+)?(?:deadline|closing date|notice)\b|'
                 r'\b(?:deadline|closing date|response window)\b[^.!?]{0,50}\b(?:extended|revised|changed|amended|superseded|postponed)\b', text, re.I):
        return None
    label = re.compile(r'(?:^|(?<=[.!?\n])\s+)(?:The deadline for submitting your response is|This notice will be kept open until)\s+', re.I)
    candidates = []
    for found in label.finditer(text):
        context = text[max(0, found.start() - 140):found.end()]
        if re.search(r'\b(?:previous|original|superseded|historical|quoted?|example|indicative|provisional|draft|future questionnaire)\b', context, re.I):
            continue
        tail = re.split(r'[.!?\n]', text[found.end():found.end() + 100], maxsplit=1)[0].strip()
        match = DATE.search(tail) or MONTH_FIRST_DATE.search(tail)
        if not match:
            return None
        prefix = tail[:match.start()]
        prefix = re.sub(r'^\s*(?:by|on|at)\s+', '', prefix, flags=re.I)
        prefix = re.sub(r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*$', '', prefix, flags=re.I).strip()
        suffix = re.sub(r'^\s*(?:at|by)\s+', '', tail[match.end():], flags=re.I).strip()
        zone = re.search(r'\s+(GMT|UTC|BST)$', suffix, re.I)
        clock = suffix[:zone.start()].strip() if zone else suffix
        if ((prefix and not TIME.fullmatch(prefix)) or (clock and not TIME.fullmatch(clock))
                or (prefix and clock)):
            return None
        value = _date(tail, match)
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        published = parse_date(signal.published_at)
        if published and parsed.date() < published.date():
            continue
        if 'T' in value:
            # Find a Tender prose need not identify a timezone. Keep such dates
            # reviewable through the whole last possible calendar day.
            offset = timezone(timedelta(hours=1)) if zone and zone[1].upper() == 'BST' else timezone.utc
            value = parsed.replace(tzinfo=offset if zone else None).isoformat()
        candidates.append(value)
    # Repeated parent/lot copy is harmless; conflicting self-notice dates need
    # review rather than selecting the old date and hiding a possible extension.
    if len(set(candidates)) != 1:
        return None
    return response_deadline_instant(candidates[0])
