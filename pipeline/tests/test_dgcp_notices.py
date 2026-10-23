import copy
from datetime import UTC, datetime, timedelta

import pytest

from anthrion_signal.collectors import RawRecord, SourceUnavailable
from anthrion_signal.dgcp_notices import (
    BASE, PREFIX, VERSION, _page, collect_dgcp, normalise_dgcp,
)
from anthrion_signal.discovery import lifecycle
from anthrion_signal.utils import digest


NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
SOURCE = {"id": "dominican_dgcp", "name": "Dominican Republic DGCP", "country": "DO",
          "source_type": "official_notice", "limit": 2, "refresh_limit": 0}
SETTINGS = {"max_pages": 10, "lookback_days": 7}


def process(ident="TEST-CCC-CP-2026-0001", **changes):
    return {"codigo_proceso": ident, "titulo": "Adquisición de servicios", "descripcion": "Servicios institucionales",
            "unidad_compra": "Institución de prueba", "estado_proceso": "Proceso publicado", "modalidad": "Comparación de Precios",
            "tipo_excepcion": "Proceso ordinario", "divisa": "DOP", "monto_estimado": 750000,
            "fecha_publicacion": "2026-10-22T12:00:00.1234567Z", "fecha_enmienda": "2026-11-05T12:00:00Z",
            "fecha_fin_recepcion_ofertas": "2026-11-10T16:00:00Z",
            "url": "https://comunidad.comprasdominicana.gob.do/Public/Tendering/OpportunityDetail/Index?noticeUID=DO1.NTC.1234",
            **changes}


def detail(row=None, **changes):
    row = row or process()
    release = {"ocid": PREFIX + row["codigo_proceso"], "id": row["codigo_proceso"], "date": row["fecha_publicacion"],
               # This misleading broad tag set is from the real publisher.
               "tag": ["tender", "award", "contract"], "language": "es",
               "tender": {"id": row["codigo_proceso"], "title": row["titulo"], "description": row["descripcion"],
                          "status": "active", "procurementMethod": "open", "procurementMethodDetails": row["modalidad"],
                          "procuringEntity": {"id": "DO-UC-123", "name": row["unidad_compra"]},
                          "value": {"amount": 750000, "currency": "DOP"},
                          "tenderPeriod": {"startDate": row["fecha_publicacion"], "endDate": row["fecha_fin_recepcion_ofertas"]},
                          "items": [{"id": "1", "description": "Implementación de CRM e integración de servicios digitales",
                                     "classification": {"id": "43231503", "scheme": "UNSPSC"}}],
                          "documents": [{"id": "1", "documentType": "tenderNotice", "url": row["url"], "title": "Aviso"}]},
               **changes}
    return {"version": "1.1", "license": "https://opendatacommons.org/licenses/pddl/1-0/", "releases": [release]}


