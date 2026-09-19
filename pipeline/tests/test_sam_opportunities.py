import copy
import csv
import io
from datetime import timedelta
from email.utils import format_datetime

import httpx
import pytest

from anthrion_signal.collectors import Http, RawRecord, SourceUnavailable
from anthrion_signal.dedupe import merge
from anthrion_signal.discovery import lifecycle
from anthrion_signal.sam_opportunities import (EXTRACT_URL, FIELDS, collect_sam_opportunities,
    normalise_sam_opportunity, parse_snapshot, removed_sam_records)


def source(config):
    return {**next(s for s in config["sources"]["sources"] if s["id"] == "sam"), "minimum_rows": 1}


def row(ident="a" * 32, **changes):
    return {**dict.fromkeys(FIELDS, ""), "NoticeId": ident, "Title": "Customer services platform implementation",
        "Description": "Implement Salesforce CRM and integrate customer casework with the finance platform.",
        "PostedDate": "2026-09-08 11:34:00", "Type": "Solicitation", "BaseType": "Solicitation", "Active": "Yes",
        "ResponseDeadLine": "2026-10-01T14:30:00-04:00", "Office": "Example federal acquisition office",
        "AAC Code": "123456", "Department/Ind.Agency": "Example department", "Sub-Tier": "Example agency",
        "Sol#": "CRM-2026", "NaicsCode": "541512", "PopCountry": "DEU", **changes}


def csv_bytes(rows, encoding="utf-8", fields=FIELDS):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode(encoding)


