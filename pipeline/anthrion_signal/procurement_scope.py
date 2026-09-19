"""Conservative exclusions of a purchased deliverable, never a sector word blacklist.

A rule needs a specific purchased object AND corroborating scope/classification.
Description-led rules require explicit service provision, not just a topic. Any
separately stated application/AI deliverable protects mixed procurements. Unrecognised
or sparse scope remains a candidate. Original and exact-hash English use the same rules.
"""
import re

from .capability_matching import (GENERIC_INTEGRATION, affirmed, ai_software_delivery, business_application_development, operational_software_use,
                                  physical_integration, procedural_system)
from .vocabulary import phrase_hits

DIGITAL_SERVICE_OBJECTS = ("website maintenance", "website hosting", "software testing")
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
    "learning management system", "document management system", "records management system",
    "asset management system", "human resources management system", "payroll system",
    "financial management system", "enterprise resource planning", "dashboard development",
    "it platform", "saas based platform", "software platform", "digital platform",
    "technology support services", "it support services", "computer systems", "reporting system",
    "data space", "data spaces", "software components",
) + DIGITAL_SERVICE_OBJECTS
DELIVERY = re.compile(r"\b(?:develop\w*|deploy\w*|moderni[sz]\w*|consolidat\w*|implement\w*|build\w*|creat\w*|design\w*|deliver\w*|provi\w*|"
                      r"procur\w*|purchas\w*|suppl\w*|configur\w*|integrat\w*|migrat\w*|replac\w*|"
                      r"maintain\w*|maintenance|support|evolution|requires?|seeking|commission\w*|"
                      r"includes?|including|comprises?|comprising|supplemented by|"
                      r"entwicklung|beschaffung|implementierung|sviluppo|fornitura|desarrollo|suministro)\b")
INCIDENTAL = re.compile(r"\b(?:already (?:use|uses|using|have)|existing (?:supplier|contractor) portal|"
                        r"submit\w* (?:your |the |a )?(?:bid|tender|proposal)|using (?:our|the authority s)|"
                        r"must use (?:our|the authority s))\b")

# Bind the action to its software object through grammatical connectors. Arbitrary
# intervening words incorrectly turn equipment accessories, licence entitlements
# and numbered specification headings into commissioned software development.
NATIVE_SOFTWARE_DELIVERY = tuple(re.compile(
    rf"\b(?P<action>{action})\s+(?:(?:{connectors})\s+){{0,7}}"
    rf"(?P<object>{objects})\b") for action, connectors, objects in (
    (r"developpement|deploiement|fourniture|integration|maintenance|hebergement",
     r"de|d|du|des|un|une|le|la|les|et|nouveau|nouvelle|nouveaux|nouvelles",
     r"logiciels?|solution logicielle|solution saas|applications? informatiques?|portail(?: usager)?|outil numerique"),
    (r"implementatie|ontwikkeling|levering|onderhoud|migratie",
     r"van|de|het|een|en|nieuwe|nieuw|hosting|belasting",
     r"software|(?:belasting)?applicatie|applicaties|klantenportaal|burgerportaal|crm platform"),
    (r"entwicklung|implementierung|beschaffung|lieferung|wartung",
     r"von|einer|eines|einem|einen|der|die|das|des|den|und|sowie|hosting|neuer|neuen|neue|"
     r"individueller|individuelle|individuellen|kundenspezifischer|kundenspezifischen|eigener|eigenen",
     r"software|applikationen|anwendungen|kundenportals?|burgerportals?|crm plattform"),
    (r"sviluppo|fornitura|implementazione|integrazione|manutenzione",
     r"di|una|un|uno|della|delle|del|dello|dei|degli|ed|e|nuove|nuovi|nuova|nuovo",
     r"software|piattaforma|applicazioni|portale (?:clienti|cittadini)"),
    (r"desarrollo|suministro|implantacion|implementacion|integracion|mantenimiento",
     r"de|del|la|las|el|los|un|una|unos|unas|y|soporte|tecnico|nueva|nuevas|nuevo|nuevos",
     r"software|plataforma|aplicaciones|aplicacion informatica|portal (?:ciudadano|de clientes)"),
    (r"αναπτυξη|υλοποιηση|εγκατασταση|παραδοση|συντηρηση",
     r"του|τησ|των|μιασ|νεου|νεασ|και|ψηφιακησ",
     r"λογισμικου|εφαρμογησ|εφαρμογων|πλατφορμασ|ψηφιακησ πυλησ|crm"),
))
NATIVE_DIGITAL_CONTEXT = (
    "software", "logiciel", "logicielle", "informatique", "informatica", "informatico", "informatiche",
    "digital", "digitale", "numerique", "saas", "crm", "web", "online", "en ligne", "ψηφιακησ",
    "gestion des dossiers", "gestion des demandes", "gestion des clients", "gestione dei clienti",
    "gestione delle pratiche", "gestione dei casi", "gestionar clientes", "gestionar expedientes",
    "gestion de clientes", "gestion de expedientes", "διαχειριση υποθεσεων", "διαχειριση πελατων",
    "gestion de datos", "gestionar los clientes", "kundenportal", "kundenportals", "burgerportal",
    "klantenportaal", "burgerportaal", "dossiers", "databases", "database", "informatiker",
    "aplicaciones empresariales", "aplicaciones de negocio", "applicazioni aziendali",
)
NATIVE_IMPLEMENTATION = re.compile(r"^(?:developpement|deploiement|integration|implementatie|ontwikkeling|migratie|"
                                   r"entwicklung|implementierung|sviluppo|implementazione|integrazione|"
                                   r"desarrollo|implantacion|implementacion|integracion|αναπτυξη|υλοποιηση)$")
