"""Official keyless CanadaBuys federal CSVs, with bounded resumable revisions.

The source dictionary specifies fixed UTC-05:00 closing times, including summer.
English/French are parallel publisher fields, never two independent notices.
Source: https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/ac-cb/soutien-support-eng.html
"""
import copy
import csv
import io
import re
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .utils import clean, digest, parse_date

BASE = "https://canadabuys.canada.ca/opendata/pub/"
VERSION = "canadabuys-federal-v2"
REFERENCE = "referenceNumber-numeroReference"
SOLICITATION = "solicitationNumber-numeroSollicitation"
CONTRACT = "contractNumber-numeroContrat"
CLOSING = "tenderClosingDate-appelOffresDateCloture"
PUBLISHED = "publicationDate-datePublication"
AMENDED = "amendmentDate-dateModification"
REQUIRED = {REFERENCE, SOLICITATION, PUBLISHED, "title-titre-eng", "title-titre-fra"}


def feeds(now):
    year = now.year if now.month >= 4 else now.year - 1
    fiscal = f"{year}-{year + 1}"
    return [("new", "newTenderNotice-nouvelAvisAppelOffres.csv", "tender", 2),
            ("open", "openTenderNotice-ouvertAvisAppelOffres.csv", "tender", 24),
            (fiscal + "-tenders", fiscal + "-TenderNotice-AvisAppelOffres.csv", "tender", 24),
            (fiscal + "-awards", fiscal + "-awardNotice-avisAttribution.csv", "award", 24)]


def row_id(row, kind):
    return f"{kind}:{row[REFERENCE]}" + (":" + row.get(CONTRACT, "") if kind == "award" else "")


def parse_snapshot(content, kind, minimum=0):
    required = REQUIRED | {"awardStatus-attributionStatut-eng" if kind == "award" else "tenderStatus-appelOffresStatut-eng"}
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        if not reader.fieldnames or not required.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise SourceUnavailable("CanadaBuys omitted required CSV fields")
        latest = {}
        for row in reader:
            if (None in row or any(value is None for value in row.values()) or
                    not re.fullmatch(r"[A-Za-z0-9_.(): /-]{1,180}", row[REFERENCE]) or
                    not (row["title-titre-eng"].strip() or row["title-titre-fra"].strip()) or
                    not parse_date(row[PUBLISHED])):
                raise SourceUnavailable("CanadaBuys contains a malformed notice")
            status = row["awardStatus-attributionStatut-eng" if kind == "award" else "tenderStatus-appelOffresStatut-eng"].strip().lower()
            if status not in ({"active", "expired", "cancelled"} if kind == "award" else {"open", "expired", "cancelled"}):
                raise SourceUnavailable("CanadaBuys published an unknown notice status")
            if row.get(CLOSING) and not parse_date(row[CLOSING]):
                raise SourceUnavailable("CanadaBuys published an invalid response deadline")
            ident = row_id(row, kind)
            revised = parse_date(row.get(AMENDED) or row[PUBLISHED])
            if revised is None:
                raise SourceUnavailable("CanadaBuys published an invalid amendment date")
            # Number 10 supersedes 9 even when the publisher omits zero padding.
            number = row.get("amendmentNumber-numeroModification", "").strip()
            revision = (revised, int(number) if number.isdigit() else -1, number)
            previous = latest.get(ident)
            if previous is None or revision > previous[0]:
                latest[ident] = (revision, row)
            elif revision == previous[0] and row != previous[1]:
                raise SourceUnavailable("CanadaBuys published conflicting notice revisions")
            if len(latest) > 100_000:
                raise SourceUnavailable("CanadaBuys exceeded its bounded notice count")
        if len(latest) < minimum:
            raise SourceUnavailable("CanadaBuys snapshot is unexpectedly small")
        return {ident: row for ident, (_, row) in latest.items()}
    except (csv.Error, UnicodeError):
        raise SourceUnavailable("CanadaBuys CSV could not be decoded completely") from None


