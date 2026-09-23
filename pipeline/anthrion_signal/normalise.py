import math
import re
from datetime import datetime
from html import unescape
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Amount, Document, Lot, Provenance, Signal
from .markets import TED_COUNTRIES
from .public_context import deadline_fact, deadline_value, enrich_signal
from .utils import calendar_day, canonical_url, clean, digest, iso, official_notice_url, parse_date, unique


MATERIAL_FIELDS = ["title", "description", "buyer_name", "deadline_at", "contract_start", "contract_end",
                   "extension_end", "value_min", "value_max", "currency", "procurement_stage", "signal_type",
                   "status", "framework", "eligibility_text", "incumbent_supplier", "cpv_codes", "lot_ids", "lot_id",
                   "countries", "regions", "response_deadlines", "notice_type", "award_statuses", "amount",
                   "deadlines", "lots", "award_date", "winners", "procedure_identifiers", "contacts", "agency_name",
                   "department_name", "buyer_name_conflicts", "source_language"]


def material_payload(signal):
    data = signal.model_dump() if isinstance(signal, Signal) else signal
    result = {key: data.get(key) for key in MATERIAL_FIELDS}
    result["documents"] = sorted({canonical_url(d["url"]) for d in data.get("documents", [])
                                  if d.get("kind") not in ("tenderNotice", "awardNotice", "plannedProcurementNotice")})
    return result


def set_hashes(signal):
    payload = material_payload(signal)
    signal.content_hash = digest(payload)
    signal.material_change_hash = signal.content_hash
    signal.fingerprint = digest([clean(signal.buyer_name).casefold(), clean(signal.title).casefold(),
                                 (signal.deadline_at or "")[:10], signal.value_max, signal.currency, signal.lot_id])
    return signal


def money(value):
    try:
        amount = float(value)
        return amount if math.isfinite(amount) and amount >= 0 else None
    except (TypeError, ValueError):
        return None


def base(raw, *, title, description, url, description_limit=24000, **kwargs):
    source = raw.source
    data = raw.data
    url = canonical_url(url)
    if not url or not clean(title):
        return None
    ocid = kwargs.get("ocid")
    external_id = str(data.get("id") or (data.get("publication-number") if source["id"] == "ted" else "") or "")
    signal = Signal(
        id="sig_" + digest([ocid or url, kwargs.get("lot_id")])[:20], source=source["id"],
        source_type=source["source_type"], source_urls=[url], primary_source_url=url,
        title=clean(title, 500), description=clean(description, description_limit),
        first_seen_at=raw.retrieved_at, last_seen_at=raw.retrieved_at,
        last_material_update=kwargs.get("updated_at") or raw.retrieved_at,
        raw_source_hash=digest(data),
        provenance=[Provenance(source=source["id"], source_name=source["name"], url=url, release_id=external_id,
                               ocid=ocid, retrieved_at=raw.retrieved_at, published_at=kwargs.get("published_at"), raw_hash=digest(data))],
        **kwargs)
    return set_hashes(enrich_signal(signal))


def documents_in(release):
    documents = list(release.get("tender", {}).get("documents", []) or [])
    documents.extend(release.get("planning", {}).get("documents", []) or [])
    for group in ("awards", "contracts"):
        for record in release.get(group, []) or []:
            documents.extend(record.get("documents", []) or [])
    result = []
    seen = set()
    for document in documents:
        url = canonical_url(document.get("url", ""))
        if url and url not in seen:
            seen.add(url)
            result.append(Document(title=clean(document.get("title") or document.get("description")
                                               or document.get("documentType") or "Procurement document", 240),
                                   url=url, kind=document.get("documentType") or "document",
                                   source_revision=str(document.get("dateModified") or document.get("datePublished") or document.get("id") or "") or None))
    return result


