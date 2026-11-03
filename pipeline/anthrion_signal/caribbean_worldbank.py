"""Keyless World Bank procurement notices for Caribbean project countries.

The public API has no reliable date filter: strdate/enddate are silently ignored.
Country-scoped pages are sorted locally-verified newest first. Overlapping anchor
IDs protect offset resumes against insertions/deletions at the front of the feed.
No discovery keyword or official-country-language restriction is applied here.
"""
import copy
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .utils import canonical_url, clean, digest, parse_date

API = "https://search.worldbank.org/api/v2/procnotices"
VERSION = "worldbank-caribbean-v1"
COUNTRY_NAMES = {
    "Antigua and Barbuda": "AG", "Barbados": "BB", "Belize": "BZ", "Dominica": "DM",
    "Dominican Republic": "DO", "Grenada": "GD", "Guyana": "GY", "Haiti": "HT", "Jamaica": "JM",
    "St. Kitts and Nevis": "KN", "St. Lucia": "LC", "St. Vincent and the Grenadines": "VC",
    "Suriname": "SR", "Trinidad and Tobago": "TT", "Caribbean": "CARIBBEANREGIONAL",
    "OECS Countries": "CARIBBEANREGIONAL",
}
NOTICE_TYPES = {
    "Invitation for Bids": ("tender", "LIVE_TENDER"),
    "Request for Expression of Interest": ("tender", "LIVE_TENDER"),
    "Invitation for Prequalification": ("tender", "LIVE_TENDER"),
    "General Procurement Notice": ("planning", "PIPELINE"),
    "Contract Award": ("award", "AWARD"),
}
STATUSES = {"published": "active", "cancelled": "cancelled", "canceled": "cancelled",
            "withdrawn": "withdrawn", "closed": "closed", "expired": "expired", "revised": "unknown"}
LANGUAGES = {"english": "en", "french": "fr", "spanish": "es", "spanish; castilian": "es",
             "dutch": "nl", "portuguese": "pt", "haitian; haitian creole": "ht"}


def publication_day(row):
    value = row.get("noticedate")
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%d-%b-%Y").replace(tzinfo=UTC).date()
    except ValueError:
        # An ISO date is accepted, but collection time is never a replacement.
        parsed = parse_date(value)
        return parsed.date() if parsed else None


def notice_title(row):
    # GPNs describe the financing project rather than an individual bid, and
    # the official API legitimately omits bid_description for these records.
    value = row.get("bid_description")
    if (value is None or value == "") and row.get("notice_type") == "General Procurement Notice":
        value = row.get("project_name")
    return clean(value) if isinstance(value, str) else ""