def page(rows, number=1, total=None, limit=2):
    total = len(rows) if total is None else total
    return {"code": 200, "hasError": False, "payload": {"content": rows}, "page": number,
            "limit": limit, "totalResults": total, "pages": (total + limit - 1) // limit}


class Pages:
    def __init__(self, pages):
        self.pages, self.calls = iter(pages), []

    def json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = next(self.pages)
        if isinstance(result, Exception):
            raise result
        return result


def raw(row=None, package=None):
    row = row or process()
    return RawRecord({"id": row["codigo_proceso"], "process": row,
                      "release": (package or detail(row))["releases"][0]}, SOURCE, NOW.isoformat(), "dgcp")


def test_hydrates_generic_titles_and_preserves_original_item_scope():
    row = process()
    http = Pages([page([row]), detail(row)])
    result = collect_dgcp(SOURCE, {}, NOW, http, SETTINGS, {})
    assert result.complete and result.pages == 2 and len(result.records) == 1
    assert result.state["watermark"] == NOW.isoformat()
    assert "pending" not in result.state
    assert http.calls[1] == (BASE + "ocds/releases", {"params": {"ocid": PREFIX + row["codigo_proceso"]}})
    signal = normalise_dgcp(result.records[0])
    assert "Implementación de CRM" in signal.description
    assert signal.buyer_name == "Institución de prueba"
    assert signal.countries == ["DO"] and signal.source_language == "es"
    assert signal.cpv_codes == []  # UNSPSC is not CPV.
    assert signal.signal_type == "LIVE_TENDER" and signal.procurement_stage == "tender"
    assert signal.status == "active" and signal.incumbent_supplier is None
    assert signal.value_max == 750000 and signal.currency == "DOP"
    assert signal.amount.kind == "estimated_contract"
    assert signal.published_at == row["fecha_publicacion"]
    assert signal.updated_at == row["fecha_publicacion"]  # Never scheduled amendment date.
    assert signal.deadline_at == "2026-11-10T16:00:00+00:00"


def test_cross_review_missing_history_detail_does_not_starve_later_valid_notices():
    bad = process("BAD-CCC-CP-2026-0001", fecha_publicacion="2026-10-21T12:00:00Z")
    good = process("GOOD-CCC-CP-2026-0001", fecha_publicacion="2026-10-20T12:00:00Z")
    http = Pages([page([bad, good]), SourceUnavailable("Missing detail", status_code=404), detail(good)])
    result = collect_dgcp(SOURCE, {}, NOW, http, SETTINGS, {})
    # The independent fresh lane starts on 23 October, so it cannot recover
    # this valid older process if one missing detail blocks the original queue.
    assert [row.data["id"] for row in result.records] == [good["codigo_proceso"]]
    assert not result.complete and bad["codigo_proceso"] not in result.state["known"]
    assert good["codigo_proceso"] in result.state["known"]


def test_cross_review_open_lot_deadline_prevents_parent_expiry_after_partial_award():
    row = process(fecha_fin_recepcion_ofertas="2026-10-01T16:00:00Z")
    package = detail(row, awards=[{"id": "award-1", "status": "active", "relatedLots": ["1"],
                                  "suppliers": [{"name": "Hardware supplier"}]}])
    package["releases"][0]["tender"]["lots"] = [
        {"id": "1", "title": "Hardware", "status": "complete",
         "tenderPeriod": {"endDate": "2026-10-01T16:00:00Z"}},
        {"id": "2", "title": "CRM implementation", "status": "active",
         "tenderPeriod": {"endDate": "2026-11-20T16:00:00Z"}},
    ]
    signal = normalise_dgcp(raw(row, package))
    assert signal.status == "active" and signal.signal_type == "LIVE_TENDER"
    assert lifecycle(signal, NOW)[0] == "OPEN"
    assert any(fact.lot_id == "2" and fact.date == "2026-11-20" for fact in signal.deadlines)


def test_cross_review_awarded_lot_deadline_cannot_keep_expired_unawarded_lot_open():
    row = process(fecha_fin_recepcion_ofertas=None)
    package = detail(row, awards=[{"id": "award-1", "status": "active", "relatedLots": ["1"]}])
    package["releases"][0]["tender"]["lots"] = [
        {"id": "1", "title": "Hardware", "status": "complete",
         "tenderPeriod": {"endDate": "2026-11-20T16:00:00Z"}},
        {"id": "2", "title": "CRM implementation", "status": "active",
         "tenderPeriod": {"endDate": "2026-10-01T16:00:00Z"}},
    ]
    signal = normalise_dgcp(raw(row, package))
    assert lifecycle(signal, NOW)[0] == "EXPIRED"
    assert all(fact.lot_id != "1" or fact.status != "current" for fact in signal.deadlines)


def test_cross_review_withdrawn_award_snapshot_clears_prior_winner_after_merge():
    from anthrion_signal.dedupe import reconcile

    row = process()
    active = detail(row, awards=[{"id": "award-1", "status": "active", "relatedLots": ["1"],
                                 "suppliers": [{"name": "Withdrawn supplier"}]}])
    active["releases"][0]["tender"]["lots"] = [
        {"id": "1", "title": "Hardware", "status": "active"},
        {"id": "2", "title": "CRM implementation", "status": "active"},
    ]
    before = normalise_dgcp(raw(row, active))
    withdrawn = copy.deepcopy(active)
    withdrawn["releases"][0]["awards"][0]["status"] = "cancelled"
    later_raw = raw(row, withdrawn)
    later_raw.retrieved_at = (NOW + timedelta(hours=1)).isoformat()
    after = normalise_dgcp(later_raw)
    records, _, _ = reconcile([before], [after])
    assert len(records) == 1
    assert records[0].winners == [] and records[0].incumbent_supplier is None
    assert records[0].award_statuses != ["active"]
    assert records[0].lots[0].status == "active"
    assert {p.raw_hash for p in records[0].provenance} == {before.raw_source_hash, after.raw_source_hash}


def test_cross_review_later_observed_snapshot_can_correct_older_publisher_date():
    from anthrion_signal.dedupe import reconcile

    row = process()
    before = normalise_dgcp(raw(row))
    changed = detail(row)
    changed["releases"][0]["date"] = "2026-10-21T12:00:00Z"
    changed["releases"][0]["tender"]["tenderPeriod"]["endDate"] = "2026-12-01T16:00:00Z"
    later_raw = raw(row, changed)
    later_raw.retrieved_at = (NOW + timedelta(hours=1)).isoformat()
    after = normalise_dgcp(later_raw)
    records, _, _ = reconcile([before], [after])
    assert records[0].deadline_at == "2026-12-01T16:00:00+00:00"
    assert records[0].updated_at == "2026-10-21T12:00:00Z"


def test_cross_review_older_observation_cannot_undo_a_current_snapshot():
    from anthrion_signal.dedupe import reconcile

    row = process()
    old = detail(row, awards=[{"id": "award-1", "status": "active",
                              "suppliers": [{"name": "Former supplier"}]}])
    before = normalise_dgcp(raw(row, old))
    current = detail(row)
    current["releases"][0]["tender"]["tenderPeriod"]["endDate"] = "2026-12-01T16:00:00Z"
    current_raw = raw(row, current)
    current_raw.retrieved_at = (NOW + timedelta(hours=1)).isoformat()
    after = normalise_dgcp(current_raw)
    records, _, _ = reconcile([after], [before])
    assert records[0].deadline_at == after.deadline_at and records[0].winners == []
    assert records[0].incumbent_supplier is None and records[0].award_statuses == []
    assert records[0].last_seen_at == after.last_seen_at
    assert {p.raw_hash for p in records[0].provenance} == {before.raw_source_hash, after.raw_source_hash}


def test_cross_review_removed_deadline_does_not_survive_current_full_snapshot():
    from anthrion_signal.dedupe import reconcile

    row = process(fecha_fin_recepcion_ofertas="2026-10-01T16:00:00Z")
    before = normalise_dgcp(raw(row))
    reopened = process(fecha_fin_recepcion_ofertas=None)
    later_raw = raw(reopened)
    later_raw.retrieved_at = (NOW + timedelta(hours=1)).isoformat()
    after = normalise_dgcp(later_raw)
    records, _, _ = reconcile([before], [after])
    assert records[0].deadline_at is None
    assert not any(fact.status == "current" for fact in records[0].deadlines)
    assert lifecycle(records[0], NOW)[0] == "OPEN"


def test_cross_review_complete_multilot_snapshot_closes_prior_open_record_without_supplier_names():
    from anthrion_signal.dedupe import reconcile

    row = process()
    package = detail(row)
    package["releases"][0]["tender"]["lots"] = [
        {"id": "1", "title": "Hardware", "status": "active"},
        {"id": "2", "title": "CRM implementation", "status": "active"},
    ]
    before = normalise_dgcp(raw(row, package))
    completed = copy.deepcopy(package)
    completed["releases"][0]["tender"]["status"] = "complete"
    completed["releases"][0]["awards"] = [{"id": "award-1", "status": "active", "relatedLots": ["1", "2"]}]
    later_raw = raw({**row, "estado_proceso": "Proceso adjudicado y celebrado"}, completed)
    later_raw.retrieved_at = (NOW + timedelta(hours=1)).isoformat()
    after = normalise_dgcp(later_raw)
    assert after.status == "awarded" and not after.winners
    records, _, _ = reconcile([before], [after])
    assert not any(lifecycle(record, NOW)[0] == "OPEN" for record in records)
    assert len(records) == 1 and records[0].status == "awarded"


def test_cross_review_different_exact_process_ids_do_not_merge_on_same_public_url():
    from anthrion_signal.dedupe import reconcile

    active = normalise_dgcp(raw(process("OPEN-CCC-CP-2026-0001")))
    cancelled = normalise_dgcp(raw(process("CLOSED-CCC-CP-2026-0001", estado_proceso="Proceso cancelado")))
    assert active.title == cancelled.title and active.primary_source_url == cancelled.primary_source_url
    records, _, _ = reconcile([active], [cancelled])
    assert len(records) == 2 and {record.ocid for record in records} == {active.ocid, cancelled.ocid}
    assert {lifecycle(record, NOW)[0] for record in records} == {"OPEN", "CANCELLED"}


def test_cross_review_all_terminal_lots_do_not_reopen_on_future_parent_deadline():
    package = detail()
    package["releases"][0]["tender"]["lots"] = [
        {"id": "1", "title": "Hardware", "status": "cancelled"},
        {"id": "2", "title": "CRM implementation", "status": "unsuccessful"},
    ]
    signal = normalise_dgcp(raw(package=package))
    assert lifecycle(signal, NOW)[0] in {"CLOSED", "CANCELLED", "WITHDRAWN"}
    # A genuinely unknown lot must not be swept into a whole-process closure.
    package["releases"][0]["tender"]["lots"].append({"id": "3", "title": "Integration", "status": "unknown"})
    assert lifecycle(normalise_dgcp(raw(package=package)), NOW)[0] == "OPEN"


@pytest.mark.parametrize("malformed", ["related_lots", "lot_period"])
def test_cross_review_malformed_nested_detail_is_isolated_before_cache_or_normalization(malformed):
    bad, good = process("BAD-CCC-CP-2026-0001"), process("GOOD-CCC-CP-2026-0001")
    broken = detail(bad)
    if malformed == "related_lots":
        broken["releases"][0]["awards"] = [{"id": "award-1", "status": "active", "relatedLots": None}]
    else:
        broken["releases"][0]["tender"]["lots"] = [{"id": "1", "status": "active", "tenderPeriod": "invalid"}]
    result = collect_dgcp(SOURCE, {}, NOW, Pages([page([bad, good]), broken, detail(good)]), SETTINGS, {})
    assert not result.complete and [record.data["id"] for record in result.records] == [good["codigo_proceso"]]
    assert bad["codigo_proceso"] not in result.state["known"]
    assert normalise_dgcp(result.records[0]).status == "active"


@pytest.mark.parametrize("ident", ["ARS SENASA-CCC-LPN-2026-0011", "Ayto. Verón-CCC-CP-2026-0009"])
def test_official_identifiers_keep_spaces_periods_and_accented_letters(ident):
    row = process(ident)
    http = Pages([page([row]), detail(row)])
    result = collect_dgcp(SOURCE, {}, NOW, http, SETTINGS, {})
    assert result.complete and len(result.records) == 1
    assert http.calls[1] == (BASE + "ocds/releases", {"params": {"ocid": PREFIX + ident}})
    assert normalise_dgcp(result.records[0]).ocid == PREFIX + ident


def test_resumes_unhydrated_rows_without_rereading_or_losing_a_partial_page():
    one, two = process(), process("TEST-CCC-CP-2026-0002")
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page([one, two]), detail(one)]),
                         {**SETTINGS, "max_pages": 2}, {})
    assert not first.complete and len(first.records) == 1
    assert first.state["pending"]["offset"] == 1 and "watermark" not in first.state
    old = copy.deepcopy(first.state)
    http = Pages([detail(two)])
    second = collect_dgcp(SOURCE, first.state, NOW + timedelta(hours=1), http, {**SETTINGS, "max_pages": 1}, {})
    assert second.complete and len(second.records) == 1 and second.pages == 1
    assert second.state["watermark"] == NOW.isoformat()
    assert first.state == old


