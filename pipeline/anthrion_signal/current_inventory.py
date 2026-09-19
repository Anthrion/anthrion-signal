"""Bounded TED inventory of response windows that remain open, irrespective of age.

This supplements publication-window collection; it does not replace amendments,
deadline-free early engagement, national sources or the historical archive lane.
API/query reference: https://docs.ted.europa.eu/api/latest/search.html and
https://ted.europa.eu/en/help/search-browse (verified 18 September 2026).
"""
import copy
import re
from datetime import timedelta

from .utils import digest, parse_date


def inventory_scope(terms, settings):
    prefixes = terms.get("collection_cpv_prefixes", terms.get("cpv_prefixes", ["48", "72"]))
    codes = " ".join(prefix + "*" for prefix in prefixes if re.fullmatch(r"\d{2,8}", prefix))
    phrases = [p.replace('"', '').replace('\\', '').strip() for p in terms.get("high_intent", [])]
    clauses = [f'FT ~ "{phrase}"' for phrase in phrases if phrase and len(phrase) <= 120]
    return settings.get("ted_scope_filter") or " OR ".join([f"classification-cpv IN ({codes or '48* 72*'})", *clauses])


def collect_ted_inventory(source, state, frozen, http, settings, terms):
    # Runtime import keeps this helper independent of the collector's dispatch map.
    from .collectors import Collection, RawRecord, SourceUnavailable, TED_FIELDS, defer_collection

    result = Collection(state=copy.deepcopy(state))
    budget = max(0, int(settings.get("max_pages", 0)))
    countries = sorted({code for country, market in terms["markets"].items()
                        if market["enabled"] and country in source.get("countries", terms["markets"])
                        for code in market.get("ted_codes", []) if re.fullmatch(r"[A-Z]{3}", code)})
    if not countries or not budget:
        return result
    deferred = parse_date(state.get("retry_at"))
    if deferred and deferred > frozen:
        result.complete, result.message = False, "Open-notice inventory is waiting for the source retry window."
        return result
    scope = inventory_scope(terms, settings)
    version = digest([countries, scope, "deadline-inventory-v2-unique-order"])
    completed = parse_date(state.get("completed_at"))
    if state.get("query_version") == version and completed and completed > frozen - timedelta(hours=6):
        return result
    pending = state.get("pending") if state.get("query_version") == version else None
    if not isinstance(pending, dict) or not parse_date(pending.get("started_at")) or (
            parse_date(pending["started_at"]) < frozen - timedelta(days=7)):
        pending = {"started_at": frozen.isoformat(), "cutoff": (frozen - timedelta(days=1)).strftime("%Y%m%d"),
                   "seen": [], "total": None}
        result.state.pop("completed_at", None)
    else:
        pending = copy.deepcopy(pending)
    if not re.fullmatch(r"\d{8}", str(pending.get("cutoff", ""))):
        pending["cutoff"] = (frozen - timedelta(days=1)).strftime("%Y%m%d")
    seen = {value for value in pending.get("seen", []) if isinstance(value, str)}
    restarted = False
    query = (f"buyer-country IN ({' '.join(countries)}) AND ({scope}) AND ("
             f"deadline-receipt-tender-date-lot >= {pending['cutoff']} OR "
             f"deadline-receipt-request-date-lot >= {pending['cutoff']} OR "
             f"deadline-receipt-expressions-date-lot >= {pending['cutoff']}) SORT BY publication-number DESC")
    result.state.update(query_version=version, pending=pending)
    try:
        while result.pages < budget:
            body = {"query": query, "fields": TED_FIELDS,
                    "limit": max(1, min(source.get("limit", 200), 250, 10000 // (len(TED_FIELDS) + 1))),
                    "paginationMode": "ITERATION", "scope": "ACTIVE"}
            if pending.get("token"):
                body["iterationNextToken"] = pending["token"]
            result.pages += 1
            try:
                data = http.request("POST", source["url"], json=body).json()
            except SourceUnavailable as exc:
                if exc.status_code in {400, 404, 410} and pending.get("token") and not restarted:
                    pending.pop("token", None)
                    pending["seen"], pending["total"], seen = [], None, set()
                    restarted = True
                    continue
                raise
            except ValueError:
                raise SourceUnavailable("Open-notice inventory did not return JSON") from None
            if not isinstance(data, dict) or not isinstance(data.get("notices"), list) or data.get("timedOut"):
                raise SourceUnavailable("Open-notice inventory returned an incomplete search response")
            notices = data["notices"]
            if any(not isinstance(n, dict) or not re.fullmatch(r"\d+-\d{4}", str(n.get("publication-number", ""))) for n in notices):
                raise SourceUnavailable("Open-notice inventory returned an invalid notice identifier")
            total = data.get("totalNoticeCount")
            if pending.get("total") is None and isinstance(total, int) and total >= 0:
                pending["total"] = total
            previous_count = len(seen)
            for notice in notices:
                ident = notice["publication-number"]
                if ident not in seen:
                    result.records.append(RawRecord(notice, source, frozen.isoformat(), "ted"))
                    seen.add(ident)
            pending["seen"] = sorted(seen)
            token = data.get("iterationNextToken")
            # TED may leave a continuation token on the final empty iteration.
            # Accept that terminal page only when its advertised count is met.
            exhausted = not notices and pending.get("total") is not None and len(seen) >= pending["total"]
            if not token or exhausted:
                if pending.get("total") is not None and len(seen) < pending["total"]:
                    # Never call a truncated provider result a complete inventory.
                    result.state.pop("pending", None)
                    raise SourceUnavailable("Open-notice inventory ended before the advertised result count")
                result.state.update(completed_at=frozen.isoformat(), notices=len(seen))
                result.state.pop("pending", None)
                result.state.pop("retry_at", None)
                return result
            if not isinstance(token, str) or token == pending.get("token") or len(seen) == previous_count:
                pending.pop("token", None)
                raise SourceUnavailable("Open-notice inventory did not advance its continuation")
            pending["token"] = token
        result.complete, result.message = False, "Open-notice inventory is continuing within its page budget."
    except SourceUnavailable as exc:
        defer_collection(result, exc)
    return result
