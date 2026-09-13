import copy
from datetime import timedelta

import httpx
import pytest

from anthrion_signal.collectors import Http, RawRecord
from anthrion_signal.discovery import is_public_opportunity
from anthrion_signal.la_ramp import collect_la_ramp, normalise_la_ramp


def source(config):
    return next(s for s in config["sources"]["sources"] if s["id"] == "la_ramp")


def row(ident="228705", **changes):
    return {"rampid": ident, "title": "Civil Case and Matter Management System", "stagename": "Open",
            "type": "RFP - Request For Proposal", "category": "Personal Services", "department": "City Attorney",
            "bidpost": "2026-07-21T00:00:00.000", "closedate": "2026-09-29T00:00:00.000",
            "url": {"url": "https://www.rampla.org/s/opportunity-details?id=" + ident}, **changes}


def transport(rows, revision, *, count=None, changed=False):
    checks = 0
    def handler(request):
        nonlocal checks
        if "/api/views/" in request.url.path:
            checks += 1
            return httpx.Response(200, json={"rowsUpdatedAt": revision + int(changed and checks > 1),
                "columns": [{"fieldName": "rampid", "cachedContents": {"count": str(len(rows) if count is None else count)}}]})
        return httpx.Response(200, json=rows)
    return Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)


def collect(config, now, rows, state=None, **options):
    return collect_la_ramp(source(config), state or {}, now, transport(rows, int(now.timestamp()), **options),
                           {**config["runtime"], "refresh_daily": True}, {})


def test_verified_snapshot_keeps_utc_dates_and_stable_identity(config, now):
    result = collect(config, now, [row()])
    assert result.complete and result.pages == 3
    signal = normalise_la_ramp(result.records[0])
    assert signal.deadline_at == "2026-09-29T00:00:00+00:00"
    assert signal.signal_type == "RFP" and is_public_opportunity(signal, now)
    changed = normalise_la_ramp(RawRecord(row(title="Revised case management requirements"), source(config), now.isoformat(), "la_ramp"))
    assert changed.id == signal.id


@pytest.mark.parametrize("options", [{"count": 2}, {"changed": True}])
def test_incomplete_or_moving_snapshot_cannot_remove_previous_records(config, now, options):
    state = {"open_rows": {"999": row("999")}, "watermark": "2026-09-01T00:00:00Z"}
    untouched = copy.deepcopy(state)
    result = collect(config, now, [row()], state, **options)
    assert not result.complete and not result.records
    assert result.state == untouched and state == untouched


def test_removal_needs_two_independent_revisions_and_reappearance_reopens(config, now):
    initial = collect(config, now, [row(), row("999")])
    first = collect(config, now + timedelta(days=1), [row()], initial.state)
    assert len(first.records) == 1 and "999" in first.state["open_rows"]
    same = collect(config, now + timedelta(days=1), [row()], first.state)
    assert len(same.records) == 1
    second = collect(config, now + timedelta(days=2), [row()], same.state)
    removed = normalise_la_ramp(next(r for r in second.records if r.data["rampid"] == "999"))
    assert removed.status == "not_listed" and not is_public_opportunity(removed, now)
    reappeared = collect(config, now + timedelta(days=3), [row(), row("999")], second.state)
    assert normalise_la_ramp(reappeared.records[1]).status == "active"


def test_task_order_is_held_until_participation_rights_are_confirmed(config, now):
    signal = normalise_la_ramp(RawRecord(row(type="TOS - Task Order Solicitation", title="Salesforce implementation"),
                                        source(config), now.isoformat(), "la_ramp"))
    assert signal.status == "restricted"
    assert not is_public_opportunity(signal, now)
    assert "Task-order" in signal.eligibility_text


def test_daily_cadence_does_not_make_unnecessary_requests(config, now):
    http = Http(transport=httpx.MockTransport(lambda _: pytest.fail("Daily source requested too early")))
    state = {"watermark": (now - timedelta(hours=1)).isoformat()}
    result = collect_la_ramp(source(config), state, now, http, config["runtime"], {})
    assert result.complete and result.pages == 0 and result.state == state


def test_unknown_status_and_unofficial_links_do_not_become_available(config, now):
    assert not collect(config, now, [row(url={"url": "https://example.com/login"})]).complete
    signal = normalise_la_ramp(RawRecord(row(stagename="Unknown new status"), source(config), now.isoformat(), "la_ramp"))
    assert not is_public_opportunity(signal, now)
