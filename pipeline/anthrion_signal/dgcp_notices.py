"""Keyless Dominican Republic DGCP API, with complete OCDS scope and bounded replay.

The /ocds/releases/all endpoint is an index, not a bulk release package. Each
new process is hydrated before classification, including processes whose
generic title hides relevant items. Publication windows do not expose every
old amendment, so previously active processes have an independent refresh lane.
"""

import copy
import math
import re
from datetime import timedelta
from urllib.parse import urlparse

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .utils import clean, digest, parse_date, unique

BASE = "https://datosabiertos.dgcp.gob.do/api-dgcp/v1/"
VERSION = "dgcp-complete-ocds-v1"
PREFIX = "ocds-6550wx-"
# These are human agency/process codes: spaces, periods and accented letters
# occur in the official index. They are encoded query values, never URL paths.
IDENTIFIER = re.compile(r"\w[\w .-]{1,178}\w")
TERMINAL = {"cancelled", "withdrawn", "unsuccessful", "complete", "closed", "awarded"}


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise SourceUnavailable("DGCP returned an invalid process identifier")
    return value


def _date(value, name, required=False):
    if not value and not required:
        return None
    if not isinstance(value, str) or not parse_date(value):
        raise SourceUnavailable(f"DGCP returned an invalid {name}")
    return value


def _page(package, page, limit):
    """Reject incomplete pages rather than checkpointing a silent gap."""
    if (not isinstance(package, dict) or package.get("code") != 200
            or package.get("hasError") is not False or not isinstance(package.get("payload"), dict)):
        raise SourceUnavailable("DGCP returned an invalid process envelope")
    rows = package["payload"].get("content")
    total, pages = package.get("totalResults"), package.get("pages")
    if (not isinstance(rows, list) or type(total) is not int or total < 0
            or type(pages) is not int or pages not in {math.ceil(total / limit), max(1, math.ceil(total / limit))}
            or package.get("page") != page or package.get("limit") != limit
            or len(rows) != min(limit, max(0, total - (page - 1) * limit))):
        raise SourceUnavailable("DGCP process page is incomplete or its pagination changed")
    identifiers = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SourceUnavailable("DGCP process page contains a malformed row")
        ident = _identifier(row.get("codigo_proceso"))
        if ident in identifiers or not clean(row.get("titulo")) or not clean(row.get("unidad_compra")):
            raise SourceUnavailable("DGCP process page has duplicate or missing required facts")
        identifiers.add(ident)
        _date(row.get("fecha_publicacion"), "publication date", required=True)
        _date(row.get("fecha_fin_recepcion_ofertas"), "response deadline")
        url = urlparse(str(row.get("url") or ""))
        if (url.scheme != "https" or url.hostname != "comunidad.comprasdominicana.gob.do"
                or url.username or url.password):
            raise SourceUnavailable("DGCP process notice link is outside its official portal")
    return rows, total


