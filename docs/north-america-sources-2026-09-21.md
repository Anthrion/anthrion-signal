# North American and European source follow-up — 21 September 2026

This is an implementation backlog, not a coverage or recall claim. It retains the
useful findings from [PR #18](https://github.com/Anthrion/anthrion-signal/pull/18),
reviewed against the shipped collectors and official documentation. It adds no
collector, enables no source, and changes no admission rule.

## What is already shipped

| Area | Current implementation |
| --- | --- |
| United States | `sam_csv` streams GSA's public CSV without a SAM account or API key. NYC, LA and Grants.gov provide additional coverage. |
| Canada | `canada_buys` reads federal new/open notices and fiscal-year tenders/awards. Provincial and municipal portals are not included by that integration. |
| Market groups | North America is US + CA. European country and grouped-market filters are already present. New European market filters do not imply national or below-threshold collection beyond TED. |
| Canada source links | `normalise_canada_buys()` derives a canonical notice URL from the reference, including SSC colon normalization. An empty optional `noticeURL` does not remove that link. |

See [Canada implementation notes](context-and-canada-2026-09-21.md),
[SAM implementation audit](sam-context-audit-2026-09-19.md) and
[the existing European assessment](free-apis-market-expansion-2026-09-18.md).

The [official SAM Get Opportunities API documentation](https://open.gsa.gov/api/get-opportunities-public-api/)
requires an API key and publication-date bounds and supports up to 1,000 results per
request. Authenticated access and the account's assigned quota were not tested here.
Missing-key responses do not establish that the keyed API is unavailable. The existing
keyless extract remains available independently of that question.

## Native classification metadata is a real gap; missed-lead volume is unknown

The source-code finding survives review:

- `sam_opportunities.py` validates CSV headers including `NaicsCode` and
  `ClassificationCode`. The normalizer temporarily puts NAICS in `categories`;
  `discovery.py` later replaces `categories` with sector labels. There is no dedicated
  normalized NAICS/PSC classification field or scoring path.
- `canada_buys.py` retains the raw CSV row but does not normalize UNSPSC/GSIN into
  scheme-specific classification fields.
- `discovery.py` uses `cpv_codes` for classification evidence. It also has several
  independent text, capability, functional-scope and exclusion paths.

Consequently, testing `BUSINESS_OBJECTS` alone is not a test of the discovery
pipeline. Broad IT classifications are not a labelled set of work Anthrion can
deliver. Neither a keyword hit rate nor the absence of CPV on North American records
establishes a product recall percentage.

A useful follow-up should:

1. Preserve native classifications separately by scheme, code and source provenance.
   Do not put NAICS, PSC, UNSPSC or GSIN values in `cpv_codes`: their prefixes have
   different meanings. Missing codes must not exclude a record.
2. Reproduce candidate gaps on retained full notices, with stable source IDs,
   input hashes, classifier revision and an independently reviewed suitability label.
   Include original and available English text, sparse notices and mixed lots.
3. Measure metadata preservation separately from any proposed admission change.
   Run the complete classifier, including scope exclusions and lifecycle checks.
   Hardware, physical works and supplier use of software must not become delivery
   evidence merely because they carry an IT-related code.
4. Compare gained/lost IDs, reasons, duplicate handling and collection cost before
   changing production relevance rules. Review any lost valid record individually.

This work needs no new source subscription. It does need evaluation; the report
does not claim that a code-based admission bonus will improve precision or recall.

## Quebec: a useful source to evaluate next

The [official SEAO dataset](https://www.donneesquebec.ca/recherche/dataset/systeme-electronique-dappel-doffres-seao)
lists CC BY 4.0 and covers Quebec public bodies, including municipalities. Its
description distinguishes JSON containing ongoing calls for tenders from XML
contract history. Weekly and monthly JSON resources are listed; the publisher
describes their format as inspired by OCDS. Use the linked format specification,
rather than assuming every release satisfies the complete standard.

The initial PR reported that consecutive weekly files omit still-open notices
present in earlier files. Treat that as a delta-handling requirement to reproduce,
not proof that a fixed backfill window is complete. A collector should retain
previous notices, process cancellations/awards/amendments and respect deadlines;
absence from one weekly file must not close an opportunity.

Before implementation, pin representative resource URLs and hashes. Verify whether
each notice is a full-state release or a partial update before choosing a merge
algorithm. Keep release identities and history; do not discard a process's earlier
awards or lots just because another release has the same `ocid`. The
[OCDS merge rules](https://standard.open-contracting.org/latest/en/schema/merging/)
are the reference for partial releases, including explicit deletions.

Measure current update lag, description completeness, French translation work,
corrected historical files and overlap with CanadaBuys. Catalogue availability is
not a seven-day delivery guarantee. Use conditional requests where supported,
bounded resumable backfill and attribution. Confirm the chosen distribution's
terms separately from linked documents or the interactive SEAO application.

## Poland: a documented read API with pagination checks to reproduce

The [official integration page](https://ezamowienia.gov.pl/pl/integracja/) identifies
`https://ezamowienia.gov.pl/mo-board/api/v1/notice` as the BZP read interface and
says this read access does not require the integration procedure used by other
platform APIs. [Platform terms, section 11](https://ezamowienia.gov.pl/pl/regulamin/),
describe a free service and require users to review the terms.

The original research reported these observations, without committed response hashes:

- `PageSize=500` could return exactly 500 rows without indicating truncation;
  several guessed pagination parameters appeared to be ignored.
- `CpvCode=72` returned codes containing `72` in the middle as well as at the start.
- CPV values could contain labels and multiple codes; `htmlBody` dominated payload size.

These are useful fixture requirements, not a claim that all pagination mechanisms
are absent or that one day's successful query proves complete coverage. Check the
current documented contract. A saturated response must trigger verified pagination
or smaller supported time windows; if completeness cannot be established, preserve
the checkpoint and report partial coverage. Apply exact CPV prefix matching locally,
and collect lifecycle changes as well as new competitions. Check relevant records
without CPV before choosing a code-only collection filter.

Establish the applicable reuse scope for descriptions and separate translations
before public republication. Retain explicit source/TED identifiers for deduplication;
a below-threshold flag or similar title alone is not a cross-source identifier.

## Ireland and Portugal: separate interfaces and freshness

| Source | What is supported by the evidence | Next check |
| --- | --- | --- |
| Irish catalogue distribution | The [official eTenders dataset](https://data.gov.ie/dataset/contract-notices-published-on-etenders) is labelled CC BY 4.0. | Inspect the selected file's latest notice/update dates; a recently edited catalogue entry does not establish fresh records. |
| Irish live website export | PR #18 reported a working `POST https://www.etenders.gov.ie/epps/viewCFTSAction.do` using the search form. | Verify the live interface's access/reuse terms separately. The catalogue licence is not evidence that additional/current website content is covered. |
| Portuguese announcements | The [IMPIC announcements catalogue](https://dados.gov.pt/pt/datasets/contratos-publicos-portal-base-impic-anuncios-de-2012-a-2026/) is already in the disabled registry. | Verify current resource freshness, lifecycle and reuse scope for the chosen resource. Failure of one BASE endpoint is not proof that other official distributions are unavailable. |

The Irish probe reported that `isQuickSearch=false` and paired `cpvArray` /
`cpvLabels` were important to avoid ignored filters. It also found a catalogue
file ending 2026-06-30. Those are dated observations to reproduce, not permanent
properties. No current delivery forecast or integration priority is based on them.

## Sweden: public reading and systematic collection are different

[Konkurrensverket's March 2026 decision summary](https://www.konkurrensverket.se/informationsmaterial/nyhetsarkiv/2026/konkurrensverket-avslutar-arende-om-krav-pa-funktioner-i-annonsdatabas/)
confirms that Mercell changed public search and award-notice access following its
investigation. That establishes useful human access; it does not establish
permission for Signal's bulk extraction and republication.

The [Kommers eLite terms](https://www.kommersannons.se/elite/Info/TermsOfUse.aspx)
require prior written approval for systematic extraction unless an API or designated
interface expressly permits it (section 3.4). Sections 3.3 and 5.4 also address
redistribution and attribution. Keep Kommers disabled pending an applicable approved
route. An unsuccessful search for terms at guessed URLs is not evidence that no
terms exist.

Mercell and e-Avrop remain candidates for interface/permission verification.
The [Mercell terms landing page](https://www.mercell.com/en/82175855/terms-and-conditions.aspx)
directs users to its current legal documentation. Match terms to the exact service
and intended use. This assessment does not certify yearly notice volumes, incremental
coverage beyond TED, vendor redistribution offerings or subscription prices.

## Other leads retained for later investigation

These are disabled candidates, not additional collected coverage. A reported
restriction or failed request is scoped to that interface and test date.

| Candidate | Useful lead | Unresolved work |
| --- | --- | --- |
| Saskatchewan / SaskTenders | PR #18 reported paginated public notices and award details. | Establish supported collection and reuse terms; absence of a located licence is not a legal conclusion about every record. |
| Nova Scotia | The [official catalogue](https://open.canada.ca/data/en/dataset/d8a4e021-434d-709f-b135-4e282987d09c) links an awarded-tenders distribution (`m6ps-8j6u`). | Verify current licence and updates. Award dates are not necessarily modification timestamps; do not use them alone as a changed-since cursor. |
| BC Bid, Alberta APC, Ontario Tenders | Potential provincial procurement coverage. Earlier browser/API probes encountered access or response problems. | Verify a supported interface and its conditions; do not bypass CAPTCHA or infer province-wide absence from an endpoint error or catalogue search. |
| MERX / Manitoba | Potential coverage through an authorized distribution or agreement. | Applicable terms and a permitted route remain unresolved; no permanent market exclusion is established. |
| bids&tenders | Potential municipal notice coverage. | Its [terms of service](https://bidsandtenders.com/terms-of-service/) restrict automated commercial extraction. Establish an authorized supply route before implementation. |
| Texas ESBD / Virginia eVA | PR #18 reported JSON/Solr interfaces. | Check supported access, terms, pagination and genuine update cursors before relying on them. |
| ComprasMX | A potential Mexican source requiring its own assessment. | Establish the chosen distribution's licence, fields, lifecycle and retrieval contract. General website terms alone do not establish the terms of every independent dataset. Mexico is not added to North America. |

[Robots Exclusion Protocol, RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)
matches crawler identities and paths and is not access authorization. Respect the
applicable restrictions; a robots rule is neither a reuse licence nor proof that no
separately authorized distribution can exist. Do not assume a paid subscription
or reseller includes bulk republication rights without examining its terms.

## Implementation order and verification

First measure the native-classification gap against complete retained records.
In parallel with a future implementation decision, Quebec's explicit distribution
and Poland's documented read API are useful candidates for small reproducible
adapter evaluations. Resolve Ireland's live-export scope and Swedish systematic
access before treating those interfaces as ready to implement.

Each adapter needs bounded requests, resumable updates, overlap/deduplication,
source attribution and retained history. Unknown or missing classification must
not silently discard good records. Missing snapshot entries and incomplete pages
must not become fabricated cancellations. Keep English translations separate from
the source and reuse existing publisher English when present.

The registry additions are all disabled; all pre-existing source definitions and
enabled collectors remain unchanged. No API key, paid service, outbound contact,
new UI copy or production collection change is introduced by this research PR.