NATIVE_LICENCE = re.compile(r"\b(?:licen[cs]\w*|lizenz\w*|lizenzen|licenz\w*|αδειων|αδεια|software assurance)\b")


def native_equipment_bundle(text):
    """A supplied appliance and its controls, rather than separately built software."""
    return bool(
        re.search(r"\bsoftware\s+(?:asociado|asociada|integrado|embebido|mitgeliefert|beiliegend)\b", text)
        or (re.search(r"\b(?:suministro|instalacion|alquiler|mantenimiento|disponibilidad)\b", text)
            and re.search(r"\b(?:equipos de reprografia|mupis|lavavajillas|sistema de riego)\b", text))
    )


def transaction_software_component(text):
    """An explicitly ordered business-system component in a coordinated lot.

    Greek genitive lists can place another component between the purchase verb
    and the software noun. Require both that software noun and a transaction or
    records function; a control system, paper administration or tool use fails.
    Callers already separate description sentences and semicolon-delimited lots.
    """
    pattern = (r"\b(?:προμηθεια|εγκατασταση|αναπτυξη|υλοποιηση)"
               r"(?P<between>(?:\s+\w+){0,16}?)\s+"
               r"λογισμικου\s+συστηματοσ\s+(?:διαχειρισησ|εκδοσησ|καταγραφησ|παρακολουθησησ)\s+"
               r"(?:παραγγελιων|τιμολογιων|κουπονιων|πληρωμων|υποθεσεων|αιτησεων|πελατων|εγγραφων)\b")
    for hit in re.finditer(pattern, text):
        before = text[max(0, hit.start() - 90):hit.start()]
        if re.search(r"\b(?:χρηση|χρησιμοποι\w*|υφισταμεν\w*|ενσωματωμεν\w*|συνοδευ\w*|με|χωρισ)\b", hit["between"]):
            continue
        if re.search(r"\bχωρισ\s+(?:\w+\s+){0,4}$", before):
            continue
        if affirmed(text, hit.group()) and not INCIDENTAL.search(text):
            return hit.group()
    return None