def test_budget_counts_listing_and_detail_requests_even_when_one_fails():
    row = process()
    result = collect_dgcp(SOURCE, {}, NOW, Pages([page([row]), SourceUnavailable("API unavailable")]), SETTINGS, {})
    assert not result.complete and result.pages == 2 and not result.records
    assert result.state["known"] == {}
    assert result.state["detail_retries"][row["codigo_proceso"]]["process"] == row
    assert result.state["watermark"] == NOW.isoformat()
    assert "1 unresolved full notices" in result.message


def test_failed_detail_stays_at_the_same_identifier_for_retry():
    row = process()
    package = detail(row)
    package["releases"][0]["ocid"] = PREFIX + "OTHER-PROCESS"
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page([row]), package]), SETTINGS, {})
    assert not first.complete and not first.records and not first.state["known"]
    assert row["codigo_proceso"] in first.state["detail_retries"]
    waiting = collect_dgcp(SOURCE, first.state, NOW, Pages([]), SETTINGS, {})
    assert not waiting.complete and waiting.pages == 0
    second = collect_dgcp({**SOURCE, "detail_retry_hours": 1}, first.state, NOW + timedelta(hours=1),
                          Pages([page([row], limit=1), detail(row)]), SETTINGS, {})
    assert second.complete and len(second.records) == 1
    assert second.state["detail_retries"] == {}