def classify(stage, title, description, notice_type=None, framework=None):
    text = (title + " " + description[:1000]).lower()
    if stage in ("award", "implementation", "contract"):
        return "AWARD"
    if stage == "planning":
        if re.search(r"\brfi\b|request for information", text):
            return "RFI"
        if notice_type == "UK2" or re.search(r"market engag|prior information|pre.market|soft market", text):
            return "EARLY_MARKET_ENGAGEMENT"
        return "PIPELINE"
    if framework and stage == "tender":
        return "FRAMEWORK"
    if re.search(r"\brfi\b|request for information", text):
        return "RFI"
    if re.search(r"\brfp\b|request for proposal", text):
        return "RFP"
    return "LIVE_TENDER"


def normalise_ocds(raw, prior=None):
    r, source = raw.data, raw.source
    tender = r.get("tender") or {}
    awards = r.get("awards") or []
    contracts = r.get("contracts") or []
    docs = documents_in(r)
    title = tender.get("title") or r.get("planning", {}).get("project", {}).get("title") or (prior.title if prior else None)
    if not title:
        return None
    description = tender.get("description") or ""
    lots = tender.get("lots") or []
    if lots:
        lot_text = " ".join(f"Lot {lot.get('id')}: {lot.get('title', '')}. {lot.get('description', '')}" for lot in lots)
        description = description + " " + lot_text
    if not description.strip() and prior:
        description = prior.description
    party = next((p for p in r.get("parties", []) if "buyer" in (p.get("roles") or [])), {})
    buyer = r.get("buyer") or party
    address = party.get("address") or {}
    tag = " ".join(r.get("tag") or []).lower()
    stage = "award" if "award" in tag or "contract" in tag else "planning" if "planning" in tag else "tender"
    status = tender.get("status") or "unknown"
    if "cancel" in tag and status != "withdrawn":
        status = "cancelled"
    notice_type = next((d.get("noticeType") for d in tender.get("documents", []) if d.get("noticeType")), None)
    value = tender.get("value") or {}
    min_value = tender.get("minValue") or {}
    if not value and len(lots) == 1:
        value = lots[0].get("value") or {}
    if not value and len(awards) == 1:
        value = awards[0].get("value") or {}
    actual_awards = [a for a in awards if a.get("status", "active") == "active" and a.get("value")]
    if stage == "award" and len(actual_awards) == 1:
        value, min_value = actual_awards[0]["value"], {}
    period = tender.get("contractPeriod") or {}
    if not period and len(lots) == 1:
        period = lots[0].get("contractPeriod") or {}
    if len(contracts) == 1:
        period = contracts[0].get("period") or period
    elif len(awards) == 1:
        period = awards[0].get("contractPeriod") or period
    classification = [tender.get("classification") or {}]
    regions = [source.get("region"), address.get("region")]
    countries = [source.get("country")]
    for item in tender.get("items", []):
        classification.extend([item.get("classification") or {}, *(item.get("additionalClassifications") or [])])
        for delivery in item.get("deliveryAddresses") or []:
            regions.extend([delivery.get("region"), delivery.get("locality")])
        delivery = item.get("deliveryLocation") or {}
        if delivery.get("description"):
            regions.append(delivery["description"])
    techniques = tender.get("techniques") or {}
    framework_info = techniques.get("frameworkAgreement")
    has_framework = techniques.get("hasFrameworkAgreement")
    framework = None
    # The OCDS description is free-form procedure detail, not a framework name.
    if has_framework is True or (has_framework is not False and isinstance(framework_info, dict) and framework_info):
        framework = "Framework agreement"
    elif has_framework is not False and "framework agreement" in clean(tender.get("procurementMethodDetails")).lower():
        framework = "Framework agreement"
    if notice_type in ("UK13", "UK14", "UK15", "UK16"):
        framework = "Dynamic market"
    notice_docs = [d.url for d in docs if d.kind in ("tenderNotice", "awardNotice", "plannedProcurementNotice")]
    url = (notice_docs or [d.url for d in docs if "/Notice/" in d.url] or [""])[0]
    if not url:
        if source["id"] == "find_tender":
            url = source["website"] + "/Notice/" + str(r.get("id", ""))
        elif source["id"] == "contracts_finder":
            match = re.match(r"([a-f0-9-]{36})", str(r.get("id", "")))
            url = source["website"] + "/Notice/" + match.group(1) if match else source["record_url"].format(ocid=r["ocid"])
        else:
            url = source["record_url"].format(ocid=r.get("ocid"))
    identifiers = unique([f"{x.get('scheme', '')}:{x.get('id', '')}" for x in [party.get("identifier", {})] if x.get("id")])
    eligibility = tender.get("eligibilityCriteria") or tender.get("selectionCriteria")
    if isinstance(eligibility, dict):
        eligibility = eligibility.get("description") or " ".join(clean(c.get("description")) for c in eligibility.get("criteria", []))
    elif isinstance(eligibility, list):
        eligibility = " ".join(clean(x.get("description")) for x in eligibility if isinstance(x, dict))
    suppliers = unique([s.get("name") for a in awards if a.get("status", "active") == "active" for s in a.get("suppliers", [])])
    buyer_reference = clean(tender.get("id"))
    if len(buyer_reference) < 6 or buyer_reference.lower() in ("tender", "notice", "contract", "unknown"):
        buyer_reference = ""
    deadlines = []
    for period_name, kind in (("enquiryPeriod", "questions"), ("participationPeriod", "application"), ("tenderPeriod", "tender")):
        fact = deadline_fact((tender.get(period_name) or {}).get("endDate"), url, kind)
        if fact:
            deadlines.append(fact)
    for lot in lots:
        for period_name, kind in (("participationPeriod", "application"), ("tenderPeriod", "tender")):
            fact = deadline_fact((lot.get(period_name) or {}).get("endDate"), url, kind, lot_id=str(lot.get("id", "")))
            if fact:
                deadlines.append(fact)
    responses = [fact for fact in deadlines if fact.kind == "application"] or [fact for fact in deadlines if fact.kind == "tender"]
    from .notice_dates import response_deadline_instant
    upcoming = [fact for fact in responses if response_deadline_instant(deadline_value(fact)) > parse_date(raw.retrieved_at)]
    response = min(upcoming, key=lambda fact: response_deadline_instant(deadline_value(fact))) if upcoming else max(responses, key=lambda fact: response_deadline_instant(deadline_value(fact)), default=None)
    amount_kind = "award" if stage == "award" and len(actual_awards) == 1 else "estimated_contract"
    if money(value.get("amount")) is None and money(min_value.get("amount")) is None:
        amount_kind = "unknown"
    structured_lots = []
    for lot in lots:
        lot_ident = str(lot.get("id", ""))
        lot_awards = [a for a in awards if lot_ident in [str(v) for v in a.get("relatedLots", [])] and a.get("status", "active") == "active"]
        structured_lots.append(Lot(id=lot_ident, title=clean(lot.get("title")), description=clean(lot.get("description")),
            status="awarded" if lot_awards else lot.get("status") or "unknown", source_url=url,
            deadline_at=(lot.get("tenderPeriod") or {}).get("endDate"), value_max=money((lot.get("value") or {}).get("amount")),
            currency=(lot.get("value") or {}).get("currency")))
    award_dates = unique([a.get("date") for a in awards if a.get("status", "active") == "active"])
    winners = [{"name": clean(s.get("name")), "identifiers": unique([s.get("id")]),
                "lot_ids": [str(v) for v in a.get("relatedLots", [])], "source_url": url}
               for a in awards if a.get("status", "active") == "active" for s in a.get("suppliers", []) if s.get("name")]
    record_lot = r.get("lot_id")
    known_lots = {str(lot.get("id")) for lot in lots} or set(prior.lot_ids if prior else [])
    result_lots = {str(ident) for award in awards for ident in award.get("relatedLots", [])}
    if stage == "award" and result_lots:
        # Cancellation uses the same lot identity as the award it revises.
        record_lot = next(iter(result_lots)) if len(result_lots) == 1 else "lots:" + ",".join(sorted(result_lots))
    elif stage == "award" and len(known_lots) > 1:
        # A partial/unspecified award is a linked notice, not a terminal update to
        # every lot of the original procedure. Preserve an independently stable ID.
        record_lot = "award:" + str(r.get("id", ""))
    return base(raw, title=title, description=description, url=url, ocid=r.get("ocid"),
        lot_id=record_lot, lot_ids=sorted(result_lots) if record_lot and stage == "award" else [str(lot.get("id")) for lot in lots],
        lots=structured_lots, procedure_identifiers=["ocid:" + r["ocid"]] if r.get("ocid") else [],
        award_date=iso(award_dates[0]) if len(award_dates) == 1 else None, winners=winners,
        external_ids=unique([f"{source['id']}:{r.get('id')}" if r.get("id") else None,
                             f"buyer-ref:{clean(buyer.get('name')).lower()}:{buyer_reference}" if buyer_reference and buyer.get("name") else None]),
        buyer_name=clean(buyer.get("name")) or None, buyer_identifiers=identifiers,
        signal_type=classify(stage, clean(title), clean(description), notice_type, framework),
        procurement_stage=stage, notice_type=notice_type, status=status,
        published_at=iso(r.get("date")), updated_at=iso(r.get("date")),
        deadline_at=deadline_value(response) if response else None, deadlines=deadlines,
        response_deadlines=unique([deadline_value(fact) for fact in responses]) if len({deadline_value(fact) for fact in responses}) > 1 else [],
        amount=Amount(kind=amount_kind, minimum=money(min_value.get("amount")), maximum=money(value.get("amount")),
            currency=value.get("currency") or min_value.get("currency"), source_label="awards[].value" if amount_kind == "award" else "tender.value / tender.minValue", source_url=url),
        contract_start=iso(period.get("startDate")), contract_end=iso(period.get("endDate")),
        extension_end=iso(period.get("maxExtentDate")), value_min=money(min_value.get("amount")),
        value_max=money(value.get("amount")), currency=value.get("currency") or min_value.get("currency"),
        cpv_codes=unique([str(c["id"]) for c in classification if c.get("id") and c.get("scheme", "CPV") == "CPV"]),
        regions=unique([clean(x) for x in regions]), countries=unique(countries), framework=framework,
        incumbent_supplier=", ".join(suppliers) or None,
        award_statuses=unique([a.get("status") for a in awards if a.get("status")]),
        eligibility_text=clean(eligibility) or None, documents=docs)


