"""Conservative exclusions of a purchased deliverable, never a sector word blacklist.

A rule needs a specific title AND corroborating scope/classification. Any separately
stated application/AI deliverable protects mixed procurements. Unrecognised or sparse
scope remains a candidate. Original and exact-hash English evidence use the same rules.
"""
import re

from .capability_matching import affirmed, operational_software_use, physical_integration
from .vocabulary import phrase_hits

BUSINESS_OBJECTS = (
    "salesforce", "mulesoft", "agentforce", "tableau", "customer relationship", "crm software",
    "crm platform", "crm system", "customer portal", "citizen portal", "patient portal", "employee portal",
    "case management system", "case management software", "case management platform", "casework system",
    "relationship management", "grants management system", "grant management system", "housing allocation system",
    "admissions system", "student information system", "customer information system", "information system",
    "business application", "business software", "workflow automation", "process automation", "workflow platform",
    "business intelligence", "data platform", "data warehouse", "analytics platform", "reporting platform",
    "ai assistant", "ai agent", "ai agents", "chatbot", "chatbots", "virtual assistant", "language model",
    "generative ai", "document intelligence", "intelligent document processing", "enterprise search",
    "systems integration", "system integration", "api integration", "software development", "application development",
    "website development", "web platform", "software engineering", "digital transformation", "it consultancy",
    "it consultants", "digital and it professional services", "remote patient monitoring",
    "cashless parking", "digital payment services", "online booking system", "incident management system",
)
DELIVERY = re.compile(r"\b(?:develop\w*|implement\w*|build\w*|creat\w*|design\w*|deliver\w*|provi\w*|"
                      r"procur\w*|purchas\w*|suppl\w*|configur\w*|integrat\w*|migrat\w*|replac\w*|"
                      r"maintain\w*|maintenance|support|evolution|requires?|seeking|commission\w*|"
                      r"entwicklung|beschaffung|implementierung|sviluppo|fornitura|desarrollo|suministro)\b")
INCIDENTAL = re.compile(r"\b(?:already (?:use|uses|using|have)|existing (?:supplier|contractor) portal|"
                        r"submit\w* (?:your |the |a )?(?:bid|tender|proposal)|using (?:our|the authority s)|"
                        r"must use (?:our|the authority s))\b")


def physical_payment_equipment(text, phrase):
    return phrase == "cashless parking" and bool(phrase_hits(text, ("parking machines", "parking meters")))


def addressable_delivery(segments):
    """Return positive quoted scope, not a capability inferred from an industry/CPV."""
    for segment in segments:
        text = segment["text"]
        # Purchasing/developing software is positive scope even for an unfamiliar
        # domain. Merely requiring a contractor to use software is not.
        delivered_software = re.search(r"\b(?:develop|build|implement|create)\w*\s+(?:\w+\s+){0,7}"
                                      r"(?:software|platform|web application|information system)\b", text)
        if delivered_software and affirmed(text, delivered_software.group()) and not INCIDENTAL.search(text):
            return segment
        native_delivery = re.search(r"\b(?:desarrollo|implementacion|integracion|entwicklung|implementierung|sviluppo|implementazione|integrazione)"
                                    r"\s+(?:\w+\s+){0,6}(?:software|plataforma|aplicaciones|applikationen|anwendungen|piattaforma|applicazioni)\b", text)
        if native_delivery and affirmed(text, native_delivery.group()) and not INCIDENTAL.search(text):
            return segment
        # An AI service is a delivery signal even in a physical industry. The
        # hardware's capacity to run a model is a different purchased object.
        ai_service = re.search(r"\b(?:ai|artificial intelligence)\b.{0,60}\b(?:service|software|platform|assistant|solution|tool)\b", text)
        if ai_service and affirmed(text, ai_service.group()) and segment["field"] == "title" and not re.search(r"\b(?:server|hardware|equipment|appliance)\b", text):
            return segment
        hits = [p for p in phrase_hits(text, BUSINESS_OBJECTS)
                if affirmed(text, p) and not physical_integration(text, p)
                and not operational_software_use(text, p) and not physical_payment_equipment(text, p)]
        if set(hits) <= {"language model"} and re.search(r"\b(?:server|hardware|computer|gpu)\b", text):
            hits = []
        if not hits:
            continue
        if segment["field"] == "title":
            return segment
        if DELIVERY.search(text) and not INCIDENTAL.search(text):
            return segment
    return None