def _release(package, ident):
    if not isinstance(package, dict) or not isinstance(package.get("releases"), list):
        raise SourceUnavailable("DGCP did not return a complete OCDS package")
    rows = package["releases"]
    if len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get("ocid") != PREFIX + ident:
        raise SourceUnavailable("DGCP detail does not identify the requested process")
    release = rows[0]
    tender = release.get("tender")
    if (not isinstance(tender, dict) or tender.get("id") != ident
            or not clean(tender.get("title")) or not clean(tender.get("status"))
            or not isinstance(tender.get("procuringEntity"), dict)
            or not clean(tender["procuringEntity"].get("name"))):
        raise SourceUnavailable("DGCP OCDS detail omitted required tender facts")
    _date(release.get("date"), "publication date", required=True)
    if not isinstance(tender.get("tenderPeriod", {}), dict):
        raise SourceUnavailable("DGCP OCDS detail has a malformed response period")
    _date((tender.get("tenderPeriod") or {}).get("endDate"), "response deadline")
    for group in ("awards", "contracts", "parties"):
        if not isinstance(release.get(group, []), list) or any(not isinstance(x, dict) for x in release.get(group, [])):
            raise SourceUnavailable("DGCP OCDS detail has a malformed lifecycle section")
    for group in ("items", "lots", "documents"):
        if not isinstance(tender.get(group, []), list) or any(not isinstance(x, dict) for x in tender.get(group, [])):
            raise SourceUnavailable("DGCP OCDS detail has a malformed scope section")
    for award in release.get("awards", []):
        related = award.get("relatedLots", [])
        suppliers = award.get("suppliers", [])
        if (not isinstance(related, list) or any(type(value) not in (str, int) for value in related)
                or not isinstance(suppliers, list) or any(not isinstance(value, dict) for value in suppliers)):
            raise SourceUnavailable("DGCP OCDS detail has malformed award lot or supplier references")
    planning = release.get("planning", {})
    if not isinstance(planning, dict):
        raise SourceUnavailable("DGCP OCDS detail has a malformed planning section")
    # Validate nested shapes used by normalization before a detail is emitted
    # or cached. A malformed notice belongs in its retry queue, not in a whole
    # source-run failure after other valid notices have already been collected.
    sections = [tender, planning, *tender.get("items", []), *tender.get("lots", []),
                *release.get("awards", []), *release.get("contracts", [])]
    for section in sections:
        for name in ("value", "classification", "tenderPeriod", "contractPeriod", "period"):
            if name in section and not isinstance(section[name], dict):
                raise SourceUnavailable(f"DGCP OCDS detail has a malformed {name} section")
        documents = section.get("documents", [])
        if not isinstance(documents, list) or any(not isinstance(value, dict) for value in documents):
            raise SourceUnavailable("DGCP OCDS detail has malformed document references")
        _date((section.get("tenderPeriod") or {}).get("endDate"), "response deadline")
    if "language" in release and not isinstance(release["language"], str):
        raise SourceUnavailable("DGCP OCDS detail has a malformed language")
    return release


def _status(release, process):
    """DGCP always sets broad tender/award/contract tags, even before an award."""
    status = clean(release["tender"].get("status")).lower()
    label = clean(process.get("estado_proceso")).casefold()
    if status in {"cancelled", "withdrawn", "unsuccessful"}:
        return status
    if re.search(r"cancelad|anulad", label):
        return "cancelled"
    if "desierto" in label:
        return "unsuccessful"
    awarded = any(a.get("status") == "active" for a in release.get("awards", []))
    contracted = any(c.get("status") in {"active", "terminated"} for c in release.get("contracts", []))
    if "adjudicado" in label:
        return "awarded" if awarded or contracted else "closed"
    if "etapa cerrada" in label or "sobres" in label:
        # Opened bids are no longer a new response route. A status label alone
        # is not enough to fabricate a contract award, supplier, or award value.
        return "closed"
    lots = release["tender"].get("lots", [])
    awarded_lots = _awarded_lots(release)
    all_awarded = bool(lots) and all(str(lot.get("id")) in awarded_lots for lot in lots)
    if (awarded or contracted) and (status in {"complete", "closed"} or all_awarded):
        return "awarded"
    if lots and all(str(lot.get("id")) in awarded_lots or lot.get("status") in TERMINAL for lot in lots):
        # A generic active parent cannot reopen explicitly closed lots. A
        # missing/unknown lot status deliberately prevents this inference.
        return "complete"
    # An award for one part is not proof that the whole active process closed.
    # Preserve other published lots and keep refreshing their response route.
    return status if status in {"planning", "planned", "active", "complete", "closed"} else "unknown"


def _awarded_lots(release):
    awarded = {str(lot) for award in release.get("awards", []) if award.get("status") == "active"
               for lot in award.get("relatedLots", [])}
    awarded.update(str(lot.get("id")) for lot in release["tender"].get("lots", [])
                   if lot.get("id") and lot.get("status") == "awarded")
    return awarded


def _detail(source, ident, process, frozen, http, result, observed_at=None):
    result.pages += 1
    package = http.json(BASE + "ocds/releases", params={"ocid": PREFIX + ident})
    release = _release(package, ident)
    raw = RawRecord({"id": ident, "process": process, "release": release,
                     "license": package.get("license"), "publicationPolicy": package.get("publicationPolicy")},
                    source, frozen.isoformat(), "dgcp")
    result.records.append(raw)
    result.state.get("detail_retries", {}).pop(ident, None)
    return {"hash": digest(process), "checked_at": frozen.isoformat(),
            "source_observed_at": observed_at or frozen.isoformat(),
            "published_at": process.get("fecha_publicacion") or release["date"],
            "status": _status(release, process)}


