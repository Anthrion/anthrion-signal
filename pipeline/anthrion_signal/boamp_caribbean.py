"""French Caribbean notices from DILA's public BOAMP API.

Publication departments are distribution tags, not procurement locations. Route
only on explicit performance/buyer addresses. Source eForms offsets are retained;
older forms' unzoned local clocks are not silently converted to UTC by trusting
the catalogue's synthetic offset. Corrections can retain stale structured dates,
so an unverified corrected deadline is deliberately unknown.
"""

import copy
import json
import re
import unicodedata
from datetime import timedelta
from urllib.parse import urlencode, urlparse

from .collectors import Collection, RawRecord, SourceUnavailable, defer_collection
from .models import Amount, Document, Lot
from .normalise import base, classify, money
from .public_context import deadline_fact
from .utils import canonical_url, clean, digest, parse_date, unique


API_URL = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
VERSION = "boamp-caribbean-v3"
MAX_DAY_IDS = 200
MAX_QUERY_BYTES = 7000
MAX_PARENT_DEPTH = 5
MAX_PARENT_RECORDS = 20
ID = re.compile(r"\d{2}-\d{1,9}")
CARIBBEAN = {"GP", "MQ", "BL", "MF"}
PUBLIC_FIELDS = (
    "idweb", "objet", "nomacheteur", "dateparution", "nature", "nature_libelle", "etat",
    "contractfolderid", "annonce_lie", "donnees", "titulaire", "procedure_libelle",
)


def _many(value):
    return value if isinstance(value, list) else [value] if value is not None else []


def _text(value, limit=24000):
    if isinstance(value, dict):
        return _text(value.get("#text", ""), limit)
    return clean(value, limit) if isinstance(value, (str, int, float)) else ""


def _at(value, *path):
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _find(value, key):
    if isinstance(value, dict):
        for name, child in value.items():
            if name == key:
                yield from _many(child)
            else:
                yield from _find(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from _find(child, key)


def _fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)).casefold()


def _territories(address):
    """Use only an address/performance subtree, never every org in a notice."""
    if isinstance(address, (dict, list)):
        postal = [_text(v) for key in ("cp", "cbc:PostalZone") for v in _find(address, key)]
        text = " ".join(_text(v) for key in ("ville", "cbc:CityName", "cbc:CountrySubentityCode", "cbc:Description")
                        for v in _find(address, key))
        explicit = {_text(_at(country, "cbc:IdentificationCode")) for country in _find(address, "cac:Country")}
        named = {"GLP": "GP", "MTQ": "MQ", "BLM": "BL", "MAF": "MF", "GUF": "GF"}
        proved = {named[code] for code in explicit if code in named}
        if proved:
            return proved
    else:
        text = _text(address)
        postal = re.findall(r"(?<!\d)(?:97\d{3})(?!\d)", text)
    countries = []
    for code in postal:
        code = code.strip()
        if re.fullmatch(r"\d{5}", code):
            country = ("BL" if code == "97133" else "MF" if code == "97150" else
                       "GP" if code.startswith("971") else "MQ" if code.startswith("972") else
                       "GF" if code.startswith("973") else "FR")
            countries.append(country)
    if countries:
        return set(countries)  # Postal detail distinguishes MF/BL from broad FRY1.
    text = _fold(text)
    for pattern, country in ((r"\b(?:guadeloupe|fry1\d?)\b", "GP"),
                             (r"\b(?:martinique|fry2\d?)\b", "MQ"),
                             (r"\b(?:guyane|fry3\d?)\b", "GF"),
                             (r"\b(?:collectivite (?:de |d'outre-mer de )saint[- ]barthelemy|977)\b", "BL"),
                             (r"\b(?:collectivite (?:de |d'outre-mer de )saint[- ]martin|978)\b", "MF")):
        if re.search(pattern, text):
            countries.append(country)
    return set(countries)