def native_software_delivery(text, title_context=""):
    """Find an affirmative purchased software object, preserving mixed lots."""
    for pattern in NATIVE_SOFTWARE_DELIVERY:
        for hit in pattern.finditer(text):
            before = text[max(0, hit.start() - 100):hit.start()]
            after = text[hit.end():hit.end() + 100]
            local = hit.group() + after
            implementation = bool(NATIVE_IMPLEMENTATION.fullmatch(hit.group("action")))
            # Reselling entitlements and maintaining manufacturer licences are
            # not implementation. A separate development/integration statement
            # is checked independently and can still protect a mixed contract.
            if not implementation and NATIVE_LICENCE.search(before + local):
                continue
            if not implementation and native_equipment_bundle(before + local + " " + title_context):
                continue
            # Applications can mean uses of a drug or manufacturing process.
            # Require local IT/business meaning instead of treating that noun
            # alone as software, while preserving precise software objects.
            if hit.group("object") in ("anwendungen", "aplicaciones", "applicazioni", "εφαρμογησ", "εφαρμογων"):
                if not phrase_hits(before + local, NATIVE_DIGITAL_CONTEXT):
                    continue
            if hit.group("object") in ("piattaforma", "plataforma", "πλατφορμασ", "portail"):
                # A lifting platform or metal gate is a physical object even if
                # its controls use software. A separate software lot still wins.
                if re.match(r"\s+(?:aerea|elevadora|elevatrice|offshore|di sollevamento|de elevacion|"
                            r"metallique|coulissant|battant|en metal|en acier|en aluminium|ανυψωσησ)\b", after):
                    continue
                if not phrase_hits(local, NATIVE_DIGITAL_CONTEXT):
                    continue
            # Normalisation folds Greek final sigma to sigma. Include that form
            # and Dutch negatives beyond the shared affirmative-scope guard.
            if re.search(r"\b(?:zonder|geen|χωρισ)\s+(?:\w+\s+){0,4}$", before):
                continue
            if phrase_hits(hit.group(), ("sans", "ohne", "kein", "keine", "keinen", "sin", "senza",
                                         "zonder", "geen", "χωρις", "δεν περιλαμβανει")):
                continue
            # Delivering equipment *for using* software, or executing fieldwork
            # *with existing* software, does not purchase that software itself.
            if re.search(r"\b(?:utilis(?:er|ant|ent)|utiliz(?:ar|ando|an)|utilizz(?:are|ando|ano)|usando|"
                         r"voor gebruik|gebruik van|zur nutzung|zum einsatz|per usare|para ejecutar|"
                         r"για χρηση|με χρηση|a l aide)\b", hit.group()):
                continue
            if (re.search(r"\b(?:avec|mit|con|met|με)\s+(?:\w+\s+){0,3}" + re.escape(hit.group("object")) + r"$", hit.group())
                    and phrase_hits(local, ("existant", "existante", "vorhandener", "bestehender", "esistente",
                                            "existente", "bestaande", "υφισταμενου"))):
                continue
            # A contractor using an existing tool does not buy its implementation.
            if re.search(r"\b(?:utilisant|utilizando|utilizzando|gebruik van|χρηση)\s+(?:\w+\s+){0,3}$", before):
                continue
            if affirmed(text, hit.group()) and not INCIDENTAL.search(text):
                return hit.group()
    return transaction_software_component(text)


def information_system_connection(text):
    connection = re.search(r"\b(?:it connection\b.{0,70}\binformation system|"
                           r"conexion informatica\b.{0,70}\bsistema de informacion)\b", text)
    return bool(connection and affirmed(text, connection.group()) and not INCIDENTAL.search(text))


def physical_payment_equipment(text, phrase):
    return phrase == "cashless parking" and bool(phrase_hits(text, ("parking machines", "parking meters")))


def addressable_delivery(segments):
    """Return positive quoted scope, not a capability inferred from an industry/CPV."""
    title_context = " ".join(s["text"] for s in segments if s["field"] == "title")
    for segment in segments:
        text = segment["text"]
        if (ai_software_delivery(text) and not INCIDENTAL.search(text)) or information_system_connection(text):
            return segment
        # Purchasing/developing software is positive scope even for an unfamiliar
        # domain. Merely requiring a contractor to use software is not.
        delivered_software = re.search(r"\b(?:develop|build|implement|create|maintain)\w*\s+(?:\w+\s+){0,7}"
                                      r"(?P<object>software|platform|web application|information system)\b", text)
        if (delivered_software and affirmed(text, delivered_software.group()) and not INCIDENTAL.search(text)
                and not operational_software_use(text, delivered_software.group("object"))):
            return segment
        if native_software_delivery(text, title_context):
            return segment
        # An AI service is a delivery signal even in a physical industry. The
        # hardware's capacity to run a model is a different purchased object.
        ai_service = re.search(r"\b(?:ai|artificial intelligence)\b.{0,60}\b(?:service|software|platform|assistant|solution|tool)\b", text)
        if ai_service and affirmed(text, ai_service.group()) and segment["field"] == "title" and not re.search(r"\b(?:server|hardware|equipment|appliance)\b", text):
            return segment
        hits = [p for p in phrase_hits(text, BUSINESS_OBJECTS)
                if affirmed(text, p) and not physical_integration(text, p, title_context)
                and (p != "application development" or business_application_development(text))
                and not operational_software_use(text, p) and not physical_payment_equipment(text, p)
                and not procedural_system(text, p)
                and (p not in ("computer systems", *DIGITAL_SERVICE_OBJECTS) or business_system_scope(text, p))]
        if set(hits) <= {"language model"} and re.search(r"\b(?:server|hardware|computer|gpu)\b", text):
            hits = []
        if not hits:
            continue
        if segment["field"] == "title":
            return segment
        # "Integration" inside the matched noun cannot be its own delivery verb:
        # an event aimed at companies offering system integration buys an event.
        delivered = any(p not in GENERIC_INTEGRATION or DELIVERY.search(text.replace(p, " ")) for p in hits)
        # These phrases name purchased technical work themselves, including
        # support/testing lots that do not commission a new implementation.
        service = any(p in DIGITAL_SERVICE_OBJECTS for p in hits)
        if delivered and (DELIVERY.search(text) or service) and not INCIDENTAL.search(text):
            return segment
    return None