def _finish(result, frozen, refresh_hours):
    due = sum(item.get("status") not in TERMINAL
              and (parse_date(item.get("checked_at")) or frozen - timedelta(days=365))
              <= frozen - timedelta(hours=refresh_hours)
              for item in result.state.get("known", {}).values())
    if due:
        result.complete = False
        message = f"DGCP has {due} older active notices awaiting a bounded source refresh."
        result.message = " ".join(filter(None, [result.message, message]))
    if result.state.get("fresh_pending"):
        result.complete = False
        result.message = " ".join(filter(None, [result.message, "DGCP fresh-notice lane resumes next collection."]))
    retries = result.state.get("detail_retries", {})
    if retries:
        result.complete = False
        result.message = " ".join(filter(None, [result.message,
            f"DGCP has {len(retries)} unresolved full notices retained for retry."]))
    return result


def _window(start, frozen, limit):
    return {"from": start.date().isoformat(), "until": frozen.date().isoformat(),
            "through": frozen.isoformat(), "page": 1, "limit": limit,
            "rows": [], "offset": 0, "seen_ids": []}


def _scan_window(source, pending, known, frozen, http, result, stop):
    """Advance one frozen inventory without consuming another lane's budget."""
    limit = pending["limit"]
    while result.pages < stop:
        if not pending["rows"]:
            result.pages += 1
            package = http.json(BASE + "procesos", params={
                "page": pending["page"], "limit": limit,
                "startdate": pending["from"], "enddate": pending["until"],
            })
            rows, total = _page(package, pending["page"], limit)
            seen = set(pending.get("seen_ids", []))
            if (("total" in pending and pending["total"] != total)
                    or any(row["codigo_proceso"] in seen for row in rows)):
                # Never continue a shifted offset index across an uncertain gap.
                pending.update(page=1, rows=[], offset=0, seen_ids=[])
                pending.pop("total", None)
                raise SourceUnavailable("DGCP publication index changed; replaying the frozen window")
            if any(not pending["from"] <= row["fecha_publicacion"][:10] <= pending["until"] for row in rows):
                raise SourceUnavailable("DGCP process page ignored its publication window")
            pending["seen_ids"] = [*pending.get("seen_ids", []), *(row["codigo_proceso"] for row in rows)]
            pending.update(rows=rows, offset=0, total=total, page_observed_at=frozen.isoformat())
        while pending["offset"] < len(pending["rows"]) and result.pages < stop:
            process = pending["rows"][pending["offset"]]
            ident = process["codigo_proceso"]
            observed_at = pending.get("page_observed_at") or pending["through"]
            cached = known.get(ident, {})
            newer = parse_date(cached.get("source_observed_at") or cached.get("checked_at"))
            # The fresh lane or an old-active lookup may have observed a later
            # cancellation/reopening than this queued page. Reading its OCDS
            # now does not make the older summary status a new observation.
            superseded = newer and newer > parse_date(observed_at)
            if superseded:
                result.state.get("detail_retries", {}).pop(ident, None)
            retry = result.state.get("detail_retries", {}).get(ident)
            recent_failure = (retry and digest(retry.get("process")) == digest(process)
                              and parse_date(retry.get("failed_at"))
                              > frozen - timedelta(hours=max(1, int(source.get("detail_retry_hours", 6)))))
            if not superseded and not recent_failure and cached.get("hash") != digest(process):
                try:
                    known[ident] = _detail(source, ident, process, frozen, http, result, observed_at)
                except SourceUnavailable as exc:
                    if exc.retry_at or exc.status_code in {401, 403, 429, 503}:
                        raise
                    # Retain the unresolved identifier and summary explicitly;
                    # a single missing detail cannot block every later row.
                    result.state.setdefault("detail_retries", {})[ident] = {
                        "process": process, "source_observed_at": observed_at,
                        "failed_at": frozen.isoformat(), "message": str(exc),
                    }
                    defer_collection(result, exc)
            pending["offset"] += 1
        if pending["offset"] < len(pending["rows"]):
            return False
        if pending["page"] * limit >= pending["total"]:
            return True
        pending.update(page=pending["page"] + 1, rows=[], offset=0)
    return False