def test_malformed_response_period_preserves_pending_detail():
    row = process()
    package = detail(row)
    package["releases"][0]["tender"]["tenderPeriod"] = "invalid"
    result = collect_dgcp(SOURCE, {}, NOW, Pages([page([row]), package]), SETTINGS, {})
    assert not result.complete and not result.records
    assert row["codigo_proceso"] in result.state["detail_retries"]


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(hasError=True),
    lambda p: p.update(totalResults=3),
    lambda p: p.update(page=2),
    lambda p: p.update(limit=100),
    lambda p: p["payload"].update(content="not an array"),
    lambda p: p["payload"]["content"][0].update(fecha_publicacion="yesterday"),
    lambda p: p["payload"]["content"][0].update(url="https://example.org/fake"),
    lambda p: p["payload"]["content"][0].update(codigo_proceso="../api/secret"),
])
def test_malformed_pages_fail_closed_without_a_checkpoint(mutation):
    payload = page([process()])
    mutation(payload)
    result = collect_dgcp(SOURCE, {}, NOW, Pages([payload]), SETTINGS, {})
    assert not result.complete and not result.records and not result.state["known"]
    assert "watermark" not in result.state


def test_duplicate_processes_cannot_complete_a_page():
    with pytest.raises(SourceUnavailable):
        _page(page([process(), process()]), 1, 2)


