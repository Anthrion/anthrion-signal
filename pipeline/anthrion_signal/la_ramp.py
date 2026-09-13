"""Official LA RAMP open-opportunity snapshot, without credentials or page scraping."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .normalise import base
from .utils import clean, iso, parse_date

FIELDS = ("rampid", "title", "stagename", "category", "type", "bidpost", "closedate", "department", "url")


def collect_la_ramp(source, state, frozen, http, settings, terms):
    result = Collection(state=dict(state))
    watermark = parse_date(state.get("watermark"))
    if not settings.get("refresh_daily") and watermark and timedelta(0) <= frozen - watermark < timedelta(hours=source.get("refresh_hours", 24)):
        return result
    if settings["max_pages"] < 3:
        return Collection(state=dict(state), complete=False, message="LA RAMP needs three requests to verify its snapshot.")
    limit = 5000
    try:
        result.pages += 1
        before = http.json(source["metadata_url"])
        revision = before.get("rowsUpdatedAt") if isinstance(before, dict) else None
        if not isinstance(revision, int) or frozen - datetime.fromtimestamp(revision, UTC) > timedelta(days=3):
            raise SourceUnavailable("LA RAMP's upstream snapshot is stale or has no verifiable revision")
        result.pages += 1
        rows = http.json(source["url"], params={"$select": ",".join(FIELDS), "$order": "rampid ASC", "$limit": limit})
        if not isinstance(rows, list) or not rows or len(rows) >= limit:
            raise SourceUnavailable("LA RAMP snapshot is empty, invalid or exceeds its verified size limit")
        result.pages += 1
        after = http.json(source["metadata_url"])
        if not isinstance(after, dict) or after.get("rowsUpdatedAt") != revision:
            raise SourceUnavailable("LA RAMP changed during collection; previous snapshot retained")
        id_column = next((c for c in after.get("columns", []) if c.get("fieldName") == "rampid"), {})
        expected = id_column.get("cachedContents", {}).get("count")
        if expected is None or int(expected) != len(rows):
            raise SourceUnavailable("LA RAMP returned an incomplete snapshot")
        current = {}
        for row in rows:
            ident = str(row.get("rampid", "")) if isinstance(row, dict) else ""
            url = row.get("url", {}).get("url", "") if isinstance(row, dict) and isinstance(row.get("url"), dict) else ""
            parsed = urlparse(url)
            if (not re.fullmatch(r"\d{1,16}", ident) or ident in current or not row.get("title")
                    or parsed.scheme != "https" or parsed.netloc not in ("www.rampla.org", "rampla.org")
                    or not row.get("stagename")):
                raise SourceUnavailable("LA RAMP omitted a required opportunity identifier, status or official URL")
            current[ident] = {key: row[key] for key in FIELDS if key in row}
        result.records = [RawRecord(row, source, frozen.isoformat(), "la_ramp") for row in current.values()]
        previous = state.get("open_rows", {})
        missing = {}
        # Absence is not an award. Require two independently revised, complete
        # snapshots before suppressing a previously listed opportunity.
        for ident, row in previous.items():
            if ident in current:
                continue
            observed = state.get("missing", {}).get(ident)
            if observed is not None and observed != revision:
                result.records.append(RawRecord({**row, "catalogue_removed": True}, source, frozen.isoformat(), "la_ramp"))
            else:
                current[ident] = row
                missing[ident] = revision
        result.state.update(watermark=frozen.isoformat(), snapshot_revision=revision, open_rows=current, missing=missing)
    except (ValueError, TypeError):
        result.records = []
        result.complete, result.message = False, "LA RAMP returned malformed snapshot metadata; previous records retained."
    except SourceUnavailable as exc:
        result.records = []
        defer_collection(result, exc)
    return result


def normalise_la_ramp(raw):
    row = raw.data
    ident = str(row.get("rampid", ""))
    if not re.fullmatch(r"\d{1,16}", ident):
        return None
    notice = clean(row.get("type"))
    title = clean(row.get("title"))
    stage = clean(row.get("stagename")).casefold()
    task_order = bool(re.search(r"\bTOS\b|task[ -]order", notice, re.IGNORECASE))
    restricted = task_order and not raw.source.get("allow_task_orders", False)
    if row.get("catalogue_removed"):
        status = "not_listed"
    elif restricted:
        status = "restricted"
    elif stage in ("open", "amended"):
        status = "active"
    elif stage in ("closed", "awarded", "cancelled", "canceled"):
        status = stage
    else:
        status = "unverified"
    signal_type = "RFI" if notice.upper().startswith("RFI") else "RFP" if notice.upper().startswith("RFP") else "LIVE_TENDER"
    return base(raw, title=title, description=title, url=row.get("url", {}).get("url", ""),
        ocid="la-ramp-" + ident, external_ids=["la-ramp:" + ident], buyer_name=clean(row.get("department")) or None,
        signal_type=signal_type, procurement_stage="planning" if signal_type == "RFI" else "tender",
        notice_type=notice if notice != "None" else None, status=status,
        # The dataset's column descriptions explicitly specify UTC, despite its calendar_date type.
        published_at=iso(row.get("bidpost")), updated_at=raw.retrieved_at, deadline_at=iso(row.get("closedate")),
        categories=[clean(row.get("category"))] if row.get("category") != "None" else [],
        countries=["US"], regions=["Los Angeles"],
        eligibility_text="Task-order solicitation under an existing contract; participation rights must be confirmed." if task_order else None)
