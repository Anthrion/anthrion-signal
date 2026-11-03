"""Bounded public CDB listing/detail collection, with source-faithful deadlines."""
import copy
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .utils import canonical_url, clean, digest, parse_date

ORIGIN = "https://www.caribank.org"
CURRENT = ORIGIN + "/work-with-us/procurement/procurement-notices"
GENERAL = ORIGIN + "/work-with-us/procurement/general-procurement-notices"
DETAIL_PATH = "/work-with-us/procurement/procurement-notices/"
VERSION = "cdb-public-v1"
COUNTRY_NAMES = {
    "Anguilla": "AI", "Antigua and Barbuda": "AG", "The Bahamas": "BS", "Bahamas": "BS",
    "Barbados": "BB", "Belize": "BZ", "British Virgin Islands": "VG", "Cayman Islands": "KY",
    "Dominica": "DM", "Grenada": "GD", "Guyana": "GY", "Haiti": "HT", "Jamaica": "JM",
    "Montserrat": "MS", "Saint Lucia": "LC", "St. Lucia": "LC", "Saint Kitts and Nevis": "KN",
    "Saint Vincent and the Grenadines": "VC", "Suriname": "SR", "Trinidad and Tobago": "TT",
    "Turks and Caicos Islands": "TC", "Regional": "CARIBBEANREGIONAL", "CDB": "CARIBBEANREGIONAL",
}


def notice_url(value, base=CURRENT):
    url = canonical_url(urljoin(base, str(value)))
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "www.caribank.org" or parsed.port not in (None, 443)
            or not parsed.path.startswith(DETAIL_PATH) or not parsed.path[len(DETAIL_PATH):]
            or parsed.query):
        raise SourceUnavailable("CDB notice link left its public procurement path")
    return url


def parse_listing(html, url, kind):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main")
    if not main:
        raise SourceUnavailable("CDB did not return its public procurement listing")
    table = main.select_one("table")
    if not table:
        empty = main.select_one(".view-empty")
        if empty and re.search(r"no (?:results|notices|procurement|content)", empty.get_text(" ", strip=True), re.I):
            return [], None
        raise SourceUnavailable("CDB procurement listing structure changed")
    if not table.select_one("th.views-field-field-cdb-country-tag"):
        raise SourceUnavailable("CDB procurement listing omitted country fields")
    rows = []
    for tr in table.select("tbody tr"):
        title_cell = tr.select_one("td.views-field-field-cdb-role-service, td.views-field-title")
        country_cell = tr.select_one("td.views-field-field-cdb-country-tag")
        link = title_cell.select_one("a[href]") if title_cell else None
        country = clean(country_cell.get_text(" ", strip=True)) if country_cell else ""
        if not link or not clean(link.get_text()) or country not in COUNTRY_NAMES:
            raise SourceUnavailable("CDB contains an incomplete notice or unknown country")
        sector = tr.select_one("td.views-field-field-sector-tag")
        rows.append({"url": notice_url(link["href"], url), "listing_title": clean(link.get_text(" ", strip=True)),
                     "country": country, "sector": clean(sector.get_text()) if sector else "", "listed_as": kind})
    if not rows:
        raise SourceUnavailable("CDB returned an empty table without an explicit empty result")
    next_link = main.select_one(".pager__item--next a[href]")
    next_url = None
    if next_link:
        next_url = canonical_url(urljoin(url, next_link["href"]))
        before, after = urlparse(url), urlparse(next_url)
        query = parse_qs(after.query)
        current_page = int(parse_qs(before.query).get("page", ["0"])[0])
        page = query.get("page", [""])[0]
        if (after.scheme != "https" or after.netloc != "www.caribank.org" or after.path != before.path
                or set(query) != {"page"} or not page.isdigit() or int(page) != current_page + 1
                or int(page) > 250):
            raise SourceUnavailable("CDB pagination link needs review")
    return rows, next_url


def visible_day(value):
    value = clean(value)
    if not value:
        return None
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %B %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise SourceUnavailable("CDB published an unrecognized visible date")


def visible_clock(value):
    value = clean(value).upper().replace("A.M.", "AM").replace("P.M.", "PM")
    if not value:
        return None
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).strftime("%H:%M")
        except ValueError:
            continue
    raise SourceUnavailable("CDB published an unrecognized visible closing time")


