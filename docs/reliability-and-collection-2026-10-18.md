# Build, collection and storage audit — 18 October 2026

## Build failures

Of the latest 100 runs inspected (9–18 October), two failed and one was cancelled.
Runs [39071137300](https://github.com/Anthrion/anthrion-signal/actions/runs/39071137300)
and [38943313103](https://github.com/Anthrion/anthrion-signal/actions/runs/38943313103)
both failed the UK awards browser assertion after its 10-second wait. Collection
had persisted successfully; publication was correctly withheld. The trace and
screenshot show that the 11,499 UK awards subsequently rendered.

The exact failed-run UK index contained 247,546,756 decoded bytes. Cache admission
serialized it again before rejecting it as oversized. Local replay measured
1,417 ms and about 497 MB of additional heap for that unnecessary operation.
Remembering the decoded JSON weight removes that second serialization (0.3 ms in
the same replay). The weak reference adds no retention and cache limits remain.
The independent Playwright data reader now disposes response buffers on success,
fallback and error. The data-specific rendering assertion allows 45 seconds and
identifies the market in the test step; correctness assertions are retained.

Award indexes now omit only the repeated procedure timeline, retain every search,
ranking, source and translation field, and load the complete existing detail on
opening a record or research page. Publication validation requires exact equality
with that detail except for the intentionally omitted timeline and summary flag.
For the same UK payload this reduces decoded size to 64,337,457 bytes (74% smaller),
and gzip transfer from 20,061,891 to 8,790,275 bytes (56% smaller). No history is deleted.

Another run encountered a long Git fetch and was later cancelled. Release and PR
checkouts now use `filter: blob:none` with full commit ancestry: current files are
checked out, while historical file bodies are fetched only if needed. No signing,
review, receipt, publication or branch-protection checks are bypassed.

## Collection audit

Snapshot: main `5d7b9e38bfa38abacd74fdb5a3cb996001378759`, collected 18 October at
15:28 UTC. All 33 selectable countries have retained current candidates. Since
12 October, 31 countries have new candidates still present in that current feed;
Canada and Iceland have none in that subset. This is not a count of all raw notices
or proof of complete national coverage. UK has 104 and Ireland 11.

| Source | Observation | Action |
| --- | --- | --- |
| Find a Tender / Contracts Finder | Healthy; 105 / 1 rows received on the inspected pass | Preserve cursor, overlap and retry behavior |
| Digital Outcomes / upcoming agreements | Healthy; 49 / 47 rows | No collector change |
| GOV.UK | 166 rows; query-family budget continues next run | Preserve resumable search |
| Scotland / Wales | Connection failures, reproduced with a 60-second read-only probe | Retain records and retry; an upstream connection failure cannot be fixed by disabling validation or TLS |
| TED | 887 rows; open-notice inventory continues within its budget | Keep current collection and resumable historical/inventory work |
| Germany national | 15 October OCDS export has 1,301 entries, eForms only 1,000 | Admit the 1,000 verified pairs, retain the incomplete day and missing pairs for retry, continue other days |
| Spain | Healthy; unchanged head, zero new rows on this pass | No change |
| SAM / NYC / Los Angeles | Healthy snapshots/checkpoints | No change |
| Grants.gov | 356 rows; some individual details unavailable | Retained details remain; failed details retry |
| CanadaBuys | 12 open notices omit publication/amendment dates; rejecting these blocked all 899 open notices | Preserve omitted dates as unknown, use explicit amendment numbers when dates are unavailable, reject invalid dates and ambiguous revisions; checkpoint the four snapshots independently |

The German repair was replayed against the actual two source ZIPs: all 1,000
paired entries normalized, including 387 broad retrieval candidates. The 301
unpaired entries remain outstanding; they are not silently marked collected.
An initial Canadian probe returned HTTP 403. A follow-up using the collector's
normal identity succeeded: the annual tender and award files contained 3,497 and
4,603 valid rows. The open file had 899 rows, including 12 SSC notices whose dates
were genuinely blank. These now remain unknown rather than being invented or
blocking the snapshot; the deadline and amendment number remain available.
Offline replay of all three downloaded files parsed and normalized 8,999 rows
successfully, with precisely those 12 publication dates left unknown.
Failure messages name the affected Canadian snapshot. Run summaries list partial/failed sources as well
as overall collection success, making these gaps visible in Actions.

Collector HTTP requests already use a 40-second timeout and bounded retries,
not a 10-second timeout. Find a Tender's 10.1-second inter-request pause is a rate
limit interval, not an abandonment deadline. It is retained.

Most European countries use TED coverage, with additional national adapters for
Germany and Spain. Canada is federal; US coverage is federal plus the configured
city/funding feeds. An enabled country is not a claim that every national,
regional, municipal or below-threshold portal is included.

## Storage

The inspected checkout contains 649,519,125 tracked bytes (619.4 MiB), including
636,159,942 bytes of retained data. Rejected-notice retention is already compressed
and occupies 417,053,490 bytes (64.2% of the checkout). The published website is a
separate footprint: the last successful build measured about 500 MiB, roughly
half of GitHub Pages' 1 GB published-site limit. The verified rebuild is 482.2 MiB.

Source state, deduplication and archive indexes previously remained plain because
each was below the old 32 MiB compression threshold. Their combined 45,276,163
bytes compress losslessly to 13,845,842 bytes: a 31,430,321-byte saving. The threshold
is now 8 MiB, the index writers preserve compression, and every migrated byte is
verified after writing. Scheduled collection performs the migration on its latest
state; this release does not overwrite current checkpoints with an older local copy.

Keep the useful awards, translations, renewal facts and replayable rejection
history. These changes buy headroom without deleting any of them. Compression
reduces current snapshots and future growth; it does not shrink old Git history
or make storage unlimited. Existing size checks remain in place. If continued
growth approaches those budgets, move immutable data to object storage rather
than deleting useful records or splitting the application across repositories.

## Workspace changes

UK&I appears immediately after All by default, using the existing GB and IE
shards with record-ID deduplication. Both countries remain independently
selectable/pinnable; explicit country links and saved starting-market preferences
remain valid. The old UK pin migrates once; subsequent custom arrangements persist.
The Slack placeholder and unused logo are removed. Salesforce continues to use
the configured sandbox and Gmail/copy-link remain available.

## Verification

The complete export validates 8,403 current records, 40,077 awards and 67,356
hashed data files, including evidence and linked histories. The production build
is 482.2 MiB. All ten real-data desktop/mobile checks pass, including every award
market. Fixture UI checks, full-history hydration, translations, CSP, frontend
unit tests and the relevance benchmark also pass. The first GitHub PR verification
completed in 8m57s; its filtered full-history checkout took 24 seconds.