def validate_notice(row, country=None):
    if not isinstance(row, dict) or not re.fullmatch(r"OP\d{8,12}", str(row.get("id", ""))):
        raise SourceUnavailable("World Bank returned an invalid procurement identifier")
    if row.get("project_ctry_name") not in COUNTRY_NAMES:
        raise SourceUnavailable("World Bank returned an unsupported project country")
    if country is not None and row.get("project_ctry_name") != country:
        raise SourceUnavailable("World Bank did not respect the project-country filter")
    if (not notice_title(row)
            or not isinstance(row.get("notice_text", ""), str) or publication_day(row) is None):
        raise SourceUnavailable("World Bank returned a malformed notice or publication date")
    if row.get("notice_type") not in NOTICE_TYPES:
        raise SourceUnavailable("World Bank published an unknown procurement notice type")
    if clean(row.get("notice_status")).casefold() not in STATUSES:
        raise SourceUnavailable("World Bank published an unknown procurement status")
    day = row.get("submission_deadline_date")
    clock = row.get("submission_deadline_time")
    if day and (not isinstance(day, str) or not re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", day)
                or parse_date(day) is None):
        raise SourceUnavailable("World Bank published an invalid response deadline")
    if clock and (not day or not isinstance(clock, str)
                  or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?", clock.strip())):
        raise SourceUnavailable("World Bank published an invalid local response time")


def parse_page(payload, country, offset, page_size):
    if (not isinstance(payload, dict) or not isinstance(payload.get("procnotices"), list)
            or str(payload.get("os")) != str(offset)):
        raise SourceUnavailable("World Bank returned an unexpected page envelope")
    try:
        total = int(payload["total"])
    except (ValueError, TypeError, KeyError):
        raise SourceUnavailable("World Bank omitted its result count") from None
    rows = payload["procnotices"]
    # A short response before the reported tail is not an exhausted page. A
    # resumed offset beyond a shrunken tail may legitimately return no rows;
    # the missing overlap anchor then restarts the scan from the front.
    if total < 0 or len(rows) != min(page_size, max(0, total - offset)):
        raise SourceUnavailable("World Bank returned an incomplete procurement page")
    for row in rows:
        validate_notice(row, country)
    order = [(-publication_day(row).toordinal(), row["id"]) for row in rows]
    if order != sorted(order) or len({row["id"] for row in rows}) != len(rows):
        raise SourceUnavailable("World Bank procurement ordering needs review")
    return rows, total


def collect_worldbank_caribbean(source, state, frozen, http, settings, terms):
    """Collect a bounded rotating inventory; unchanged source rows are not emitted."""
    countries = source.get("project_countries") or list(COUNTRY_NAMES)
    if (not isinstance(countries, list) or not countries or len(set(countries)) != len(countries)
            or any(country not in COUNTRY_NAMES for country in countries)):
        raise SourceUnavailable("World Bank project-country configuration needs review")
    page_size = max(2, min(100, int(source.get("page_size", 50))))
    overlap = max(1, min(page_size - 1, page_size // 5))
    budget = max(0, min(int(settings.get("max_pages", 0)), int(source.get("max_pages", 80))))
    lookback = max(1, min(3650, int(source.get("lookback_days", 365))))
    refresh = timedelta(hours=max(0, int(source.get("refresh_hours", 6))))
    version = digest([VERSION, countries, page_size, lookback])
    prior = state if state.get("query_version") == version else {}
    lanes = copy.deepcopy(prior.get("countries", {}))
    result = Collection(state=copy.deepcopy(prior))
    cursor = int(prior.get("next_country", 0)) % len(countries)
    finished = set()
    failures = []
    seen = set()
    while result.pages < budget and len(finished) < len(countries):
        country = countries[cursor]
        cursor = (cursor + 1) % len(countries)
        if country in finished:
            continue
        lane = lanes.get(country, {})
        checked = parse_date(lane.get("checked_at"))
        if (not lane.get("pending") and checked and not settings.get("refresh_daily")
                and timedelta(0) <= frozen - checked < refresh):
            finished.add(country)
            continue
        active = copy.deepcopy(lane) if lane.get("pending") else {
            "pending": True, "since": (frozen - timedelta(days=lookback)).date().isoformat(),
            "offset": 0, "hashes": lane.get("hashes", {}), "seen_ids": [],
        }
        offset = int(active.get("offset", 0))
        try:
            result.pages += 1
            payload = http.json(API, params={"format": "json", "rows": page_size, "os": offset,
                "project_ctry_name_exact": country, "srt": "noticedate desc,id asc"})
            rows, total = parse_page(payload, country, offset, page_size)
            anchor = active.get("anchor")
            ids = [row["id"] for row in rows]
            if anchor and anchor not in ids:
                # A source insertion/deletion moved the resume boundary. Replay
                # from the front and retain hashes; never skip an uncertain gap.
                active.update(offset=0, anchor=None)
                lanes[country] = active
                result.complete = False
                continue
            start = ids.index(anchor) + 1 if anchor else 0
            since = parse_date(active["since"]).date()
            hashes = dict(active.get("hashes", {}))
            inventory = set(active.get("seen_ids", []))
            for row in rows:
                if publication_day(row) < since:
                    continue
                ident = row["id"]
                inventory.add(ident)
                checksum = digest(row)
                if hashes.get(ident) != checksum and (ident, checksum) not in seen:
                    result.records.append(RawRecord(row, source, frozen.isoformat(), "worldbank_caribbean"))
                    seen.add((ident, checksum))
                hashes[ident] = checksum
            exhausted = not rows or len(rows) < page_size or offset + len(rows) >= total
            exhausted = exhausted or any(publication_day(row) < since for row in rows)
            if exhausted:
                lanes[country] = {"checked_at": frozen.isoformat(), "hashes": {
                    ident: checksum for ident, checksum in hashes.items() if ident in inventory}}
                finished.add(country)
            elif start == len(rows):
                # The anchor moved to the end of this overlap page. Start at
                # the anchor itself next time so it remains verifiable.
                active.update(offset=offset + len(rows) - 1, hashes=hashes, seen_ids=sorted(inventory))
                lanes[country] = active
            else:
                active.update(offset=offset + len(rows) - overlap, anchor=rows[-1]["id"],
                              hashes=hashes, seen_ids=sorted(inventory))
                lanes[country] = active
        except SourceUnavailable as exc:
            # Failed pages do not advance the country checkpoint. A working
            # country's progress survives an independent failed response.
            failures.append(f"{country}: {exc}")
            defer_collection(result, exc)
            finished.add(country)
            if exc.retry_at:
                break
    result.state.update(query_version=version, countries=lanes, next_country=cursor)
    pending = any(country not in lanes or lanes[country].get("pending") for country in countries)
    # A previous inventory can exist but be due for refresh; a budget-limited
    # attempt must not label every country successfully refreshed.
    due = any(country not in finished and (settings.get("refresh_daily")
              or not parse_date(lanes.get(country, {}).get("checked_at"))
              or frozen - parse_date(lanes[country]["checked_at"]) >= refresh) for country in countries)
    if pending or due or failures:
        result.complete = False
        result.message = "; ".join(failures) or "World Bank country pages resume on the next collection."
    return result


def normalise_worldbank_caribbean(raw):
    from .models import Document
    from .normalise import base
    from .public_context import deadline_fact, deadline_value

    row = raw.data
    validate_notice(row)
    url = "https://projects.worldbank.org/en/projects-operations/procurement-detail/" + row["id"]
    stage, signal_type = NOTICE_TYPES[row["notice_type"]]
    status = STATUSES[clean(row["notice_status"]).casefold()]
    if stage == "award" and status == "active":
        status = "complete"
    project = clean(row.get("project_id"))
    reference = clean(row.get("bid_reference_no"))
    buyer = clean(row.get("contact_organization")) or None
    country_name = row["project_ctry_name"]
    country = COUNTRY_NAMES[country_name]
    description = clean(row.get("notice_text"), None)
    fact = None
    if stage != "award" and row.get("submission_deadline_date"):
        # This field's T00:00:00Z is the API's date container. The separate
        # submission_deadline_time is local; no timezone is supplied by API.
        deadline = row["submission_deadline_date"][:10]
        if row.get("submission_deadline_time"):
            deadline += "T" + row["submission_deadline_time"].strip()
        kind = "expression_of_interest" if "Expression of Interest" in row["notice_type"] else "tender"
        fact = deadline_fact(deadline, url, kind)
    documents = []
    seen = {url}
    soup = BeautifulSoup(row.get("notice_text", ""), "html.parser")
    for link in soup.select("a[href]"):
        address = canonical_url(urljoin(url, link["href"]))
        if address and address not in seen:
            documents.append(Document(title=clean(link.get_text(" ", strip=True), 240) or "Notice attachment",
                                      url=address, kind="document"))
            seen.add(address)
    contact = {key: clean(row.get(field)) for key, field in (
        ("name", "contact_name"), ("email", "contact_email"), ("telephone", "contact_phone_no"),
        ("address", "contact_address"), ("url", "contact_web_url")) if clean(row.get(field))}
    published = publication_day(row).isoformat()
    return base(raw, title=notice_title(row), description=description, description_limit=None, url=url,
        ocid="worldbank:" + row["id"], external_ids=["worldbank:" + row["id"]], buyer_name=buyer,
        procedure_identifiers=["worldbank-procedure:" + digest([project, reference])] if project and reference else [],
        countries=[country], regions=[country_name] if country == "CARIBBEANREGIONAL" else [],
        source_language=LANGUAGES.get(clean(row.get("notice_lang_name")).casefold(), "und"),
        notice_type=row["notice_type"], signal_type=signal_type, procurement_stage=stage, status=status,
        published_at=published, updated_at=published,
        deadline_at=deadline_value(fact) if fact else None, deadlines=[fact] if fact else [],
        response_deadlines=[deadline_value(fact)] if fact else [], documents=documents,
        contacts=[{**contact, "source_url": url}] if contact else [],
        eligibility_text=clean(row.get("procurement_method_name")) or None,
        categories=[clean(row["procurement_group"])] if row.get("procurement_group") else [])
