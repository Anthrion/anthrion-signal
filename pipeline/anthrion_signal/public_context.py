"""Deterministic public facts, with provenance and deliberately unknown qualification.

This module neither scores company fit nor reads private company evidence. Names are
only grouped verbatim within a source; cross-source identities require identifiers.
"""
import re
from collections import defaultdict
from html import unescape

from .models import Amount, Deadline
from .utils import canonical_url, clean, digest, parse_date, unique

PUBLIC_EXCLUDE = {"analysis", "analysis_cache_key", "ai_status", "ai_model", "ai_scored_at", "fit_score",
                  "confidence_score", "known_weight", "score_components", "score_explanation", "recommendation",
                  "prefilter_score", "scope_evidence", "lot_award_baseline"}
DELIVERY = re.compile(r"\b(?:implement\w*|develop\w*|deliver\w*|build\w*|integrat\w*|migrat\w*|"
                      r"configur\w*|maintain\w*|replace\w*|upgrade\w*|procure\w*|supply|support|"
                      r"mise en [œo]euvre|maintenance|ontwikkel\w*|implementatie|toteut\w*|hank\w*|"
                      r"einführ\w*|entwicklung|implementierung|realizz\w*)\b", re.I)
EXISTING = re.compile(r"\b(?:existing|currently uses?|already uses?|current system|installed|was developed)\b", re.I)
REQUIRED_DELIVERY = re.compile(r"\b(?:must|shall|requires?|required to|seeks?|will implement|will develop|"
                               r"will replace|to be implemented|to be developed|procure\w*)\b|"
                               r"(?:^|[.;:]\s+)(?:implement|develop|integrate|replace|upgrade|maintain)\b", re.I)
PREREQUISITE = re.compile(r"\b(?:must|shall|required|mandatory|eligible|eligibility|membership|certification|"
                         r"minimum (?:turnover|insurance|experience)|consorti\w*|subcontract\w*|"
                         r"muss|müssen|erforderlich|zwingend|mindestens|nachweis|doit|doivent|obligatoire|exig[ée]\w*|"
                         r"moet|moeten|verplicht|minimaal|vereist)\b", re.I)
QUALIFICATION = re.compile(r"framework|certific|turnover|insurance|qualifying references?|relevant references?|"
                           r"consorti|subcontract|eligible|eligibility|membership|licen[sc]e|security clearance|domestic|"
                           r"citizenship|registered|mitglieder|mitgliedschaft|zertifiz|umsatz|versicherung|referenzen|"
                           r"rahmenvertrag|zulassung|chiffre d.affaires|assurance|références|agrément|licence|"
                           r"lidmaatschap|omzet|verzekering|referenties|raamovereenkomst|vergunning", re.I)
WAIVED = re.compile(r"\b(?:not required|not mandatory|need not|no requirement|nicht erforderlich|nicht notwendig|"
                    r"pas obligatoire|niet verplicht|niet vereist)\b", re.I)


def deadline_fact(value, source_url, kind="unknown", *, timezone=None, lot_id=None):
    """Preserve source-local precision; an offset on a date is not a clock time."""
    if not isinstance(value, str) or not parse_date(value):
        return None
    day = re.match(r"\d{4}-\d{2}-\d{2}", value)
    if not day:
        return None
    clock = re.search(r"[T ](\d{2}:\d{2}(?::\d{2})?)", value)
    offset = re.search(r"(Z|[+-]\d{2}:\d{2})$", value) if clock else None
    return Deadline(kind=kind, date=day[0], time=clock[1] if clock else None,
        timezone=timezone or ("UTC" if offset and offset[1] == "Z" else offset[1] if offset else None),
        precision="instant" if clock and offset else "local_time" if clock else "date",
        instant=parse_date(value).isoformat(timespec="seconds") if clock and offset else None,
        source_text=value, source_url=source_url, lot_id=lot_id)


def deadline_value(fact):
    return fact.instant or (fact.date + "T" + fact.time if fact.time else fact.date)


def buyer_identity(signal):
    if signal.buyer_id and signal.buyer_identity_basis == "identifier":
        return signal.buyer_id, "identifier"
    if signal.buyer_identifiers:
        identifier = signal.buyer_identifiers[0]
        # OCDS party IDs and unschemed national IDs are local to their source.
        registry = bool(re.match(r"(?:[A-Z]{2}-[A-Z0-9]+|grants-agency):", identifier))
        anchor = identifier if registry else [signal.source, sorted(signal.countries), identifier]
        return "buyer_" + digest(anchor)[:20], "identifier"
    if signal.buyer_name:
        # Exact spelling after whitespace/case normalization, never fuzzy names.
        return "buyer_" + digest([signal.source, sorted(signal.countries), clean(signal.buyer_name).casefold()])[:20], "source_name"
    return None, "unknown"


def procedure_identity(signal):
    if signal.procedure_id:
        return signal.procedure_id
    identifiers = signal.procedure_identifiers or (["ocid:" + signal.ocid] if signal.ocid else [])
    return "proc_" + digest(identifiers[:1] or [signal.id])[:20]