def test_changed_offset_snapshot_restarts_window_without_advancing_watermark():
    one, two = process(), process("TEST-CCC-CP-2026-0002")
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page([one, two], total=3), detail(one), detail(two)]),
                         {**SETTINGS, "max_pages": 3}, {})
    later = page([process("TEST-CCC-CP-2026-0003"), process("TEST-CCC-CP-2026-0004")], number=2, total=4)
    second = collect_dgcp(SOURCE, first.state, NOW, Pages([later]), SETTINGS, {})
    assert not second.complete and second.state["pending"]["page"] == 1
    assert "watermark" not in second.state and len(second.state["known"]) == 2


def test_repeated_or_shifted_page_cannot_silently_skip_records_when_total_is_unchanged():
    one, two = process(), process("TEST-CCC-CP-2026-0002")
    result = collect_dgcp(SOURCE, {}, NOW,
                         Pages([page([one, two], total=4), detail(one), detail(two),
                                page([one, two], number=2, total=4)]), SETTINGS, {})
    assert not result.complete and result.state["pending"]["page"] == 1
    assert "watermark" not in result.state and len(result.records) == 2


def test_an_ignored_date_filter_does_not_checkpoint_the_wrong_inventory():
    row = process(fecha_publicacion="2025-01-01T00:00:00Z")
    result = collect_dgcp(SOURCE, {}, NOW, Pages([page([row])]), SETTINGS, {})
    assert not result.complete and not result.records and "watermark" not in result.state


def test_unchanged_replay_uses_full_detail_cache_but_changed_scope_rehydrates():
    row = process()
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page([row]), detail(row)]), SETTINGS, {})
    http = Pages([page([row])])
    second = collect_dgcp(SOURCE, first.state, NOW + timedelta(hours=7), http, SETTINGS, {})
    assert second.complete and second.pages == 1 and not second.records
    assert http.calls[0][1]["params"]["startdate"] == "2026-10-16"
    changed = {**row, "descripcion": "Integración de una plataforma de servicios"}
    third = collect_dgcp(SOURCE, second.state, NOW + timedelta(hours=14), Pages([page([changed]), detail(changed)]), SETTINGS, {})
    assert third.complete and third.pages == 2 and len(third.records) == 1


def test_active_refresh_catches_old_deadline_changes_without_listing_scope_change():
    row = process()
    state = {"query_version": VERSION, "checked_at": NOW.isoformat(), "watermark": NOW.isoformat(),
             "known": {row["codigo_proceso"]: {"hash": digest(row), "status": "active",
                       "checked_at": (NOW - timedelta(days=2)).isoformat(), "published_at": row["fecha_publicacion"]}}}
    changed = {**row, "fecha_fin_recepcion_ofertas": "2026-12-01T16:00:00Z"}
    http = Pages([page([changed], limit=1), detail(changed)])
    result = collect_dgcp({**SOURCE, "refresh_limit": 2}, state, NOW, http, SETTINGS, {})
    assert result.complete and result.pages == 2 and len(result.records) == 1
    assert http.calls[0][1]["params"]["proceso"] == row["codigo_proceso"]
    assert normalise_dgcp(result.records[0]).deadline_at == "2026-12-01T16:00:00+00:00"


def test_unfinished_old_active_refresh_is_explicitly_partial():
    row = process()
    state = {"query_version": VERSION, "checked_at": NOW.isoformat(), "watermark": NOW.isoformat(),
             "known": {row["codigo_proceso"]: {"hash": digest(row), "status": "active",
                       "checked_at": (NOW - timedelta(days=2)).isoformat(), "published_at": row["fecha_publicacion"]}}}
    result = collect_dgcp(SOURCE, state, NOW, Pages([]), SETTINGS, {})
    assert not result.complete and "1 older active notices" in result.message
    assert result.state["known"] == state["known"]


def test_missing_old_process_does_not_starve_new_notices_or_infer_cancellation():
    old = process()
    fresh = process("NEW-CCC-CP-2026-0001")
    state = {"query_version": VERSION, "known": {old["codigo_proceso"]: {
        "hash": digest(old), "status": "active", "checked_at": (NOW - timedelta(days=2)).isoformat(),
        "published_at": old["fecha_publicacion"]}}}
    http = Pages([page([], limit=1), page([fresh]), detail(fresh)])
    result = collect_dgcp({**SOURCE, "refresh_limit": 1}, state, NOW, http, SETTINGS, {})
    assert not result.complete and len(result.records) == 1 and result.records[0].data["id"] == fresh["codigo_proceso"]
    assert result.state["known"][old["codigo_proceso"]]["status"] == "active"
    assert result.state["known"][old["codigo_proceso"]]["refresh_failed_at"] == NOW.isoformat()
    assert result.state["watermark"] == NOW.isoformat()


