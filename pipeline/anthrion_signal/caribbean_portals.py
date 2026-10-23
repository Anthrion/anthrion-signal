"""Public notice pages for Montserrat and Saint Lucia.

The collector uses the normal robots-aware HTTP path, reads complete notice
descriptions, and never treats a missing listing as evidence of cancellation.
Saint Lucia's catalogue expiry is not a response deadline: it also labels old
awards 'Open', sometimes years after award. Only response wording in the notice
can establish its submission date.
"""

import copy
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, unquote, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .models import Document
from .normalise import base, classify
from .utils import canonical_url, clean, digest, parse_date


VERSION = "caribbean-public-portals-v1"
PORTALS = {
    "montserrat": ("https://tenders.gov.ms", "MS", "America/Montserrat"),
    "saint_lucia": ("https://www.finance.gov.lc", "LC", "America/St_Lucia"),
}
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_TEXT = rf"(?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*20\d{{2}}|\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}\s+20\d{{2}})"
RESPONSE = re.compile(
    r"\b(?:(?:expressions? of interest|proposals?|bids?|tenders?|applications?)\s+"
    r"(?:(?:must|shall|should)\s+)?(?:be\s+)?(?:received|submitted|delivered)\s+"
    r"(?:no later than|not later than|on or before|before|by)|"
    r"(?:submission|response|closing)\s+(?:date|deadline)(?:\s+(?:is|shall be))?\s*:?)"
    rf"\s*(?P<window>[^.!?\n]{{0,35}}?{DATE_TEXT}(?:[^.!?\n]{{0,65}})?)", re.I,
)


def _url(value, portal, *, detail=False):
    """Allow only the configured public notice paths, including on resume."""
    origin = PORTALS[portal][0]
    url = canonical_url(urljoin(origin + "/", str(value)))
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != urlparse(origin).netloc:
        raise SourceUnavailable("Caribbean portal linked outside its approved origin")
    pattern = r"/listings/[^/?#]+" if portal == "montserrat" else r"/tenders/view/\d+"
    if detail:
        valid = re.fullmatch(pattern, parsed.path) and not parsed.query
    elif portal == "montserrat":
        valid = parsed.path in ("", "/listings") and all(
            key in ("page", "search[status]") for key, _ in parse_qsl(parsed.query)
        )
    else:
        valid = bool(re.fullmatch(r"/tenders(?:/index(?:/page(?::|%3A)\d+)?)?", parsed.path, re.I))
        valid = valid and not parsed.query
    if not valid:
        raise SourceUnavailable("Caribbean portal returned an unexpected public page path")
    return url


def _date(value, zone=None):
    text = clean(value)
    text = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", text, flags=re.I)
    text = re.sub(r",\s*", " ", text)
    for fmt in ("%b %d %Y - %I:%M %p", "%B %d %Y - %I:%M %p"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=ZoneInfo(zone)).isoformat() if zone else None
        except ValueError:
            pass
    for fmt in ("%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _response_deadline(description, zone):
    values = []
    # Dotted meridians are part of a clock, not sentence boundaries.
    description = re.sub(r"\b([ap])\.\s*m\.", r"\1m", description, flags=re.I)
    for match in RESPONSE.finditer(description):
        window = match["window"]
        found = re.search(DATE_TEXT, window, re.I)
        day = _date(found[0]) if found else None
        if not day:
            continue
        tail = window[found.end():]
        clock = re.match(r"\s*(?:at\s+)?(\d{1,2}):(\d{2})(?:\s*(AM|PM))?\b", tail, re.I)
        if clock:
            hour, minute, meridian = int(clock[1]), int(clock[2]), (clock[3] or "").lower()
            if minute > 59 or (meridian and not 1 <= hour <= 12) or (not meridian and hour > 23):
                continue
            if meridian:
                hour = hour % 12 + (12 if meridian == "pm" else 0)
            tz = ZoneInfo(zone)
            suffix = tail[clock.end():].replace("−", "-")
            explicit = re.search(r"\b(?:UTC|GMT)(?:\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?)?\b", suffix, re.I)
            if explicit:
                hours, minutes = int(explicit[2] or 0), int(explicit[3] or 0)
                if hours > 23 or minutes > 59:
                    continue
                offset = timedelta(hours=hours, minutes=minutes)
                tz = timezone(-offset if explicit[1] == "-" else offset)
                if re.search(r"\bAST\b", suffix) and tz.utcoffset(None) != timedelta(hours=-4):
                    continue
            elif re.search(r"\bAST\b", suffix):
                tz = timezone(timedelta(hours=-4))
            elif re.match(r"\s*(?:\(\s*)?[A-Z]{2,6}\b", suffix):
                # Preserve a clock without inventing an offset for an
                # unsupported explicit timezone abbreviation.
                tz = None
            day = datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=tz).isoformat()
        values.append(day)
    # Ambiguous extensions need a source check, not an earliest/latest-date guess.
    days = {value[:10] for value in values}
    clocks = {value for value in values if len(value) > 10}
    return max(values, key=len) if len(days) == 1 and len(clocks) <= 1 else None


