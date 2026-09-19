"""Anonymous SAM.gov public opportunity extract; no API key or browser scraping."""
import codecs
import csv
import io
import re
import tempfile
import time
from datetime import timedelta
from email.utils import parsedate_to_datetime

import httpx

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .models import Amount, Document
from .normalise import base, money, set_hashes
from .public_context import deadline_fact, deadline_value
from .utils import clean, digest, parse_date

EXTRACT_URL = "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv"
VERSION = "sam-public-csv-v1"
FIELDS = (
    "NoticeId", "Title", "Sol#", "Department/Ind.Agency", "CGAC", "Sub-Tier", "FPDS Code", "Office",
    "AAC Code", "PostedDate", "Type", "BaseType", "ArchiveDate", "SetASideCode", "SetASide",
    "ResponseDeadLine", "NaicsCode", "ClassificationCode", "PopCity", "PopState", "PopCountry",
    "Active", "AwardNumber", "AwardDate", "Award$", "Awardee", "Description",
)
REQUIRED = {"NoticeId", "Title", "PostedDate", "Type", "BaseType", "Active", "Description", "ResponseDeadLine"}


def _snapshot_metadata(response, frozen, maximum):
    if response.status_code != 200:
        raise SourceUnavailable("SAM public extract metadata is unavailable")
    try:
        size = int(response.headers["Content-Length"])
        modified = parsedate_to_datetime(response.headers["Last-Modified"])
        etag = response.headers["ETag"]
        if not etag.startswith('"') or not etag.endswith('"') or not 0 < size <= maximum:
            raise ValueError
        if not timedelta(minutes=-10) <= frozen - modified <= timedelta(days=3):
            raise ValueError
    except (KeyError, ValueError, TypeError):
        raise SourceUnavailable("SAM public extract is stale or its snapshot metadata is invalid") from None
    return size, etag, modified.isoformat()


def _download(http, target, size, etag, maximum):
    # A streaming download keeps the large official file off the heap and out of
    # the repository. If-Match prevents a midnight replacement mixing revisions.
    http.sleeper(max(0, 0.2 - (time.monotonic() - http.last_request)))
    http.last_request = time.monotonic()
    try:
        with http.client.stream("GET", EXTRACT_URL, follow_redirects=False,
                headers={"If-Match": etag, "Accept-Encoding": "identity", "Accept": "text/csv"}) as response:
            if response.status_code != 200 or response.headers.get("ETag") != etag:
                raise SourceUnavailable("SAM public extract changed or is unavailable; previous records retained",
                                        status_code=response.status_code)
            if int(response.headers.get("Content-Length", "0")) != size or response.headers.get("Content-Encoding", "identity") != "identity":
                raise SourceUnavailable("SAM public extract download did not match the verified snapshot")
            received = 0
            for chunk in response.iter_bytes():
                received += len(chunk)
                if received > min(size, maximum):
                    raise SourceUnavailable("SAM public extract exceeded its verified size")
                target.write(chunk)
            if received != size:
                raise SourceUnavailable("SAM public extract download was incomplete")
    except (httpx.HTTPError, ValueError):
        raise SourceUnavailable("SAM public extract download failed; previous records retained") from None
    target.seek(0)


def _encoding(stream):
    # The verified September 2026 extract uses Windows-1252. Accept a future
    # UTF-8 export too, without lossy replacement or mojibake in valid UTF-8.
    for encoding in ("utf-8-sig", "cp1252"):
        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        stream.seek(0)
        try:
            while block := stream.read(1024 * 1024):
                decoder.decode(block)
            decoder.decode(b"", final=True)
            stream.seek(0)
            return encoding
        except UnicodeDecodeError:
            continue
    raise SourceUnavailable("SAM public extract text encoding changed; previous records retained")


