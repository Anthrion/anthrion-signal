"""Evidence-local tagging; source classifications remain a separate recall route."""
import re

from .vocabulary import phrase_hits, search_text

SOFTWARE = ("software", "platform", "application", "information system", "information systems",
            # An English compound names the system without ending in "-system" the way
            # the German and Nordic single words do, so it needs listing separately.
            # "digital solutions" and "computer system" stay out: reviewed decisions
            # already hold that neither establishes a technology scope on its own.
            "management system", "management systems", "it system", "it systems", "digital system",
            "digital systems", "web application", "web applications",
            "it solution", "it solutions", "software solution", "software solutions",
            "web portal", "internet portal",
            "automation", "workflow", "api", "crm", "saas", "database", "logiciel", "sistema", "sistemi",
            "applicazioni", "applicazione", "applikationen", "anwendungen", "virtualisierbar", "softwarewartung",
            "plataforma", "piattaforma", "softwareentwicklung", "systeme", "jarjestelma", "jarjestelman",
            "ohjelmisto", "logismiko", "λογισμικο", "συστημα", "συστηματος", "συστηματων", "πλατφορμα",
            "ψηφιακων", "ψηφιακος", "tietojarjestelma", "tietojarjestelman", "kerfi", "kerfis")
INTEGRATION = ("integration", "integrate", "integrated", "integrating", "interface", "interfaces", "connect",
               "connecting", "interoperability", "systemintegration", "schnittstelle", "schnittstellen",
               "integrazione", "interoperabilita", "integracion", "interoperabilidad", "διασυνδεση",
               "διασυνδεσης", "διαλειτουργικοτητα", "integraatio", "integrasjon")
NEGATED_BEFORE = re.compile(r"\b(?:no|without|excluding|exclude|excludes|not include|not including|does not require|"
                            r"not required(?: to)?|not responsible for|no requirement (?:to|for)|does not include|"
                            r"sans|ohne|kein|keine|keinen|sin|senza|χωρις|δεν περιλαμβανει)\s+(?:\w+\s+){0,4}$")
NEGATED_AFTER = re.compile(r"^\s*(?:\w+\s+){0,3}(?:is |are |will be )?(?:not included|not required|excluded|out of scope|"
                           r"δεν περιλαμβανεται|δεν περιλαμβανονται)")
AMBIGUOUS_NEEDS = {"account management", "client management", "contact management", "application processing",
                   "licensing applications", "casework", "case working", "case handling", "case processing",
                   "case management", "claims management", "patient engagement", "customer journeys",
                   "volunteer management", "donor management", "beneficiary management", "grant management",
                   "student lifecycle", "learner engagement", "contact centre", "contact center", "call centre",
                   "call center", "digital transformation", "service transformation", "business transformation",
                   "data quality", "data governance", "master data", "data cleansing", "data visualisation",
                   "data visualization", "business intelligence", "schnittstellenmanagement", "stakeholdermanagement",
                   "kundenmanagement", "kundhantering", "asiakashallinta", "gestion de donantes", "gestione dei donatori",
                   "stakeholder management", "constituent management", "member management", "membership management",
                   "supporter management", "fundraising management", "service user management", "alumni management",
                   "partner management", "grantee management", "applicant management", "tenant management",
                   "resident management", "customer lifecycle", "complaint handling", "complaints management",
                   "case tracking", "case allocation", "case triage", "referral management", "permit management",
                   "investigation management", "appeals management", "grievance management", "enquiry management",
                   "inquiry management", "workforce scheduling", "mobile workforce", "field service management"}
GENERIC_INTEGRATION = {"systems integration", "system integration", "integration with existing systems",
                       "integrate with existing systems", "systemintegration", "schnittstellenmanagement"}
PHYSICAL_SYSTEMS = ("pipework", "ventilation", "air handling", "compressed air", "heating", "boilers",
                    "high voltage", "switchgear", "electrical installations", "building management system",
                    "building management systems", "mechanical systems", "tiefengeothermie", "gas systems")
