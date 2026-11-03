"""Purchased-scope controls across sectors, languages and mixed procurements."""
import pytest

from anthrion_signal.discovery import prefilter


def classify(signal, config, title, description, cpv=()):
    signal.title, signal.description, signal.cpv_codes = title, description, list(cpv)
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    return signal.prefilter_score >= 12 and not signal.exclusion_reasons


@pytest.mark.parametrize("title,description,cpv", [
    ("Pump Optimisation and Aeration Efficiency Analysis",
     "Test pumping equipment at operational assets. Suppliers must contribute to ongoing enhancement.", ["71314200"]),
    ("Reservoir Independent Technical Advisor",
     "Civil engineering assurance for reservoir construction and capital delivery.", ["79411000"]),
    ("Port Independent Technical Adviser", "Construction and civil engineering assurance.", ["72224000"]),
    ("Construction Consultancy Framework", "Building surveying and RIBA design services.", ["79411000"]),
    ("Building Consultancy Services", "Building surveying and construction management.", ["79411000"]),
    ("Employment-orientated case management for parents", "Human coaching and employment support.", ["85312300"]),
    ("Beschäftigungsorientiertes Fallmanagement für Erziehende", "Fallmanagement für Erziehende.", ["85312300"]),
    ("Welding cobot with no-code programming", "Supply equipment for welding and integrate existing welding power sources.", []),
    ("High Voltage Equipment, Supply and Installation", "Electrical test equipment for system integration exercises.", ["71320000"]),
    ("Maintenance and docking of a sailing vessel", "Systems integration of rigging, machinery, deck and fittings.", []),
    ("Supply of IT equipment", "Supply computers and hardware.", ["30200000"]),
    ("Supply of a server", "GPU compute capacity for running language models.", ["48820000"]),
    ("Supply of switches", "Network hardware supply.", ["48000000"]),
    ("Access to eBook Subject Collections: Artificial Intelligence", "Copyright access to a publisher's books.", ["72400000"]),
    ("Asset Valuations & Associated Services", "Valuation of land and properties.", ["79411000"]),
    ("PR Agency Services", "Public relations campaigns and media briefings.", ["79413000"]),
    ("Post-construction Monitoring of Birds & Bats", "Field surveys of protected species and habitats.", ["79310000"]),
    ("Pest control", "Si los licitadores experimentan alguna incidencia informática, contacten con el soporte.", ["90900000"]),
    ("Venta de terrenos", "Las ofertas se presentarán a través de la sede electrónica del ayuntamiento.", ["70122000"]),
    ("Roofing and insulation", "The procedure uses the AI-Vergabemanager procurement platform.", ["45000000"]),
    ("Food response teams", "Use National Incident Management System (NIMS) principles to coordinate response teams.", []),
    ("Space research grants", "Proposers should login to the database system and select Account Management then Email Subscriptions.", []),
    ("Work Focused Activities", "The Supplier Portal Help page explains registering for an account. Jobcentre social services.", []),
    ("Youth welfare report", "In contrast to previous reports which studied digital transformation, this report inventories youth services.", []),
    ("Physical maintenance", "No software development is required. Catering services only.", ["50000000"]),
    ("Employee Assistance Program", "Counselling for employees.", ["79414000"]),
    ("Framework for company health services", "Statutory HSE and workplace physician services.", ["79311000"]),
    ("Nuclear security consultancy", "Radiation protection and handling used fuel.", ["72220000"]),
    ("Agricultural consultancy", "Advice on agricultural production regulations.", ["72224000"]),
    ("Property technical consultancy", "Services from building inspectors and structural engineers.", ["72000000"]),
    ("Fitness equipment and service", "Supply spinning bicycles and free weights.", ["48931000"]),
    ("Population survey service", "Conduct interviews with respondents on safety.", ["79310000"]),
    ("Qualitative survey of citizens", "Questionnaires and fieldwork.", ["79320000"]),
    ("Delegates for an energy programme", "Represent the UK at the executive committee.", ["72222300"]),
    ("Energy business trip", "Organise a specialist conference and business contacts.", ["75131000"]),
    ("Purchase of desktop computer systems", "Supply 160 desktop computer systems.", ["30210000"]),
    ("Eye clinic liaison", "Maintain accurate patient records and input quality data using multiple IT systems.", ["85323000"]),
    ("Microsoft M365 licences", "M365 licences which support the current Electronic Document and Records Management system.", ["72000000"]),
    ("Research grants", "The agency maintains an electronic notification system to alert interested parties of program announcements.", []),
    ("TEST - Digital delivery partner", "Summary of work Test 3. Timeline Test 4. How to apply Test.", ["72000000"]),
    ("Energy business trip", "Organise business contacts. The measure is aimed at SMEs offering system integration and software.", ["75131000"]),
    ("Acciones formativas", "Impartición de itinerarios formativos en seguridad informática.", ["80000000"]),
    ("Suministro de equipamiento informático", "Renovar equipos y dispositivos electrónicos para ejecutar las aplicaciones informáticas.", ["30200000"]),
])
def test_non_digital_purchased_scope(signal, config, title, description, cpv):
    assert not classify(signal, config, title, description, cpv)