def parse_snapshot(stream, source, previous, retrieved_at, previous_rows=0):
    """Validate the complete CSV before emitting changed rows; no keyword/NAICS gate."""
    encoding = _encoding(stream)
    text = io.TextIOWrapper(stream, encoding=encoding, newline="")
    hashes, changed, pending = {}, [], 0
    limit = max(1, min(int(source.get("max_records_per_run", 3000)), 10000))
    try:
        reader = csv.DictReader(text, strict=True)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise SourceUnavailable("SAM public extract omitted required columns")
        for row in reader:
            ident = row.get("NoticeId", "")
            if (None in row or any(value is None for value in row.values()) or not re.fullmatch(r"[a-fA-F0-9]{32}", ident)
                    or ident.lower() in hashes or not row["Title"].strip() or not parse_date(row["PostedDate"])
                    or row["Active"].strip().casefold() not in ("yes", "no") or not row["Type"].strip()):
                raise SourceUnavailable("SAM public extract contains malformed or duplicate notices")
            facts = {key: row.get(key, "") for key in FIELDS}
            ident = facts["NoticeId"] = ident.lower()
            facts["id"] = ident
            hashes[ident] = digest(facts)
            if previous.get(ident) != hashes[ident]:
                if len(changed) < limit:
                    changed.append(RawRecord(facts, source, retrieved_at, "sam_csv"))
                else:
                    pending += 1
            if len(hashes) > int(source.get("max_rows", 250000)):
                raise SourceUnavailable("SAM public extract exceeded its notice limit")
        if len(hashes) < int(source.get("minimum_rows", 1000)):
            raise SourceUnavailable("SAM public extract is empty or unexpectedly small")
        if len(hashes) < max(previous_rows, len(previous)) * 0.75:
            raise SourceUnavailable("SAM public extract notice count fell unexpectedly; previous records retained")
        return hashes, changed, pending
    except (csv.Error, UnicodeError):
        raise SourceUnavailable("SAM public extract CSV could not be decoded completely") from None
    finally:
        text.detach()  # The temporary-file context owns the stream.


def collect_sam_opportunities(source, state, frozen, http, settings, terms):
    result = Collection(state=dict(state))
    previous = state if state.get("query_version") == VERSION else {}
    checked = parse_date(previous.get("watermark"))
    if not previous.get("pending_records") and not settings.get("refresh_daily") and checked and timedelta(0) <= frozen - checked < timedelta(hours=source.get("refresh_hours", 24)):
        return result
    if settings["max_pages"] < 2:
        return Collection(state=dict(state), complete=False, message="SAM public extract needs two requests to verify its snapshot.")
    if source.get("url", EXTRACT_URL) != EXTRACT_URL:
        return Collection(state=dict(state), complete=False, message="SAM public extract URL needs configuration review.")
    maximum = min(int(source.get("max_bytes", 512 * 1024 * 1024)), 512 * 1024 * 1024)
    try:
        result.pages += 1
        size, etag, modified = _snapshot_metadata(http.request("HEAD", EXTRACT_URL, follow_redirects=False), frozen, maximum)
        if previous.get("snapshot_etag") == etag and not previous.get("pending_records"):
            result.state.update(watermark=frozen.isoformat(), removed_ids=[])
            return result
        with tempfile.TemporaryFile() as target:
            result.pages += 1
            _download(http, target, size, etag, maximum)
            processed = previous.get("record_hashes", {})
            hashes, records, pending = parse_snapshot(target, source, processed, frozen.isoformat(), previous.get("snapshot_rows", 0))
        missing, removed = {}, []
        # Absence is not an award or cancellation. Only retire a retained open
        # notice after two independently revised, validated full snapshots.
        for ident in (previous.get("record_hashes", {}).keys() | previous.get("missing", {}).keys()) - hashes.keys():
            earlier = previous.get("missing", {}).get(ident)
            if earlier and earlier != etag:
                removed.append(ident)
            else:
                missing[ident] = earlier or etag
        result.records = records
        # Only acknowledge emitted rows. A bounded bootstrap continues on the next
        # collection even if the upstream ETag is unchanged; unprocessed scope is
        # never labelled irrelevant or silently checkpointed past.
        accepted = {ident: value for ident, value in processed.items() if ident in hashes}
        accepted.update({record.data["NoticeId"]: hashes[record.data["NoticeId"]] for record in records})
        result.complete = pending == 0
        if pending:
            result.message = f"Verified public snapshot; {pending:,} new or changed notices remain in the resumable backlog."
        result.state.update(query_version=VERSION, watermark=frozen.isoformat(), snapshot_etag=etag,
            snapshot_modified=modified, snapshot_bytes=size, snapshot_rows=len(hashes),
            record_hashes=accepted, pending_records=pending, missing=missing, removed_ids=sorted(removed))
    except SourceUnavailable as exc:
        result.records = []
        defer_collection(result, exc)
    return result