def _narrative(value, *, eforms=False):
    """Preserve substantive original prose without XML keys, codes or contacts."""
    parts = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.startswith("@") or key in {"organisme", "coord", "adressesComplt", "cac:Contact", "efac:Organizations"}:
                continue
            if eforms:
                if key in {"cbc:Name", "cbc:Description", "efbc:ChangeDescription", "efbc:ReasonDescription"}:
                    parts.extend(_text(item, None) for item in _many(child))
                elif isinstance(child, (dict, list)):
                    parts.extend(_narrative(child, eforms=True))
            elif isinstance(child, (dict, list)):
                parts.extend(_narrative(child))
            elif isinstance(child, str) and not re.search(r"url|mail|contact|telephone|identifiant|date", key, re.I):
                if len(clean(child)) >= 25 or re.search(r"description|intitule|objet|infosRectif|principales", key, re.I):
                    parts.append(clean(child, None))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                parts.append(clean(item, None))
            else:
                parts.extend(_narrative(item, eforms=eforms))
    return unique([part for part in parts if part and not re.match(r"https?://", part)])


def _safe_link(value):
    value = _text(value)
    if value.startswith("www."):
        value = "https://" + value
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    return canonical_url(value) if parsed.scheme in ("https", "http") and parsed.netloc and not (parsed.username or parsed.password) else None


def _date(value):
    value = _text(value)
    return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value) and parse_date(value[:10]) else None