@pytest.mark.parametrize("title,description", [
    ("Pump optimisation software", "Develop a data platform and AI agent for pump efficiency."),
    ("Aeration Efficiency Analysis", "Test physical assets. Lot 2: Implement an analytics platform."),
    ("Independent Technical Advisor", "Reservoir construction assurance. Lot 2 includes a customer portal."),
    ("Reservoir customer service", "Implement Salesforce CRM and migrate customer records."),
    ("Water utility records", "Provide a data platform for water assets with APIs."),
    ("Construction Consultancy Framework", "Lot 2: Build a document management system."),
    ("Asset Valuation Software", "Develop software to manage property valuations."),
    ("Legal Services Case Management System", "Provide a case management platform."),
    ("Insurance broker services", "Claims handling includes a customer portal."),
    ("Employment support", "Develop software for managing employment casework."),
    ("Welding cobot", "Supply welding equipment. Lot 2: Build an AI assistant for maintenance enquiries."),
    ("High Voltage Equipment", "Supply test equipment. Lot 2: Implement an integration platform for business records."),
    ("Supply of IT equipment", "Lot 1: Computers. Lot 2: Implement a payroll system."),
    ("Supply of a server", "Supply GPU hardware and develop an AI application."),
    ("Supply of switches", "Lot 2: Develop an asset management system."),
    ("Access to books and teaching aids", "Lot 2: Develop a library web application."),
    ("National Incident Management System software", "Build software for managing emergency incidents."),
    ("Roofing", "Submit bids via AI-Vergabemanager. Lot 2: Develop an AI assistant for residents."),
    ("AI platform and bidding client", "Develop an AI platform and use AI-Vergabemanager to submit the bid."),
    ("Sede electrónica", "Desarrollo de aplicaciones para la sede electrónica municipal."),
    ("Portal implementation", "Build a supplier portal where suppliers log in and submit tenders."),
    ("Customer account management", "Build a database system to manage customer accounts and email subscriptions."),
    ("Consultancy services", "Scope will be specified at the market engagement event."),
    ("IT development services", "IT development services."),
    ("Youth welfare report", "Previous reports focused on social policy. This contract includes digital transformation and a CRM platform."),
    ("Microsoft SaaS subscriptions and managed services", "Licences and a separately supplied managed services contract."),
    ("Support Service for User Assistance and Supply of IT Equipment",
     "Lot 1: Technology support services for the education and social services system. Lot 2: IT equipment."),
    ("Modernisation of Physical Security Systems",
     "Replace cameras and physical security controls. Consolidate separate components into a centrally managed SaaS-based platform."),
    ("Video control system", "Lot 4 comprises maintenance services. The services include hardware and software components."),
    ("Development of a data space and AI startup incubator", "Develop a data space for language AI and a technological platform."),
    ("Employee assistance", "Lot 2: Develop an employee portal and implement case management software."),
    ("Nuclear security consultancy", "Handle used fuel. Lot 2: Implement a document management system."),
    ("Agricultural consultancy", "Advise on production. Lot 2: Develop a CRM platform for farmers."),
    ("Fitness equipment", "Supply exercise machines. Lot 2: Develop an online booking system."),
    ("Population survey service", "Lot 2: Build a customer feedback platform."),
    ("Energy business trip", "Organise a specialist conference. Lot 2: Build an event CRM platform."),
    ("Notification service", "Develop an electronic notification system to alert interested parties of programme announcements."),
    ("Test automation platform", "Provide software test automation and delivery pipelines."),
    ("Contrato de seguridad informática", "Servicio de seguridad informática, soporte y un curso para administradores."),
    ("Suministro de equipamiento informático", "Suministro de ordenadores. Lote 2: Desarrollo de aplicaciones para gestionar los clientes."),
    ("Suministro de equipamiento informático", "Suministro de ordenadores. Lote 2: Implantación de una plataforma informática."),
])
def test_mixed_and_sparse_workable_scope_survives(signal, config, title, description):
    assert classify(signal, config, title, description, ["79411000"])


