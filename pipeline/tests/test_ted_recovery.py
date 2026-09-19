import copy
import json
from datetime import timedelta

import httpx
import pytest

from anthrion_signal.collectors import Http, RawRecord, collect_ted, collect_ted_discovery, ted_keyword_groups
from anthrion_signal.discovery import is_public_opportunity, lifecycle
from anthrion_signal.dedupe import reconcile
from anthrion_signal.normalise import normalise_ted


def source(config):
    return next(s for s in config["sources"]["sources"] if s["id"] == "ted")


def notice(**changes):
    return {"publication-number": "635159-2025", "title-proc": "CRM software renewal competition",
            "form-type": "competition", "notice-type": "cn-standard", "buyer-country": ["DEU"], **changes}


def test_keyword_lane_is_additive_bounded_and_resumes_exact_query(config, now):
    bodies = []
    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(200, json={"notices": [notice()], "iterationNextToken": "next-" + str(len(bodies))})
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    terms = {**config["search_terms"], "discovery_phrases": ["Salesforce Public Sector", "OmniStudio", "τεχνητή νοημοσύνη"]}
    settings = {**config["runtime"], "max_pages": 5}
    initial = {}
    first = collect_ted_discovery(source(config), initial, now, http, settings, terms)
    assert initial == {} and first.pages == 5
    assert "classification-cpv IN" in bodies[0]["query"]
    old_keyword = next(body for body in bodies if body["scope"] == "ALL" and "classification-cpv" not in body["query"])
    assert 'FT ~ "Salesforce Public Sector"' in old_keyword["query"]
    assert 'buyer-country IN' in old_keyword["query"]
    old_token = "next-" + str(bodies.index(old_keyword) + 1)
    assert sum(body["scope"] == "ACTIVE" for body in bodies) == 2
    frozen_state = copy.deepcopy(first.state)
    second = collect_ted_discovery(source(config), first.state, now + timedelta(hours=1), http, settings, terms)
    assert first.state == frozen_state and second.pages <= 5
    new_keyword = next(body for body in bodies[5:] if body["scope"] == "ALL" and "classification-cpv" not in body["query"])
    assert new_keyword["query"] == old_keyword["query"]
    assert new_keyword["iterationNextToken"] == old_token


def test_changed_keyword_query_does_not_reuse_old_continuation_or_reset_cpv(config, now):
    bodies = []
    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"notices": [notice()], "iterationNextToken": str(len(bodies))})
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    settings = {**config["runtime"], "max_pages": 5}
    first = collect_ted_discovery(source(config), {}, now, http, settings,
                                  {**config["search_terms"], "discovery_phrases": ["CRM"]})
    second = collect_ted_discovery(source(config), first.state, now, http, settings,
                                   {**config["search_terms"], "discovery_phrases": ["OmniStudio"]})
    assert "iterationNextToken" in bodies[5]
    keyword = next(body for body in bodies[5:] if body["scope"] == "ALL" and "classification-cpv" not in body["query"])
    assert "iterationNextToken" not in keyword
    assert first.state["query_version"] == second.state["query_version"]
    assert len(second.state["ted_keywords"]["lanes"]) == 1


def test_keyword_requests_are_small_and_do_not_contain_generic_context(config):
    groups = ted_keyword_groups(config["search_terms"])
    assert all(len(group.encode("utf-8")) < 6000 for group in groups)
    assert not any(term in group for group in groups for term in ('FT ~ "public sector"', 'FT ~ AI OR', 'FT ~ Teams OR'))


def test_changed_query_preserves_an_unfinished_window_older_than_lookback(config, now):
    bodies = []
    http = Http(transport=httpx.MockTransport(lambda request: (
        bodies.append(json.loads(request.content)) or httpx.Response(200, json={"notices": []}))), sleeper=lambda _: None)
    old = now - timedelta(days=40)
    state = {"query_version": "old-vocabulary", "ted_pending": {"from": old.isoformat(),
        "until": (old + timedelta(days=1)).isoformat(), "through": now.isoformat(), "token": "stale"}}
    collect_ted(source(config), state, now, http, {**config["runtime"], "max_pages": 1}, config["search_terms"])
    assert old.strftime("%Y%m%d") in bodies[0]["query"]
    assert "iterationNextToken" not in bodies[0]