def _period(period):
    day, clock = _text(_at(period, "cbc:EndDate")), _text(_at(period, "cbc:EndTime"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:Z|[+-]\d{2}:\d{2})?", day) or not _date(day):
        return None
    if not clock:
        return day[:10]
    if not re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", clock):
        return None
    day_offset = re.search(r"(Z|[+-]\d{2}:\d{2})$", day)
    clock_offset = re.search(r"(Z|[+-]\d{2}:\d{2})$", clock)
    if day_offset and clock_offset and day_offset[1] != clock_offset[1]:
        return None
    if not clock_offset and day_offset:
        clock += day_offset[1]
    value = day[:10] + "T" + clock
    return value if parse_date(value) else None


def _value(node, key="@currencyID"):
    if not isinstance(node, dict):
        return None, None
    return money(node.get("#text")), _text(node.get(key)) or None


def _eforms(data, url):
    if not isinstance(data, dict) or len(data) != 1:
        raise SourceUnavailable("BOAMP eForms notice structure was not recognised")
    notice_kind, notice = next(iter(data.items()))
    if not isinstance(notice, dict):
        raise SourceUnavailable("BOAMP eForms notice body was not recognised")
    extension = _at(notice, "ext:UBLExtensions", "ext:UBLExtension", "ext:ExtensionContent", "efext:EformsExtension") or {}
    organizations = {_text(_at(item, "efac:Company", "cac:PartyIdentification", "cbc:ID")): item.get("efac:Company", {})
                     for item in _many(_at(extension, "efac:Organizations", "efac:Organization")) if isinstance(item, dict)}
    buyer_refs = [_text(_at(party, "cac:Party", "cac:PartyIdentification", "cbc:ID"))
                  for party in _many(notice.get("cac:ContractingParty"))]
    buyers = [organizations[ref] for ref in buyer_refs if ref in organizations]
    project = notice.get("cac:ProcurementProject") or {}
    lot_nodes = _many(notice.get("cac:ProcurementProjectLot"))
    locations = [location for item in [project, *[lot.get("cac:ProcurementProject", {}) for lot in lot_nodes]]
                 for location in _many(item.get("cac:RealizedLocation"))]
    performance = set().union(*(_territories(location) for location in locations))
    countries = performance or set().union(*(_territories(buyer.get("cac:PostalAddress", {})) for buyer in buyers))
    change = extension.get("efac:Changes") or {}
    cancelled = _text(_at(change, "efac:ChangeReason", "cbc:ReasonCode")) == "cancel"
    results = _at(extension, "efac:NoticeResult") or {}
    lot_results = {_text(_at(item, "efac:TenderLot", "cbc:ID")): _text(item.get("cbc:TenderResultCode"))
                   for item in _many(results.get("efac:LotResult")) if isinstance(item, dict)}
    lots, facts = [], []
    for node in lot_nodes:
        ident, lot = _text(node.get("cbc:ID")), node.get("cac:ProcurementProject") or {}
        if not ident:
            continue
        lot_facts = []
        for path, kind in (("cac:ParticipationRequestReceptionPeriod", "application"),
                           ("cac:TenderSubmissionDeadlinePeriod", "tender")):
            for period in _many(_at(node, "cac:TenderingProcess", path)):
                value = _period(period)
                fact = deadline_fact(value, url, kind, lot_id=ident) if value else None
                if fact:
                    lot_facts.append(fact)
        facts.extend(lot_facts)
        state = {"selec-w": "awarded", "clos-nw": "unsuccessful", "open-nw": "unknown"}.get(lot_results.get(ident), "unknown")
        lots.append(Lot(id=ident, title=_text(lot.get("cbc:Name")), description=_text(lot.get("cbc:Description"), None),
                        status=state, source_url=url))
    amount = _at(project, "cac:RequestedTenderTotal", "cbc:EstimatedOverallContractAmount")
    kind = "estimated_contract"
    if amount is None:
        amount = next(_find(project.get("cac:RequestedTenderTotal", {}), "efbc:FrameworkMaximumAmount"), None)
        kind = "framework_ceiling"
    if notice_kind == "ContractAwardNotice":
        ceiling = results.get("efbc:OverallMaximumFrameworkContractsAmount")
        amount = ceiling if ceiling is not None else results.get("cbc:TotalAmount")
        kind = "framework_ceiling" if ceiling is not None else "award"
    maximum, currency = _value(amount)
    award_dates = unique([_date(item) for item in _find(results.get("efac:SettledContract", {}), "cbc:AwardDate")])
    return {
        "countries": sorted(countries & CARIBBEAN), "description": "\n\n".join(_narrative(notice, eforms=True)),
        "buyer_identifiers": unique(["FR-SIRET:" + v for buyer in buyers
                                     if re.fullmatch(r"\d{14}", v := _text(_at(buyer, "cac:PartyLegalEntity", "cbc:CompanyID")))]),
        "reference": _text(project.get("cbc:ID")), "procedure": _text(notice.get("cbc:ContractFolderID")),
        "cpv_codes": unique([_text(v) for v in _find(notice, "cbc:ItemClassificationCode") if re.fullmatch(r"\d{8}", _text(v))]),
        "lots": lots, "facts": facts, "cancelled": cancelled, "amended": bool(change),
        "award": notice_kind == "ContractAwardNotice", "award_date": award_dates[0] if len(award_dates) == 1 else None,
        "amount": Amount(kind=kind, maximum=maximum, currency=currency, source_label=kind, source_url=url),
        "links": unique([link for v in _find(notice, "cbc:URI") if (link := _safe_link(v))]),
    }


def _french_form(data, url):
    organism = data.get("organisme") or {}
    body = data.get("initial") or data.get("rectificatif") or data.get("annulation") or data.get("attribution") or {}
    locations = [v for key in ("lieuExecution", "lieuExecutionLivraison") for v in _find(body, key)]
    performance = set().union(*(_territories(location) for location in locations))
    countries = performance or _territories(organism.get("adr") or organism)
    reference = _text(_at(body, "communication", "identifiantInterne")) or _text(_at(body, "renseignements", "idMarche"))
    if re.match(r"https?://|www\.", reference):
        reference = ""
    facts = []
    for key in ("dateReceptionOffres", "receptionOffres"):
        for value in _find(body, key):
            fact = deadline_fact(_text(value), url, "tender")
            if fact:
                facts.append(fact)
    # MAPA has a typed replacement field; other corrections can be free text.
    correction = body.get("infosRectif")
    replacement = _at(correction, "lireDate") if _at(correction, "rubDelais") == "ReceptionOffres" else None
    if replacement:
        fact = deadline_fact(_text(replacement), url, "tender")
        facts = [fact] if fact else []
    amount = _at(body, "natureMarche", "valeurEstimee") or {}
    minimum = money(_at(amount, "fourchette", "valeurBasse"))
    maximum = money(_at(amount, "fourchette", "valeurHaute"))
    if maximum is None:
        maximum = money(amount.get("valeur"))
    lots = []
    for item in _many(_at(body, "lots", "lot")):
        if not isinstance(item, dict):
            continue
        description = _text(item.get("description"), None)
        ident = _text(item.get("numero")) or _text(item.get("numLot"))
        match = re.match(r"(?:Lot\s*(?:n[°º]?\s*)?)?(\d+)\s*[-:]", description, re.I)
        ident = ident or (match[1] if match else "")
        if ident:
            lots.append(Lot(id=ident, title=description, description=description, source_url=url))
    return {
        "countries": sorted(countries & CARIBBEAN), "description": "\n\n".join(_narrative(body)),
        "buyer_identifiers": ["FR-SIRET:" + v] if re.fullmatch(r"\d{14}", v := _text(organism.get("codeIdentificationNational"))) else [],
        "reference": reference, "procedure": "", "lots": lots, "facts": facts,
        "cancelled": "annulation" in data, "amended": "rectificatif" in data,
        "verified_replacement": bool(replacement and facts), "award": "attribution" in data, "award_date": None,
        "cpv_codes": unique([_text(v) for v in _find(body, "classPrincipale") if re.fullmatch(r"\d{8}", _text(v))]),
        "amount": Amount(kind="estimated_contract", minimum=minimum, maximum=maximum,
                         currency=_text(amount.get("@devise")) or None, source_label="valeurEstimee", source_url=url),
        "links": unique([link for key in ("urlDocConsul", "urlProfilAch", "urlProfilAcheteur")
                         for v in _find(data, key) if (link := _safe_link(v))]),
    }


def parse_boamp_record(row):
    ident = str(row.get("idweb", ""))
    if not ID.fullmatch(ident) or not _text(row.get("objet")) or not _date(row.get("dateparution")):
        raise SourceUnavailable("BOAMP omitted a required notice identifier, title or publication date")
    try:
        data = json.loads(row["donnees"]) if isinstance(row.get("donnees"), str) else row.get("donnees")
    except (ValueError, TypeError):
        raise SourceUnavailable("BOAMP returned invalid original notice JSON") from None
    if not isinstance(data, dict) or len(data) != 1:
        raise SourceUnavailable("BOAMP original notice schema was not recognised")
    schema, content = next(iter(data.items()))
    url = f"https://www.boamp.fr/pages/avis/?q=idweb:{ident}"
    if schema == "EFORMS":
        facts = _eforms(content, url)
    elif schema in {"FNSimple", "MAPA"} and isinstance(content, dict):
        facts = _french_form(content, url)
    else:
        raise SourceUnavailable("BOAMP returned an unsupported original notice schema: " + clean(schema, 40))
    if not facts["countries"]:
        return None
    facts.update(id=ident, title=_text(row["objet"]), buyer=_text(row.get("nomacheteur")), url=url,
                 published_at=_date(row["dateparution"]), notice_type=_text(row.get("nature_libelle")),
                 winner="; ".join(_text(v) for v in _many(row.get("titulaire")) if _text(v)))
    facts["cancelled"] = facts["cancelled"] or row.get("etat") == "ANNULATION" or row.get("nature") == "ANNULATION"
    facts["amended"] = facts["amended"] or row.get("etat") == "RECTIFICATIF" or row.get("nature") == "RECTIFICATIF"
    facts["award"] = facts["award"] or row.get("nature") == "ATTRIBUTION"
    facts["competition"] = row.get("nature") == "APPEL_OFFRE"
    previous = [_text(v) for v in _many(row.get("annonce_lie")) if ID.fullmatch(_text(v))]
    facts["previous"] = previous
    if (facts["amended"] and not facts.get("verified_replacement")) or facts["cancelled"] or facts["award"]:
        facts["facts"] = []
    return facts


def _sparse_correction(row, facts=None):
    facts = facts or parse_boamp_record(row)
    data = json.loads(row["donnees"]) if isinstance(row.get("donnees"), str) else row.get("donnees", {})
    return bool(facts and facts["amended"] and not facts["award"] and not facts["cancelled"] and "EFORMS" not in data)


def _payload(row):
    payload = {field: row[field] for field in PUBLIC_FIELDS if field in row}
    payload["id"] = row["idweb"]
    # Actual source publication date also orders parent notices before amendments
    # in the shared normalisation loop; it is not a retrieval-time substitute.
    payload["date"] = row["dateparution"]
    return payload


def _parent_plan(job, available):
    """Return missing IDs and ancestors in topological order, with strict bounds."""
    missing, ordered, emitted = set(), [], set()
    root = job["row"]
    parents = job.setdefault("parents", {})

    def visit(row, path):
        ident = row["idweb"]
        if ident in path:
            raise SourceUnavailable("BOAMP correction predecessor chain contains a cycle")
        if len(path) > MAX_PARENT_DEPTH:
            raise SourceUnavailable("BOAMP correction predecessor chain exceeds its safe depth")
        if len(emitted) + len(missing) > MAX_PARENT_RECORDS:
            raise SourceUnavailable("BOAMP correction predecessor chain exceeds its record budget")
        facts = parse_boamp_record(row)
        if not facts:
            raise SourceUnavailable("BOAMP correction predecessor has no proved Caribbean location")
        if _sparse_correction(row, facts):
            if not facts["previous"]:
                raise SourceUnavailable("BOAMP sparse correction has no explicit predecessor identifier")
            for previous in facts["previous"]:
                parent = parents.get(previous) or available.get(previous)
                if parent is None:
                    missing.add(previous)
                else:
                    parents[previous] = parent
                    visit(parent, [*path, ident])
        if ident != root["idweb"] and ident not in emitted:
            ordered.append(row)
            emitted.add(ident)

    visit(root, [])
    if len(emitted) + len(missing) > MAX_PARENT_RECORDS:
        raise SourceUnavailable("BOAMP correction predecessor chain exceeds its record budget")
    return missing, ordered


def _hydrate_corrections(result, source, frozen, http, budget, available, jobs):
    """Retry unresolved originals independently; one bad parent cannot block new notices."""
    attempted = set()
    emitted = {raw.data["idweb"] for raw in result.records}
    retry_hours = max(1, int(source.get("parent_retry_hours", 6)))
    while jobs:
        requested, selected = set(), []
        for ident, job in sorted(list(jobs.items()), key=lambda item: (item[1].get("last_attempt", ""), item[0])):
            try:
                missing, ancestors = _parent_plan(job, available)
            except SourceUnavailable as exc:
                job["message"] = str(exc)
                job["retry_at"] = (frozen + timedelta(hours=retry_hours)).isoformat()
                continue
            if not missing:
                for row in [*ancestors, job["row"]]:
                    if row["idweb"] not in emitted:
                        result.records.append(RawRecord(_payload(row), source, frozen.isoformat(), "boamp_caribbean"))
                        emitted.add(row["idweb"])
                jobs.pop(ident)
                continue
            retry_at = parse_date(job.get("retry_at"))
            if retry_at and frozen < retry_at:
                continue
            needed = missing - attempted
            if needed and len(requested | needed) <= MAX_PARENT_RECORDS:
                requested.update(needed)
                selected.append(job)
        if not requested or result.pages >= budget:
            break
        result.pages += 1
        rows = http.json(API_URL, params={
            "where": "idweb in (" + ",".join("'" + ident + "'" for ident in sorted(requested)) + ")",
            "limit": len(requested), "order_by": "dateparution ASC,idweb ASC",
        })
        page = rows.get("results") if isinstance(rows, dict) else None
        total = rows.get("total_count") if isinstance(rows, dict) else None
        if not isinstance(page, list) or total != len(page) or len(page) > len(requested):
            raise SourceUnavailable("BOAMP predecessor lookup returned an incomplete page")
        found = {}
        for row in page:
            ident = str(row.get("idweb", "")) if isinstance(row, dict) else ""
            if ident not in requested or ident in found:
                raise SourceUnavailable("BOAMP predecessor lookup returned an unexpected identifier")
            if parse_boamp_record(row):
                found[ident] = _payload(row)
        available.update(found)
        attempted.update(requested)
        for job in selected:
            job["last_attempt"] = frozen.isoformat()
            # A missing parent is retried later, while other originals and fresh
            # notices keep moving. The staged amendment is never emitted incomplete.
            try:
                missing, _ = _parent_plan(job, available)
            except SourceUnavailable as exc:
                job["message"] = str(exc)
                job["retry_at"] = (frozen + timedelta(hours=retry_hours)).isoformat()
                continue
            if missing & requested:
                job["retry_at"] = (frozen + timedelta(hours=retry_hours)).isoformat()
                job["message"] = "BOAMP predecessor is unavailable or outside proved Caribbean coverage"
    return jobs


def normalise_boamp_caribbean(raw, prior=None):
    facts = parse_boamp_record(raw.data)
    if not facts:
        return None
    status = ("cancelled" if facts["cancelled"] else "awarded" if facts["award"] else
              "amended" if facts["amended"] else "active" if facts["competition"] else "unknown")
    stage = "award" if facts["award"] else "tender" if facts["competition"] or facts["amended"] or facts["cancelled"] else "unknown"
    aliases = ["boamp:" + facts["id"]]
    if not facts["award"] and (facts["amended"] or facts["cancelled"]):
        aliases.extend("boamp:" + previous for previous in facts["previous"])
        if prior is not None and set(prior.external_ids).intersection(aliases):
            # A later correction can refer to the original or any intermediate
            # notice. Keep the exact alias chain so every reference resolves to
            # the latest scope instead of an older, incomplete amendment.
            aliases = unique([*aliases, *prior.external_ids])
    procedure = ("ted-procedure:" + facts["procedure"] if facts["procedure"] else
                 "boamp-procedure:" + digest([facts["buyer"], facts["reference"]]) if facts["reference"] else None)
    dates = facts["facts"]
    applications = [fact for fact in dates if fact.kind == "application"]
    actionable = applications or dates
    # Local clocks remain visible in Deadline evidence, but cannot establish an instant.
    values = unique([fact.instant or fact.date for fact in actionable])
    now = parse_date(raw.retrieved_at)
    upcoming = [value for value in values if parse_date(value[:10]).date() >= now.date()]
    deadline = min(upcoming, key=parse_date) if upcoming else max(values, key=parse_date) if values else None
    amount = facts["amount"]
    if facts["award"] and amount.kind == "estimated_contract":
        amount = Amount(kind="unknown", source_label="Published award", source_url=facts["url"])
    description = facts["description"] or facts["title"]
    original = json.loads(raw.data["donnees"]) if isinstance(raw.data.get("donnees"), str) else raw.data["donnees"]
    sparse = facts["amended"] and "EFORMS" not in original
    if prior is not None and sparse and set(prior.external_ids).intersection(aliases):
        # Older French forms publish only the correction. Keep the full scope
        # and untouched lots; an eForms correction republishes its own full body.
        if clean(description, None) not in clean(prior.description, None):
            description = (prior.description + "\n\n" +
                f"Rectificatif publié le {facts['published_at']} : {description}")
        else:
            description = prior.description
        revised = {lot.id: lot for lot in prior.lots}
        revised.update({lot.id: lot for lot in facts["lots"]})
        facts["lots"] = list(revised.values())
    return base(raw, title=facts["title"], description=description,
                description_limit=None, url=facts["url"], source_language="fr", countries=facts["countries"],
                buyer_name=facts["buyer"] or None, buyer_identifiers=facts["buyer_identifiers"], external_ids=aliases,
                procedure_identifiers=[procedure] if procedure else [], published_at=facts["published_at"],
                updated_at=facts["published_at"], notice_type=facts["notice_type"] or None,
                signal_type=classify(stage, facts["title"], facts["description"]) if stage != "unknown" else "STRATEGIC_INTENT",
                procurement_stage=stage, status=status,
                cpv_codes=facts["cpv_codes"], lot_ids=[lot.id for lot in facts["lots"]], lots=facts["lots"],
                deadline_at=deadline, response_deadlines=values, deadlines=dates, award_date=facts["award_date"],
                incumbent_supplier=facts["winner"] or None, amount=amount, value_min=amount.minimum,
                value_max=amount.maximum, currency=amount.currency,
                documents=[Document(title="Avis officiel BOAMP", url=facts["url"], kind="notice"),
                           *[Document(title="Documents de consultation", url=url) for url in facts["links"]]])


def collect_boamp_caribbean(source, state, frozen, http, settings, terms):
    """Resume by publication day, excluding only IDs already seen on that day.

    Opendatasoft supports IN filters, but not text > comparisons. Exact ID
    exclusions avoid skipped notices when a source insertion/deletion shifts an
    offset page. The next completed refresh also replays seven publication days.
    """
    result = Collection(state=copy.deepcopy(state))
    if source.get("url", API_URL) != API_URL:
        raise SourceUnavailable("BOAMP source must use the documented public dataset endpoint")
    same_version = state.get("query_version") == VERSION
    pending = copy.deepcopy(state.get("pending")) if same_version else None
    jobs = copy.deepcopy(state.get("pending_corrections", {})) if same_version else {}
    watermark = parse_date(state.get("scan_watermark") or state.get("watermark")) if same_version else None
    recent = bool(not settings.get("refresh_daily") and watermark and timedelta(0) <= frozen - watermark < timedelta(hours=max(1, int(source.get("refresh_hours", 12)))))
    if not pending and recent and not jobs:
        return result
    if not pending and recent:
        pending = None
    elif not isinstance(pending, dict) or not all(_date(pending.get(key)) for key in ("from", "until")):
        start = watermark - timedelta(days=7) if watermark else frozen - timedelta(days=settings["lookback_days"])
        pending = {"from": start.date().isoformat(), "until": frozen.date().isoformat(),
                   "snapshot_at": frozen.isoformat(), "cursor_day": "", "seen_ids": []}
    else:
        pending = dict(pending)
        pending["from"], pending["until"] = _date(pending["from"]), _date(pending["until"])
    day = _date((pending or {}).get("cursor_day")) or ""
    seen = pending.get("seen_ids", []) if day else []
    result.state.update(query_version=VERSION, pending_corrections=jobs)
    if pending:
        result.state["pending"] = pending
    else:
        result.state.pop("pending", None)
    limit = max(1, min(100, int(source.get("limit", 100))))
    budget = max(0, min(settings["max_pages"], int(source.get("max_pages_per_run", 20))))
    available = {}
    try:
        if not isinstance(jobs, dict):
            raise SourceUnavailable("BOAMP correction checkpoint was not recognised")
        if not isinstance(seen, list) or any(not isinstance(ident, str) or not ID.fullmatch(ident) for ident in seen):
            raise SourceUnavailable("BOAMP daily checkpoint contained invalid identifiers")
        seen = set(seen)
        while pending and result.pages < budget:
            # Reserve a small part of each run for staged originals while the
            # ordinary listing cursor continues independently.
            if jobs and budget - result.pages <= min(2, budget // 3):
                break
            if len(seen) > MAX_DAY_IDS:
                raise SourceUnavailable("BOAMP daily checkpoint exceeds the bounded query size; source partition review required")
            where = ("code_departement in ('971','972','977','978') "
                     f"AND dateparution <= date'{pending['until']}' "
                     f"AND (dateparution >= date'{pending['from']}' OR datelimitereponse >= date'{pending['until']}')")
            if day:
                where += f" AND dateparution >= date'{day}'"
            if seen:
                where += " AND NOT (idweb in (" + ",".join("'" + ident + "'" for ident in sorted(seen)) + "))"
            params = {"where": where, "order_by": "dateparution ASC,idweb ASC", "limit": limit}
            if len(urlencode(params).encode("ascii")) > MAX_QUERY_BYTES:
                raise SourceUnavailable("BOAMP daily checkpoint exceeds the bounded query size; source partition review required")
            result.pages += 1
            page = http.json(API_URL, params=params)
            rows = page.get("results") if isinstance(page, dict) else None
            total = page.get("total_count") if isinstance(page, dict) else None
            if not isinstance(rows, list) or not isinstance(total, int) or total < len(rows) or len(rows) > limit or (not rows and total):
                raise SourceUnavailable("BOAMP returned an invalid or incomplete page")
            if len(rows) < limit and total > len(rows):
                raise SourceUnavailable("BOAMP returned a short page before its result count")
            batch, staged, available_page, batch_ids, last = [], {}, {}, set(), (day, "")
            for row in rows:
                if not isinstance(row, dict):
                    raise SourceUnavailable("BOAMP returned an invalid notice row")
                parsed = parse_boamp_record(row)
                key = (_date(row.get("dateparution")), str(row.get("idweb", "")))
                # The source applies natural numeric collation to text IDs:
                # 26-99605 precedes 26-100178. We only require monotonic days
                # and unique IDs; exact exclusions make within-day order moot.
                if key[0] < last[0] or key[1] in seen or key[1] in batch_ids:
                    # A server ignoring its ID filter must never silently complete
                    # the snapshot. Replaying is safe because reconciliation is by ID.
                    pending.update(cursor_day=day, seen_ids=[])
                    raise SourceUnavailable("BOAMP pagination did not advance")
                batch_ids.add(key[1])
                if parsed:
                    payload = _payload(row)
                    available_page[row["idweb"]] = payload
                    if _sparse_correction(row, parsed):
                        previous = jobs.get(row["idweb"])
                        staged[row["idweb"]] = previous if previous and previous.get("row") == payload else {"row": payload, "parents": {}}
                    else:
                        batch.append(RawRecord(payload, source, frozen.isoformat(), "boamp_caribbean"))
                last = key
            result.records.extend(batch)
            jobs.update(staged)
            available.update(available_page)
            complete = total == len(rows)
            last_day_ids = {str(row["idweb"]) for row in rows if _date(row.get("dateparution")) == last[0]}
            seen = seen | last_day_ids if last[0] == day else last_day_ids
            day = last[0]
            pending.update(cursor_day=day, seen_ids=sorted(seen))
            if complete:
                result.state["scan_watermark"] = pending.get("snapshot_at", frozen.isoformat())
                result.state.pop("pending", None)
                pending = None
        _hydrate_corrections(result, source, frozen, http, budget, available, jobs)
        if not jobs:
            result.state.pop("pending_corrections", None)
        if not pending and not jobs:
            result.state["watermark"] = result.state.get("scan_watermark", frozen.isoformat())
        else:
            result.complete = False
            result.message = (f"BOAMP has {len(jobs)} correction(s) awaiting verified predecessor scope; other notices continue to refresh."
                              if jobs else "BOAMP collection budget reached; remaining notices resume next run.")
    except SourceUnavailable as exc:
        defer_collection(result, exc)
    return result