def normalise_govuk(raw):
    r = raw.data
    title, description = clean(r.get("title")), clean(r.get("description"))
    text = (title + " " + description).lower()
    kind = "PIPELINE" if "pipeline" in text else "FUNDING" if re.search(r"funding competition|apply for funding", text) else "STRATEGIC_INTENT"
    return base(raw, title=title, description=description, url=urljoin("https://www.gov.uk", r.get("link", "")),
        buyer_name=", ".join(o.get("title", "") for o in r.get("organisations", [])) or None,
        signal_type=kind, procurement_stage="planning", status="published", countries=["GB"],
        external_ids=["govuk:" + r.get("link", "")], published_at=iso(r.get("public_timestamp")),
        updated_at=iso(r.get("public_timestamp")), notice_type=r.get("format"))


def normalise_html(raw):
    r = raw.data
    links = unique(official_notice_url(u) for u in r.get("source_links", []))
    signal = base(raw, title=r["title"], description=r["description"], url=r["url"],
        buyer_name=r.get("buyer"), signal_type=r["signal_type"], procurement_stage=r["stage"],
        status=r.get("status", "unknown"), countries=[raw.source["country"]],
        external_ids=[raw.source["id"] + ":" + r["id"]], deadline_at=r.get("deadline") if parse_date(r.get("deadline")) else None,
        contract_start=iso(r.get("contract_start")), contract_end=iso(r.get("contract_end")),
        value_max=money(r.get("value")), currency="GBP" if r.get("value") is not None else None,
        framework=r.get("framework"), documents=[Document(title="Official procurement notice", url=link, kind="tenderNotice")
                                                 for link in links])
    if signal:
        # Every published link is canonicalised here, never trusted as collected.
        signal.source_urls = unique([signal.primary_source_url, *links])
    return signal