DIGITAL_SYSTEMS = ("software", "application", "database", "crm", "salesforce", "api", "middleware",
                   "information system", "information systems", "data platform", "customer portal", "ai agent")


def physical_integration(text, phrase):
    """A mechanical connection is not application integration; mixed digital lots survive."""
    return (phrase in GENERIC_INTEGRATION and bool(phrase_hits(text, PHYSICAL_SYSTEMS))
            and not phrase_hits(text, DIGITAL_SYSTEMS))


def operational_software_use(text, phrase):
    """Recording fieldwork in a buyer's tool is not delivery of that tool.

    Require both a data-entry action and operational records. Updating software
    itself, or a separate implementation sentence, remains positive evidence.
    """
    if not phrase_hits(text, ("inspection actions", "inspection results", "visit records", "case notes", "inspection records")):
        return False
    if phrase_hits(text, ("software development", "software upgrade", "implement", "develop", "configure", "migrate")):
        return False
    for hit in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
        before = text[max(0, hit.start() - 100):hit.start()]
        if re.search(r"\b(?:updating|recording (?:in|on)|entering (?:in|into)|logging (?:in|into))\s+(?:\w+\s+){0,8}$", before):
            return True
    return False


SOFTWARE_CPV = ("48", "72")
CONTEXT_GUARDS = {
    "salesforce": ("salesforce", "force com", "visualforce", "omnistudio"),
    "external_integration": INTEGRATION,
    "analytics": ("analytics", "business intelligence", "dashboard platform", "crm", "reporting system",
                  "develop", "implement", "build", "development", "implementation"),
    "field_service": ("field service", "workforce", "scheduling software", "work order system", "crm"),
    "sales_revenue": ("crm", "commerce", "sales", "revenue", "subscription", "quotation", "quote"),
    "data": ("customer", "client", "master data", "data quality", "data governance", "data integration"),
    "knowledge": ("knowledge management", "knowledge base", "document intelligence", "artificial intelligence",
                  "ai", "llm", "retrieval", "semantic", "chatbot"),
    "contact_centre": ("customer", "citizen", "patient", "patients", "omnichannel", "contact centre", "contact center", "crm",
                       "helpdesk software", "helpdesk platform", "service desk platform"),
}
# A funding programme that studies AI is not a buyer implementing it. Named
# products stay explicit evidence; a topical mention needs delivery framing.
AI_DELIVERY = ("implementation", "implement", "implementing", "deploy", "deployment", "deploying",
               "procure", "procurement", "purchase", "acquire", "acquisition", "supplier", "vendor",
               "contractor", "licence", "license", "subscription", "chatbot", "ai assistant",
               "ai agent", "virtual assistant", "integrate", "integration", "configure", "configuration")
MANAGEMENT_PROCESS = re.compile(r"\b(?:quality|information security|environmental|health and safety) management systems?\b")


def acronym_case_evidence(quote, phrase):
    """Disambiguate occurrences, without penalising all-capitals procurement titles."""
    for hit in re.finditer(r"(?<!\w)" + re.escape(phrase.upper()) + r"(?!\w)", quote):
        after = search_text(quote[hit.end():hit.end() + 50]).strip()
        # Italian prepositional clauses and the named bidding client are not AI.
        if phrase == "ai" and re.match(r"(?:sensi|fini|cittadini|concorrenti|partecipanti|soggetti|bietercockpit)\b", after):
            continue
        return True
    return False


def affirmed(text, phrase):
    """Ignore only explicit local exclusions, not a whole document containing 'not'."""
    pattern = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)")
    for hit in pattern.finditer(text):
        before, after = text[max(0, hit.start() - 85):hit.start()], text[hit.end():hit.end() + 85]
        if not NEGATED_BEFORE.search(before) and not NEGATED_AFTER.search(after):
            return True
    return False


def has_software(text):
    # A quality-management process/certification is not itself a software system.
    text = MANAGEMENT_PROCESS.sub("management process", text)
    return bool(phrase_hits(text, SOFTWARE)) or bool(re.search(
        r"\b\w+(?:system|systeme|systemen|systemet|systemer|systema|jarjestelma|jarjestelman|plattform|plattformen)\b", text))