def quick_facts(article):
    result = {}
    for field in article.select(".quick-facts--wrap .field-display--above"):
        label = field.select_one(".field--label")
        if not label:
            continue
        name = clean(label.get_text(" ", strip=True)).casefold()
        clone = BeautifulSoup(str(field), "html.parser")
        clone.select_one(".field--label").decompose()
        result[name] = clean(clone.get_text(" ", strip=True))
    return result


def parse_detail(html, entry):
    url = notice_url(entry["url"])
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.node--type-cdb-procurement-notices[data-history-node-id]")
    if not article or not re.fullmatch(r"\d{1,12}", str(article.get("data-history-node-id", ""))):
        raise SourceUnavailable("CDB did not return an identified procurement notice")
    canonical = soup.select_one('link[rel="canonical"][href]')
    if canonical:
        url = notice_url(canonical["href"])
    facts = quick_facts(article)
    body = article.select_one(".field--node--body")
    if not body or not clean(body.get_text(" ", strip=True)):
        raise SourceUnavailable("CDB notice omitted its published scope")
    # Eligibility, instructions, lots and contacts are separate Drupal paragraph
    # components after Overview. Selecting only field--node--body loses them.
    content = BeautifulSoup(str(article), "html.parser")
    for facts_panel in content.select(".quick-facts--wrap"):
        facts_panel.decompose()
    country = facts.get("country", "")
    if country not in COUNTRY_NAMES:
        raise SourceUnavailable("CDB notice has an unknown project country")
    if entry.get("country") and COUNTRY_NAMES[country] != COUNTRY_NAMES.get(entry["country"]):
        raise SourceUnavailable("CDB listing and detail disagree about project country")
    title = facts.get("role/service") or facts.get("project name")
    if not title:
        raise SourceUnavailable("CDB notice omitted its project and service titles")
    day = visible_day(facts.get("deadline"))
    clock_node = article.select_one(".quick-facts--wrap .field--node--field-cdb-time")
    clock = visible_clock(clock_node.get_text(" ", strip=True)) if clock_node else None
    if clock and not day:
        raise SourceUnavailable("CDB closing time has no published date")
    # Drupal's datetime attribute used noon UTC even when the visible clock
    # was 4:30 PM AST. Only the visible day and separate clock are source facts.
    deadline = day + ("T" + clock if clock else "") if day else None
    published = None
    for tr in content.select("tr"):
        cells = tr.select("td")
        if len(cells) == 2 and clean(cells[0].get_text()).casefold().rstrip(":") in {
                "issue date", "publication date", "date published"}:
            published = visible_day(cells[1].get_text(" ", strip=True))
            break
    headings = [title, facts.get("project name", ""), *[
        clean(node.get_text(" ", strip=True)) for node in content.select("h1,h2,h3,h4")],
        *[clean(node.get_text(" ", strip=True)) for node in body.select("p, strong")[:5]]]
    status = "active"
    for text in headings:
        if re.match(r"^(?:cancelled|canceled)(?:\s*[-:–]|$)|^notice of cancellation\b|^tender cancelled\b", text, re.I):
            status = "cancelled"
        elif re.match(r"^withdrawn(?:\s*[-:–]|$)|^notice of withdrawal\b|^tender withdrawn\b", text, re.I):
            status = "withdrawn"
    heading_text = " ".join(headings)
    if any(re.match(r"^(?:contract award notice|notice of (?:contract )?award)\b", text, re.I)
           for text in headings):
        stage, signal_type = "award", "AWARD"
    elif re.search(r"\b(?:request for information|market sounding|early market engagement)\b", heading_text, re.I):
        stage, signal_type = "planning", "RFI"
    elif entry["listed_as"] == "general" or re.search(r"\bgeneral procurement notice\b", heading_text, re.I):
        stage, signal_type = "planning", "PIPELINE"
    else:
        stage, signal_type = "tender", "LIVE_TENDER"
    if stage == "award" and status == "active":
        status = "complete"
    elif stage == "planning" and signal_type == "PIPELINE" and status == "active":
        status = "planned"
    documents = []
    seen = {url}
    for link in article.select("a[href]"):
        href = link["href"]
        # Country/type taxonomy links and the issuer's homepage are not attachments.
        if any(part in href for part in ("/countries-and-members/", "/contract-awards/")):
            continue
        address = canonical_url(urljoin(url, href))
        if address and address not in seen:
            documents.append({"title": clean(link.get_text(" ", strip=True), 240) or "Procurement document",
                              "url": address, "kind": "document"})
            seen.add(address)
    return {"id": article["data-history-node-id"], "url": url, "title": title,
        "project_name": facts.get("project name", ""), "description": clean(content.get_text(" ", strip=True), None),
        "country": country, "sector": entry.get("sector", ""), "notice_type": facts.get("type", ""),
        "buyer": facts.get("buyer") or facts.get("contracting authority") or
                 ("Caribbean Development Bank" if country == "CDB" else None),
        "published_at": published, "deadline_at": deadline, "deadline_text": " ".join(filter(None, [
            facts.get("deadline"), clean(clock_node.get_text()) if clock_node else None])),
        "procurement_stage": stage, "signal_type": signal_type, "status": status, "documents": documents}