def test_retry_after_during_refresh_prevents_more_provider_requests():
    row = process()
    state = {"query_version": VERSION, "known": {row["codigo_proceso"]: {
        "hash": digest(row), "status": "active", "checked_at": (NOW - timedelta(days=2)).isoformat()}}}
    retry = NOW + timedelta(hours=1)
    http = Pages([SourceUnavailable("Rate limit", status_code=429, retry_at=retry)])
    result = collect_dgcp({**SOURCE, "refresh_limit": 1}, state, NOW, http, SETTINGS, {})
    assert not result.complete and result.state["retry_at"] == retry.isoformat()
    assert len(http.calls) == 1 and not result.records


@pytest.mark.parametrize(("label", "status"), [
    ("Proceso cancelado", "cancelled"), ("Proceso con etapa cerrada", "closed"),
    ("Sobres abiertos o aperturados", "closed"), ("Sobres estan abriendose", "closed"),
    ("Proceso adjudicado y celebrado", "closed"),
])
def test_closed_source_labels_do_not_create_live_competitions_or_invent_awards(label, status):
    signal = normalise_dgcp(raw(process(estado_proceso=label)))
    assert signal.status == status and signal.signal_type != "AWARD"


def test_actual_award_preserves_winner_and_uses_award_value_not_estimate():
    row = process(estado_proceso="Proceso adjudicado y celebrado")
    package = detail(row, awards=[{"id": "1", "status": "active", "date": "2026-10-23T09:00:00Z",
                              "suppliers": [{"id": "SUP-1", "name": "Proveedor SA"}],
                              "value": {"amount": 500000, "currency": "DOP"}}])
    signal = normalise_dgcp(raw(row, package))
    assert signal.signal_type == "AWARD" and signal.status == "awarded"
    assert signal.incumbent_supplier == "Proveedor SA" and signal.value_max == 500000
    assert signal.amount.kind == "award" and signal.award_date == "2026-10-23T09:00:00Z"


def test_partial_lot_award_keeps_the_other_open_lot_and_its_original_estimate():
    package = detail(awards=[{"id": "award-1", "status": "active", "relatedLots": ["1"],
                              "suppliers": [{"name": "Proveedor SA"}],
                              "value": {"amount": 100000, "currency": "DOP"}}])
    package["releases"][0]["tender"]["lots"] = [
        {"id": "1", "title": "Equipos", "status": "complete"},
        {"id": "2", "title": "CRM e integración", "status": "active"},
    ]
    signal = normalise_dgcp(raw(package=package))
    assert signal.status == "active" and signal.signal_type == "LIVE_TENDER"
    assert lifecycle(signal, NOW)[0] == "OPEN"
    assert [(lot.id, lot.status) for lot in signal.lots] == [("1", "awarded"), ("2", "active")]
    assert signal.winners[0]["lot_ids"] == ["1"]
    assert signal.amount.kind == "estimated_contract" and signal.value_max == 750000
    package["releases"][0]["awards"][0]["relatedLots"] = ["1", "2"]
    finished = normalise_dgcp(raw(package=package))
    assert finished.status == "awarded" and lifecycle(finished, NOW)[0] == "AWARDED"
    assert finished.value_max == 100000 and finished.amount.kind == "award"


def test_unscoped_award_does_not_prove_an_active_process_is_wholly_awarded():
    package = detail(awards=[{"id": "award-1", "status": "active", "suppliers": [{"name": "Proveedor SA"}]}])
    signal = normalise_dgcp(raw(package=package))
    assert signal.status == "active" and lifecycle(signal, NOW)[0] == "OPEN"
    package["releases"][0]["tender"]["status"] = "complete"
    assert lifecycle(normalise_dgcp(raw(package=package)), NOW)[0] == "AWARDED"


def test_cancelled_award_is_not_a_winner_or_an_open_opportunity():
    row = process(estado_proceso="Proceso con etapa cerrada")
    package = detail(row, awards=[{"id": "1", "status": "cancelled", "suppliers": [{"name": "Cancelled supplier"}]}])
    signal = normalise_dgcp(raw(row, package))
    assert signal.status == "closed" and signal.incumbent_supplier is None