def _next(soup, url, portal):
    for link in soup.select("a[href]"):
        if re.sub(r"[^a-z]", "", link.get_text().lower()) != "next":
            continue
        if "disabled" in link.get("class", []) or "disabled" in link.parent.get("class", []):
            continue
        target = _url(urljoin(url, link["href"]), portal)
        if target == url:
            raise SourceUnavailable("Caribbean portal pagination did not advance")
        return target
    return None


def parse_portal_listing(html, url, portal):
    soup = BeautifulSoup(html, "html.parser")
    hits = []
    if portal == "montserrat":
        container = soup.select_one("turbo-frame#listings")
        if not container:
            raise SourceUnavailable("Montserrat listing structure was not recognised")
        for card in container.select(".list-group-item"):
            link = card.select_one("h3 a[href]")
            if not link or not clean(link.get_text()):
                raise SourceUnavailable("Montserrat listing omitted a notice title or link")
            hits.append({"url": _url(link["href"], portal, detail=True),
                         "title": clean(link.get_text()), "listing_signature": digest(clean(card.get_text()))})
        if not hits and not re.search(r"no (?:tenders|listings|results|records)|nothing found", container.get_text(), re.I):
            raise SourceUnavailable("Montserrat returned an unexplained empty listing")
    else:
        table = soup.find("table")
        if not table or not all(label in table.get_text() for label in ("Title", "Category", "Published")):
            raise SourceUnavailable("Saint Lucia listing structure was not recognised")
        for row in table.select("tr"):
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            link = cells[0].select_one('a[href*="/tenders/view/"]')
            if len(cells) != 6 or not link:
                raise SourceUnavailable("Saint Lucia listing omitted required notice columns")
            hits.append({"url": _url(link["href"], portal, detail=True), "title": clean(link.get_text()),
                         "category": clean(cells[1].get_text()), "buyer": clean(cells[4].get_text()),
                         "published_at": _date(cells[5].get_text()),
                         "listing_signature": digest([clean(cell.get_text()) for cell in cells])})
        if not hits:
            raise SourceUnavailable("Saint Lucia returned an unexplained empty listing")
    return hits, _next(soup, url, portal)


def _heading_value(container, label):
    node = container.find("h4", string=lambda value: clean(value).casefold() == label.casefold())
    sibling = node.find_next_sibling() if node else None
    return clean(sibling.get_text()) if sibling else ""


def _label_value(container, label):
    node = container.find("b", string=lambda value: clean(value).rstrip(":").casefold() == label.casefold())
    parts = []
    for sibling in node.next_siblings if node else []:
        if getattr(sibling, "name", None) in ("br", "b", "address"):
            break
        parts.append(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling))
    return clean(" ".join(parts))


