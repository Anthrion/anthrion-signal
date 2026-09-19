# European national procurement source assessment — 18 September 2026

Reviewed on 19 September 2026 while integrating the research from
[PR #8](https://github.com/Anthrion/anthrion-signal/pull/8), revision `cb82604`.
This document separates primary documentation checked during review from the
contributor's reported API observations. The review made no national-provider
collection calls and did not enable a national collector.

France, Belgium, the Netherlands, Luxembourg, Austria and Switzerland are covered
by the existing bounded TED collector. Country records remain distinct inside
the Benelux and DACH groups. TED coverage means notices actually published on TED;
it is not complete national coverage. National sources below are disabled research
entries in `config/sources.yaml`. The existing German and Spanish national
collectors remain enabled and are outside this proposed addition.

## Evidence and coverage limits

The [TED Search API documentation](https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html)
describes the supported notice-search interface. Swiss notices can appear in TED;
Swiss membership of neither the EU nor the EEA does not imply their absence. A
national notice without a TED counterpart is not necessarily below a particular
threshold, and a national portal is not necessarily exhaustive either. Coverage
comparisons need notice type, publication window, buyer location and place of
performance recorded separately.

PR8 reported these TED counts for 1–18 September 2026 using `buyer-country`:

| Market      | Contributor-reported notices |
| ----------- | ---------------------------: |
| France      |                        4,284 |
| Netherlands |                        1,363 |
| Belgium     |                        1,142 |
| Switzerland |                          703 |
| Austria     |                          604 |
| Luxembourg  |                          125 |

These are attributed historical snapshots, not independently reproduced review
results or current coverage guarantees. They precede CPV and scope filtering.
Buyer-country counts can include EU institutions based in Belgium or Luxembourg;
they do not measure exclusively domestic demand. PR8 also reported two different
Belgian national totals, 1,475 and 2,947, for its September comparisons. Their
query definitions were not reconciled, so no coverage multiplier is asserted.

Other PR measurements—notice percentages, daily volumes, record completeness,
rate limits, pagination caps, archive completeness and WAF behaviour—remain
implementation hypotheses until reproduced against an approved interface. None
is a service-level guarantee or permission to automate access.

## Sources with primary documentation checked

### France

**BOAMP** is a strong candidate for additional French notices.
[DILA's official API catalogue entry](https://www.data.gouv.fr/dataservices/api-bulletin-officiel-des-annonces-des-marches-publics-boamp)
describes free access under Licence Ouverte 2.0 plus API conditions. It exposes
notice searching and exports. This is a useful reuse basis, subject to the actual
API conditions and personal-data requirements; it does not cover every linked
document automatically. The catalogue still names Explore v2.0, while PR8 tested
v2.1. Confirm the supported version, request limits and permitted bulk route before
implementation. The separate DILA XML flow is retained as an alternative source
format, not a second collector to run concurrently by default.

BOAMP cannot be assumed to cover every French procurement. Source-specific
publication routes vary. Preserve exact notice, procedure and lot identifiers;
PR8's `contractfolderid` observation alone does not justify closing all lots after
one award or cancellation.

**DECP / AIFE** is useful for awarded-contract and buyer history, rather than a
feed of open response windows. The [official API DECP dataset](https://www.data.gouv.fr/datasets/api-decp)
publishes contract and concession data under Licence Ouverte 2.0. Use the current
resources and their modification dates; do not infer freshness from a catalogue's
page date or treat a past contract as an open opportunity.

**PLACE and regional Atexo platforms** remain research candidates. PR8 reported
reproduction restrictions and a rolling consultation window for PLACE. This
review did not independently retrieve its current terms or reproduce those
queries. Verify the exact [PLACE service](https://www.marches-publics.gouv.fr/)
terms, authorisation route and history coverage. Each regional deployment needs
its own review; a shared endpoint shape proves neither common permission nor
complete coverage.

### Netherlands

The [official government TenderNed catalogue](https://data.overheid.nl/dataset/aankondigingen-van-overheidsopdrachten---tenderned)
lists CC0 1.0 notice data, RSS and a public TNS JSON webservice. It warns that the
webservice can change without notice. Distinguish this route from the
[documented XML API](https://www.tenderned.nl/info/swagger/), which requires
credentials. TenderNed's [dataset guidance](https://www.tenderned.nl/cms/nl/aanbesteden-in-cijfers/datasets-aanbestedingen)
currently says new XML API requests are waitlisted and may take months; this is
not proof of an indefinite closure.

PR8's PAPI pagination and ignored-parameter findings should become bounded
collector tests before activation. TenderNed also explains that
[below-threshold procedures open to the whole market must be announced](https://www.tenderned.nl/cms/nl/voor-aanbestedende-diensten/publiceren-op-tenderned).
This does not establish visibility of every invited procurement.

### Belgium

[BOSA's current e-Procurement terms](https://bosa.belgium.be/en/conditions-use-and-availability-services-e-procurement-platform)
describe free public access to market consultations, prior notices, contract
notices and awards. They also reserve intellectual-property rights over the site
and associated material. The reviewed terms do not establish the bulk
redistribution permission required for Signal's full descriptions and separate
translations. Obtain a supported access route and clarify that scope before
activation. This is an unresolved integration requirement, not a claim that all
Belgian procurement data is legally inaccessible.

PR8 reported a token-based internal search interface. No credential was copied,
used or tested in this review. Credentials found in client code are not a
substitute for a documented authorisation route. Do not record or use them.
Claims that BDA is the only free route, that no other national publication exists,
or that regional/catalogue sources contain no usable notices were not established.

### Luxembourg

The [procurement portal's published site terms](https://marches.public.lu/fr/support/aspects-legaux.html)
reserve reproduction rights and limit the ordinary download permission to private
informational use. Identify the exact terms applicable to PMP's data interface
and obtain permission for republication before integrating it. A reachable public
JSON endpoint does not settle that question.

PR8 reported useful deadlines and CPV fields, sentinel test dates and incomplete
award/cancellation fields. These are valuable test cases to reproduce, not proof
that every record lacks lifecycle data. Neither PMP's exclusivity nor the absence
of useful data on data.public.lu was verified.

### Austria

[USP confirms the switch from the legacy Kerndaten format to eForms on 1 October 2026](https://www.usp.gv.at/hilfe-und-support/ausschreibungssuche/eforms.html).
A collector spanning that date needs both formats, with explicit dates and
source identifiers. This change does not establish that all Austrian national
notices will appear in TED.

The [data.gv.at reuse guidance](https://www.data.gv.at/netiquette/) explains its
CC-BY framework, and an [example statutory Kerndaten distribution](https://www.data.gv.at/datasets/7e80bc4b-3537-42fd-881f-d9290b34782e)
explicitly lists CC BY 4.0. Check each chosen distribution's licence and access
conditions rather than applying a single licence to every host or linked
document. USP remains a candidate index; its interface, pagination and reuse
scope need separate review.

PR8 reported ANKÖ host directives including `ai-input=no`. That observation was
not independently refreshed here. Its meaning is material: Cloudflare's
[Content Signals policy](https://blog.cloudflare.com/content-signals-policy/)
defines AI input to include inference and grounding, separately from training.
An LLM returning only quotes or links still consumes its input. Quote-only output
does not bypass such a restriction. An independently licensed source may provide
a legitimate alternative, but its provenance, terms and permitted use must be
established; another host is not automatic permission.

### Switzerland

The [simap API terms](https://www.simap.ch/en/about/legal) permit commercial
redistribution of publication data, allow unauthenticated publication search and
currently state no API fee. They also require unchanged source content, separation
from commentary, the prescribed non-official-publication notice, correction and
quality notices, and release no earlier than 08:00 on publication day. The
platform specifies Europe/Zurich time. Downstream-user obligations and possible
future fees must also be assessed for a public website. Signal's separate English
translations require review under these terms. No Swiss national collector is
enabled by this assessment.

Keep the [API documentation and version changes](https://www.simap.ch/api/specifications/changelog.html)
with any implementation. **`publicationTed` is a boolean, not a TED notice
identifier.** It cannot identify a matching record, prove exact deduplication or
resolve procedure/lot identity. Require an explicit published identifier or
source-provided link; do not introduce fuzzy merging.

Amtsblattportal/SHAB is retained as a possible source of additional cantonal
notices. PR8's interface and field observations remain unverified. Check its
publication rubrics, access documentation and reuse scope independently. Neither
simap nor SHAB is described as the only route to every Swiss procurement.

## Other national candidates

| Candidate                                      | Reviewed purpose and remaining checks                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Denmark — udbud.dk                             | Its [system-provider guidance](https://udbud.dk/hjaelp/hjaelpSystemudbydere) permits attributed reproduction and describes notice retrieval for third-party monitoring. It also describes API-access registration: do not assume every endpoint is keyless. Confirm the appropriate read API, limits and update cursor.                                                                                                                                                                                                    |
| Greece — KIMDIS                                | The [official Open Data API help](https://cerpp.eprocurement.gov.gr/khmdhs-opendata/help) states free availability under CC BY 4.0. Separate open competitions from other registered decisions; verify deadlines, lifecycle and request limits. No universal threshold-based completeness claim is made.                                                                                                                                                                                                                   |
| Norway — Doffin                                | Official notice portal and potential national supplement. PR8 reported a public search API; its supported bulk interface and reuse licence remain to be checked. A `sentToTed` flag cannot substitute for a TED identifier.                                                                                                                                                                                                                                                                                                |
| Italy — ANAC                                   | ANAC describes [national legal publication through BDNCP](https://www.anticorruzione.it/-/digitalizzazione-contratti-pubblici). Review a supported public retrieval interface separately from authenticated buyer submission services. PR8's field/filter findings do not establish a permanent absence of numeric CPV data.                                                                                                                                                                                               |
| Finland — Hilma                                | Potential national notices and procurement plans. PR8 reported a free-key API and substantive-content/direct-marketing restrictions. Reconfirm the current contract through [Hilma's official guidance](https://www.hankintailmoitukset.fi/en/info) before integration. This review could not extract the current dynamic terms page. Quotes, links and preserved originals do not by themselves establish permission for inference or separate translations.                                                              |
| Sweden — registered notice databases           | [Konkurrensverket's March 2026 decision summary](https://www.konkurrensverket.se/informationsmaterial/nyhetsarkiv/2026/konkurrensverket-avslutar-arende-om-krav-pa-funktioner-i-annonsdatabas/) confirms free search and full published award notices after Mercell's changes, with basic notice information available without an account. PR8's “paid feed or nothing” conclusion is incorrect. Public reading is distinct from an approved bulk API or republication licence; those remain unverified for each operator. |
| Ireland — eTenders                             | Candidate national supplement. PR8 reported CSV export and substantial non-TED content. Verify the supported export, deadlines, lifecycle and reuse permission with the official service. Do not describe it as the only live route.                                                                                                                                                                                                                                                                                       |
| Portugal — IMPIC announcements on dados.gov.pt | The [official announcements catalogue](https://dados.gov.pt/pt/datasets/contratos-publicos-portal-base-impic-anuncios-de-2012-a-2026/) identifies IMPIC as publisher and labels the dataset public domain. Inspect resource freshness, schema and deadline coverage before implementing bounded downloads; contract registers and announcements serve different purposes.                                                                                                                                                  |

Iceland's national options remain outside this bounded registry import; PR8's
limited RSS observation does not establish the absence of other interfaces.
OpenTender is a separate third-party reuse candidate, not an official national
source. Its current dataset licences and update dates need checking before any
commercial integration; no blanket all-country end date is asserted here.

The EU Funding & Tenders Portal is already registered as `eu_funding`. SEDIA is
not added as a duplicate source. PR8's reported type filters, counts and ECB
coverage conclusions require verification against the official interface before
implementation.

## Implementation order and activation conditions

The current change preserves TED collection and adds research metadata only.
BOAMP, TenderNed and Denmark are reasonable next feasibility studies because the
review found explicit official access/reuse guidance. Their relative value still
needs measurement against the retained TED corpus. Contract-history sources such
as DECP should be evaluated separately from open-opportunity discovery.

Before activating a national adapter, establish its supported free access and
reuse scope for original descriptions, translations and any model input; preserve
source/lot identities, corrections and exact deadline precision; reproduce bounded
pagination and retry behaviour; and measure overlap without fuzzy merging. API
availability alone proves neither bidder eligibility nor complete market coverage.
Source documents can have rights and authentication requirements separate from
their notice metadata. Existing collection and translation quotas remain unchanged.