# Title, corroborating description, CPV support. Neither a CPV nor a word in an
# unrelated paragraph can trigger exclusion by itself. This is a taxonomy of work.
RULES = (
    ("ai_compute_capacity", r"\bai system\b",
     r"\b(?:artificial intelligence computing system|gpu computing resources|gpu cluster)\b",
     (), "Computing capacity and its bundled software rather than an AI application"),
    ("industrial_efficiency", r"\b(?:pump optimi[sz]ation|aeration efficiency|wastewater testing)\b",
     r"\b(?:pumping|aeration|site based testing|water samples|sampling|operational assets)\b",
     ("421", "71314", "716"), "Physical plant efficiency testing or wastewater sampling"),
    ("infrastructure_advice", r"\b(?:independent technical advis\w*|construction consultancy|"
     r"highways and infrastructure professional services|land management professional services|"
     r"building consultancy services|construction consultant)\b",
     r"\b(?:reservoir|construction|civil engineering|building surveying|riba|highways|land acquisition)\b",
     (), "Engineering or surveying advice for physical infrastructure"),
    ("legal_insurance", r"\b(?:legal advisory|legal advice|legal counsel|employment law|liability insurance|"
     r"insurance broker|insurance brokerage|legal services|asesoramiento juridico|seguro de responsabilidad)\b",
     r"\b(?:legal|law|insurance|claims|juridico|letrado|seguro|liability)\b",
     ("66", "791"), "Legal representation or insurance services"),
    ("employment_support", r"\b(?:employment orientated case management|employment oriented case management|"
     r"beschaftigungsorientiertes fallmanagement|work focused activities)\b",
     r"\b(?:parents|erziehende|jobcentre|employment|training|social|fallmanagement)\b",
     ("80", "85"), "Human employment support or coaching services"),
    ("industrial_equipment", r"\b(?:welding|high voltage equipment|switchgear|"
     r"laboratory instruments?|chromatographic instrument|particle size and shape analyser|"
     r"handheld analysis instrument|miniprobe|thermal offset plates|heat pump)\b",
     r"\b(?:equipment|instrument|laboratory|hardware|voltage|supply|suministro|installation|welding|pump)\b",
     ("30", "31", "33", "38", "42", "44", "45"), "Specialist physical equipment or consumables"),
    ("laboratory_incubator", r"\bincubators?\b",
     r"\b(?:cell culture|incubation temperature|laboratory equipment|neonatal)\b",
     ("3315", "380"), "Laboratory or clinical incubation equipment"),
    ("printed_content", r"\b(?:ebook subject collections|foreign periodicals|books and media for the library|"
     r"books and teaching aids|printed teaching aids)\b",
     r"\b(?:subscription|access|copyright|publisher|publications|printed|books|periodicals)\b",
     ("22", "7998"), "Access to published books or journals rather than delivery of a digital system"),
    ("physical_security", r"\b(?:security and reception services|surveillance service|video control system|"
     r"modernisation of physical security systems|electronic door locks)\b",
     r"\b(?:guard|guards|cctv|camera|cameras|locking|locks|cabling|physical security)\b",
     ("351", "445", "453", "506", "7971"), "Physical security, cameras or access hardware"),
    ("physical_works", r"\b(?:scaffolding|roofing|roof insulation|construction auxiliary services|"
     r"construction support services|new construction of|general refurbishment|"
     r"nature restoration designs|remedial works survey|sailing vessel|wastewater treatment plant)\b",
     r"\b(?:construction|building|installation|works|renovation|refurbishment|ecology|habitat|"
     r"docking|rigging|scaffolding|riba)\b", ("45", "50", "71"),
     "Physical construction, refurbishment, engineering or ecological works"),
    ("physical_it_supply", r"\b(?:supply of it equipment|it equipment supply|supply of computers|"
     r"procurement of it equipment|supply of switches|supply of cameras|supply of firewalls|"
     r"supply of a server|supply of basic it hardware|desktop computers?|desktop computer systems|"
     r"hardware for hybrid video|multi function (?:machines|devices)|multifunction device|"
     r"hardware components|data centre infrastructure equipment|server infrastructure.{0,40}(?:expansion|upgrade)|"
     r"expansion of the server infrastructure|procurement of gpu computing resources)\b",
     r"\b(?:hardware|equipment|devices|server|servers|computers|licences|licenses|supply|purchase|gpu|printing)\b",
     ("30", "32", "48"), "Physical IT, printing or compute capacity supply"),
    ("native_it_hardware", r"\b(?:suministro|compra|adquisicion) de (?:equipos|equipamiento|material) informatico\b",
     r"\b(?:ordenadores|portatiles|dispositivos electronicos|hardware)\b", (),
     "Physical IT equipment purchased to run existing applications"),
    ("quantum_computer_delivery", r"\bquantum\b",
     r"\b(?:build\w*|develop\w*|deploy\w*|manufactur\w*|scaling)\b.{0,100}"
     r"\b(?:fault tolerant.{0,60}quantum comput\w*|quantum hardware|quantum computer\w*.{0,60}logical qubits)\b",
     (), "Development or scaling of specialist quantum computing hardware"),
    ("parking_equipment", r"\b(?:cashless parking machines|parking meters)\b",
     r"\b(?:refurbishment|purchase|units|supply|hardware|equipment)\b", ("3873",),
     "Physical parking payment equipment"),
    ("occupational_safety", r"\b(?:occupational safety specialist|occupational health (?:physician|services)|health and safety adviser|safety officer|"
     r"company health services|employee counselling|employee assistance program\w*)\b",
     r"\b(?:physician|workplace|hazards?|safety|inspections|risk assessment|counselling|employee assistance|hse)\b", ("71317", "851", "79417"),
     "Occupational health or workplace safety services"),
    ("survey_coding", r"\b(?:(?:sic(?: and soc)?|soc|occupational|industrial) coding|coding of.*survey)\b",
     r"\b(?:classification|survey responses|occupational information|coding)\b", ("7233", "7931"),
     "Coding or classification of survey responses as a service"),
    ("business_promotion", r"\b(?:business engagement consultancy|business development consultancy|investment promotion services|business trip)\b",
     r"\b(?:industry partners|industry funding|value propositions|promote|investors|marketing|business contacts|travel profile|specialist conference)\b", ("7941", "7999"),
     "Business promotion or partnership development consultancy"),
    ("physical_it_installation", r"\b(?:digital modernisation|digital modernization|digitale modernisierung)\b",
     r"\b(?:supply of items|lieferung von gegenstanden)\b.{0,120}\b(?:servers?|nw server|wlan|access points)\b",
     (), "Supply and installation of physical IT infrastructure"),
    ("field_surveys", r"\b(?:bird survey|breeding and resting bird|tree surveys?|sediment coring|"
     r"geotechnical survey|ecological survey|environmental surveys|asbestos census|crane condition survey|rastvogelerfassung|"
     r"monitoring of birds|surveys for peatland|canine samples)\b",
     r"\b(?:sampling|samples|sediment|vibrocorer|on foot|habitats?|species|asbestos|crane|vogelschutz|peatland|birds)\b", ("71", "90", "7931"),
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
     r"windows|oracle|sap|sophos|arcsight|fortinet|trellix|trend ai)\b.*\b(?:licen[csz]\w*|subscription\w*|renewal|extension|verlangerung)\b|"
     r"\b(?:licen[csz]\w*|subscription\w*|renewal|extension|verlangerung)\b.*\b(?:microsoft|adobe|acrobat|vmware|citrix|autodesk|"
     r"veeam|commvault|red hat|windows|oracle|sap|sophos|arcsight|fortinet|trellix|trend ai)\b",
     r"\b(?:licen[csz]\w*|subscription\w*|renewal|renew|rights of use|lizenzen)\b", ("48", "72"),
     "Resale or renewal of unrelated product licences"),
    ("property_valuation", r"\b(?:property valuation services|land and property valuation|appraisal of real estate|asset valuations?|"
     r"consultancy services strategic property development)\b",
     r"\b(?:properties|property|land|valuation|valuations|appraisal|estates)\b", ("70", "71", "7941"), "Property appraisal services"),
    ("financial_audit", r"\b(?:internal audit services|financial audits|audit of the proof of use|reinsurance broker)\b",
     r"\b(?:financial|accounting|audit|audits|insurance)\b", ("66", "792", "7941"), "Financial audit or insurance services"),
    ("creative_agency", r"\b(?:creative agency|marketing and communications services|communication and marketing services|"
     r"brand process and production of campaign|public relations work|pr agency services|"
     r"public relations.*consultancy|brand strategy and rebranding|strategic communication agency)\b",
     r"\b(?:advertising|copy writing|copywriting|media|campaign|brand|public relations)\b", ("793", "79413"),
     "Creative, advertising or public relations services"),
    ("survey_execution", r"\b(?:tenant survey(?: services)?|online panel survey services|audience research services|"
     r"market research (?:services|studies)|employee survey at|residents survey|stakeholder research|"
     r"population survey service|qualitative survey|eurobarometer surveys|implementation of survey studies|"
     r"durchfuhrung der feldarbeiten|realizacion de estudios de opinion)\b",
     r"\b(?:interviews|questionnaires|respondents|survey|surveys|fieldwork|participants|research|"
     r"stichprobenziehung|befragung|offener antworten|encuestas|personas entrevistadas|cuestionario)\b",
     ("7931", "7932"), "Execution of surveys or market research"),
    ("native_physical_engineering", r"\b(?:servizi di ingegneria e architettura|ispezioni speciali)\b",
     r"\b(?:ponti|viadotti|cavalcavia|sottovia|autostrada)\b", (),
     "Engineering or safety inspection of physical transport infrastructure"),
    ("traffic_engineering_studies", r"\bingenierie (?:de|du) trafic\b",
     r"\b(?:etude|etudes|diagnostic|mesure)\b", (),
     "Traffic engineering studies, diagnosis or measurement"),
    ("archaeologist_services", r"\b(?:archaeologist services|archaeological services)\b",
     r"\b(?:flood relief|drainage|excavation|archaeological fieldwork)\b", (),
     "Archaeologist services for physical works or fieldwork"),
    ("grant_programme_advice", r"\basistencia tecnica\b.{0,180}\bconvocatorias de ayudas\b",
     r"\b(?:identificacion|elaboracion|gestion|seguimiento)\b", ("79411",),
     "Consultancy to identify, prepare or administer grant calls and projects"),
    ("specialist_physical_advice", r"\b(?:nuclear security|nukl(?:ae|æ)r security|agricultural consultancy|property technical consultancy)\b",
     r"\b(?:nuclear material|atomic installations|radiation protection|used fuel|agricultural production|building inspectors?|structural engineers?)\b",
     (), "Specialist advice on physical assets, radiation safety or agricultural production"),
    ("industry_representation", r"\bdelegates? for\b",
     r"\b(?:represent the uk|primary liaison|executive committee|industry and academia)\b",
     (), "Industry representation and liaison rather than delivery of a digital system"),
    ("fitness_equipment", r"\bfitness equipment\b",
     r"\b(?:spinning bicycles|elliptical machines|free weights|multigym|gymnasium|exercise machines)\b",
     ("374",), "Physical fitness equipment and servicing"),
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


def description_service_exclusion(segments, cpv_codes):
    """Explicit purchased services when a title is opaque or names a programme.

    Neither an HR/energy topic nor a consultancy CPV alone is an exclusion. The
    scope must say what the supplier is to do; digital delivery is checked first.
    """
    titles = [s for s in segments if s["field"] == "title"]
    scope_text = " ".join(s["text"] for s in segments)
    for detail in (s for s in segments if s["field"] == "description"):
        text = detail["text"]
        hr_service = phrase_hits(text, ("παροχη συμβουλευτικων υπηρεσιων",))
        hr_programme = re.search(
            r"\bπρογραμματοσ προσληψεων και ενταξησ ανθρωπινου δυναμικου\b", text)
        if (hr_service and hr_programme and affirmed(text, hr_service[0])
                and any(str(code).startswith("79414") for code in cpv_codes)):
            return {"rule": "hr_programme_consultancy", "reason": "Human recruitment and onboarding programme consultancy without separately stated software delivery.",
                    "basis": detail["basis"], "title": titles[0]["quote"] if titles else "", "quote": detail["quote"]}
        support = re.search(r"\b(?:objective of (?:this|the) contract|provide|providing|provision of)\b"
                            r".{0,100}\badministrative and logistical support\b", text)
        programme_title = next((s for s in titles if re.search(
            r"\bimplementation of\b.{0,100}\b(?:initiative|programme|program|action plan)\b", s["text"])), None)
        if (support and programme_title and affirmed(text, support.group())
                and phrase_hits(scope_text, ("regulatory framework",))
                and phrase_hits(scope_text, ("stakeholder consultation", "stakeholder forum", "policy coordination"))):
            return {"rule": "programme_policy_support", "reason": "Administrative and logistical support for a policy programme without separately stated software delivery.",
                    "basis": detail["basis"], "title": programme_title["quote"], "quote": detail["quote"]}
    return None


def scope_exclusion(segments, cpv_codes):
    if addressable_delivery(segments):
        return None
    scope_text = " ".join(s["text"] for s in segments)
    # Some multi-category DPS notices explicitly define their selectable services
    # by CPV. A legal/engineering category must not erase their IT categories.
    if (phrase_hits(scope_text, ("dynamic purchasing system", "dps"))
            and phrase_hits(scope_text, ("cpv categories", "cpv codes", "cpv classifications"))
            and any(str(code).startswith("72") for code in cpv_codes)):
        return None
    if (phrase_hits(scope_text, ("digital teaching aids", "digital learning materials"))
            and any(str(code).startswith(("4816", "4819")) for code in cpv_codes)):
        return None
    if (phrase_hits(scope_text, ("dynamic purchasing system", "dps", "sistema dinamico de adquisicion", "sistema dinamico de adquisiciones"))
            and phrase_hits(scope_text, ("software",)) and any(str(code).startswith("48") for code in cpv_codes)):
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
                    r"\b(?:implementation|integration|migration|conversion|converting|convert|development|configuration|customisation|professional services|managed services|"
                    r"implementierung|integration|migration|entwicklung|konfiguration|implementacion|integracion|"
                    r"migracion|desarrollo|configuracion|servicios profesionales|implementazione|integrazione|migrazione|"
                    r"conversione|configurazione|personalizzazione|umstellung|sviluppo)\b", s["text"])
                    ):
                continue
            detail = next((s for s in segments if s["field"] == "description"
                           for match in detail_pattern.finditer(s["text"])
                           if key != "quantum_computer_delivery" or affirmed(s["text"], match.group())), None)
            if detail or any(str(code).startswith(prefixes) for code in cpv_codes):
                return {"rule": key, "reason": f"{label} without a separately stated business-application, Salesforce or AI delivery scope.",
                        "basis": title["basis"], "title": title["quote"],
                        "quote": (detail or title)["quote"]}
    return description_service_exclusion(segments, cpv_codes)