# Title, corroborating description, CPV support. Neither a CPV nor a word in an
# unrelated paragraph can trigger exclusion by itself. This is a taxonomy of work.
RULES = (
    ("parking_equipment", r"\b(?:cashless parking machines|parking meters)\b",
     r"\b(?:refurbishment|purchase|units|supply|hardware|equipment)\b", ("3873",),
     "Physical parking payment equipment"),
    ("occupational_safety", r"\b(?:occupational safety specialist|occupational health (?:physician|services)|health and safety adviser|safety officer)\b",
     r"\b(?:physician|workplace|hazards?|safety|inspections|risk assessment)\b", ("71317", "851", "79417"),
     "Occupational health or workplace safety services"),
    ("survey_coding", r"\b(?:(?:sic(?: and soc)?|soc|occupational|industrial) coding|coding of.*survey)\b",
     r"\b(?:classification|survey responses|occupational information|coding)\b", ("7233", "7931"),
     "Coding or classification of survey responses as a service"),
    ("business_promotion", r"\b(?:business engagement consultancy|business development consultancy|investment promotion services)\b",
     r"\b(?:industry partners|industry funding|value propositions|promote|investors|marketing)\b", ("7941", "7999"),
     "Business promotion or partnership development consultancy"),
    ("physical_it_installation", r"\b(?:digital modernisation|digital modernization|digitale modernisierung)\b",
     r"\b(?:supply of items|lieferung von gegenstanden)\b.{0,120}\b(?:servers?|nw server|wlan|access points)\b",
     (), "Supply and installation of physical IT infrastructure"),
    ("field_surveys", r"\b(?:bird survey|breeding and resting bird|tree surveys?|sediment coring|"
     r"geotechnical survey|ecological survey|asbestos census|crane condition survey|rastvogelerfassung)\b",
     r"\b(?:sampling|sediment|vibrocorer|on foot|habitats?|species|asbestos|crane|vogelschutz)\b", ("71", "90", "7931"),
     "Physical field surveys or sampling"),
    ("construction", r"\b(?:building automation|building renovation|greenhouse construction|"
     r"construction management|architectur\w* and engineering services|active travel (?:route|path)|"
     r"cyclepath|upgrading of tunnels|fire alarm design|grounds maintenance|gebaudeautomation)\b",
     r"\b(?:construction|installation|works|cabling|ventilation|riba|engineering|tunnel|building|surveys)\b",
     ("45", "50", "71", "489210"), "Construction, building control or physical maintenance"),
    ("equipment_maintenance", r"\b(?:fermenter|air conditioning and ventilation|maintenance of electrical installations|"
     r"maintenance of navigation and communication equipment|physical infrastructures and facilities)\b",
     r"\b(?:calibration|spare|parts|repairs|ventilation|electrical|installations|physical)\b", ("38", "50", "45"),
     "Maintenance of physical equipment"),
    ("hardware", r"\b(?:ai server|server appliances|server and storage|server hardware|hardware acquisition|"
     r"hardware framework|notebooks|printers|workplace computers|pcs and equipment|thinpro|"
     r"supply of led panels|audio visual equipment|bandwidth management equipment|hydrological monitoring stations|clinical simulation manikins)\b",
     r"\b(?:hardware|equipment|server|servers|computers|licences|licenses|supply|purchase|stations|manikins)\b",
     ("30", "32", "38", "48"), "Physical computing, network or measurement equipment"),
    ("licence_resale", r"\b(?:microsoft|adobe|acrobat|vmware|citrix|autodesk|veeam|commvault|red hat|"
     r"windows|oracle|sap|sophos|arcsight|fortinet|trellix|trend ai)\b.*\b(?:licen[cs]\w*|subscription\w*|renewal|extension|verlangerung)\b|"
     r"\b(?:licen[cs]\w*|subscription\w*|renewal|extension|verlangerung)\b.*\b(?:microsoft|adobe|acrobat|vmware|citrix|autodesk|"
     r"veeam|commvault|red hat|windows|oracle|sap|sophos|arcsight|fortinet|trellix|trend ai)\b",
     r"\b(?:licen[cs]\w*|subscription\w*|renewal|renew|rights of use|lizenzen)\b", ("48", "72"),
     "Resale or renewal of unrelated product licences"),
    ("property_valuation", r"\b(?:property valuation services|land and property valuation|appraisal of real estate)\b",
     r"\b(?:properties|property|land|valuation|appraisal)\b", ("70", "71", "7941"), "Property appraisal services"),
    ("financial_audit", r"\b(?:internal audit services|financial audits|audit of the proof of use|reinsurance broker)\b",
     r"\b(?:financial|accounting|audit|audits|insurance)\b", ("66", "792", "7941"), "Financial audit or insurance services"),
    ("creative_agency", r"\b(?:creative agency|marketing and communications services|communication and marketing services|"
     r"brand process and production of campaign|public relations work)\b",
     r"\b(?:advertising|copy writing|copywriting|media|campaign|brand|public relations)\b", ("793", "79413"),
     "Creative, advertising or public relations services"),
    ("survey_execution", r"\b(?:tenant survey(?: services)?|online panel survey services|audience research services|"
     r"market research (?:services|studies)|employee survey at|residents survey|stakeholder research)\b",
     r"\b(?:interviews|questionnaires|respondents|survey|surveys|fieldwork|participants|research)\b",
     ("7931", "7932"), "Execution of surveys or market research"),
    ("human_services", r"\b(?:independent housing information and advice|recruitment services.*intern|"
     r"hospital discharge coding service|indexing and coding in icd|security guard services|"
     r"staff and student accommodation|off site storage|formal service of process)\b",
     r"\b(?:housing|homeless|internships|clinical|hospital|guard|accommodation|storage|process)\b",
     ("75", "79", "80", "85", "7233"), "Human service delivery or physical records storage"),
    ("academic_training", r"\b(?:master s degree|postdoctoral research fellowships)\b",
     r"\b(?:training|degree|fellowships|postdoctoral)\b", ("80", "79632"), "Academic degrees or research fellowships"),
    ("physical_research", r"\b(?:transport phenomena|thermohydraulic modelling|human wildlife conflict|"
     r"deterrent culls|feasibility study.*composting plant)\b",
     r"\b(?:fundamental research|fluids|thermal|wildlife|cormorant|composting|plant)\b", ("71", "73", "90", "7931"),
     "Physical science, ecological or plant feasibility work"),
)
COMPILED_RULES = [(key, re.compile(title), re.compile(detail), cpv, label)
                  for key, title, detail, cpv, label in RULES]


