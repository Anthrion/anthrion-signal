# Discovery and capability upgrade

## Decisions

- Keep classification-based collection as a high-recall path. A classification alone does not assign a capability.
- Share the same specific vocabulary between tagging, German/Spanish collection gates, TED keyword queries and the site's search catalog.
- Search in English and the active markets' native languages: German, Italian, Spanish, Greek, Swedish, Finnish, Norwegian, Danish and Icelandic. Brand names remain untranslated. French, Dutch and Portuguese aliases remain available too.
- Use qualified terms such as Salesforce Public Sector and Salesforce Government Cloud. Distinctive names such as OmniStudio, MuleSoft and Agentforce can stand alone. Generic context words such as public sector, Teams, data and AI are not standalone TED keyword searches.
- Add functional phrases for benefits, housing allocation, grants, inspections, appointments, customer identity, document generation, business rules, employee self-service and financial analytics without claiming that a notice requires Salesforce.
- Check original text first and supplement it with an exact-source-hash, validated English translation. Never change source text, notice identity, first-seen dates or hidden-record keys to improve tags.
- Retain ambiguous classified and explicitly digital notices without a capability rather than inventing one. No keyword system can guarantee perfect precision or recall.

## Evidence and exclusions

Matches are local to source sentences, with phrase, field, source/translation basis and supporting text retained in canonical diagnostic evidence. This evidence is omitted from the browser download to avoid unnecessary payload growth.

Context-only product mentions need relevant context. Microsoft licences are not integration work; ordinary teams are not Microsoft Teams; backup deduplication is not customer-data work; an explicitly excluded helpdesk is not a service requirement. Stage vocabulary does not create a capability. Relationship databases require nearby relationship-management evidence, not separate grant eligibility and research data-management passages.

The fresh collection also exposed administrative grant-submission text and regulatory paperwork matches. Existing EDGE submission-platform boilerplate and instructions to submit through a portal do not establish a delivery scope. An Investigational New Drug application is not software development. Data-integration phrases in funding notices need actual software/platform/database evidence, rather than generic coordination of research. Positive software, patient-CRM, clinical-data-platform and application-portal funding examples are protected by regression tests.

Clear hardware and commodity-licence supplies without addressable application/CRM/AI scope are suppressed. Positively identified broadband construction and connectivity-only contracts are also excluded, even when a provider assigns an IT classification. Mixed lots with relevant software remain. Generic IT-infrastructure services and sparse application roll-outs are retained. Source availability, awards, participation restrictions and deadlines still take precedence.

## Collection and restart behaviour

TED's existing classification query and historical checkpoint remain intact. Additional bounded keyword groups have their own exact-query identities, fixed publication windows and continuation tokens. They share the existing request budget, rotate fairly, preserve unfinished older windows when vocabulary changes, and honour provider cooldowns. An initial keyword catch-up can take several hourly runs; it is reported as partial coverage, not falsely described as complete.

German and Spanish collectors replay the recent lookback once when vocabulary changes, preserving pending work and known notice identities. The discovery vocabulary version is separate from the existing annual collection-backfill version, so retagging does not reset a year's collection.

Grants.gov retains its existing searches and adds bounded Boolean groups from the shared specific English capability vocabulary. US city feeds already enumerate their available notices rather than relying on a sparse keyword list. All results still pass the same scope and eligibility checks. Grants.gov's documented exact-phrase and OR syntax: https://grants.gov/search-tips.

Translation-only publication also recomputes capability tags, so a newly completed translation can improve tags without waiting for another collection. Publication does not claim a new source-fetch time. Hourly collections and translation-check schedules are unchanged.

## Browser behaviour

Most recent and date-based views retain CRM/Salesforce-first ordering. Explicit Highest value and Lowest value sorts now order the whole selected market by published numeric amount, with unknown amounts last. There is no currency conversion; select a currency when comparing like-for-like values.

Capability A-Z sorts by the displayed capability names with untagged notices last. Currency names replace ISO codes in the currency selector, which sits beside CPV code. ISO values remain stable in URLs, filtering and exports.

## Verification

The release comparison uses a frozen 1,668-record public snapshot from 2026-09-13T14:07:52Z. `scripts/verify_discovery_release.py` produces an inspectable before/after report without modifying source records or checkpoints. The regression suite covers positive and negative examples, each active native-language pack, mixed lots, stale translations, stable record identity, query restarts and bounded replay.

In that frozen comparison, 100 previously untagged records gained supported capabilities. Fifty-three notices were suppressed as out-of-scope supplies, construction, network infrastructure or incidental matches without the required delivery evidence, leaving 1,615 records before any new collection or deadline changes. This includes eight connectivity-only notices caught in the live value-sort check. Some remaining records intentionally have no tag because their published facts do not establish one. These are reproducible snapshot figures, not a promise about the continually changing live count.

The production collection at 2026-09-13T17:38:50Z fetched 6,287 raw records. Auditing its 1,656-record published snapshot with validated translations left 1,631 after the final scope corrections, including the new submission-boilerplate cases. Genuine additions include a Spanish CRM implementation and an intelligent-agent delivery project.

External coverage is not guaranteed: the Scottish and Welsh API hosts currently fail certificate-chain validation; this was reproduced independently of GitHub. TLS verification remains enabled, previous records are retained, and Sell2Wales keeps its existing public-listing fallback. Spain's published feed is dated 2026-09-08, so newer national-only coverage cannot be claimed. TED, German, GOV.UK and grant-detail catch-up work remains checkpointed within the existing budgets.

Official TED syntax and limits: https://ted.europa.eu/en/help/search-browse and https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html. All 18 final TED keyword groups and all eight additional Grants.gov groups were accepted by their public APIs during bounded read-only probes. Syntax acceptance is not evidence that every returned notice is relevant; local scope and availability checks remain necessary.