def generic_digital_scope(segments):
    """Recall route for sparse but explicit digital delivery, without fabricated tags."""
    scope_text = " ".join(s["text"] for s in segments)
    title_context = " ".join(s["text"] for s in segments if s["field"] == "title")
    phrases = ("digital and it professional services", "it consultancy", "it consultants", "ict consultants",
               "it systems", "software testing", "software engineering",
               "ai adoption", "ai pilots", "remote patient monitoring", "digital delivery capability",
               "digital and technology delivery services", "digital data and technology",
               "digital service lifecycle", "digital products and services",
               "software configuration", "software customisation", "software customization",
               "cashless parking", "digital payment services", "digital delivery services",
               "online learning platform", "incident management system", "clinical patient management system",
               # Web estate and named business systems. Each states a built or maintained
               # digital deliverable; a generic "digital" or "solution" still does not.
               "website development", "website design", "website relaunch", "website redesign",
               "website maintenance", "website hosting", "web development", "web portal",
               "internet portal", "open data portal", "transparency portal",
               "content management system", "learning management system", "document management system",
               "records management system", "record management system", "records management solution",
               "record management solution", "patient record management", "asset management system",
               "computer application", "it platform", "saas based platform", "software platform",
               "technology support services", "it support services", "computer systems",
               # Native-language recall is separate from named-vendor tagging.
               "servicios informaticos", "estructura informatica", "sistemas fisicos y logicos",
               "seguridad informatica", "aplicacion informatica", "aplicaciones informaticas",
               "plataforma informatica", "escritorios virtuales", "sistema de gestion de turnos", "sistemas de gestion de turnos",
               "solucion de laboratorios", "data space", "data spaces",
               "quality management system", "enterprise architecture management system",
               "digital workplace", "epos system", "point of sale system",
               # Named business systems that are bought as software rather than as a
               # service. Industrial control (SCADA, telemetry) is deliberately absent,
               # and so are "procurement system", "online portal" and "intranet": those
               # name the e-tendering platform or a publication channel far more often
               # than a purchased deliverable.
               "notification system", "ordering system", "booking system", "scheduling system",
               "reporting system", "registration system", "ticketing system", "archive system",
               "contract management system", "invoicing system", "billing system",
               "rostering system", "referral tool",
               "self service portal", "customer portal", "citizen portal", "tenant portal")
    matches = [p for s in segments for p in phrase_hits(s["text"], phrases)
                             if affirmed(s["text"], p) and not physical_payment_equipment(s["text"], p)
                             and business_system_scope(s["text"], p, scope_text)
                             and not operational_software_use(s["text"], p) and not procedural_system(s["text"], p)]
    # A stated software interface can be subcontractable even when the principal
    # lot buys equipment. Do not turn the generic word "informatica" into a brand
    # tag, or lose the separately published information-system connection.
    for segment in segments:
        text = segment["text"]
        if information_system_connection(text):
            matches.append("information-system connection")
        if native_software_delivery(text, title_context):
            matches.append("native-language software delivery")
        # Explicit maintenance of central computer systems can include hardware
        # and software. That broad IT service is different from appliance supply.
        system_support = re.search(r"\bmantenimiento y soporte tecnico del hardware y software de los sistemas informaticos\b", text)
        if system_support and affirmed(text, system_support.group()):
            matches.append("computer-system maintenance")
        assistance = re.search(r"\b(?:asistencia|soporte)\s+(?:tecnica\s+(?:material e\s+)?)?informatica\b", text)
        if assistance and affirmed(text, assistance.group()) and not INCIDENTAL.search(text):
            matches.append("IT assistance")
    return list(dict.fromkeys(matches))