def enrich_signal(signal):
    signal.buyer_id, signal.buyer_identity_basis = buyer_identity(signal)
    signal.procedure_id = procedure_identity(signal)
    if signal.amount is None:
        kind = ("grant_range" if signal.source == "grants" else "unknown" if signal.signal_type == "AWARD"
                else "estimated_contract" if signal.source in {"ted", "find_tender", "contracts_finder", "scotland", "wales", "germany", "spain"}
                else "unknown")
        labels = {"grant_range": "Published grant award floor / ceiling", "award": "Published award value",
                  "framework_ceiling": "Published framework value", "estimated_contract": "Estimated contract value",
                  "unknown": "Published amount; meaning not established"}
        signal.amount = Amount(kind=kind, minimum=signal.value_min, maximum=signal.value_max,
            currency=signal.currency, source_label=labels[kind], source_url=signal.primary_source_url)
    elif signal.amount.minimum is None and signal.amount.maximum is None and (signal.value_min is not None or signal.value_max is not None):
        # Older sparse merges could retain a number but replace its type/source
        # metadata with an empty revision. That revision cannot prove meaning.
        signal.amount = Amount(kind="unknown", minimum=signal.value_min, maximum=signal.value_max,
            currency=signal.currency, source_label="Retained published amount; meaning not established",
            source_url=signal.primary_source_url)
    if not signal.deadlines:
        kind = "application" if signal.signal_type == "FUNDING" else "unknown"
        signal.deadlines = [fact for value in unique(signal.response_deadlines + [signal.deadline_at])
                            if (fact := deadline_fact(value, signal.primary_source_url, kind))]
    if not signal.winners and signal.incumbent_supplier:
        # A combined source label is never split into invented separate suppliers.
        signal.winners = [{"name": signal.incumbent_supplier, "identifiers": [], "lot_ids": [],
                           "source_url": signal.primary_source_url}]
    return signal


def public_capability_evidence(signal, translation=None):
    result = []
    translated = translation.model_dump() if hasattr(translation, "model_dump") else translation or {}
    valid_translation = translated.get("source_hash") == digest([signal.title, signal.description])
    for evidence in signal.capability_evidence:
        field = evidence.get("field", "")
        if field not in ("title", "description") or evidence.get("capability") not in signal.matched_capabilities:
            continue
        quote = evidence.get("quote", "")
        original = getattr(signal, field)
        english = evidence.get("basis") == "english_translation"
        reference = translated.get(field, "") if english and valid_translation else original if not english else ""
        if not quote or clean(unescape(quote), limit=None) not in clean(unescape(reference), limit=None):
            continue
        context = ("existing_system" if EXISTING.search(quote) and not REQUIRED_DELIVERY.search(quote)
                   else "delivery" if DELIVERY.search(quote) else "uncertain")
        item = {key: evidence.get(key, "") for key in ("capability", "phrase", "strength", "basis", "field", "quote")}
        item.update(source_url=signal.primary_source_url, language="en" if english else signal.source_language,
                    context=context, source_hash=digest([signal.title, signal.description]))
        if english:
            # Translation matching is field-level, not a claimed sentence alignment.
            item.update(original_quote=original, translated_quote=quote, original_language=signal.source_language,
                        original_field=field)
        else:
            item["original_quote"] = quote
        result.append(item)
    return result


def participation_requirements(signal, translation=None):
    requirements = []
    eligibility = signal.eligibility_text or ""
    eligibility = re.sub(r"Multiple lot deadlines are published\. The (?:next remaining date|earliest) is shown; check the source notice for the relevant lot\.", "", eligibility).strip()
    if signal.source == "la_ramp" and eligibility.startswith("Task-order solicitation under an existing contract;"):
        eligibility = ""
    passages = [eligibility] if eligibility else []
    def candidates(text):
        return [part for part in re.split(r"(?<=[.!?;])\s+|\n+", text)
                if PREREQUISITE.search(part) and QUALIFICATION.search(part) and not WAIVED.search(part)]
    passages += candidates(signal.description)
    for passage in unique(passages)[:12]:
        requirements.append({"id": "req_" + digest([signal.id, passage])[:16], "requirement": passage,
            "status": "needs_checking", "source_quote": passage, "source_url": signal.primary_source_url,
            "company_evidence": None})
    translated = translation.model_dump() if hasattr(translation, "model_dump") else translation or {}
    if not requirements and translated.get("source_hash") == digest([signal.title, signal.description]):
        for passage in unique(candidates(translated.get("description", "")))[:6]:
            requirements.append({"id": "req_" + digest([signal.id, passage])[:16], "requirement": passage,
                "status": "needs_checking", "source_quote": signal.description, "translated_quote": passage,
                "source_hash": translated["source_hash"], "source_url": signal.primary_source_url,
                "company_evidence": None})
    return requirements


