# Collection, build time and storage — 19 September 2026

## Failed build and measured costs

[Run 35445946721](https://github.com/Anthrion/anthrion-signal/actions/runs/35445946721) failed while pushing generated data: `data/signals.jsonl` reached 106.36 MB and GitHub rejected it. Its checks had passed. The subsequent translation-only run deployed successfully from the previous retained data; that did not repair the next collection's file-size problem.

| Work in the failed run | Duration |
| --- | ---: |
| Collection, reconciliation and initial public export | 16m 33s |
| Translation preparation, another public export and capped translation | 8m 47s |
| Validation, final public export and translation audit | 4m 32s |
| Python regression tests and lint | 3m 47s |
| Frontend unit tests and build | 29s |
| Browser installation | 20s |
| Data refresh browser checks | 1m 52s |

The full desktop/mobile suite was already skipped on this data-only run. Deleting browser checks would save little compared with avoiding repeated processing.

Within the collection step, the last source finished at 13:34:21 (about three minutes after starting), while reconciliation/classification completed at 13:42:40. Repeated scope evaluation, not just network collection, was a major cost. A new discardable classification cache reuses only decisions with identical source scope, buyer, CPV, source/type, translation and policy/engine signature. Duplicate input versions share evaluation. Cache corruption or eviction causes recomputation; source records and rejection evidence remain retained. Lifecycle, deadlines and cancellation remain fresh checks. Translation preparation saves these derived decisions for the final export to reuse.

The updated workflow exports the public assets once, after translation. Collection still validates and persists canonical records and source checkpoints. Translation selects the same eligible source records without assembling unrelated award/history assets. Full Python and browser regression suites run for changed code, daily verification or an explicit full-test request. All publications retain schema, source-evidence, URL, public-data, translation, frontend and desktop/mobile smoke checks. A failed full run never marks that code/day as verified. Translation calls, quota reservation and provider backoff remain unchanged.

These changes remove redundant work; they are not a guaranteed runtime. Source latency, backlog and first-time policy reclassification still vary. Confirm steady-state duration from successful production runs after deployment.

## Storage decision

| Local snapshot | Before | Lossless gzip |
| --- | ---: | ---: |
| Canonical records | 97.68 MB | 17.41 MB |
| Current dataset | 71.28 MB | 9.74 MB |

These are decimal MB measured on the local retained snapshot, not the rejected runner's unavailable file. Decompression reproduces the input bytes exactly. Source fields, descriptions, archives, IDs and audit evidence are preserved. Small files remain plain until 32 MiB; once migrated they stay compressed. Browser-facing files remain ordinary JSON with the existing market/detail partitions.

GitHub blocks regular Git files above [100 MiB](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). A 95 MiB pre-push guard provides headroom. No Git LFS, new subscription, history rewrite or silent record truncation is introduced.

Avoid a `part-2` file opened whenever `part-1` reaches 90 MB. Amendments then need a global index to locate the original record; records can cross size boundaries and make unrelated partitions churn. The next deliberate migration should use stable notice-ID hash buckets for current records, with a versioned manifest containing counts and hashes. Keep older historical records in their existing time partitions, with smaller subpartitions if needed. Verify the union of IDs and all source fields before switching readers. That migration is recommended, not implemented by this compression repair.

Compression does not stop Git history from growing. Monitor total repository and publication size as well as individual files. GitHub recommends small repositories and limits published [Pages sites to 1 GB](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits). If collection becomes much larger, put mutable data in purpose-built storage with a reviewed budget while retaining code in Git. File splitting alone does not solve a growing total dataset.

## Keyless SAM.gov

GSA lists the public opportunity extract in the [federal data catalogue](https://catalog.data.gov/dataset/contract-opportunities-from-sam-gov), linking to [SAM public data services](https://sam.gov/data-services/Contract%20Opportunities?privacy=Public). Its anonymous distribution is [ContractOpportunitiesFullCSV.csv](https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv). The authenticated opportunity search API is a different interface.

The verified 19 September snapshot contained 83,951 rows and 243,979,752 bytes. It downloads to temporary storage on the collection runner, not to the browser or Git. No AWS account or SAM API key is needed. This is the published extract, not a guarantee of all historical contracts, full attachments or real-time updates.

The collector checks freshness, ETag, exact byte count, encoding, CSV structure, duplicate IDs and snapshot size before advancing. It handles the observed Windows-1252 and UTF-8 without replacement characters. At most 3,000 new or changed notices are classified per collection. Pending records resume even when the file's ETag has not changed; they are not discarded as irrelevant. Once caught up, daily cooldown and ETag checks avoid unchanged downloads and repeated normalization. Source health reports the remaining backlog.

Every row is eligible for the common classifier: no hard-coded NAICS allowlist or title blacklist is used. Administrative submission, invoicing and quotation clauses cannot establish software scope. Separate CRM, API, AI or other commissioned software still preserves mixed physical procurements. Original text remains intact and rejected source records remain replayable. Regression fixtures cover both negative examples and their positive mixed-scope counterparts.

`Active=Yes` means listed in the extract, not that bidding is open. Published deadlines and notice type control lifecycle; awards go to historical intelligence. Set-aside wording is retained without inventing Anthrion's qualification. A notice disappearing from two independently revised, fully validated snapshots is marked no longer listed, not assumed awarded. Reappearance restores its source status. A partial/failed download cannot retire existing records. Published office identifiers scope buyer and solicitation matching; overseas performance locations do not incorrectly move a US federal buyer into another market.

## Country collection coverage

| Market | Active collection | Remaining gap |
| --- | --- | --- |
| France | TED | Dedicated BOAMP/PLACE and below-threshold completeness are not implemented. |
| Benelux | TED for Belgium, Netherlands and Luxembourg | Direct national portals, including TenderNed and Belgian e-Procurement, remain research entries. |
| DACH | TED for Germany, Austria and Switzerland; German official national exports | Direct Austrian and Swiss portal coverage is not complete. |
| Spain | TED plus the national PLACSP feed | National pagination/backfill can be partial and resumes under the request budget. |
| Italy, Greece, Nordics and other European tabs | TED country queries and resumable inventory | A country tab does not establish exhaustive national/below-threshold coverage. |
| UK | Find a Tender, Contracts Finder, Scotland, Wales fallback, Digital Outcomes and other configured official sources | Provider outages and bounded backlogs remain visible in source health. |
| US | SAM public CSV, NYC, LA and Grants.gov | SAM bootstrap and grant-detail backlog are resumable; no assertion of every state/local portal. |

Grouped and individual market tabs use the same country records. Splitting the UI does not require duplicate collection. France and Benelux have a real TED pipeline; they do not yet have complete independent national pipelines. Translation is separately queued across countries, with original records visible while English text is pending.