def ted_text(value):
    if isinstance(value, dict):
        return ted_text(value.get("eng") or value.get("en") or next(iter(value.values()), ""))
    if isinstance(value, list):
        return "; ".join(ted_text(v) for v in value)
    return clean(value)


def normalise_ted(raw):
    r = raw.data
    number = ted_text(r.get("publication-number"))
    if not re.fullmatch(r"\d+-\d{4}", number):
        raise ValueError("Missing TED publication number")
    form = ted_text(r.get("form-type")).lower()
    notice_type = ted_text(r.get("notice-type")).lower()
    direct_award = form == "dir-awa-pre" or notice_type in ("veat", "dir-awa-pre")
    stage = "award" if form in ("result", "cont-modif") or direct_award else "planning" if form == "planning" else "tender" if form == "competition" else "unknown"
    title = ted_text(r.get("title-proc")) or ted_text(r.get("notice-title"))
    description = "\n\n".join(unique([ted_text(r.get("description-proc")), ted_text(r.get("description-lot"))]))
    region = ted_text(r.get("place-of-performance"))
    buyer_countries = r.get("buyer-country") or r.get("place-of-performance") or []
    if isinstance(buyer_countries, str):
        buyer_countries = [buyer_countries]
    deadlines, facts = [], []
    url = f"https://ted.europa.eu/en/notice/-/detail/{number}"
    for phase in ("request", "expressions", "tender"):
        dates = r.get(f"deadline-receipt-{phase}-date-lot") or []
        times = r.get(f"deadline-receipt-{phase}-time-lot") or []
        dates = [dates] if isinstance(dates, str) else dates
        times = [times] if isinstance(times, str) else times
        for day in dates:
            # Search arrays have no lot/time pairing. Do not invent an exact
            # cutoff for multiple lots. Qualification precedes invitation to bid.
            value = day[:10] + "T" + times[0] if len(dates) == len(times) == 1 else day[:10]
            fact = deadline_fact(value, url, {"request": "application", "expressions": "expression_of_interest", "tender": "tender"}[phase])
            if fact:
                if phase == "tender" and any(f.kind == "application" for f in facts):
                    fact.kind = "invited_submission"
                facts.append(fact)
    for kind in ("application", "expression_of_interest", "tender"):
        deadlines = [deadline_value(fact) for fact in facts if fact.kind == kind]
        if deadlines:
            break
    deadlines = sorted(set(deadlines))
    now = parse_date(raw.retrieved_at)
    from .notice_dates import response_deadline_instant
    upcoming = [value for value in deadlines if response_deadline_instant(value) > now]
    deadline = min(upcoming) if upcoming else max(deadlines, default=None)
    terminated = r.get("competition-termination-proc") is True or r.get("competition-termination-proc") == "true"
    framework_values = r.get("framework-agreement-lot") or []
    framework = "Framework agreement" if any(v in ("fa-mix", "fa-w-rc", "fa-wo-rc") for v in framework_values) else None
    value = money(r.get("total-value")) if stage == "award" else money(r.get("estimated-value-proc"))
    currencies = r.get("total-value-cur") if stage == "award" else r.get("estimated-value-cur-proc")
    if isinstance(currencies, list):
        currencies = unique(currencies)
        currencies = currencies[0] if len(currencies) == 1 else None
    change_ref = ted_text(r.get("change-notice-version-identifier"))
    changed_notice = re.fullmatch(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})(?:-\d+)?", change_ref)
    # BT-758 explicitly replaces a notice version. A general previous-procedure
    # reference does not: a lot award must not close an entire admission system.
    aliases = ["ted:" + number, "ted-notice:" + ted_text(r.get("notice-identifier")) if r.get("notice-identifier") else None]
    if changed_notice:
        aliases.append("ted-notice:" + changed_notice[1])
    procedure = ted_text(r.get("procedure-identifier"))
    lot_ids = unique(r.get("identifier-lot") if isinstance(r.get("identifier-lot"), list) else [r.get("identifier-lot")])
    original_titles = r.get("title-proc") or r.get("notice-title") or {}
    language = ("en" if "eng" in original_titles else next(iter(original_titles), "und")) if isinstance(original_titles, dict) else "und"
    # The Official Journal publication day, e.g. "2026-07-02+02:00": a date, not midnight UTC.
    published = calendar_day(ted_text(r.get("publication-date")))
    return base(raw, title=title, description=description or title, url=url,
        buyer_name=ted_text(r.get("buyer-name")) or None, signal_type=classify(stage, title, description, framework=framework) if stage != "unknown" else "STRATEGIC_INTENT", procurement_stage=stage,
        external_ids=unique(aliases),
        procedure_identifiers=["ted-procedure:" + procedure] if procedure else [], source_language=language,
        lot_ids=lot_ids, lots=[Lot(id=str(ident), title="", description=ted_text(r.get("description-lot")) if len(lot_ids) == 1 else "",
            status="unknown", source_url=url) for ident in lot_ids],
        notice_type=notice_type, status="cancelled" if terminated else "closed" if direct_award else "awarded" if stage == "award" else "active",
        published_at=published, updated_at=published,
        deadline_at=deadline, response_deadlines=deadlines, deadlines=facts,
        value_max=value, currency=currencies, framework=framework, incumbent_supplier=ted_text(r.get("winner-name")) or None,
        amount=Amount(kind=("award" if stage == "award" else "estimated_contract") if value is not None else "unknown",
            maximum=value, currency=currencies, source_label="total-value" if stage == "award" else "estimated-value-proc", source_url=url),
        documents=[Document(title="Official notice (PDF)", url=f"https://ted.europa.eu/en/notice/{number}/pdf", kind="notice", source_revision=number)],
        cpv_codes=re.findall(r"\d{8}", ted_text(r.get("classification-cpv"))), regions=[region] if region else [],
        countries=unique([TED_COUNTRIES[c] for c in buyer_countries if c in TED_COUNTRIES]))


