from datetime import UTC, datetime, timedelta

from rapidfuzz.fuzz import ratio

from .models import Change, Signal
from .normalise import MATERIAL_FIELDS, material_payload, set_hashes
from .public_context import enrich_signal
from .utils import digest, normal_text, parse_date, unique


def exact_keys(s):
    suffix = f"|lot:{s.lot_id or ''}"
    return [key + suffix for key in unique([
        "ocid:" + s.ocid if s.ocid else None,
        *["ref:" + ref for ref in s.external_ids],
        *["url:" + url for url in s.source_urls]])]


def compatible_identifiers(left, right):
    if left.signal_type != "AWARD" and len(left.lot_ids) > 1 and right.signal_type == "AWARD":
        if not right.lot_id or set(right.lot_ids) != set(left.lot_ids):
            return False
    return left.lot_id == right.lot_id and not (
        left.source == right.source and left.ocid and right.ocid and left.ocid != right.ocid)


def is_fuzzy_duplicate(left, right):
    if left.lot_id != right.lot_id or left.related_signal_id or right.related_signal_id:
        return False
    if left.ocid and right.ocid and left.ocid != right.ocid and left.source == right.source:
        return False
    if not left.buyer_name or not right.buyer_name:
        return False
    if ratio(normal_text(left.buyer_name), normal_text(right.buyer_name)) < 95:
        return False
    if ratio(normal_text(left.title), normal_text(right.title)) < 94:
        return False
    if left.lot_ids and right.lot_ids and set(left.lot_ids) != set(right.lot_ids):
        return False
    # A fuzzy title alone is insufficient: require an independent procurement anchor.
    if left.deadline_at and right.deadline_at:
        if abs((parse_date(left.deadline_at) - parse_date(right.deadline_at)).total_seconds()) > 86400:
            return False
        date_anchor = True
    else:
        date_anchor = False
    if left.value_max is not None and right.value_max is not None:
        if left.currency != right.currency or abs(left.value_max - right.value_max) > max(1, left.value_max * .02):
            return False
        value_anchor = True
    else:
        value_anchor = False
    pub1, pub2 = parse_date(left.published_at), parse_date(right.published_at)
    if pub1 and pub2 and abs(pub1 - pub2) > timedelta(days=45):
        return False
    return date_anchor and value_anchor


def merge_provenance(previous, incoming):
    """Keep distinct source versions even when a publisher reuses its release ID."""
    def observed_at(item):
        return parse_date(item.retrieved_at) or datetime.min.replace(tzinfo=UTC)

    versions = {}
    for item in previous + incoming:
        key = (item.source, item.release_id, item.url, item.raw_hash)
        existing = versions.get(key)
        if existing is None or observed_at(item) > observed_at(existing):
            versions[key] = item
    return sorted(versions.values(), key=observed_at)[-60:]


def merge(old, incoming):
    old_payload = material_payload(old)
    merged = old.model_copy(deep=True)
    older = (parse_date(incoming.updated_at) or parse_date(incoming.first_seen_at)) < (
        parse_date(old.updated_at) or parse_date(old.first_seen_at))
    if not older:
        # Retained releases from the older schema carry only scalar prices.
        # Apply the normal evidence policy to that release before merging, so
        # new numbers never inherit an earlier amount's type, units or source.
        incoming_amount = incoming.amount
        if incoming_amount is None:
            incoming_values = (incoming.value_min, incoming.value_max, incoming.currency)
            proved_values = (old.amount.minimum, old.amount.maximum, old.amount.currency) if old.amount else None
            incoming_amount = (old.amount if incoming_values == proved_values else
                               enrich_signal(incoming.model_copy(deep=True)).amount)
        for field in MATERIAL_FIELDS + ["updated_at", "buyer_identifiers", "countries", "regions", "notice_type"]:
            if field in {"amount", "value_min", "value_max", "currency"}:
                continue
            value = getattr(incoming, field)
            if value not in (None, "", [], "unknown"):
                setattr(merged, field, value)
        if incoming_amount is not None and (incoming_amount.minimum is not None or incoming_amount.maximum is not None):
            # A sparse revision has no new financial fact. When a value is
            # published, replace its bounds, currency and provenance together;
            # retaining an old upper bound/currency would invent a mixed range.
            merged.amount = incoming_amount.model_copy(deep=True)
            merged.value_min, merged.value_max = incoming_amount.minimum, incoming_amount.maximum
            merged.currency = incoming_amount.currency
        # NYC sometimes retains a placeholder date after explicitly postponing bids.
        if incoming.source == "nyc_city_record" and incoming.status == "postponed" and incoming.deadline_at is None:
            merged.deadline_at = None
        if old.source == incoming.source == "sam":
            # SAM's full snapshot may remove a date or restore a previously
            # unlisted notice. Unknown bid status must not inherit a closed one.
            merged.status = incoming.status
            merged.deadline_at = incoming.deadline_at
            merged.response_deadlines = incoming.response_deadlines
            if not incoming.deadlines:
                merged.deadlines = []
        merged.raw_source_hash = incoming.raw_source_hash
        if incoming.deadlines and old.deadlines:
            current = {(d.kind, d.lot_id, d.source_text) for d in incoming.deadlines}
            superseded = [d.model_copy(update={"status": "superseded"}) for d in old.deadlines
                          if (d.kind, d.lot_id, d.source_text) not in current]
            merged.deadlines = incoming.deadlines + superseded[-20:]
        # Prefer current official notice facts over derivative publications.
        if incoming.source_type == "official_notice" or old.source_type != "official_notice":
            merged.source, merged.source_type = incoming.source, incoming.source_type
            merged.primary_source_url = incoming.primary_source_url
    merged.ocid = old.ocid or incoming.ocid
    merged.external_ids = unique(old.external_ids + incoming.external_ids)
    merged.source_urls = unique(old.source_urls + incoming.source_urls)
    merged.first_seen_at = min(old.first_seen_at, incoming.first_seen_at)
    merged.last_seen_at = max(old.last_seen_at, incoming.last_seen_at)
    if incoming.published_at:
        merged.published_at = min(filter(None, [old.published_at, incoming.published_at]))
    merged.documents = list({d.url: d for d in old.documents + incoming.documents}.values())[-40:]
    merged.provenance = merge_provenance(old.provenance, incoming.provenance)
    set_hashes(merged)
    changed = [k for k in old_payload if old_payload[k] != material_payload(merged)[k]]
    if changed:
        merged.last_material_update = incoming.last_seen_at
        merged.changes = (old.changes + [Change(at=incoming.last_seen_at, kind="updated", fields=changed,
                                               source_url=incoming.primary_source_url)])[-30:]
        merged.analysis = None
        merged.fit_score = None
        merged.ai_status = "pending"
        merged.analysis_cache_key = None
        merged.ai_scored_at = None
    return merged, bool(changed)