def test_budget_persists_token_and_exact_window_across_runs(config, now):
    bodies = []
    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(200, json={"notices": [notice()], "iterationNextToken": f"token-{len(bodies)}"})
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    settings = {**config["runtime"], "max_pages": 1}
    initial = {}
    first = collect_ted(source(config), initial, now, http, settings, config["search_terms"])
    saved = copy.deepcopy(first.state)
    second = collect_ted(source(config), saved, now + timedelta(hours=1), http, settings, config["search_terms"])
    assert initial == {} and saved == first.state
    assert not first.complete and not second.complete
    assert bodies[0]["query"] == bodies[1]["query"]
    assert bodies[1]["iterationNextToken"] == "token-1"
    assert second.state["ted_pending"]["token"] == "token-2"
    assert "watermark" not in second.state
    assert len(bodies[0]["fields"]) * bodies[0]["limit"] <= 10000


def test_expired_token_rewinds_only_unfinished_day(config, now):
    settings = {**config["runtime"], "max_pages": 1}
    first_http = Http(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
        "notices": [notice()], "iterationNextToken": "expired"})), sleeper=lambda _: None)
    first = collect_ted(source(config), {}, now, first_http, settings, config["search_terms"])
    bodies = []
    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(400) if len(bodies) == 1 else httpx.Response(200, json={"notices": []})
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    second = collect_ted(source(config), first.state, now + timedelta(hours=2), http,
                         {**settings, "max_pages": 2}, config["search_terms"])
    assert bodies[0]["query"] == bodies[1]["query"]
    assert "iterationNextToken" not in bodies[1]
    assert second.state["watermark"] == first.state["ted_pending"]["until"]
    assert second.state["ted_pending"]["through"] == first.state["ted_pending"]["through"]
    assert not second.complete


@pytest.mark.parametrize("phase", ["request", "expressions"])
def test_expired_participation_deadline_is_not_an_open_lead(config, now, phase):
    row = notice(**{f"deadline-receipt-{phase}-date-lot": ["2025-10-27+01:00"],
                    f"deadline-receipt-{phase}-time-lot": ["10:00:00+01:00"]})
    signal = normalise_ted(RawRecord(row, source(config), now.isoformat(), "ted"))
    assert signal.deadline_at == "2025-10-27T09:00:00+00:00"
    assert not is_public_opportunity(signal, now)


@pytest.mark.parametrize("changes", [{"form-type": "dir-awa-pre"}, {"notice-type": "veat"},
                                     {"competition-termination-proc": True}])
def test_structured_direct_award_and_cancellation_are_unavailable(config, now, changes):
    signal = normalise_ted(RawRecord(notice(**changes), source(config), now.isoformat(), "ted"))
    assert not is_public_opportunity(signal, now)


def test_open_renewal_and_old_future_notice_without_deadline_stay_available(config, now):
    for changes in ({}, {"form-type": "planning", "publication-date": "2025-01-01"}):
        signal = normalise_ted(RawRecord(notice(**changes), source(config), now.isoformat(), "ted"))
        assert is_public_opportunity(signal, now)


def test_later_open_lot_is_not_removed_after_the_first_deadline(config, now):
    row = notice(**{"deadline-receipt-tender-date-lot": ["2025-10-01", "2027-10-01"]})
    signal = normalise_ted(RawRecord(row, source(config), now.isoformat(), "ted"))
    assert signal.deadline_at.startswith("2027-10-01")
    signal.deadline_at = signal.response_deadlines[0]
    assert lifecycle(signal, now)[0] == "OPEN"


def test_explicit_notice_amendment_keeps_identity_but_lot_awards_do_not_alias_the_whole_procedure(config, now):
    prior_id = "83790896-0cd3-4adf-9c41-07420c702431"
    old = normalise_ted(RawRecord(notice(**{"notice-identifier": prior_id}), source(config), now.isoformat(), "ted"))
    amended = normalise_ted(RawRecord(notice(**{"publication-number": "635160-2025",
        "change-notice-version-identifier": prior_id + "-01", "title-proc": "CRM delivery, revised scope"}),
        source(config), (now + timedelta(days=1)).isoformat(), "ted"))
    merged, _, _ = reconcile([old], [amended])
    assert len(merged) == 1 and merged[0].id == old.id
    assert merged[0].title == amended.title
    lot_award = normalise_ted(RawRecord(notice(**{"publication-number": "635161-2025", "form-type": "result",
        "previous-notice-id-proc": [prior_id + "-01"]}), source(config), now.isoformat(), "ted"))
    assert "ted-notice:" + prior_id not in lot_award.external_ids