def scope_exclusion(segments, cpv_codes):
    if addressable_delivery(segments):
        return None
    for title in (s for s in segments if s["field"] == "title"):
        for key, title_pattern, detail_pattern, prefixes, label in COMPILED_RULES:
            if not title_pattern.search(title["text"]):
                continue
            if key not in ("licence_resale", "hardware", "equipment_maintenance") and phrase_hits(title["text"], ("software", "platform", "application", "crm")):
                continue
            # Maintenance/support of a licence is not implementation. Conversely,
            # a genuine new deployment/migration keeps a mixed licence procurement.
            if key == "licence_resale" and any(affirmed(s["text"], match.group()) for s in segments
                    if not INCIDENTAL.search(s["text"]) for match in re.finditer(
                    r"\b(?:implementation|integration|migration|conversion|converting|convert|development|configuration|customisation|professional services|"
                    r"implementierung|integration|migration|entwicklung|konfiguration|implementacion|integracion|"
                    r"migracion|desarrollo|configuracion|servicios profesionales|implementazione|integrazione|conversione|umstellung|sviluppo)\b", s["text"])
                    ):
                continue
            detail = next((s for s in segments if s["field"] == "description" and detail_pattern.search(s["text"])), None)
            if detail or any(str(code).startswith(prefixes) for code in cpv_codes):
                return {"rule": key, "reason": f"{label} without a separately stated business-application, Salesforce or AI delivery scope.",
                        "basis": title["basis"], "title": title["quote"],
                        "quote": (detail or title)["quote"]}
    return None


def generic_digital_scope(segments):
    """Recall route for sparse but explicit digital delivery, without fabricated tags."""
    phrases = ("digital and it professional services", "it consultancy", "it consultants", "ict consultants",
               "it systems", "software testing", "software engineering",
               "ai adoption", "ai pilots", "remote patient monitoring", "digital delivery capability",
               "digital and technology delivery services", "digital data and technology",
               "digital service lifecycle", "digital products and services",
               "software configuration", "software customisation", "software customization",
               "cashless parking", "digital payment services", "digital delivery services",
               "online learning platform", "incident management system", "clinical patient management system")
    return list(dict.fromkeys(p for s in segments for p in phrase_hits(s["text"], phrases)
                             if affirmed(s["text"], p) and not physical_payment_equipment(s["text"], p)
                             and not operational_software_use(s["text"], p)))