def parse_portal_detail(html, hit, portal):
    soup = BeautifulSoup(html, "html.parser")
    url = _url(hit["url"], portal, detail=True)
    _, country, zone = PORTALS[portal]
    documents = []
    if portal == "montserrat":
        container = soup.select_one('[id^="listing_"]')
        if not container:
            raise SourceUnavailable("Montserrat notice structure was not recognised")
        ident = container.get("id", "").removeprefix("listing_")
        if not re.fullmatch(r"[a-f0-9-]{36}", ident):
            raise SourceUnavailable("Montserrat notice identifier was not recognised")
        description_node = container.select_one(".trix-content")
        description = clean(description_node.get_text(" ", strip=True), 120000) if description_node else ""
        title = _heading_value(container, "Title")
        published = _date(_heading_value(container, "Publish Date"))
        deadline = _date(_heading_value(container, "Deadline Date"), zone)
        status_text = _heading_value(container, "Status")
        status = {"active": "active", "under evaluation": "closed", "awarded": "awarded",
                  "cancelled": "cancelled", "canceled": "cancelled", "withdrawn": "withdrawn",
                  "closed": "closed", "expired": "expired"}.get(status_text.casefold(), "unknown")
        category = _heading_value(container, "Category")
        buyer = _heading_value(container, "Procuring Entity")
        for link in soup.select('a[href*="/rails/active_storage/blobs/"]'):
            document_url = canonical_url(urljoin(url, link["href"]))
            if document_url and urlparse(document_url).netloc == urlparse(url).netloc:
                documents.append({"title": clean(unquote(urlparse(document_url).path.rsplit("/", 1)[-1]), 240),
                                  "url": document_url})
        reference = None
    else:
        container = soup.select_one("#main-container .content")
        title_node = container.find("h2") if container else None
        description_label = container.find("b", string=lambda value: clean(value) == "Description:") if container else None
        if not title_node or not description_label:
            raise SourceUnavailable("Saint Lucia notice structure was not recognised")
        parts = []
        for sibling in description_label.next_siblings:
            if getattr(sibling, "name", None) == "h5":
                break
            parts.append(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling))
        description = clean(" ".join(parts), 120000)
        title = clean(title_node.get_text())
        ident = urlparse(url).path.rsplit("/", 1)[-1]
        category = _label_value(container, "Category")
        buyer = _label_value(container, "Implementing Agency")
        reference = _label_value(container, "Public Reference") or None
        published = hit.get("published_at")
        awarded = category.casefold() == "award of contracts"
        status_text = _label_value(container, "Status")
        # The catalogue 'Open - YYYY-MM-DD' is a visibility period, not proof of
        # an available bid; explicit terminal wording still takes precedence.
        terminal = re.match(r"\s*(cancelled|canceled|withdrawn|closed|expired)\b", status_text, re.I)
        status = "awarded" if awarded else terminal[1].lower() if terminal else "unknown"
        deadline = None if awarded else _response_deadline(description, zone)
        if deadline and status == "unknown":
            status = "active"
        for link in container.select('a[href*="/tenders/download/"]'):
            document_url = canonical_url(urljoin(url, link["href"]))
            if document_url and urlparse(document_url).netloc == urlparse(url).netloc:
                documents.append({"title": clean(link.get_text(), 240), "url": document_url})
    if not title or not description:
        raise SourceUnavailable("Caribbean notice omitted its title or public scope")
    return {"id": f"{country.lower()}:{ident}", "url": url, "country": country, "title": title,
            "description": description, "buyer": buyer or None, "published_at": published,
            "deadline_at": deadline, "status": status, "source_status": status_text,
            "category": category, "reference": reference, "documents": documents}


def _detail_priority(pair, cache):
    url, hit = pair
    fetched = parse_date(cache.get(url, {}).get("fetched_at"))
    published = parse_date(hit.get("published_at"))
    # New notices should not wait behind a lexical crawl of historic numeric IDs.
    # Previously fetched notices retain oldest-refresh-first ordering.
    return (1, fetched.timestamp(), url) if fetched else (0, -published.timestamp() if published else 0, url)