def ai_software_delivery(text):
    """Affirmative delivery of an AI application, including a mixed hardware lot."""
    ai_object = r"(?:ai|artificial intelligence|machine learning|generative ai)\s+(?:\w+\s+){0,3}(?:software|application|platform|assistant|agent|chatbot|service)"
    patterns = (r"\b(?:build|develop|implement|deploy|configure|integrate|procure)\w*\s+(?:\w+\s+){0,6}" + ai_object + r"\b",
                r"\b" + ai_object + r"\s+(?:development|implementation|deployment)\b")
    return any(affirmed(text, hit.group()) for pattern in patterns for hit in re.finditer(pattern, text))


def funded_ai_build(text):
    """Research funding can commission real AI tools/models as well as study a topic."""
    pattern = (r"\b(?:build|develop|implement|deploy)\w*\s+(?:\w+\s+){0,12}"
               r"(?:ai|artificial intelligence|machine learning)\s+(?:\w+\s+){0,8}"
               r"(?:tools?|models?|algorithms?|software|applications?|platforms?)\b")
    return any(affirmed(text, hit.group()) for hit in re.finditer(pattern, text))


def paper_application(text):
    return bool(phrase_hits(text, ("investigational new drug", "grant application", "funding application",
        "patent application", "clinical trial application", "drug application"))) and not phrase_hits(text,
        ("software", "digital", "crm", "database", "web application", "application platform"))


def business_application_development(text):
    """Disambiguate each occurrence; scientific computing is not a business app.

    A programme name can contain 'application development' while referring to
    quantum algorithms and scientific discovery. Require both that computing
    context and a scientific objective locally; never exclude a sector wholesale.
    A separate business application occurrence remains usable evidence.
    """
    if paper_application(text):
        return False
    for hit in re.finditer(r"\bapplication development\b", text):
        local = text[max(0, hit.start() - 110):hit.end() + 110]
        quantum = re.search(r"\bquantum (?:computers?|computing|algorithms?)\b", local)
        scientific = phrase_hits(local, ("discovery science", "scientific discovery", "scientific workflows",
                                        "quantum algorithms", "quantum algorithm", "logical qubits", "fault tolerant"))
        business = phrase_hits(local, ("crm", "salesforce", "customer", "business application", "business software",
                                      "enterprise application", "portal", "case management", "workflow automation"))
        if not (quantum and scientific) or business:
            return True
    return False


def evidence_excerpt(quote, phrase):
    tokens = list(re.finditer(r"\w+", quote))
    words = [search_text(token.group()).strip() for token in tokens]
    target = phrase.split()
    for i in range(len(words) - len(target) + 1):
        if words[i:i + len(target)] == target:
            return quote[max(0, tokens[i].start() - 100):tokens[i + len(target) - 1].end() + 100]
    return quote