def collect_canada_buys(source, state, frozen, http, settings, terms):
    result = Collection(state=copy.deepcopy(state))
    prior = state if state.get("query_version") == VERSION else {}
    snapshots = copy.deepcopy(prior.get("feeds", {}))
    limit = max(1, min(int(source.get("max_records_per_feed", 1000)), 3000))
    budget = max(0, int(settings.get("max_pages", 0)))
    try:
        for name, filename, kind, hours in feeds(frozen):
            previous = snapshots.get(name, {})
            checked = parse_date(previous.get("checked_at"))
            if checked and not previous.get("pending") and not settings.get("refresh_daily") and timedelta(0) <= frozen - checked < timedelta(hours=hours):
                continue
            if result.pages + 2 > budget:
                result.complete = False
                result.message = "CanadaBuys snapshots resume on the next collection."
                break
            url = BASE + filename
            result.pages += 1
            head = http.request("HEAD", url, follow_redirects=False)
            etag = head.headers.get("ETag", "")
            size = int(head.headers.get("Content-Length", "0"))
            modified = parsedate_to_datetime(head.headers.get("Last-Modified", ""))
            if not etag or not 0 < size <= 40_000_000 or modified > frozen + timedelta(hours=1) or modified < frozen - timedelta(days=7):
                raise SourceUnavailable("CanadaBuys snapshot metadata needs review")
            if previous.get("etag") == etag and not previous.get("pending"):
                snapshots[name] = {**previous, "checked_at": frozen.isoformat()}
                continue
            result.pages += 1
            response = http.request("GET", url, headers={"If-Match": etag, "Accept-Encoding": "identity"}, follow_redirects=False)
            if response.headers.get("ETag") != etag or len(response.content) != size:
                raise SourceUnavailable("CanadaBuys changed during download; previous snapshot retained")
            minimum = max(int(source.get("minimum_open_rows", 100)) if name == "open" else 0,
                          int(previous.get("rows", 0) * 0.75) if name != "new" else 0)
            rows = parse_snapshot(response.content, kind, minimum)
            old_hashes = previous.get("hashes", {})
            hashes = {ident: digest(row) for ident, row in rows.items()}
            changed = [ident for ident in rows if old_hashes.get(ident) != hashes[ident]]
            changed.sort(key=lambda ident: (rows[ident].get(AMENDED) or rows[ident][PUBLISHED], ident), reverse=True)
            emitted = changed[:limit]
            accepted = {ident: value for ident, value in old_hashes.items() if ident in rows}
            accepted.update({ident: hashes[ident] for ident in emitted})
            for ident in emitted:
                result.records.append(RawRecord({**rows[ident], "id": ident, "_kind": kind}, source, frozen.isoformat(), "canada_buys"))
            entry = {"etag": etag, "checked_at": frozen.isoformat(), "rows": len(rows), "hashes": accepted, "pending": len(changed) - len(emitted)}
            if name == "open":
                missing = previous.get("missing", {})
                gone = (old_hashes.keys() | missing.keys()) - hashes.keys()
                entry["removed"] = sorted(ident for ident in gone if missing.get(ident) and missing[ident] != etag)
                entry["missing"] = {ident: missing.get(ident) or etag for ident in gone}
            snapshots[name] = entry
            if entry["pending"]:
                result.complete = False
                result.message = "CanadaBuys verified snapshots have a resumable notice backlog."
        # Checkpoints acknowledge only emitted notices, and are committed only after
        # the common normalizer accepts every row in this collection.
        result.state.update(query_version=VERSION, feeds=snapshots)
    except (SourceUnavailable, ValueError, TypeError) as exc:
        result.records = []
        result.state = copy.deepcopy(state)
        defer_collection(result, exc if isinstance(exc, SourceUnavailable) else SourceUnavailable("CanadaBuys snapshot could not be verified"))
    return result