def public_signal(signal, translation=None):
    enrich_signal(signal)
    result = signal.model_dump(exclude=PUBLIC_EXCLUDE | ({"buyer_history"} if signal.buyer_history_ref else set()))
    if signal.buyer_history_ref:
        result["buyer_history"] = []
    evidence = public_capability_evidence(signal, translation)
    result["capability_evidence"] = evidence
    # Every displayed label has a traceable source/translation passage.
    result["matched_capabilities"] = [c for c in signal.matched_capabilities if any(e["capability"] == c for e in evidence)]
    delivery = [e for e in evidence if e["context"] == "delivery"]
    component = [e for e in delivery if re.search(r"\b(?:lot|component|basket)\s*\d", e["quote"], re.I)]
    role = ("funded_project" if signal.signal_type == "FUNDING" else "advertised_component" if component
            else "direct_supplier" if delivery and signal.procurement_stage == "tender" else "unknown")
    result["delivery_role"] = {"kind": role, "evidence": (component or delivery)[:4]}
    result["participation_requirements"] = participation_requirements(signal, translation)
    if not signal.reviewed_guidance:
        result.pop("reviewed_guidance", None)
    return result


def history_entry(signal):
    return {"signal_id": signal.id, "procedure_id": signal.procedure_id, "title": signal.title,
        "source": signal.source, "countries": signal.countries,
        "buyer_name": signal.buyer_name, "buyer_id": signal.buyer_id,
        "signal_type": signal.signal_type, "notice_type": signal.notice_type, "published_at": signal.published_at,
        "award_date": signal.award_date, "award_statuses": signal.award_statuses,
        "supplier": signal.incumbent_supplier, "status": signal.status,
        "source_url": signal.primary_source_url, "lot_ids": signal.lot_ids or ([signal.lot_id] if signal.lot_id else []),
        "amount": signal.amount.model_dump() if signal.amount else None, "contract_start": signal.contract_start,
        "contract_end": signal.contract_end, "extension_end": signal.extension_end,
        "winners": signal.winners, "lots": [lot.model_dump() for lot in signal.lots]}


def attach_history(signals, history, translations=None):
    buyers, procedures = defaultdict(list), defaultdict(list)
    latest = {s.id: enrich_signal(s) for s in history}
    latest.update({s.id: enrich_signal(s) for s in signals})
    for signal in latest.values():
        item = history_entry(signal)
        translation = (translations or {}).get(signal.id)
        translated = translation.model_dump() if hasattr(translation, "model_dump") else translation or {}
        if translated.get("source_hash") == digest([signal.title, signal.description]) and translated.get("title"):
            item["title_en"] = translated["title"]
        if signal.buyer_id:
            buyers[signal.buyer_id].append(item)
        procedures[signal.procedure_id].append(item)
    def order(item):
        return (item["award_date"] or item["published_at"] or "", item["signal_id"])
    for buyer in buyers:
        buyers[buyer].sort(key=order, reverse=True)
    for procedure in procedures:
        procedures[procedure].sort(key=order)
    for signal in signals:
        signal.buyer_history = buyers[signal.buyer_id]
        signal.procedure_history = list(procedures[signal.procedure_id])
        # Retain source release lineage even where a normalized record was updated.
        known = {item["source_url"] for item in signal.procedure_history}
        for source in signal.provenance:
            if source.url not in known and canonical_url(source.url):
                signal.procedure_history.append({"signal_id": signal.id, "title": source.release_id,
                    "published_at": source.published_at, "status": "unknown", "source_url": source.url, "lot_ids": []})
                known.add(source.url)


def backfill_retained_facts(signals, state):
    """Repair legacy Grants.gov facts only when the retained API cache proves them."""
    from .normalise import set_hashes

    cache = state.get("grants", {}).get("detail_cache", {})
    for signal in signals:
        if signal.source == "grants":
            ident = next((value.split(":", 1)[1] for value in signal.external_ids if value.startswith("grants:")), None)
            cached = cache.get(ident, {}).get("record", {})
            if cached:
                from .collectors import RawRecord
                from .normalise import normalise_grants
                raw = RawRecord(cached, {"id": "grants", "name": "Grants.gov", "source_type": "official_funding"},
                                signal.last_seen_at, "grants")
                restored = normalise_grants(raw)
                for field in ("buyer_name", "buyer_identifiers", "agency_name", "department_name", "contacts",
                              "buyer_name_conflicts", "deadline_at", "deadlines", "amount", "value_min", "value_max", "currency"):
                    setattr(signal, field, getattr(restored, field))
                signal.documents = list({d.url: d for d in restored.documents + signal.documents}.values())
            elif signal.deadline_at and re.search(r"T00:00:00(?:\+00:00|Z)$", signal.deadline_at):
                # This adapter historically manufactured midnight for date fields.
                signal.deadline_at = signal.deadline_at[:10]
                signal.response_deadlines = [v[:10] if "T00:00:00" in v else v for v in signal.response_deadlines]
                signal.deadlines = []
            if not cached and not signal.agency_name and not signal.buyer_identifiers and signal.buyer_name:
                signal.buyer_name_conflicts = unique(signal.buyer_name_conflicts + [signal.buyer_name])
                signal.buyer_name = None
        enrich_signal(signal)
        # Enrichment is material too: records without a refreshed response date
        # otherwise retain the hash of their earlier, less complete schema.
        set_hashes(signal)