def capability_hits(cap, segments, software_cpv=False, funding=False):
    if cap["id"] == "pipeline":
        return []
    evidence = []
    for segment in segments:
        text = segment["text"]
        technical = has_software(text) or (funding and cap["id"] in ("ai", "genai") and funded_ai_build(text))
        weak_text = MANAGEMENT_PROCESS.sub("management process", text)
        weak_technical = bool(phrase_hits(weak_text, ("system", "systems", "implementation", "development", "digital")))
        if cap["id"] in {"ai", "genai"} and phrase_hits(text, (
                "computer system for running", "computing system for training", "laptop for processing",
                # Capacity to run a model is a different purchased object from the model.
                "gpu computing resources", "gpu cluster", "inference workloads", "compute resources",
                "υπολογιστικο συστημα", "φορητος υπολογιστης")) and not ai_software_delivery(text):
            continue
        for level, phrases in (("explicit", cap.get("explicit", [])),
                               ("needs", cap.get("needs", []) + cap.get("aliases", [])),
                               ("contextual", cap.get("contextual", []))):
            for phrase in phrase_hits(text, phrases):
                hint_only = False
                if not affirmed(text, phrase) or operational_software_use(text, phrase):
                    continue
                if cap["id"] in ("integration", "external_integration") and physical_integration(text, phrase):
                    continue
                if cap["id"] == "ai" and phrase in ("claude", "gemini"):
                    if not phrase_hits(text, ("ai", "artificial intelligence", "llm", "anthropic", "google ai",
                                              "chatbot", "language model", "generative", "api", "licence", "license",
                                              "subscription", "implementation", "sonnet", "opus", "haiku", "gemini pro", "gemini flash")):
                        if re.search(r"\bClaude\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+\b", segment["quote"]) or phrase_hits(text, ("observatory", "telescope")):
                            continue
                        hint_only = True
                if phrase == "application development" and not business_application_development(text):
                    continue
                if funding and phrase in ("data integration", "data harmonisation", "data harmonization"):
                    if not software_cpv and not phrase_hits(text, ("software", "database", "api", "crm", "platform",
                            "middleware", "information system", "data pipeline", "etl")):
                        continue
                # A foreign-language alias may describe a human service. Software CPV
                # supports a functional phrase, but never proves a tag by itself.
                if level == "needs" and phrase in AMBIGUOUS_NEEDS and not (technical or software_cpv):
                    if not weak_technical:
                        continue
                    hint_only = True
                # Generic data quality/governance also occurs in fieldwork and
                # administrative reporting, including its translated aliases.
                if cap["id"] == "data" and level == "needs" and not (technical or software_cpv):
                    if not phrase_hits(text, ("customer", "client", "master data", "data platform", "data warehouse")):
                        hint_only = True
                if level == "contextual":
                    # A short notice can name AI in its title and nothing else: "RFI AI
                    # Interpreter" has no surrounding technical vocabulary to lean on, and
                    # the case test above already separates the acronym from foreign prose.
                    titled_acronym = (cap["id"] == "ai" and phrase == "ai"
                                      and segment["field"] == "title"
                                      and bool(phrase_hits(text, ("interpreter", "assistant", "agent", "adoption", "pilot",
                                          "services", "service", "platform", "software", "solution", "tool", "implementation")))
                                      and acronym_case_evidence(segment["quote"], phrase))
                    if not (technical or weak_technical or titled_acronym):
                        continue
                    guard = CONTEXT_GUARDS.get(cap["id"])
                    if guard and not phrase_hits(text, guard):
                        continue
                    hint_only |= not technical and not titled_acronym
                    if cap["id"] in ("ai", "genai") and phrase in ("ai", "mcp", "rag"):
                        if not acronym_case_evidence(segment["quote"], phrase):
                            continue
                # A research programme about AI is a lead, not an implementation
                # requirement; keep it reviewable without promoting its priority.
                if (funding and cap["id"] in ("ai", "genai") and level != "explicit"
                        and not ai_software_delivery(text) and not funded_ai_build(text)
                        and not any(affirmed(text, p) for p in phrase_hits(text, AI_DELIVERY))):
                    hint_only = True
                evidence.append({"capability": cap["id"], "phrase": phrase, "strength": "hint" if hint_only else level,
                                 "basis": segment["basis"], "field": segment["field"], "quote": segment["quote"]})
        if cap["id"] == "relationships" and re.search(
                r"\b(?:stakeholder|constituent|member|donor|volunteer|customer|client|coalition|tenant|resident)s?\b"
                r".{0,120}\bdatabase\b|\bdatabase\b.{0,120}"
                r"\b(?:stakeholder|constituent|member|donor|volunteer|customer|client|coalition|tenant|resident)s?\b", text):
            if phrase_hits(text, ("management", "manage", "tracking", "communication", "engagement", "contacts")):
                if not phrase_hits(text, ("permanent resident", "citizenship eligibility", "eligible applicants")):
                    evidence.append({"capability": cap["id"], "phrase": "relationship-management database",
                                     "strength": "needs", "basis": segment["basis"], "field": segment["field"],
                                     "quote": segment["quote"]})
    return evidence