@pytest.mark.parametrize("title,description", [
    ("Informatica PowerCenter support", "Maintain the Informatica PowerCenter integration platform."),
    ("Informatica Cloud", "Provide Informatica Cloud data integration."),
    ("INFORMATICA POWERCENTER support", "Maintain INFORMATICA POWERCENTER."),
    ("informatica support", "Provide support for informatica cloud."),
])
def test_real_vendor_retains_evidence(signal, config, title, description):
    assert classify(signal, config, title, description)
    assert any(e["phrase"] == "informatica" for e in signal.capability_evidence)


@pytest.mark.parametrize("title,description", [
    ("Aplicación informática", "Suministro de una aplicación informática para gestionar expedientes."),
    ("Servizi di informatica", "Manutenzione di applicazioni informatiche."),
])
def test_computing_word_is_not_vendor_evidence(signal, config, title, description):
    assert classify(signal, config, title, description, ["72000000"])
    assert not any(e["phrase"] == "informatica" for e in signal.capability_evidence)


@pytest.mark.parametrize("digital_lot", [False, True])
def test_buyer_name_is_not_purchased_scope(signal, config, digital_lot):
    signal.buyer_name = "Ministry for Digital Transformation"
    title = "Liability insurance for the Ministry for Digital Transformation"
    description = "Insurance services for the Ministry for Digital Transformation."
    if digital_lot:
        description += " Lot 2: Implement a customer portal for insurance casework."
    assert bool(classify(signal, config, title, description, ["66510000"])) is digital_lot
    assert signal.buyer_name in signal.title


def test_generic_improvement_is_not_managed_application_support(signal, config):
    classify(signal, config, "Engineering services", "Ongoing enhancement of physical operational processes.")
    assert "managed" not in signal.matched_capabilities
    assert classify(signal, config, "Application services", "Ongoing enhancement of the CRM platform.")
    assert "managed" in signal.matched_capabilities


@pytest.mark.parametrize("title,description", [
    ("Computer systems support", "Support, administration and maintenance of computer systems."),
    ("Document storage and IT platform", "Collection of paper files, digitisation and an IT platform."),
    ("Laboratory equipment and interface", "Equipment with an IT connection to the laboratory information system."),
    ("Material para el laboratorio", "Conexión informática al Sistema de Información del Laboratorio."),
    ("Soporte CAU", "Mantenimiento y evolución de la estructura informática y servicios informáticos corporativos."),
    ("Mantenimiento Oracle", "Soporte de los Sistemas Físicos y Lógicos Oracle."),
    ("Operación de aulas informáticas", "Mantenimiento de la solución de laboratorios virtuales."),
    ("Implantación de una plataforma informática", "Gestión de la carrera profesional y evaluación del desempeño."),
    ("Servicio de escritorios virtuales", "Mantenimiento de la infraestructura de escritorios virtuales Horizon."),
    ("Sistemas de gestión de turnos de atención ciudadana", "Sistema de gestión de turnos para atender a ciudadanos."),
    ("Servicios de gestión tributaria", "Asistencia técnica, material e informática al ejercicio de gestión tributaria."),
])
def test_uncoded_software_component_survives_vendor_disambiguation(signal, config, title, description):
    assert classify(signal, config, title, description)