def removed_sam_records(previous_signals, state, retrieved_at):
    removed = set(state.get("removed_ids", []))
    result = []
    for signal in previous_signals:
        if signal.source != "sam" or signal.status == "not_listed" or signal.signal_type == "AWARD":
            continue
        if not any(alias.startswith("sam:") and alias[4:] in removed for alias in signal.external_ids):
            continue
        updated = signal.model_copy(deep=True)
        updated.status = "not_listed"
        updated.updated_at = updated.last_seen_at = updated.last_material_update = retrieved_at
        result.append(set_hashes(updated))
    return result


def normalise_sam_opportunity(raw):
    row = raw.data
    ident = row["NoticeId"]
    url = f"https://sam.gov/opp/{ident}/view"
    notice = clean(row.get("Type"))
    notice_type = notice.casefold()
    if notice_type == "modification/amendment/cancel":
        notice_type = clean(row.get("BaseType")).casefold()
    awarded = notice_type == "award notice"
    stage = "award" if awarded else "planning" if notice_type in ("sources sought", "presolicitation", "special notice", "consolidate/(substantially) bundle") else "tender"
    signal_type = ("AWARD" if awarded else "RFI" if notice_type == "sources sought" else
                   "PIPELINE" if notice_type == "presolicitation" else "STRATEGIC_INTENT" if stage == "planning" else "LIVE_TENDER")
    known = {"award notice", "sources sought", "presolicitation", "special notice", "consolidate/(substantially) bundle",
             "solicitation", "combined synopsis/solicitation", "justification", "justification and approval (j&a)", "sale of surplus property"}
    status = "awarded" if awarded else "unknown"  # Active in this extract means listed, not necessarily accepting bids.
    if notice_type in ("justification", "justification and approval (j&a)", "sale of surplus property") or row["Active"].casefold() == "no":
        status = "closed" if not awarded else "awarded"
    elif notice_type not in known:
        status = "unverified"
    published = row.get("PostedDate", "")[:10]  # PostedDate has no documented timezone in the extract.
    deadline = deadline_fact(row.get("ResponseDeadLine"), url, "expression_of_interest" if stage == "planning" else "tender") if not awarded else None
    awarded_amount = money(row.get("Award$", "").replace(",", "").replace("$", "").strip()) if awarded else None
    winner = clean(row.get("Awardee")) if awarded else ""
    office = clean(row.get("Office"))
    agency = clean(row.get("Department/Ind.Agency"))
    sub_tier = clean(row.get("Sub-Tier"))
    office_id = clean(row.get("AAC Code"))
    solicitation = clean(row.get("Sol#"))
    buyer_id = f"sam-office:{office_id}" if office_id else ""
    signal = base(raw, title=row["Title"], description=row.get("Description") or "", description_limit=131072, url=url,
        external_ids=["sam:" + ident], buyer_name=office or sub_tier or agency or None,
        buyer_identifiers=[buyer_id] if buyer_id else [], agency_name=agency or None, department_name=sub_tier or None,
        procedure_identifiers=[f"sam-solicitation:{office_id}:{solicitation}"] if office_id and solicitation else [],
        source_language="en", countries=["US"], regions=[value for value in (clean(row.get("PopCity")), clean(row.get("PopState"))) if value],
        categories=[f"NAICS {row['NaicsCode']}"] if row.get("NaicsCode") else [],
        notice_type=notice, signal_type=signal_type, procurement_stage=stage, status=status,
        published_at=published, updated_at=raw.retrieved_at, deadline_at=deadline_value(deadline) if deadline else None,
        deadlines=[deadline] if deadline else [], award_date=row.get("AwardDate")[:10] if awarded and parse_date(row.get("AwardDate")) else None,
        value_max=awarded_amount, currency="USD" if awarded_amount is not None else None,
        amount=Amount(kind="award", maximum=awarded_amount, currency="USD", source_label="Award$", source_url=url) if awarded_amount is not None else None,
        incumbent_supplier=winner or None,
        winners=[{"name": winner, "identifiers": [], "lot_ids": [], "source_url": url}] if winner else [],
        eligibility_text=("Set-aside: " + clean(row["SetASide"])) if row.get("SetASide") else None,
        documents=[Document(title="Official SAM.gov notice", url=url, kind="awardNotice" if awarded else "tenderNotice")])
    # On first discovery the catalogue may contain a very old notice. A current
    # download is not evidence that this buyer published fresh intent today.
    signal.last_material_update = published
    return signal
