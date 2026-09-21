# Context, country labels and Canada

## Workspace changes

Grouped markets, including All, show each notice's country beside its type and update marker. North America replaces the default US tab. United States and Canada remain independently selectable and pinnable. Existing US links still work; the one-time preference migration preserves other pins and ordering.

Context has the selected record, related current signals, and related awards, in that order. Only the selected record has a metal border. At smaller widths the columns stack. Each related column has text search and a Filters control containing buyer/supplier, date and value ranges. Mixed currencies require a selected currency before applying a value range; there is no currency conversion. Only a small page of matches is rendered, but filtering covers all matching records.

Related records combine exact procedure and buyer connections, shared capabilities within a country, and distinctive terms from original and cached English text. Boilerplate and frequent corpus terms carry less weight. The text index runs in a browser worker: a local 25,068-record corpus took about 3.6 seconds to index and 61 ms per query before moving this work off the interface thread. No model requests are made. These are related records, not assertions that two notices describe the same contract.

English/Original uses one saved preference across the main page, Context, buyer/supplier timelines and opened records. History entries reuse valid cached English titles. A source revision and its translation update together. Missing translations fall back to original text.

Record titles in these pages open the actual retained record with full details and Back navigation. Historical records are published as linked history details, separate from current opportunities and relevant award indexes. No source facts are borrowed from the record used to reach a timeline. Salesforce is hidden on unavailable/awarded records; Gmail and the existing Slack placeholder remain. Salesforce prefill is the next integration stage.

Buyer timelines retain the metal border; their selected-record and contact panels use plain borders. Distinct sources include their hostname beside the existing source button. Repeated links to the same listing remain collapsed.

## Canada collection

The enabled `canada_buys` adapter uses the official, anonymous CanadaBuys CSV downloads. No API key, account, AWS service, or paid data subscription is needed for these downloads. The [official data catalogue](https://canadabuys.canada.ca/en/procurement-and-contracting-data) links tender notices, awards, contract history, and standing-offer/supply-arrangement datasets. This implementation collects new/open tenders and the current fiscal year's tender and award files. **Its coverage is federal; it does not claim provincial or municipal coverage.**

The [publisher's supporting documentation](https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/ac-cb/soutien-support-eng.html) defines bilingual columns in one row, fixed UTC−05:00 closing times, two-hourly new notices and daily remaining files. Some source systems arrive later, including monthly award transfers. The adapter respects these distinctions and uses the source's English text where supplied; French-only scope enters the existing translation queue.

The current fiscal year changes in April. Retained records remain available after rollover, while older fiscal-year backfill and dedicated provincial adapters remain future work. The publisher's small OCDS pilot is not treated as a complete live API. Published supply-arrangement restrictions remain source facts to check; an open notice does not establish Anthrion's eligibility.

Implementation boundaries:

- HEAD metadata and a matching GET ETag/length validate each complete snapshot before advancing its checkpoint. Per-file size, row count, request budget and emitted revisions are bounded.
- At most 1,000 changed records per file are emitted in a pass. Checkpoints acknowledge emitted rows only; pending history resumes. English and French fields do not create duplicate notices.
- Reference/contract identifiers keep amendments stable and awards separate. Published solicitation number plus buyer connects procurement history.
- “Open” source status does not override an expired response deadline. Removal from the daily open list needs two distinct verified snapshots; it never manufactures an award, cancellation or fresh deadline. Explicit/new incoming notices take precedence over list absence.
- Original descriptions, typed award amounts/currency, supplier names, contract dates, published tender links and document links are retained. Document reuse rights are not inferred from the dataset licence.
- The first verified live pass contained 2,901 notices; historical bootstrap is resumable. Coverage counts continue to change as collection runs.

## Relevance audit

The Canadian feed contains useful delivery scope beyond named Salesforce notices, including [IRB Digital Case Management TBIPS](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-803-76594845), application maintenance/development and cloud transformation. The IRB notice was present in the verified source with a 25 September 2026 response deadline and a supply-arrangement route; eligibility remains a manual source check.

The audit also found concrete noise: SAP Ariba registration text mentioning Commerce Cloud on a trailer procurement, mechanical gate integration, physical alarm monitoring, retail goods fulfilment and uncrewed equipment. Matching now distinguishes those from separately commissioned business software. Each added exclusion has a paired test that adds real Salesforce/API delivery and confirms the record remains eligible for discovery. Original notices remain in retained storage. This is an evidence-based improvement, not a claim of perfect recall or precision across all markets.

## Data size and future work

Public JSON is compacted without changing parsed source facts or canonical content hashes. Linked history details have their own publication view and cannot enter the live index. Export and build validation reject unrelated history files and preserve the existing site-size guard.

For the buyer page, a useful next addition would be a compact list of published contract end dates and supplier relationships. It should distinguish recorded end dates from speculative renewals and should use the same retained evidence. Salesforce prefill and source-grounded summaries remain separate implementation stages.