def reconcile(previous: list[Signal], incoming: list[Signal]):
    records = {s.id: s.model_copy(deep=True) for s in previous if not s.related_signal_id}
    # Re-evaluate derived lot outcomes every run, including award cancellations.
    # Keep source statuses separate so withdrawing an award never invents a new
    # source status or leaves a previously inferred whole-process closure behind.
    for record in records.values():
        baseline = record.lot_award_baseline
        record.status = baseline.get("status", record.status)
        for lot in record.lots:
            lot.status = baseline.get("lot:" + lot.id, lot.status)
        record.lot_award_baseline = {}
    index = {key: s.id for s in records.values() for key in exact_keys(s)}
    buyer_index = {}
    for s in records.values():
        buyer_index.setdefault(normal_text(s.buyer_name), set()).add(s.id)
    stats = {"new_signals": 0, "material_updates": 0, "duplicates_merged": 0}
    for signal in sorted(incoming, key=lambda s: s.updated_at or s.first_seen_at):
        match_id = next((index[k] for k in exact_keys(signal) if k in index
                         and compatible_identifiers(records[index[k]], signal)), None)
        # Similar names, amounts and closing days do not establish legal identity.
        if match_id:
            merged, changed = merge(records[match_id], signal)
            records[match_id] = merged
            stats["material_updates"] += int(changed)
            stats["duplicates_merged"] += 1
            signal = merged
        else:
            if signal.id in records:
                # Source IDs sometimes identify a whole OCDS process. A partial
                # result cannot overwrite that process merely by reusing its ID.
                release = signal.provenance[-1].release_id if signal.provenance else signal.raw_source_hash
                signal = signal.model_copy(update={"id": "sig_" + digest([signal.id, signal.source, release])[:20]})
            records[signal.id] = signal
            signal.changes = [Change(at=signal.first_seen_at, kind="discovered", fields=[], source_url=signal.primary_source_url)]
            stats["new_signals"] += 1
        for key in exact_keys(signal):
            index[key] = signal.id
        buyer_index.setdefault(normal_text(signal.buyer_name), set()).add(signal.id)
    by_procedure = {}
    for signal in records.values():
        if signal.ocid:
            by_procedure.setdefault(signal.ocid, []).append(signal)
    for family in by_procedure.values():
        for award in (s for s in family if s.signal_type == "AWARD"
                      and s.status.lower() not in {"cancelled", "canceled", "withdrawn", "unsuccessful"}
                      and (not s.award_statuses or "active" in s.award_statuses)):
            awarded = {str(lot) for winner in award.winners for lot in winner.get("lot_ids", [])}
            for original in (s for s in family if s.signal_type != "AWARD"):
                for lot in original.lots:
                    if lot.id in awarded and lot.status != "awarded":
                        original.lot_award_baseline["lot:" + lot.id] = lot.status
                        lot.status = "awarded"
                if original.lots and all(lot.status == "awarded" for lot in original.lots):
                    original.lot_award_baseline.setdefault("status", original.status)
                    original.status = "complete"
    return list(records.values()), index, stats