def business_system_scope(text, phrase, scope_text=""):
    """Ambiguous system names need digital context; concrete software remains eligible."""
    if phrase == "computer systems" and not re.search(
            r"\b(?:support|administration|maintenance|consultancy|develop\w*|implement\w*|configur\w*|integrat\w*)\b", text):
        return False
    if phrase == "solucion de laboratorios" and not phrase_hits(text, ("aulas de informatica", "laboratorios virtuales")):
        return False
    if (phrase == "seguridad informatica"
            and phrase_hits(scope_text or text, ("acciones formativas", "itinerarios formativos", "imparticion", "curso"))
            and not re.search(r"\b(?:servicios?|contrato|soporte|mantenimiento|desarrollo|implantacion)\b", text)):
        return False
    if (phrase == "notification system"
            and phrase_hits(text, ("alert interested parties", "program announcements", "programme announcements"))
            and not re.search(r"\b(?:build\w*|develop\w*|implement\w*|procur\w*|replac\w*|maintain|maintenance)\b", text)):
        return False
    # Ordering goods through the supplier's tool does not buy that tool. Check each
    # occurrence so a separate implementation in the same sentence still counts.
    uses = list(re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))
    def incidental_use(hit):
        before = text[max(0, hit.start() - 120):hit.start()]
        route = re.search(r"\b(?:via|through|using|on|under|from|must use)\s+(?:\w+\s+){0,8}$", before)
        if not route:
            return False
        if re.match(r"\s+(?:solutions?\s+)?framework\b", text[hit.end():]):
            return True
        # Work on a CMS or a new service built using one is still software work.
        # A preposition alone cannot turn affirmative delivery into mere use.
        delivered = re.search(r"\b(?:(?:develop|implement|configure|migrate|maintain|upgrade|design|build)\w*|maintenance)\b.*$", before)
        return not (delivered and affirmed(text, delivered.group() + phrase))
    if uses and all(incidental_use(hit) for hit in uses):
        return False
    digital = bool(phrase_hits(text, ("software", "saas", "application", "platform", "web based", "cloud based")))
    # A title or sentence can name a process whose purchased scope is explained
    # elsewhere. Corroborate that ambiguity, while keeping mixed software lots.
    context = scope_text or text
    context_digital = digital or bool(phrase_hits(context, ("software", "saas", "application", "platform", "web based", "cloud based")))
    if ("management system" in phrase and not context_digital
            and phrase_hits(context, ("certification", "recertification", "iso 55001", "iso 9001", "iso 27001"))):
        return False
    if (phrase == "booking system" and not context_digital
            and phrase_hits(context, ("venue hire", "hire of venues", "room hire"))):
        return False
    if phrase == "quality management system" and not digital:
        return False
    if phrase == "notification system" and phrase_hits(text, ("sirens", "loudspeakers", "beacons")) and not digital:
        return False
    return True