def collect_caribbean_portal(source, state, frozen, http, settings, terms):
    """Snapshot small public catalogues, then resume full details within budget."""
    portal = source.get("portal")
    if portal not in PORTALS:
        raise SourceUnavailable("Unsupported Caribbean public portal")
    result = Collection(state=copy.deepcopy(state))
    budget = max(0, min(int(settings["max_pages"]), int(source.get("max_pages_per_run", 40))))
    old_version = state.get("query_version") != VERSION
    pending = copy.deepcopy(state.get("pending")) if not old_version else None
    watermark = parse_date(state.get("watermark"))
    if not pending and not old_version and watermark and not settings.get("refresh_daily"):
        if timedelta(0) <= frozen - watermark < timedelta(hours=max(1, source.get("refresh_hours", 12))):
            return result
    cache = {} if old_version else copy.deepcopy(state.get("detail_cache", {}))
    if not isinstance(pending, dict) or pending.get("refresh_listing"):
        pending = {"next": _url(source["url"], portal), "seen": [], "hits": {}, "queue": None}
    result.state.update(query_version=VERSION, pending=pending, detail_cache=cache)
    try:
        while pending.get("next"):
            if result.pages >= budget:
                raise SourceUnavailable("Caribbean listing budget reached; pagination resumes next run")
            url = _url(pending["next"], portal)
            if url in pending["seen"] or len(pending["seen"]) >= 100:
                raise SourceUnavailable("Caribbean portal pagination repeated or exceeded its safe limit")
            result.pages += 1
            hits, following = parse_portal_listing(http.html(url), url, portal)
            for hit in hits:
                pending["hits"][hit["url"]] = hit
            pending["seen"].append(url)
            pending["next"] = following
        if pending.get("queue") is None:
            threshold = frozen - timedelta(hours=max(1, source.get("detail_cache_hours", 24)))
            candidates = dict(pending["hits"])
            # A removed active notice gets a detail refresh, never a synthesized
            # closure. Terminal cached entries do not need perpetual refetches.
            for url, item in cache.items():
                if item.get("status") in ("active", "unknown") and url not in candidates:
                    candidates[url] = {"url": url, "published_at": item.get("published_at")}
            pending["queue"] = [hit for url, hit in sorted(candidates.items(), key=lambda pair: _detail_priority(pair, cache))
                if cache.get(url, {}).get("signature") != hit.get("listing_signature")
                or (parse_date(cache.get(url, {}).get("fetched_at")) or threshold) <= threshold]
        failures = []
        last_failure = None
        while pending["queue"]:
            if result.pages >= budget:
                pending["queue"].extend(failures)
                raise SourceUnavailable("Caribbean detail budget reached; remaining notices resume next run")
            hit = pending["queue"][0]
            url = _url(hit["url"], portal, detail=True)
            result.pages += 1
            try:
                record = parse_portal_detail(http.html(url), hit, portal)
            except SourceUnavailable as exc:
                failures.append(pending["queue"].pop(0))
                last_failure = exc
                if exc.status_code in (401, 403, 429, 503) or exc.retry_at:
                    pending["queue"].extend(failures)
                    raise
                continue
            result.records.append(RawRecord(record, source, frozen.isoformat(), "caribbean_portal"))
            cache[url] = {"signature": hit.get("listing_signature"), "fetched_at": frozen.isoformat(),
                          "status": record["status"], "published_at": record["published_at"]}
            pending["queue"].pop(0)
        if failures:
            pending["queue"] = failures
            # A permanently missing detail must not freeze discovery at an old
            # catalogue snapshot. Keep verified cached facts and start a fresh
            # listing pass after every attempted detail has had its turn.
            pending["refresh_listing"] = True
            raise last_failure
        result.state["watermark"] = frozen.isoformat()
        result.state.pop("pending", None)
    except SourceUnavailable as exc:
        defer_collection(result, exc)
    return result


def normalise_caribbean_portal(raw):
    r = raw.data
    portal = raw.source.get("portal")
    if portal not in PORTALS or r.get("country") != PORTALS[portal][1]:
        return None
    try:
        url = _url(r.get("url", ""), portal, detail=True)
    except SourceUnavailable:
        return None
    ident = clean(r.get("id"))
    if not ident.startswith(r["country"].lower() + ":"):
        return None
    stage = "award" if r.get("status") == "awarded" else "planning" if (
        clean(r.get("category")).casefold() == "general procurement notices"
    ) else "tender"
    title, description = clean(r.get("title")), clean(r.get("description"), 120000)
    signal_type = classify(stage, title, description)
    documents = [Document(title="Official procurement notice", url=url,
                          kind="awardNotice" if stage == "award" else "tenderNotice")]
    for item in r.get("documents", []):
        link = canonical_url(item.get("url", ""))
        if link and urlparse(link).netloc == urlparse(url).netloc:
            documents.append(Document(title=clean(item.get("title"), 240) or "Procurement document", url=link))
    return base(raw, title=title, description=description, description_limit=120000, url=url,
                ocid="caribbean-" + ident, buyer_name=r.get("buyer"), source_language="en",
                signal_type=signal_type, procurement_stage=stage, status=r.get("status", "unknown"),
                notice_type=r.get("category") or None, countries=[r["country"]],
                published_at=r.get("published_at"), deadline_at=r.get("deadline_at"),
                external_ids=["caribbean:" + ident],
                procedure_identifiers=[r["reference"]] if r.get("reference") else [], documents=documents)
