import copy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from anthrion_signal.collectors import SourceUnavailable
from anthrion_signal.current_inventory import collect_ted_inventory

NOW = datetime(2026, 9, 18, 20, tzinfo=UTC)
SOURCE = {"id": "ted", "url": "https://api.ted.europa.eu/v3/notices/search", "countries": ["FI", "IE"], "limit": 200}
TERMS = {"markets": {"FI": {"enabled": True, "ted_codes": ["FIN"]}, "IE": {"enabled": True, "ted_codes": ["IRL"]}},
         "collection_cpv_prefixes": ["48", "72"], "high_intent": ["Salesforce", "case management"]}


class Http:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append(kwargs["json"])
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(json=lambda: response)


def page(ids, token=None, total=None, **extra):
    return {"notices": [{"publication-number": id} for id in ids], "iterationNextToken": token,
            "totalNoticeCount": total if total is not None else len(ids), **extra}


def collect(http, state=None, budget=2, at=NOW, terms=TERMS):
    return collect_ted_inventory(SOURCE, state or {}, at, http, {"max_pages": budget}, terms)


def test_old_dps_inventory_has_no_publication_lower_bound_and_preserves_current_window():
    http = Http([page(["367551-2026"])])
    result = collect(http)
    request = http.requests[0]
    assert request["scope"] == "ACTIVE"
    assert "publication-date >=" not in request["query"]
    assert "SORT BY publication-number DESC" in request["query"]
    assert "deadline-receipt-request-date-lot >= 20260917" in request["query"]
    assert 'FT ~ "case management"' in request["query"]
    assert result.complete and result.records[0].data["publication-number"] == "367551-2026"


def test_budget_resumes_frozen_query_across_days_without_mutating_input():
    first = collect(Http([page(["1-2026"], "cursor", 2)]), budget=1)
    original = copy.deepcopy(first.state)
    http = Http([page(["2-2026"], total=2)])
    second = collect(http, first.state, at=NOW + timedelta(days=1))
    assert first.state == original
    assert http.requests[0]["iterationNextToken"] == "cursor"
    assert "20260917" in http.requests[0]["query"]
    assert second.complete and second.state["notices"] == 2


def test_does_not_claim_complete_when_provider_truncates_or_times_out():
    short = collect(Http([page(["1-2026"], total=10)]))
    assert not short.complete and "completed_at" not in short.state
    timeout = collect(Http([page(["1-2026"], timedOut=True)]))
    assert not timeout.complete and not timeout.records


def test_empty_terminal_iteration_with_token_requires_the_full_advertised_count():
    complete = collect(Http([page(["1-2026", "2-2026"], "cursor", 2), page([], "cursor", 2)]))
    assert complete.complete and complete.state["notices"] == 2
    assert "pending" not in complete.state
    truncated = collect(Http([page(["1-2026"], "cursor", 2), page([], "cursor", 2)]))
    assert not truncated.complete and "completed_at" not in truncated.state


def test_expired_cursor_restarts_once_inside_same_budget():
    first = collect(Http([page(["1-2026"], "expired", 2)]), budget=1)
    http = Http([SourceUnavailable("expired", status_code=410), page(["1-2026", "2-2026"])])
    result = collect(http, first.state)
    assert result.complete and result.pages == 2
    assert "iterationNextToken" not in http.requests[1]


def test_retry_after_and_completed_cycle_avoid_unnecessary_calls():
    first = collect(Http([page([])]))
    assert collect(Http([]), first.state, at=NOW + timedelta(hours=1)).pages == 0
    deferred = collect(Http([]), {"retry_at": (NOW + timedelta(hours=1)).isoformat()})
    assert not deferred.complete and deferred.pages == 0


def test_changed_geography_invalidates_old_token_and_repeats_are_not_success():
    first = collect(Http([page(["1-2026"], "cursor", 2)]), budget=1)
    terms = copy.deepcopy(TERMS)
    terms["markets"]["IE"]["enabled"] = False
    http = Http([page(["3-2026"])])
    assert collect(http, first.state, terms=terms).complete
    assert "iterationNextToken" not in http.requests[0]
    repeated = collect(Http([page(["1-2026"], "same", 4), page(["1-2026"], "same", 4)]))
    assert not repeated.complete and len(repeated.records) == 1


def test_provider_retry_is_preserved_and_changed_query_cannot_reuse_old_completion():
    result = collect(Http([SourceUnavailable("deferred", status_code=429, retry_at=NOW + timedelta(hours=1))]))
    assert collect(Http([]), result.state).pages == 0
    old = collect(Http([page([])]))
    terms = copy.deepcopy(TERMS)
    terms["markets"]["IE"]["enabled"] = False
    changed = collect(Http([page(["1-2026"], "next", 2)]), old.state, budget=1, terms=terms)
    assert "completed_at" not in changed.state
    resume = Http([page(["2-2026"], total=2)])
    assert collect(resume, changed.state, terms=terms).complete
    assert resume.requests[0]["iterationNextToken"] == "next"
