# Caribbean collection

Source research and live checks: 23 October 2026.

## Market behavior

Caribbean is one combined market, after France in the default pinned row. It can be dragged,
unpinned and selected again in More. Individual Caribbean countries are deliberately absent
from the market organizer. Notice cards retain the actual country or **Caribbean (regional)**.
Belize, Guyana and Suriname are included as Caribbean community markets. A regional agency's
office address does not turn a regional project into a single-country opportunity.

The group and country partitions share record identities. All loads the group once, without
also downloading its country partitions. The internal regional partition is separate from the
group identifier to prevent regional notices disappearing from All.

## Enabled sources

| Source | Coverage | Access and collection |
| --- | --- | --- |
| [World Bank](https://projects.worldbank.org/en/projects-operations/procurement) | Project notices for AG, BB, BZ, DM, DO, GD, GY, HT, JM, KN, LC, VC, SR, TT and explicit Caribbean/OECS regional projects | Keyless public procurement API. Full notice text, rotating country lanes, one-year rolling inventory and bounded refresh. This is project coverage, not complete national coverage. |
| [Dominican Republic DGCP](https://datosabiertos.dgcp.gob.do/api-dgcp/docs/index.html) | Public national process index and complete OCDS scope | Keyless API. A separate published-state inventory finds older current notices. Hydrate full item descriptions, including generic titles, with independent fresh/historical lanes, active-notice refresh and explicit retry queues. |
| [BOAMP](https://boamp-datadila.opendatasoft.com/pages/api-boamp/) | Guadeloupe, Martinique, Saint Martin and Saint Barthelemy | DILA's free public API. Original French FNSimple, MAPA and eForms notices. Actual performance/buyer addresses determine territory; publication distribution tags do not. |
| [Montserrat](https://tenders.gov.ms) | Government tender notice pages | Robots-aware public HTML collection. Full notice descriptions and source document links. |
| [Saint Lucia](https://www.finance.gov.lc/tenders/index) | Ministry of Finance public notices | Robots-aware listing and detail collection. Actual response wording determines deadlines. Award notices remain historical. |
| [Caribbean Development Bank](https://www.caribank.org/work-with-us/procurement/procurement-notices) | Bank/project notices, including BB, BZ, DM, GD, GY, JM, TT, TC and regional records in the verified listings | Public current and general procurement pages. Preserve Overview, Eligibility and Instructions. General notices are planning records. |

The six sources require no tender-data subscription or API key. Translation continues through
the existing separately budgeted translation service; adding these sources does not change its
quota settings. API and HTML calls use the existing timeouts, retry policy and source isolation.
No source failure deletes previously collected notices.

Each source has a request budget and a resumable checkpoint. A budget limit or unresolved notice
is reported as partial coverage. Initial recovery can therefore take multiple collections.
Healthy collection means the configured scan completed, not that every tender in a country was
published by that source or that Anthrion satisfies its participation conditions.

DGCP's documented `estado=Proceso publicado` filter returned 828 notices during verification;
124 were published more than 14 days earlier. The independent inventory closes that observed
initial-publication gap. Nineteen returned deadlines had already passed, so published state alone
does not establish an available response route. Multi-page inventories require a second identical
complete pass before their detail queue is updated. Pending details survive later refreshes and
source disappearance; missing from a list never means cancelled. Queue entries older than six
hours refresh their exact process summary before full detail retrieval, so an old published label
cannot override a subsequently closed or cancelled process.

## Languages and relevance

Collect complete published scope before applying the shared relevance classifier. Do not
restrict upstream collection to English keywords, technology titles or one national language.
The existing English, Spanish, French and Dutch functional vocabularies apply together. For
example, an English notice from Suriname is assessed in English; a French Haitian notice is
assessed in French. Original text remains separate from cached English translations.

Offline integration tests cover Spanish document/workflow scope, French portals/case management,
Dutch portals/integration, and English software requirements in non-English markets. Public
physical-works notices do not become relevant merely because they were collected. A software
mention in portal instructions is not project scope. No country-specific eligibility is assumed.

## Source contracts that must remain protected

- DGCP can publish tender, award and contract tags together before any award. Use actual status,
  award facts and lot coverage. An award for one lot must not close another open lot. Its
  `fecha_enmienda` is an amendment-period schedule, not a reliable last-modified timestamp.
- DGCP identifiers can include spaces, periods and accented letters. Preserve the exact ID and
  pass it as an encoded query parameter. Its UNSPSC codes are not CPV codes.
- World Bank date query parameters can be silently ignored. Verify descending publication order
  and apply the date window locally. Project country, not contact country, determines geography.
  A general procurement notice can omit the bid title while supplying a project name and full scope.
- World Bank deadline dates can use midnight Z as a date container. A separate local time does
  not establish a UTC offset. Preserve the stated precision.
- Saint Lucia's catalogue can call an old award Open and give it a display-expiry date years in
  the future. Neither field establishes an open response route.
- CDB's machine-readable date attribute can disagree with the visible closing time. Use the
  visible source facts. CDB corporate procurement is regional, not automatically Barbados.
- BOAMP can retain an obsolete typed deadline inside a correction that extends it in prose.
  Unverified replacement dates remain unknown; earlier dates become superseded evidence.
  Sparse corrections preserve previously collected scope and untouched lots. Award links never
  become aliases that incorrectly close a whole multi-lot tender.
- BOAMP sparse corrections retrieve missing original notices before classification. Exact alias
  chains retain cumulative scope, including same-day amendments; re-reading an original cannot
  undo its correction. Unresolved predecessors retry separately without blocking fresh notices.
- Failed detail pages must not block discovery of later notices. Keep retry metadata separately;
  never classify a missing page as a cancelled tender.

## Remaining coverage gaps

| Country or territory | Finding and next route |
| --- | --- |
| Antigua and Barbuda, Dominica, Grenada, Guyana, Jamaica, Saint Kitts and Nevis, Saint Vincent and the Grenadines | Multilateral coverage is enabled. National portal adapters still need verified detail, lifecycle and reuse contracts. |
| Anguilla | Public tender pages found; published reuse restrictions require an authorized supply route. No national collector enabled. |
| Aruba | Official SSR pages are available, but mix tender, award and exemption notices. A lifecycle-aware adapter remains to be verified. |
| Bahamas, Cayman Islands | Public Bonfire list data exists, but complete notice access was blocked in the probe. No listing-only collector enabled. |
| Barbados | World Bank/CDB coverage is enabled. Bonfire detail access/crawler restrictions prevent claiming complete national coverage. |
| Belize | World Bank/CDB coverage is enabled. Public national opportunity pages are a candidate for a separately verified adapter. |
| British Virgin Islands | CDB's country universe includes the territory; no current complete national source was verified. |
| Caribbean Netherlands | TED can contain relevant territorial notices. Exact territory routing still needs verification; Dutch buyer country alone is insufficient. |
| Cuba | No current keyless national notice source with a verified collection contract was established. |
| Curacao | Official Dutch notices exist, including cancellations; no stable national feed was verified. Preserve XCG where the publisher uses it. |
| Haiti | World Bank coverage is enabled. CNMP/ministry public pages were found, but reliable automated retrieval remains unresolved. |
| Puerto Rico | ASG/RUS public listings were found; direct retrieval hit an access challenge. No bypass or national collector enabled. |
| Sint Maarten, US Virgin Islands | Public notice pages exist; reliable retrieval and full deadline/detail handling remain unverified. TLS verification stays enabled. |
| Suriname | English World Bank notices are covered. Dutch national tender pages need a separate verified adapter. |
| Trinidad and Tobago | World Bank/CDB coverage is enabled. ProcureTT has current software notices, but its terms prohibit unauthorized reproduction/distribution/commercial use. Request written permission or an authorized feed before republication. |
| Turks and Caicos Islands | CDB notices are covered; a complete national adapter is not enabled. |

[IDB's public dataset](https://data.iadb.org/dataset/e3fc7d61-d934-4e8d-859b-477f2e839308)
is a promising follow-up. Its keyless API is usable, but sampled rows often lack full scope and
require linked-document extraction. OECS and CARICOM have public listings, with directory entries
and employment notices that need careful separation. UNGM access returned 403 in this check.

Reuse evidence: DGCP release packages identify their PDDL license; DILA documents free BOAMP API
reuse. IDB labels its dataset CC BY 4.0. Respect each distribution's conditions and keep attribution
and source links. Public readability alone does not justify bypassing restrictions. ProcureTT's
restriction appears in section 4 of its [Terms of Use](https://procurett.oprtt.org/wp-content/uploads/2025/07/Terms-of-Use-Policy.pdf).