def unrelated_supply(title, text, evidence, cpv_codes=()):
    """Only positively identified supplies; no inference from absent tags alone."""
    hardware = phrase_hits(title, ("servers", "server hardware", "serverbeschaffung", "backup appliance",
        "storage system", "storage systems", "storage hardware", "it infrastructure", "network equipment",
        "computer equipment", "computer hardware", "laboratory equipment", "electronic equipment", "supply of equipment",
        "chiller replacement", "chillier replacement", "προμηθεια εξοπλισμου", "special vehicles",
        "antivirus software", "supply of firewall", "network switches", "laptop computers", "desktop computers",
        "πληροφοριακων υποδομων", "διακομιστων", "δικτυακου εξοπλισμου", "ηλεκτρονικου εξοπλισμου"))
    licences = phrase_hits(title, ("microsoft licences", "microsoft licenses", "microsoft software licences",
        "microsoft software licenses", "software assurance microsoft", "siem licences", "siem licenses",
        "microsoft lizenzen", "αδειων microsoft", "αδειων λογισμικου microsoft"))
    if phrase_hits(title, ("firewall", "firewalls", "cortafuegos")) and phrase_hits(title,
            ("licences", "licenses", "licencias", "lizenzen")):
        licences.append("firewall licences")
    generic_supply = {"it infrastructure", "supply of equipment", "προμηθεια εξοπλισμου", "πληροφοριακων υποδομων"}
    if hardware and set(hardware) <= generic_supply:
        physical_codes = any(code.startswith(("30", "32", "34", "35", "38", "39", "4882")) for code in cpv_codes)
        physical_details = phrase_hits(text, ("servers", "laptops", "computers", "network switch", "storage hardware",
                                              "διακομιστες", "φορητοι υπολογιστες"))
        if not physical_codes and not physical_details:
            hardware = []
    # A CRM platform purchase, an AI implementation or an independently described
    # application lot remains addressable even when hardware/licences are included.
    addressable = any(e["strength"] != "contextual" and (
        e["capability"] in {"salesforce", "crm", "service", "relationships", "portals", "workflow", "sales_revenue",
                             "marketing", "integration", "industry", "field_service"}
        or (e["capability"] in {"ai", "genai", "automation", "knowledge"} and phrase_hits(search_text(e["quote"]),
            ("implementation", "implement", "development", "develop", "chatbot", "ai assistant", "ai agent",
             "virtual assistant", "υλοποιηση", "αναπτυξη", "integrazione", "desarrollo", "entwicklung")))
        ) for e in evidence)
    if hardware and phrase_hits(title, ("support", "services", "service", "consulting", "υπηρεσιες", "dienstleistungen")):
        hardware = []
    connectivity = phrase_hits(title, ("broadband network", "fibre network", "fiber network", "leased fibre",
        "gigabit netz", "gigabit netzes", "breitband", "breitbandanbindung", "glasfasernetz",
        "fiberforbindelser", "rete in fibra ottica", "red de fibra optica", "δικτυο οπτικων ινων"))
    network_scope = phrase_hits(title + text, ("construction", "installation", "network operator", "leased",
        "errichtung", "aufbau", "betrieb", "ausbau", "netzbetreiber", "anbindung", "hyrda",
        "costruzione", "construccion", "κατασκευη"))
    network_codes = any(code.startswith(("6421", "724110", "324")) for code in cpv_codes)
    if connectivity and (network_scope or network_codes) and not addressable:
        return "Network connectivity or broadband infrastructure without a stated business-application or AI delivery scope."
    building = phrase_hits(title, ("school", "building", "schule", "grundschule", "gebaude"))
    construction = phrase_hits(title, ("renovation", "refurbishment", "sanierung", "neubau", "umbau"))
    if building and construction and not addressable:
        return "Building renovation without a separately stated business-application or AI delivery scope."
    if (hardware or licences) and not addressable:
        return "Hardware, infrastructure or licence supply without a stated CRM, business-application or AI delivery scope."
    return None
