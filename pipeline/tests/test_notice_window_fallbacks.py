"""Self-notice response prose closes a route without manufacturing source facts."""
from datetime import UTC, datetime

import pytest

from anthrion_signal.discovery import is_public_opportunity, lifecycle
from anthrion_signal.models import Deadline, Lot
from anthrion_signal.notice_dates import engagement_notice_deadline


NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
SCOTRAIL = (
    "We invite suppliers to complete a short questionnaire via our e-sourcing portal. "
    "Any questions relating to this market engagement should be posted using the 'Messaging' tab on the e-sourcing portal. "
    "The deadline for submitting your response is by 12pm Wednesday 28th January 2026"
)
BBB = (
    "On completion of the questionnaire suppliers are kindly requested to submit via the Delta messaging centre. "
    "This notice will be kept open until January 23rd 2026 at 5pm. "
    "Following receipt and review of the completed questionnaire BBB may ask suppliers to provide a demonstration of their system."
)


def engagement(signal, description=SCOTRAIL, **updates):
    return signal.model_copy(update={
        "source": "find_tender", "signal_type": "EARLY_MARKET_ENGAGEMENT", "status": "planned",
        "procurement_stage": "planning", "published_at": "2025-12-11T11:49:46Z",
        "last_material_update": "2025-12-11T11:49:46Z", "description": description,
        "deadline_at": None, "response_deadlines": [], "deadlines": [], "lots": [], **updates,
    })


def fact(**changes):
    return Deadline(kind="tender", date="2026-12-01", precision="date", source_text="1 December 2026", source_url="https://example.test/notice").model_copy(update=changes)


@pytest.mark.parametrize("description", [SCOTRAIL, BBB, SCOTRAIL + " Lot 1: . " + SCOTRAIL])
def test_explicit_engagement_closure_retires_missing_structured_response(signal, description):
    candidate = engagement(signal, description)
    before = candidate.model_dump()
    assert lifecycle(candidate, NOW)[0] == "EXPIRED"
    assert not is_public_opportunity(candidate, NOW)
    assert candidate.model_dump() == before


@pytest.mark.parametrize("changes", [
    {"deadline_at": "2026-12-01T12:00:00Z"},
    {"response_deadlines": ["2026-12-01T12:00:00Z"]},
    {"deadlines": [fact(kind="expression_of_interest")]},
    {"deadlines": [fact(lot_id="2")]},
    {"lots": [Lot(id="2", status="active", deadline_at="2026-12-01T12:00:00Z", source_url="https://example.test/notice")]},
    {"deadlines": [fact(date="2026-01-28", status="superseded")]},
    {"deadlines": [fact(date="2026-01-28", status="conflicting")]},
])
def test_prose_does_not_override_response_facts_or_lots(signal, changes):
    candidate = engagement(signal, **changes)
    assert engagement_notice_deadline(candidate) is None
    assert lifecycle(candidate, NOW)[0] != "EXPIRED"
    assert is_public_opportunity(candidate, NOW)


@pytest.mark.parametrize("description", [
    'The previous notice stated: "' + SCOTRAIL + '"',
    'Previous notice. ' + SCOTRAIL,
    '"The deadline for submitting your response is by 12pm Wednesday 28th January 2026"',
    'Example. This notice will be kept open until January 23rd 2026 at 5pm.',
    'Future questionnaire. This notice will be kept open until January 23rd 2026 at 5pm.',
    'The deadline for submitting your response is by 12pm Wednesday 28th January.',
    'The deadline for submitting your response is by 12pm 31st February 2026.',
    'The deadline for completing the project is 28th January 2026.',
    'This notice will be kept open until the future questionnaire closes on January 23rd 2026 at 5pm.',
    'This notice will be kept open until January 23rd 2026 at 5pm subject to confirmation.',
    'This notice will be kept open until January 23rd 2026 at 5pm CET.',
    'This notice will be kept open until January 23rd 2025 at 5pm.',
    BBB + ' This notice will be kept open until December 23rd 2026 at 5pm.',
    BBB + ' The response deadline has been extended to December 23rd 2026.',
    BBB + ' New deadline: December 23rd 2026.',
    'Lot 1: ' + SCOTRAIL,
    'Lot LOT-0001: ' + SCOTRAIL,
    'Lot A: ' + SCOTRAIL,
])
def test_ambiguous_quoted_milestone_or_revised_prose_stays_reviewable(signal, description):
    candidate = engagement(signal, description)
    assert engagement_notice_deadline(candidate) is None
    assert lifecycle(candidate, NOW)[0] == "UNKNOWN"
    assert is_public_opportunity(candidate, NOW)


@pytest.mark.parametrize("changes", [{"source": "ted"}, {"signal_type": "PIPELINE"}, {"signal_type": "LIVE_TENDER", "status": "open", "procurement_stage": "tender"}])
def test_fallback_is_limited_to_fts_engagements(signal, changes):
    assert engagement_notice_deadline(engagement(signal, **changes)) is None


@pytest.mark.parametrize("date,expected", [
    ("29th September 2026", "2026-09-30T11:59:59.999999+00:00"),
    ("September 29th 2026 at 5pm", "2026-09-30T11:59:59.999999+00:00"),
    ("September 29th 2026 at 5pm GMT", "2026-09-29T17:00:00+00:00"),
    ("September 29th 2026 at 5pm BST", "2026-09-29T16:00:00+00:00"),
])
def test_comparison_preserves_untimed_and_unzoned_precision(signal, date, expected):
    candidate = engagement(signal, f"This notice will be kept open until {date}.")
    before = candidate.model_dump()
    deadline = engagement_notice_deadline(candidate)
    assert deadline.astimezone(UTC).isoformat() == expected
    assert lifecycle(candidate, NOW)[0] == "EARLY_ENGAGEMENT"
    assert candidate.model_dump() == before


def test_question_deadline_cannot_reopen_expired_response(signal):
    candidate = engagement(signal, deadlines=[fact(kind="questions")])
    assert lifecycle(candidate, NOW)[0] == "EXPIRED"


def test_yearless_indicative_dos_timeline_stays_unknown_despite_future_start(signal):
    candidate = signal.model_copy(update={
        "source": "digital_outcomes", "status": "open", "deadline_at": None,
        "response_deadlines": [], "deadlines": [], "description":
        "3. Latest start date 2026-10-30 9. Timeline THIS IS AN INDICATIVE TIMELINE. "
        "ITT published 07/08. Tender submission deadline 04/09. Standstill letters 21/09. "
        "Call-Off Contract signed 06/10. Estimated Call-Off Contract start date 12/10 "
        "10. Contracted out service or supply of resource Contracted out service. 11. How to apply Instructions to be issued.",
    })
    before = candidate.model_dump()
    assert lifecycle(candidate, NOW)[0] == "UNKNOWN"
    assert is_public_opportunity(candidate, NOW)
    assert candidate.model_dump() == before
    candidate.deadlines = [fact()]
    assert lifecycle(candidate, NOW)[0] == "OPEN"


def test_dos_project_milestones_and_non_timeline_prose_do_not_change_availability(signal):
    candidate = signal.model_copy(update={
        "source": "digital_outcomes", "status": "open", "deadline_at": None,
        "response_deadlines": [], "deadlines": [], "description":
        "2. Summary of work Build a service that tracks the application closing date. "
        "3. Latest start date 2026-10-30 9. Timeline Discovery October. Alpha November. "
        "10. Contracted out service or supply of resource Contracted out service.",
    })
    assert lifecycle(candidate, NOW)[0] == "OPEN"