def test_no_deadline_remains_unknown_and_date_only_is_not_promoted_to_midnight():
    row = process(fecha_fin_recepcion_ofertas=None)
    assert normalise_dgcp(raw(row)).deadline_at is None
    row = process(fecha_fin_recepcion_ofertas="2026-11-10")
    assert normalise_dgcp(raw(row)).deadline_at == "2026-11-10"


def test_explicit_publisher_english_language_is_preserved():
    assert normalise_dgcp(raw(package=detail(language="en"))).source_language == "en"


@pytest.mark.parametrize(("flags", "expected"), [
    ({"dirigido_mipymes": "Si", "dirigido_mipymes_mujeres": "No"}, ["Dirigido a MIPYMES: Si"]),
    ({"dirigido_mipymes": "No", "dirigido_mipymes_mujeres": "Si"}, ["Dirigido a MIPYMES mujeres: Si"]),
    ({"dirigido_mipymes": "Si", "dirigido_mipymes_mujeres": "Si"},
     ["Dirigido a MIPYMES: Si", "Dirigido a MIPYMES mujeres: Si"]),
    ({"dirigido_mipymes": "No", "dirigido_mipymes_mujeres": "No"}, []),
])
def test_affirmative_publisher_mipyme_flags_are_preserved_without_inferred_disqualification(flags, expected):
    row = process(**flags)
    original = copy.deepcopy(row)
    signal = normalise_dgcp(raw(row))
    assert signal.eligibility_text == "\n".join([row["modalidad"], row["tipo_excepcion"], *expected])
    assert signal.status == "active" and not signal.exclusion_reasons
    assert row == original  # The original flag fields and Si/No values remain unchanged.


def test_zero_budget_makes_no_network_calls_and_preserves_pending_work():
    http = Pages([])
    result = collect_dgcp(SOURCE, {}, NOW, http, {**SETTINGS, "max_pages": 0}, {})
    assert not result.complete and result.pages == 0 and http.calls == []


def test_terminal_cache_eviction_does_not_delete_canonical_source_records():
    row = process()
    state = {"query_version": VERSION, "known": {"OLD-CLOSED-2025-001": {
        "hash": "old", "status": "closed", "published_at": "2025-01-01T00:00:00Z"}}}
    result = collect_dgcp(SOURCE, state, NOW, Pages([page([row]), detail(row)]), SETTINGS, {})
    assert result.complete and "OLD-CLOSED-2025-001" not in result.state["known"]
    assert "OLD-CLOSED-2025-001" in state["known"]
    assert len(result.records) == 1 and result.rejected_records == []


def test_new_publications_are_hydrated_while_historical_window_still_resumes():
    historic = [process(f"HIST-CCC-CP-2026-{number:04}") for number in range(1, 7)]
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page(historic[:2], total=6), detail(historic[0])]),
                         {**SETTINGS, "max_pages": 2}, {})
    fresh = process("FRESH-CCC-CP-2026-0001", fecha_publicacion="2026-10-24T11:00:00Z")
    http = Pages([page([fresh]), detail(fresh), detail(historic[1]),
                  page(historic[2:4], number=2, total=6), detail(historic[2]), detail(historic[3])])
    second = collect_dgcp(SOURCE, first.state, NOW + timedelta(days=1), http, {**SETTINGS, "max_pages": 6}, {})
    assert second.pages == 6 and not second.complete
    assert [r.data["id"] for r in second.records] == [fresh["codigo_proceso"], *[r["codigo_proceso"] for r in historic[1:4]]]
    assert http.calls[0][1]["params"]["startdate"] == "2026-10-23"
    assert http.calls[0][1]["params"]["enddate"] == "2026-10-24"
    assert http.calls[3][1]["params"]["enddate"] == "2026-10-23"
    assert "watermark" not in second.state and "fresh_pending" not in second.state
    assert second.state["fresh_watermark"] == (NOW + timedelta(days=1)).isoformat()
    # Completing the old inventory cannot claim the newer window as its checkpoint.
    third = collect_dgcp(SOURCE, second.state, NOW + timedelta(days=1, hours=1),
                         Pages([page(historic[4:], number=3, total=6), detail(historic[4]), detail(historic[5])]),
                         {**SETTINGS, "max_pages": 3}, {})
    assert "pending" not in third.state and third.state["watermark"] == NOW.isoformat()
    assert not third.complete and "1 older active notices" in third.message
    assert len(third.state["known"]) == 7