def collect(config, now, rows, state=None, revision='"version-1"', body=None, **options):
    content = csv_bytes(rows) if body is None else body
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == EXTRACT_URL
        assert not request.url.query and "Authorization" not in request.headers
        headers = {"Content-Length": str(len(content)), "ETag": revision, "Last-Modified": format_datetime(now)}
        if request.method == "HEAD":
            headers.update(options.get("head", {}))
            return httpx.Response(options.get("head_status", 200), headers=headers)
        assert request.headers["If-Match"] == revision
        headers.update(options.get("get", {}))
        return httpx.Response(options.get("status", 200), headers=headers, content=content)
    http = Http(transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    try:
        result = collect_sam_opportunities({**source(config), **options.get("source_options", {})}, state or {}, now, http,
            {**config["runtime"], "refresh_daily": options.get("refresh_daily", True), "max_pages": options.get("max_pages", 80)}, {})
    finally:
        http.close()
    return result, calls


def normalise(config, now, **changes):
    return normalise_sam_opportunity(RawRecord(row(**changes), source(config), now.isoformat(), "sam_csv"))


def test_public_snapshot_includes_all_codes_and_preserves_complete_multiline_scope(config, now):
    rows = [row(Description='Agency’s requirement, with commas\n\nImplement Salesforce. ' + 'detail ' * 4500),
            row("b" * 32, Title="Water sampling services", Description="Water testing", NaicsCode="541380")]
    result, calls = collect(config, now, rows, body=csv_bytes(rows, "cp1252"))
    assert result.complete and len(result.records) == 2 and result.pages == 2
    assert len(calls) == 2 and result.state["snapshot_rows"] == 2
    signal = normalise_sam_opportunity(result.records[0])
    assert "Agency’s requirement" in signal.description and signal.description.endswith("detail")
    assert len(signal.description) > 24000
    assert signal.deadline_at == "2026-10-01T18:30:00+00:00"
    assert signal.deadlines[0].source_text == "2026-10-01T14:30:00-04:00"
    assert signal.published_at == "2026-09-08" and signal.countries == ["US"]
    assert signal.buyer_name == "Example federal acquisition office"
    assert signal.buyer_identifiers == ["sam-office:123456"]
    assert signal.amount.maximum is None and signal.amount.kind == "unknown" and signal.source_language == "en"
    assert signal.primary_source_url == "https://sam.gov/opp/" + "a" * 32 + "/view"


def test_unchanged_snapshot_skips_download_and_daily_cooldown_skips_requests(config, now):
    first, _ = collect(config, now, [row()])
    same, calls = collect(config, now + timedelta(hours=1), [row()], first.state)
    assert same.complete and not same.records and len(calls) == 1
    skipped, calls = collect(config, now + timedelta(hours=2), [row()], same.state, refresh_daily=False)
    assert skipped.complete and not skipped.records and not calls
    # A new file containing identical notices should not grow rejection storage.
    revised, _ = collect(config, now + timedelta(days=1), [row()], first.state, revision='"version-2"')
    assert revised.complete and not revised.records


def test_amendments_keep_identity_and_publish_only_changed_records(config, now):
    first, _ = collect(config, now, [row(), row("b" * 32)])
    revised, _ = collect(config, now + timedelta(days=1), [row(ResponseDeadLine="2026-11-02"), row("b" * 32)],
                         first.state, revision='"version-2"')
    assert len(revised.records) == 1
    a, b = normalise_sam_opportunity(first.records[0]), normalise_sam_opportunity(revised.records[0])
    assert a.id == b.id and a.content_hash != b.content_hash
    updated, _ = merge(a, b)
    assert updated.deadline_at == "2026-11-02" and updated.deadlines[0].precision == "date"


@pytest.mark.parametrize("options", [
    {"head_status": 302}, {"head": {"Content-Length": "0"}},
    {"head": {"Content-Length": "600000000"}}, {"head": {"ETag": ""}},
    {"head": {"Last-Modified": "Sat, 01 Jan 2000 00:00:00 GMT"}},
    {"status": 412}, {"status": 429}, {"status": 302},
    {"get": {"ETag": '"different"'}}, {"get": {"Content-Length": "1"}},
    {"get": {"Content-Encoding": "gzip"}}, {"max_pages": 1},
])
def test_failed_or_moving_snapshot_does_not_advance_checkpoint(config, now, options):
    state = {"watermark": "2026-09-01", "record_hashes": {"retained": "hash"}}
    saved = copy.deepcopy(state)
    result, _ = collect(config, now, [row()], state, **options)
    assert not result.complete and not result.records
    assert result.state == saved and state == saved


@pytest.mark.parametrize("rows", [[], [row(), row()], [row(NoticeId="invalid")], [row(Title="")],
    [row(PostedDate="not-a-date")], [row(Active="maybe")]])
def test_malformed_or_empty_extract_is_not_a_successful_empty_feed(config, now, rows):
    result, _ = collect(config, now, rows)
    assert not result.complete and not result.records and "watermark" not in result.state


def test_incomplete_csv_and_header_only_file_fail_closed(config, now):
    for body in (b'NoticeId,Title\n', csv_bytes([row(Description='"quoted field')])[:-10], b'NoticeId,Title\n"unterminated'):
        result, _ = collect(config, now, [], body=body)
        assert not result.complete and not result.records
    with pytest.raises(SourceUnavailable, match="unexpectedly"):
        parse_snapshot(io.BytesIO(csv_bytes([row()])), source(config), {str(n): "hash" for n in range(10)}, now.isoformat())


def test_bounded_bootstrap_resumes_unchanged_snapshot_without_losing_any_scope(config, now):
    rows = [row(f"{n:032x}") for n in range(7)]
    state, seen = {}, []
    for run in range(4):
        result, calls = collect(config, now + timedelta(hours=run), rows, state,
            refresh_daily=False, source_options={"max_records_per_run": 2})
        seen.extend(raw.data["NoticeId"] for raw in result.records)
        assert len(calls) == 2 and result.state["snapshot_rows"] == 7
        assert len(result.state["record_hashes"]) == min((run + 1) * 2, 7)
        assert result.state["pending_records"] == max(7 - (run + 1) * 2, 0)
        assert result.complete == (run == 3)
        state = result.state
    assert seen == [r["NoticeId"] for r in rows]
    # A broken row after the batch boundary cannot advance even the first batch.
    rows[-1]["Title"] = ""
    failed, _ = collect(config, now, rows, {}, source_options={"max_records_per_run": 2})
    assert not failed.records and not failed.state


def test_notice_disappearance_needs_two_versions_and_reappearance_restores_record(config, now):
    rows = [row(f"{n:032x}") for n in range(4)]
    first, _ = collect(config, now, rows)
    signal = normalise_sam_opportunity(first.records[-1])
    second, _ = collect(config, now + timedelta(days=1), rows[:-1], first.state, revision='"version-2"')
    assert not second.state["removed_ids"]
    same, _ = collect(config, now + timedelta(days=1), rows[:-1], second.state, revision='"version-2"')
    assert not same.state["removed_ids"]
    third, _ = collect(config, now + timedelta(days=2), rows[:-1], same.state, revision='"version-3"')
    closed = removed_sam_records([signal], third.state, (now + timedelta(days=2)).isoformat())
    assert len(closed) == 1 and closed[0].status == "not_listed"
    assert closed[0].signal_type != "AWARD" and lifecycle(closed[0], now)[0] == "CLOSED"
    fourth, _ = collect(config, now + timedelta(days=3), rows, third.state, revision='"version-4"')
    reopened, _ = merge(closed[0], normalise_sam_opportunity(fourth.records[0]))
    assert reopened.status == "unknown" and lifecycle(reopened, now)[0] == "OPEN"
    cleared, _ = merge(reopened, normalise(config, now + timedelta(days=4), NoticeId=rows[-1]["NoticeId"], ResponseDeadLine=""))
    assert cleared.deadline_at is None and not cleared.deadlines


def test_awards_are_historical_and_published_set_asides_do_not_invent_eligibility(config, now):
    award = normalise(config, now, Type="Award Notice", AwardDate="2026-09-01", Awardee="Example Supplier LLC",
                      **{"Award$": "$125,000.50"})
    assert award.signal_type == "AWARD" and lifecycle(award, now)[0] == "AWARDED"
    assert award.amount.kind == "award" and award.value_max == 125000.5
    assert award.winners[0]["name"] == "Example Supplier LLC" and award.award_date == "2026-09-01"
    assert award.deadline_at is None
    tender = normalise(config, now, SetASide="Service-Disabled Veteran-Owned Small Business", **{"Award$": "125000"})
    assert tender.eligibility_text == "Set-aside: Service-Disabled Veteran-Owned Small Business"
    assert not tender.exclusion_reasons and tender.value_max is None


def test_early_intent_and_listing_flags_never_make_old_or_awarded_notices_open(config, now):
    early = normalise(config, now, Type="Sources Sought", ResponseDeadLine="2026-10-01")
    assert early.signal_type == "RFI" and early.deadlines[0].kind == "expression_of_interest"
    old = normalise(config, now, Type="Sources Sought", PostedDate="2008-03-05 05:00:00", ResponseDeadLine="")
    assert lifecycle(old, now)[0] == "UNKNOWN"
    expired = normalise(config, now, ResponseDeadLine="2026-01-01")
    assert lifecycle(expired, now)[0] == "EXPIRED"
    justified = normalise(config, now, Type="Justification")
    assert lifecycle(justified, now)[0] == "CLOSED"
    unknown = normalise(config, now, Type="New upstream category")
    assert unknown.status == "unverified"