@pytest.mark.parametrize("title,description,cpv", [
    ("Digital and printed teaching aids", "Framework for printed and digital teaching aids.", ["48190000"]),
    ("Books and teaching aids", "Printed and digital teaching aids.", ["48160000"]),
    ("Supply of basic IT hardware", "DPS categories: Servers and minor software.", ["30200000", "48000000"]),
    ("Sistema Dinámico de Adquisición para suministro de equipamiento informático", "Ordenadores y paquetes software.", ["30200000", "48000000"]),
    ("Legal services and engineering services DPS",
     "The dynamic purchasing system covers the professional services specified by CPV categories.",
     ["79100000", "71300000", "72200000"]),
])
def test_explicit_multi_category_procurement_retains_software_categories(signal, config, title, description, cpv):
    assert classify(signal, config, title, description, cpv)


def test_explicit_digital_scope_overrides_nontechnical_cpv(signal, config):
    assert classify(signal, config, "Inventory update",
                    "Transfer asset records to a computer application with comprehensive search and reporting.", ["71356200"])


@pytest.mark.parametrize("title,description,cpv", [
    ("PR Agency Services", "Public relations campaigns and copywriting. Lot 2: Website maintenance, hosting and support.",
     ["79341000", "72200000"]),
    ("PR Agency Services", "Public relations campaigns. Lot 2: Website hosting.", ["79341000", "72200000"]),
    ("Security and reception services",
     "Security guards at council offices. Lot 2: Maintain a customer identity and access management platform.",
     ["79710000", "72200000"]),
    ("Legal Services", "Legal advice and support. Lot 2: Software testing and maintenance.", ["79100000", "72200000"]),
])
def test_mixed_maintenance_and_testing_lots_survive(signal, config, title, description, cpv):
    assert classify(signal, config, title, description, cpv)


@pytest.mark.parametrize("description", [
    "Unlike previous reports, this contract includes Salesforce implementation.",
    "In contrast to previous reports which studied youth services, this contract includes Salesforce implementation.",
    "Unlike previous reports this contract includes Salesforce implementation.",
])
def test_current_delivery_after_historical_contrast_survives(signal, config, description):
    assert classify(signal, config, "Service redesign", description)
    assert "salesforce" in signal.matched_capabilities


def test_software_integration_compatibility_retains_platform_evidence(signal, config):
    assert classify(signal, config, "Platform integration",
                    "Deliver software integration ensuring compatibility with Salesforce.")
    assert "salesforce" in signal.matched_capabilities


@pytest.mark.parametrize("title,description,cpv", [
    ("PR Agency Services", "Public relations campaigns. Website maintenance is out of scope.", ["79341000"]),
    ("Legal Services", "Legal advice. Work is performed using a software testing framework.", ["79100000"]),
    ("Supply of desktop computers", "Hardware must ensure compatibility with Salesforce.", ["30200000"]),
    ("Supply of desktop computers",
     "No requirement to implement software integration, but ensure hardware compatibility with Salesforce.", ["30200000"]),
    ("Microsoft software licence renewal", "Renew licences which support an existing software platform.", ["48000000"]),
    ("VMware Cloud Foundation Licences", "Procure subscription licences to support the existing private cloud platform.", ["48000000"]),
    ("Oracle Licences", "Oracle licences and support. Supplied by an existing software reseller.", ["48000000"]),
    ("SAP platform licences", "Maintenance and support of SAP platform licences for the years 2027 to 2030.", ["48000000"]),
])
def test_incidental_or_excluded_software_still_does_not_protect_physical_scope(signal, config, title, description, cpv):
    assert not classify(signal, config, title, description, cpv)