def test_fresh_lane_budget_resume_keeps_history_progress_and_shared_detail_cache():
    old1, old2 = process(), process("OLD-CCC-CP-2026-0002")
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page([old1, old2]), detail(old1)]),
                         {**SETTINGS, "max_pages": 2}, {})
    new1 = process("NEW-CCC-CP-2026-0001", fecha_publicacion="2026-10-24T10:00:00Z")
    new2 = process("NEW-CCC-CP-2026-0002", fecha_publicacion="2026-10-24T09:00:00Z")
    # The first half-budget fetches a complete listing, but does not pretend its
    # details were collected; the other half finishes the historical inventory.
    second = collect_dgcp(SOURCE, first.state, NOW + timedelta(days=1),
                          Pages([page([new1, new2]), detail(old2)]), {**SETTINGS, "max_pages": 2}, {})
    assert not second.complete and "pending" not in second.state
    assert second.state["fresh_pending"]["offset"] == 0
    third = collect_dgcp(SOURCE, second.state, NOW + timedelta(days=1, hours=1),
                         Pages([detail(new1), detail(new2), page([new1, new2])]),
                         {**SETTINGS, "max_pages": 4}, {})
    assert len(third.records) == 2 and third.pages == 3
    assert not third.complete and "1 older active notices" in third.message
    assert "fresh_pending" not in third.state and "pending" not in third.state
    assert len(third.state["known"]) == 4


def test_missing_fresh_detail_is_retried_without_blocking_newer_publications():
    historic = [process(f"OLD-CCC-CP-2026-{number:04}") for number in range(1, 5)]
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page(historic[:2], total=4), detail(historic[0])]),
                         {**SETTINGS, "max_pages": 2}, {})
    bad = process("BAD-CCC-CP-2026-0001", fecha_publicacion="2026-10-24T10:00:00Z")
    missing = SourceUnavailable("Missing full OCDS detail", status_code=404)
    second = collect_dgcp(SOURCE, first.state, NOW + timedelta(days=1),
                          Pages([page([bad]), missing, detail(historic[1]), page(historic[2:], number=2, total=4)]),
                          {**SETTINGS, "max_pages": 4}, {})
    assert bad["codigo_proceso"] in second.state["detail_retries"] and "watermark" not in second.state
    assert "fresh_pending" not in second.state
    new = process("NEW-CCC-CP-2026-0001", fecha_publicacion="2026-10-25T10:00:00Z")
    http = Pages([page([bad], limit=1), missing, page([new, bad]), detail(new), detail(historic[2]), detail(historic[3])])
    third = collect_dgcp(SOURCE, second.state, NOW + timedelta(days=2), http, {**SETTINGS, "max_pages": 6}, {})
    assert not third.complete and third.records[0].data["id"] == new["codigo_proceso"]
    assert third.state["fresh_pending"]["from"] == "2026-10-23"
    assert third.state["fresh_pending"]["until"] == "2026-10-25"
    assert bad["codigo_proceso"] not in third.state["known"]
    assert third.state["fresh_pending"]["rows"][1]["codigo_proceso"] == bad["codigo_proceso"]
    assert third.state["watermark"] == NOW.isoformat()
    assert third.state["fresh_watermark"] == (NOW + timedelta(days=1)).isoformat()
    assert third.state["detail_retries"][bad["codigo_proceso"]]["failed_at"] == (NOW + timedelta(days=2)).isoformat()


def test_old_queued_summary_cannot_overwrite_a_newer_verified_cancellation():
    one, old_two = process(), process("TEST-CCC-CP-2026-0002")
    first = collect_dgcp(SOURCE, {}, NOW, Pages([page([one, old_two]), detail(one)]),
                         {**SETTINGS, "max_pages": 2}, {})
    assert first.state["pending"]["page_observed_at"] == NOW.isoformat()
    cancelled = {**old_two, "estado_proceso": "Proceso cancelado"}
    # A separately observed fresh detail has arrived while the historical page
    # still has its old active summary queued for the second identifier.
    later = NOW + timedelta(hours=1)
    first.state["known"][old_two["codigo_proceso"]] = {
        "hash": digest(cancelled), "status": "cancelled", "published_at": old_two["fecha_publicacion"],
        "checked_at": later.isoformat(), "source_observed_at": later.isoformat(),
    }
    http = Pages([])
    second = collect_dgcp(SOURCE, first.state, later, http, {**SETTINGS, "max_pages": 1}, {})
    assert second.complete and not http.calls and not second.records
    assert second.state["known"][old_two["codigo_proceso"]]["status"] == "cancelled"
    # A later newly read page may explicitly reopen it; it is not suppressed.
    reopened = collect_dgcp(SOURCE, second.state, NOW + timedelta(hours=8),
                            Pages([page([old_two]), detail(old_two)]), SETTINGS, {})
    assert reopened.complete and len(reopened.records) == 1
    assert reopened.state["known"][old_two["codigo_proceso"]]["status"] == "active"