def collect_dgcp(source, state, frozen, http, settings, terms):
    """Bound requests, persist unresolved rows, and never keyword-filter titles."""
    prior = state if state.get("query_version") == VERSION else {}
    result = Collection(state=copy.deepcopy(prior))
    result.state["query_version"] = VERSION
    known = result.state.setdefault("known", {})
    budget = max(0, min(int(settings.get("max_pages", 0)), int(source.get("max_pages_per_run", 64))))
    limit = max(1, min(int(source.get("limit", 500)), 1000))
    refresh_hours = max(1, int(source.get("refresh_hours", 24)))
    refresh_limit = max(0, min(int(source.get("refresh_limit", 8)), budget // 4))
    retry_limit = max(0, min(int(source.get("detail_retry_limit", 4)), budget // 4))
    retry_hours = max(1, int(source.get("detail_retry_hours", 6)))
    retries = result.state.get("detail_retries", {})
    due_retries = sorted((ident for ident, item in retries.items()
                         if (parse_date(item.get("failed_at")) or frozen - timedelta(days=365))
                         <= frozen - timedelta(hours=retry_hours)),
                        key=lambda ident: (retries[ident].get("failed_at", ""), ident))[:retry_limit]
    for ident in due_retries:
        try:
            result.pages += 1
            page = http.json(BASE + "procesos", params={"proceso": ident, "page": 1, "limit": 1})
            rows, total = _page(page, 1, 1)
            if total != 1 or rows[0]["codigo_proceso"] != ident:
                raise SourceUnavailable("DGCP unresolved process lookup is missing or ambiguous")
            retries[ident].update(process=rows[0], source_observed_at=frozen.isoformat())
            known[ident] = _detail(source, ident, rows[0], frozen, http, result)
        except SourceUnavailable as exc:
            retries[ident].update(failed_at=frozen.isoformat(), message=str(exc))
            defer_collection(result, exc)
            if exc.retry_at or exc.status_code in {401, 403, 429, 503}:
                return _finish(result, frozen, refresh_hours)
    # Refresh oldest checked first, independently of publication-window progress.
    # Terminal notices remain in the recent replay; never infer a deletion.
    refresh = sorted((ident for ident, item in known.items()
                      if item.get("status") not in TERMINAL
                      and (parse_date(item.get("checked_at")) or frozen - timedelta(days=365))
                      <= frozen - timedelta(hours=refresh_hours)
                      and (parse_date(item.get("refresh_failed_at")) or frozen - timedelta(days=365))
                      <= frozen - timedelta(hours=6)),
                     key=lambda ident: (known[ident].get("checked_at", ""), ident))[:refresh_limit]
    for ident in refresh:
        try:
            # Re-read both current summary and full scope; list state labels
            # must not contradict a later OCDS lifecycle update.
            if result.pages + 2 > budget:
                break
            result.pages += 1
            page = http.json(BASE + "procesos", params={"proceso": ident, "page": 1, "limit": 1})
            rows, total = _page(page, 1, 1)
            if total != 1 or rows[0]["codigo_proceso"] != ident:
                raise SourceUnavailable("DGCP current process lookup is missing or ambiguous")
            known[ident] = _detail(source, ident, rows[0], frozen, http, result)
        except SourceUnavailable as exc:
            # One removed or malformed historic process must not starve fresh
            # procurement forever. Retain its facts, report partial coverage,
            # and retry later; absence alone is never a cancellation.
            known[ident]["refresh_failed_at"] = frozen.isoformat()
            defer_collection(result, exc)
            if exc.retry_at or exc.status_code in {401, 403, 429, 503}:
                return result

    pending = result.state.get("pending")
    resumed_history = bool(pending)
    watermark = parse_date(result.state.get("watermark"))
    hours = max(1, int(source.get("listing_refresh_hours", 6)))
    if not pending:
        checked = parse_date(result.state.get("checked_at"))
        if (checked and not result.state.get("fresh_pending") and not settings.get("refresh_daily")
                and timedelta(0) <= frozen - checked < timedelta(hours=hours)):
            return _finish(result, frozen, refresh_hours)
        overlap = max(1, int(source.get("overlap_days", 7)))
        start = watermark - timedelta(days=overlap) if watermark else frozen - timedelta(days=settings["lookback_days"])
        pending = _window(start, frozen, limit)
        result.state["pending"] = pending

    fresh = result.state.get("fresh_pending")
    fresh_checked = parse_date(result.state.get("fresh_checked_at")) or parse_date(pending["through"])
    fresh_due = resumed_history and (settings.get("refresh_daily") or frozen - fresh_checked >= timedelta(hours=hours))
    remaining = budget - result.pages
    if remaining >= 2 and (fresh or fresh_due):
        if fresh and fresh.get("replay_head"):
            # A failed detail stays within the retry window, while replaying
            # the head lets newer publications precede it on the next pass.
            fresh = _window(parse_date(fresh["from"]), frozen, fresh["limit"])
            result.state["fresh_pending"] = fresh
        if not fresh:
            # Do not revisit the whole bootstrap window before new notices can
            # arrive. Later fresh scans overlap one day, bounded by the original
            # snapshot day, and share verified hashes with the history lane.
            start = parse_date(result.state.get("fresh_watermark")) or parse_date(pending["through"])
            start = max(parse_date(pending["until"]), start - timedelta(days=1))
            fresh = _window(start, frozen, limit)
            result.state["fresh_pending"] = fresh
        try:
            if _scan_window(source, fresh, known, frozen, http, result, result.pages + remaining // 2):
                result.state.update(fresh_watermark=fresh["through"], fresh_checked_at=frozen.isoformat())
                result.state.pop("fresh_pending", None)
        except SourceUnavailable as exc:
            defer_collection(result, exc)
            if exc.retry_at or exc.status_code in {401, 403, 429, 503}:
                return _finish(result, frozen, refresh_hours)
            fresh["replay_head"] = True
    try:
        if _scan_window(source, pending, known, frozen, http, result, budget):
            result.state.update(watermark=pending["through"], checked_at=frozen.isoformat())
            result.state.pop("pending", None)
            # Cache eviction only causes later re-fetches; it never removes
            # canonical notices or makes an availability decision.
            cutoff = frozen - timedelta(days=max(30, int(source.get("cache_days", 90))))
            for ident, item in list(known.items()):
                if item.get("status") in TERMINAL and (parse_date(item.get("published_at")) or frozen) < cutoff:
                    del known[ident]
            return _finish(result, frozen, refresh_hours)
        result.complete = False
        result.message = "DGCP complete-notice backlog resumes next collection."
    except SourceUnavailable as exc:
        defer_collection(result, exc)
    return _finish(result, frozen, refresh_hours)


def normalise_dgcp(raw):
    from .models import Amount, Lot
    from .normalise import base, documents_in, money
    from .public_context import deadline_fact, deadline_value
    from .notice_dates import response_deadline_instant

    process, release = raw.data["process"], raw.data["release"]
    ident = _identifier(process["codigo_proceso"])
    tender = release["tender"]
    buyer = tender["procuringEntity"]
    status = _status(release, process)
    awards = [a for a in release.get("awards", []) if a.get("status") == "active"]
    awarded_lots = _awarded_lots(release)
    stage = "award" if status == "awarded" else "planning" if status in {"planning", "planned"} else "tender"
    url = process["url"]
    # Retain all item text: generic national titles often contain the actual
    # software scope only in individual UNSPSC line items or lot descriptions.
    scope = [tender.get("description") or process.get("descripcion") or ""]
    scope.extend(clean(item.get("description")) for item in tender.get("items", []))
    scope.extend(" ".join(filter(None, [str(lot.get("id") or ""), clean(lot.get("title")),
                                       clean(lot.get("description"))])) for lot in tender.get("lots", []))
    description = "\n\n".join(unique(filter(None, scope)))
    # Do not turn UNSPSC numbers into CPV codes. Both can have eight digits.
    classifications = [item.get("classification") or {} for item in tender.get("items", [])]
    cpvs = [str(c["id"]) for c in classifications if c.get("scheme") == "CPV" and c.get("id")]
    value = tender.get("value") or {}
    if stage == "award":
        value = awards[0].get("value") or {} if len(awards) == 1 else {}
    amount = money(value.get("amount"))
    currency = value.get("currency")
    open_lots = [lot for lot in tender.get("lots", [])
                 if str(lot.get("id")) not in awarded_lots and lot.get("status") not in TERMINAL]
    facts = []
    if stage != "award":
        for lot in open_lots:
            fact = deadline_fact((lot.get("tenderPeriod") or {}).get("endDate"), url, "tender", lot_id=str(lot.get("id")))
            if fact:
                facts.append(fact)
        # A global date remains useful for lots without their own response
        # window. Closed or awarded lots cannot extend another lot's deadline.
        if not open_lots or len(facts) < len(open_lots):
            parent = deadline_fact((tender.get("tenderPeriod") or {}).get("endDate"), url, "tender")
            if parent:
                facts.append(parent)
    now = parse_date(raw.retrieved_at)
    upcoming = [fact for fact in facts if response_deadline_instant(deadline_value(fact)) > now]
    shown = min(upcoming, key=lambda fact: response_deadline_instant(deadline_value(fact))) if upcoming else max(
        facts, key=lambda fact: response_deadline_instant(deadline_value(fact)), default=None)
    winners = [{"name": clean(s.get("name")), "identifiers": [s["id"]] if s.get("id") else [],
                "lot_ids": [str(v) for v in award.get("relatedLots", [])], "source_url": url}
               for award in awards for s in award.get("suppliers", []) if clean(s.get("name"))]
    period = tender.get("contractPeriod") or {}
    if stage == "award" and len(release.get("contracts", [])) == 1:
        period = release["contracts"][0].get("period") or period
    award_dates = unique(a.get("date") for a in awards if a.get("date"))
    method = clean(tender.get("procurementMethodDetails") or process.get("modalidad"))
    # These affirmative flags are explicit source context, not a finding that
    # Anthrion is ineligible. Keep the publisher's original Spanish value.
    targeted = [f"{label}: {process[field]}" for field, label in (
        ("dirigido_mipymes", "Dirigido a MIPYMES"),
        ("dirigido_mipymes_mujeres", "Dirigido a MIPYMES mujeres"),
    ) if process.get(field) == "Si"]
    eligibility = "\n".join(unique(filter(None, [method, clean(process.get("tipo_excepcion")),
                                                  clean(tender.get("eligibilityCriteria")), *targeted])))
    return base(raw, title=tender["title"], description=description, description_limit=None,
                url=url, ocid=PREFIX + ident, external_ids=["dgcp:" + ident],
                procedure_identifiers=["ocid:" + PREFIX + ident], countries=["DO"],
                source_language={"spa": "es", "eng": "en"}.get(release.get("language"), release.get("language") or "es"),
                buyer_name=buyer["name"], buyer_identifiers=[buyer["id"]] if buyer.get("id") else [],
                signal_type="AWARD" if stage == "award" else "PIPELINE" if stage == "planning" else "LIVE_TENDER",
                procurement_stage=stage, notice_type=method or None, status=status,
                published_at=release["date"], updated_at=release["date"],
                deadline_at=deadline_value(shown) if shown else None, deadlines=facts,
                response_deadlines=unique(deadline_value(fact) for fact in facts),
                value_max=amount, currency=currency,
                amount=Amount(kind=("award" if stage == "award" else "estimated_contract") if amount is not None else "unknown",
                              maximum=amount, currency=currency, source_url=url,
                              source_label="awards[].value" if stage == "award" else "tender.value"),
                cpv_codes=unique(cpvs), eligibility_text=eligibility or None, documents=documents_in(release),
                award_statuses=["active"] if awards else [], award_date=award_dates[0] if len(award_dates) == 1 else None,
                winners=winners, incumbent_supplier=", ".join(unique(w["name"] for w in winners)) or None,
                contract_start=period.get("startDate"), contract_end=period.get("endDate"),
                extension_end=period.get("maxExtentDate"),
                lot_ids=[str(lot["id"]) for lot in tender.get("lots", []) if lot.get("id")],
                lots=[Lot(id=str(lot["id"]), title=clean(lot.get("title")), description=clean(lot.get("description")),
                          status="awarded" if str(lot["id"]) in awarded_lots else lot.get("status") or "unknown", source_url=url,
                          deadline_at=(lot.get("tenderPeriod") or {}).get("endDate"))
                      for lot in tender.get("lots", []) if lot.get("id")])
