"""Keep publication lifecycle aligned with the browser's source-fact deadlines."""
from datetime import UTC, datetime

import pytest

from anthrion_signal.discovery import is_public_opportunity, lifecycle
from anthrion_signal.models import Deadline
from anthrion_signal.notice_dates import signal_response_deadline


def fact(**patch):
    return Deadline(**{"kind": "tender", "date": "2026-09-17", "precision": "local_time",
                       "time": "23:59:00", "source_text": "2026-09-17T23:59:00",
                       "source_url": "https://example.test/notice", **patch})


def test_unzoned_local_deadline_is_not_lost_when_legacy_fields_are_empty(signal):
    signal.deadline_at, signal.response_deadlines = None, []
    signal.deadlines = [fact()]
    original = signal.model_dump()
    assert lifecycle(signal, datetime(2026, 9, 18, 11, tzinfo=UTC))[0] == "OPEN"
    assert not is_public_opportunity(signal, datetime(2026, 9, 18, 12, tzinfo=UTC))
    assert signal.model_dump() == original


@pytest.mark.parametrize("events,expected", [
    ([fact(kind="questions")], None),
    ([fact(kind="invited_submission")], None),
    ([fact(status="superseded")], None),
    ([fact(status="conflicting")], None),
    ([fact(status="superseded"), fact(date="2026-10-01")], "2026-10-02T11:59:59.999999+00:00"),
    ([fact(kind="application"), fact(date="2026-10-01")], "2026-09-18T11:59:59.999999+00:00"),
    ([fact(kind="expression_of_interest"), fact(kind="invited_submission", date="2026-10-01")], "2026-09-18T11:59:59.999999+00:00"),
    ([fact(lot_id="A"), fact(lot_id="B", date="2026-10-01")], "2026-10-02T11:59:59.999999+00:00"),
    ([fact(precision="instant", instant="2026-09-17T23:59:00-04:00")], "2026-09-18T03:59:00+00:00"),
    ([fact(timezone="America/New_York")], "2026-09-18T03:59:00+00:00"),
    ([fact(timezone="Europe/London", precision="date", time=None)], "2026-09-17T22:59:59.999999+00:00"),
    ([fact(date="2026-11-01", time="01:30", timezone="America/New_York")], "2026-11-02T04:59:59.999999+00:00"),
    ([fact(date="2026-03-08", time="02:30", timezone="America/New_York")], "2026-03-09T03:59:59.999999+00:00"),
    ([fact(timezone="Unpublished/Zone")], "2026-09-18T11:59:59.999999+00:00"),
])
def test_stage_lot_revision_and_timezone_boundaries(signal, events, expected):
    # A stale flat field cannot override authoritative current structured facts.
    signal.deadline_at = "2027-01-01"
    signal.deadlines = events
    result = signal_response_deadline(signal)
    assert (result.astimezone(UTC).isoformat() if result else None) == expected


def test_legacy_response_fields_remain_supported(signal):
    signal.deadlines = []
    signal.response_deadlines = ["2026-09-17T10:00:00Z", "2026-09-19T11:00:00Z"]
    assert signal_response_deadline(signal) == datetime(2026, 9, 19, 11, tzinfo=UTC)