def normalise_usaspending(raw):
    r = raw.data
    ident = r.get("generated_internal_id")
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_\-.:]+", ident):
        raise ValueError("Missing USAspending award identifier")
    description = clean(r.get("Description"))
    return base(raw, title=description or f"Contract award {r.get('Award ID', ident)}", description=description,
        url="https://www.usaspending.gov/award/" + ident, external_ids=["usaspending:" + ident],
        buyer_name=clean(r.get("Awarding Agency")) or None, incumbent_supplier=clean(r.get("Recipient Name")) or None,
        signal_type="AWARD", procurement_stage="award", notice_type="Federal contract award", status="awarded",
        countries=["US"], updated_at=iso(r.get("Last Modified Date")), contract_start=iso(r.get("Start Date")),
        contract_end=iso(r.get("End Date")), value_max=money(r.get("Award Amount")), currency="USD")


def grants_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d-%H-%M-%S", "%m/%d/%Y"):
        try:
            # Grants.gov provides a date, not a guaranteed submission cutoff.
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def normalise_grants(raw):
    r = raw.data
    if not str(r.get("id", "")).isdigit():
        raise ValueError("Missing Grants.gov opportunity ID")
    facts = r.get("facts") or {}
    eligibility = clean(unescape(facts.get("applicantEligibilityDesc") or ""))
    types = "; ".join(clean(t.get("description")) for t in facts.get("applicantTypes", []))
    url = f"https://www.grants.gov/search-results-detail/{r['id']}"
    document_url = canonical_url(facts.get("fundingDescLinkUrl") or "")
    # agencyName in a synopsis has contained an individual contact. Prefer the
    # documented organisation objects and the authoritative search-listing label.
    agency = r.get("agencyDetails") or facts.get("agencyDetails") or {}
    parent_agency = r.get("topAgencyDetails") or facts.get("topAgencyDetails") or {}
    buyer = clean(agency.get("agencyName") or r.get("agency")) or None
    agency_code = clean(agency.get("agencyCode") or agency.get("code") or r.get("owningAgencyCode"))
    contact = {key: clean(facts.get(field)) for key, field in
               (("name", "agencyContactName"), ("role", "agencyContactDesc"), ("email", "agencyContactEmail")) if facts.get(field)}
    contacts = [{**contact, "source_url": url}] if contact else []
    conflicts = [clean(facts["agencyName"])] if facts.get("agencyName") and clean(facts["agencyName"]) != buyer else []
    deadline = grants_date(facts.get("responseDateStr") or r.get("closeDate"))
    deadline_info = deadline_fact(deadline, url, "application")
    docs = [Document(title=clean(facts.get("fundingDescLinkDesc")) or "Funding announcement", url=document_url)] if document_url else []
    for link in BeautifulSoup(facts.get("synopsisDesc") or facts.get("forecastDesc") or "", "html.parser").find_all("a", href=True):
        target = canonical_url(link["href"])
        if target and re.search(r"\.pdf(?:\?|$)|announcement|funding|\.docx?(?:\?|$)", target, re.I):
            docs.append(Document(title=clean(link.get_text()) or "Linked funding document", url=target))
    for link in r.get("document_links", []):
        if canonical_url(link.get("url", "")):
            docs.append(Document(title=clean(link.get("title")) or "Funding document", url=canonical_url(link["url"])))
    return base(raw, title=r["title"], description=clean(unescape(facts.get("synopsisDesc") or facts.get("forecastDesc") or r["title"])),
        url=url, external_ids=["grants:" + str(r["id"])], buyer_name=buyer,
        buyer_identifiers=["grants-agency:" + agency_code] if agency_code else [], agency_name=clean(parent_agency.get("agencyName")) or buyer,
        department_name=buyer if parent_agency.get("agencyName") and parent_agency["agencyName"] != buyer else None,
        contacts=contacts, buyer_name_conflicts=conflicts, source_language="en",
        signal_type="FUNDING", procurement_stage="planning" if r.get("status") == "forecasted" else "funding",
        status="complete" if r.get("status") in ("closed", "archived") else "active", notice_type="Federal funding opportunity",
        countries=["US"], published_at=grants_date(facts.get("postingDateStr") or r.get("openDate")),
        updated_at=grants_date(facts.get("createTimeStampStr")),
        deadline_at=deadline, deadlines=[deadline_info] if deadline_info else [],
        value_min=money(facts.get("awardFloor")), value_max=money(facts.get("awardCeiling")), currency="USD",
        eligibility_text="\n".join(filter(None, [types, eligibility, clean(facts.get("responseDateDesc"))])) or None,
        amount=Amount(kind="grant_range", minimum=money(facts.get("awardFloor")), maximum=money(facts.get("awardCeiling")),
                      currency="USD", source_label="awardFloor / awardCeiling", source_url=url),
        documents=list({d.url: d for d in docs}.values()))


def normalise_german(raw, prior=None):
    from .german_notices import normalise_german_notice
    return normalise_german_notice(raw, prior)


def normalise_nyc(raw):
    from .nyc_city_record import normalise_nyc_city_record
    return normalise_nyc_city_record(raw)


def normalise_ramp(raw):
    from .la_ramp import normalise_la_ramp
    return normalise_la_ramp(raw)


def normalise_spain(raw):
    from .spain_notices import normalise_spain_notice
    return normalise_spain_notice(raw)


def normalise_sam(raw):
    from .sam_opportunities import normalise_sam_opportunity
    return normalise_sam_opportunity(raw)


def normalise_canada(raw):
    from .canada_buys import normalise_canada_buys
    return normalise_canada_buys(raw)


NORMALISERS = {"ocds": normalise_ocds, "govuk": normalise_govuk, "html": normalise_html, "ted": normalise_ted,
               "usaspending": normalise_usaspending, "grants": normalise_grants,
               "german_ocds": normalise_german, "nyc_city_record": normalise_nyc, "spain_placsp": normalise_spain,
               "la_ramp": normalise_ramp, "sam_csv": normalise_sam, "canada_buys": normalise_canada}