def collect_cdb(source, state, frozen, http, settings, terms):
    """Rotate listing/detail queues; cache successful complete notices only."""
    feeds = {"current": CURRENT}
    if source.get("include_general", True):
        feeds["general"] = GENERAL
    version = digest([VERSION, list(feeds)])
    previous = state if state.get("query_version") == version else {}
    result = Collection(state=copy.deepcopy(previous))
    lanes = copy.deepcopy(previous.get("feeds", {}))
    cache = copy.deepcopy(previous.get("details", {}))
    failed_details = copy.deepcopy(previous.get("failed_details", {}))
    budget = max(0, min(int(settings.get("max_pages", 0)), int(source.get("max_pages", 40))))
    refresh = timedelta(hours=max(0, int(source.get("refresh_hours", 6))))
    names = list(feeds)
    cursor = int(previous.get("next_feed", 0)) % len(names)
    finished, failures, emitted = set(), [], set()
    def retry_ready(address):
        retry = parse_date(failed_details.get(address, {}).get("retry_at"))
        return retry is None or retry <= frozen

    while result.pages < budget and len(finished) < len(names):
        name = names[cursor]
        cursor = (cursor + 1) % len(names)
        if name in finished:
            continue
        old_lane = lanes.get(name, {})
        checked = parse_date(old_lane.get("checked_at"))
        if (not old_lane.get("active") and checked and not settings.get("refresh_daily")
                and timedelta(0) <= frozen - checked < refresh):
            finished.add(name)
            continue
        lane = copy.deepcopy(old_lane) if old_lane.get("active") else {
            "active": True, "next_page": feeds[name], "pending": [], "seen_urls": [], "pages": []}
        detail_entry = None
        try:
            if lane["pending"]:
                entry = lane["pending"][0]
                address = notice_url(entry["url"])
                detail_entry = entry
                if not retry_ready(address):
                    lane["pending"].pop(0)
                    lanes[name] = lane
                    continue
                old = cache.get(address, {})
                fingerprint = digest(entry)
                detail_checked = parse_date(old.get("checked_at"))
                if (detail_checked and timedelta(0) <= frozen - detail_checked < refresh
                        and old.get("listing_hash") == fingerprint and not settings.get("refresh_daily")):
                    lane["pending"].pop(0)
                else:
                    result.pages += 1
                    data = parse_detail(http.html(address), entry)
                    checksum = digest(data)
                    if old.get("hash") != checksum and (data["id"], checksum) not in emitted:
                        result.records.append(RawRecord(data, source, frozen.isoformat(), "caribbean_cdb"))
                        emitted.add((data["id"], checksum))
                    cache[address] = {"id": data["id"], "hash": checksum, "checked_at": frozen.isoformat(),
                        "listing_hash": fingerprint, "entry": entry, "deadline_at": data.get("deadline_at"),
                        "terminal": data["status"] in {"cancelled", "withdrawn", "closed", "complete"}}
                    failed_details.pop(address, None)
                    lane["pending"].pop(0)
            elif lane.get("next_page"):
                address = lane["next_page"]
                if address in lane["pages"]:
                    raise SourceUnavailable("CDB listing repeated a completed pagination page")
                result.pages += 1
                entries, following = parse_listing(http.html(address), address, name)
                known = set(lane["seen_urls"])
                lane["pending"] = [entry for entry in entries if entry["url"] not in known
                                   and retry_ready(entry["url"])]
                lane["seen_urls"] = sorted(known | {entry["url"] for entry in entries})
                lane["pages"].append(address)
                lane["next_page"] = following
            if not lane["pending"] and not lane.get("next_page") and not lane.get("missing_rechecked"):
                # A cancelled notice can move off the current list before its
                # advertised deadline. Revisit that known detail for evidence;
                # disappearance itself never becomes a cancellation.
                listed = set(lane["seen_urls"])
                lane["pending"] = [old["entry"] for address, old in sorted(cache.items())
                    if address not in listed and old.get("entry", {}).get("listed_as") == name
                    and retry_ready(address)
                    and not old.get("terminal") and (not old.get("deadline_at")
                        or old["deadline_at"][:10] >= frozen.date().isoformat())]
                queued = {entry["url"] for entry in lane["pending"]}
                lane["pending"].extend(old["entry"] for address, old in sorted(failed_details.items())
                    if address not in queued and old.get("entry", {}).get("listed_as") == name
                    and retry_ready(address))
                lane["missing_rechecked"] = True
            if not lane["pending"] and not lane.get("next_page"):
                # Keep only durable completion metadata. Disappearance is not
                # cancellation, and stored source records are never deleted.
                lane = {"checked_at": frozen.isoformat()}
                finished.add(name)
            lanes[name] = lane
        except SourceUnavailable as exc:
            failures.append(f"{name}: {exc}")
            defer_collection(result, exc)
            if exc.retry_at:
                break
            if detail_entry is not None:
                # A broken individual link must not block every later detail or
                # new listing. Keep its retry separately, with prior facts intact.
                attempts = int(failed_details.get(address, {}).get("attempts", 0)) + 1
                hours = int(source.get("missing_retry_hours", 24)) if exc.status_code in {404, 410} else 3
                failed_details[address] = {"entry": detail_entry, "attempts": attempts,
                    "retry_at": (frozen + timedelta(hours=max(1, hours))).isoformat(), "message": str(exc)}
                lane["pending"].pop(0)
                lanes[name] = lane
            else:
                finished.add(name)
    result.state.update(query_version=version, feeds=lanes, details=cache,
                        failed_details=failed_details, next_feed=cursor)
    pending = any(name not in lanes or lanes[name].get("active") for name in names)
    due = any(name not in finished and (settings.get("refresh_daily")
        or not parse_date(lanes.get(name, {}).get("checked_at"))
        or frozen - parse_date(lanes[name]["checked_at"]) >= refresh) for name in names)
    if pending or due or failures or failed_details:
        result.complete = False
        result.message = ("; ".join(failures) or (f"CDB retained {len(failed_details)} unavailable notice links for retry."
            if failed_details else "CDB public listing and notice queues resume next collection."))
    return result