def normalise_canada_buys(raw):
    from .models import Amount, Document
    from .normalise import base, money
    from .public_context import deadline_fact, deadline_value

    row = raw.data
    kind = row["_kind"]
    description_key = "awardDescription-descriptionAttribution" if kind == "award" else "tenderDescription-descriptionAppelOffres"
    language = "eng" if row.get("title-titre-eng", "").strip() and (row.get(description_key + "-eng", "").strip() or not row.get(description_key + "-fra", "").strip()) else "fra"
    title = row.get("title-titre-" + language) or row["title-titre-eng"] or row["title-titre-fra"]
    description = row.get(description_key + "-" + language) or row.get(description_key + "-eng") or row.get(description_key + "-fra", "")
    buyer = clean(row.get("contractingEntityName-nomEntitContractante-eng") or row.get("contractingEntityName-nomEntitContractante-" + language)) or None
    ref = row[REFERENCE]
    url = f"https://canadabuys.canada.ca/en/tender-opportunities/{'award' if kind == 'award' else 'tender'}-notice/{quote(ref.lower(), safe='')}"
    status = row["awardStatus-attributionStatut-eng" if kind == "award" else "tenderStatus-appelOffresStatut-eng"].lower().strip()
    notice = row.get("noticeType-avisType-eng", "")
    stage, signal_type = ("award", "AWARD") if kind == "award" else ("tender", "LIVE_TENDER")
    if kind != "award":
        if notice == "Request for Information":
            stage, signal_type = "planning", "RFI"
        elif notice == "Advance Contract Award Notice":
            stage, signal_type = "planning", "EARLY_MARKET_ENGAGEMENT"
        elif notice in {"Request for Supply Arrangement", "Request for Standing Offer"}:
            signal_type = "FRAMEWORK"
        elif "Proposal" in notice or notice == "RFP against Supply Arrangement":
            signal_type = "RFP"
        elif notice == "Directed Contract":
            status = "complete"
    deadline = row.get(CLOSING, "") if kind != "award" else ""
    if deadline and re.search(r"[T ]\d{2}:\d{2}", deadline) and not re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", deadline):
        deadline += "-05:00"
    fact = deadline_fact(deadline, url, "tender" if stage == "tender" else "expression_of_interest") if deadline else None
    if fact:
        fact.source_text = row[CLOSING]
    value = money(row.get("contractAmount-montantContrat")) if kind == "award" else None
    currency = (row.get("contractCurrency-contratMonnaie") or "CAD").strip() if kind == "award" else None
    supplier = clean(row.get("supplierLegalName-nomLegalFournisseur-" + language)) or None
    docs = []
    notice_url = row.get("noticeURL-URLavis-" + language) or row.get("noticeURL-URLavis-eng", "")
    if notice_url.startswith("https://") and notice_url != url:
        docs.append(Document(title="Published award link" if kind == "award" else "Published tender link", url=notice_url, kind="notice"))
    for attachment in re.split(r"[,\n]", row.get("attachment-piecesJointes-" + language, "")):
        if attachment.strip().startswith("https://"):
            docs.append(Document(title="Tender document", url=attachment.strip(), kind="tenderDocument"))
    eligibility = "\n".join(filter(None, [notice, row.get("procurementMethod-methodeApprovisionnement-" + language), row.get("limitedTenderingReason-raisonAppelOffresLimite-" + language), row.get("tradeAgreements-accordsCommerciaux-" + language)]))
    signal = base(raw, title=title, description=description, description_limit=None, url=url,
        ocid="canadabuys:" + row_id(row, kind), countries=["CA"], buyer_name=buyer,
        procedure_identifiers=["canadabuys-procedure:" + digest([buyer, row[SOLICITATION]])] if row[SOLICITATION] and buyer else [],
        external_ids=["canadabuys:" + row_id(row, kind)],
        source_language="en" if language == "eng" else "fr", signal_type=signal_type, procurement_stage=stage,
        notice_type=notice or None, status={"open": "active", "active": "awarded"}.get(status, status),
        published_at=row[PUBLISHED], updated_at=row.get(AMENDED) or row[PUBLISHED],
        deadline_at=deadline_value(fact) if fact else None, deadlines=[fact] if fact else [],
        response_deadlines=[deadline_value(fact)] if fact else [], eligibility_text=eligibility or None,
        award_date=row.get("contractAwardDate-dateAttributionContrat") or None,
        award_statuses=["active"] if kind == "award" and status in {"active", "expired"} else [status] if kind == "award" else [],
        incumbent_supplier=supplier, currency=currency, value_min=value, value_max=value,
        amount=Amount(kind="award" if kind == "award" else "unknown", minimum=value, maximum=value, currency=currency,
                      source_label="Contract amount including taxes" if kind == "award" else "No tender value published", source_url=url),
        contract_start=row.get("contractStartDate-contratDateDebut") or row.get("expectedContractStartDate-dateDebutContratPrevue") or None,
        contract_end=row.get("contractEndDate-dateFinContrat") or row.get("expectedContractEndDate-dateFinContratPrevue") or None,
        regions=[v.strip().lstrip("*") for v in row.get("regionsOfDelivery-regionsLivraison-" + language, "").splitlines() if v.strip()],
        documents=docs)
    return signal


def removed_canada_records(previous_signals, state, retrieved_at):
    from .normalise import set_hashes
    removed = {"canadabuys:" + ident for ident in state.get("feeds", {}).get("open", {}).get("removed", [])}
    result = []
    for previous in previous_signals:
        if (previous.source != "canada_buys" or not removed.intersection(previous.external_ids) or
                previous.signal_type == "AWARD" or previous.status.lower() not in {"active", "open", ""}):
            continue
        signal = previous.model_copy(deep=True)
        signal.status = "not_listed"
        signal.last_seen_at = retrieved_at
        signal.updated_at = retrieved_at
        result.append(set_hashes(signal))
    return result