def normalise_cdb(raw):
    from .models import Document
    from .normalise import base
    from .public_context import deadline_fact, deadline_value

    row = raw.data
    url = notice_url(row["url"])
    country = COUNTRY_NAMES[row["country"]]
    deadline_kind = "tender" if row["procurement_stage"] == "tender" else "expression_of_interest"
    fact = deadline_fact(row.get("deadline_at"), url, deadline_kind) if row["signal_type"] != "AWARD" else None
    if fact:
        fact.source_text = row["deadline_text"]
    return base(raw, title=row["title"], description=row["description"], description_limit=None, url=url,
        ocid="cdb:" + row["id"], external_ids=["cdb:" + row["id"]], countries=[country],
        regions=[row["country"]] if country == "CARIBBEANREGIONAL" else [],
        buyer_name=row.get("buyer"), source_language="und", status=row["status"],
        notice_type=row.get("notice_type") or None, signal_type=row["signal_type"],
        procurement_stage=row["procurement_stage"], published_at=row.get("published_at"),
        updated_at=row.get("published_at"), deadline_at=deadline_value(fact) if fact else None,
        deadlines=[fact] if fact else [], response_deadlines=[deadline_value(fact)] if fact else [],
        documents=[Document(**document) for document in row["documents"]],
        categories=[row["sector"]] if row.get("sector") else [])
