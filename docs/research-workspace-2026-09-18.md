# Research workspace release

This batch makes source evidence, buyer history and qualification research available from the existing Signal record. It retains anonymous public discovery, Salesforce/CRM-first ordering and the separate historical-award view.

## What the team can do

| Action | Result | Evidence boundary |
| --- | --- | --- |
| Click a capability | Inspect its exact supporting passage, source and context | English evidence must match the stored source-text hash; the original remains available |
| Open participation checks | See published registration, membership, licence, certification and similar requirements | “Needs checking” is not a company eligibility conclusion; missing requirements are not clearance to bid |
| Read the amount | Distinguish estimates, grant ranges and confirmed awards | An older untyped amount stays unqualified; framework estimates are not automatically maximum ceilings |
| Inspect deadline events | Separate enquiries, applications and invited submissions and add a supported event to a calendar | A date-only source remains an all-day reminder; unknown timezone does not become an invented instant |
| Click a buyer | Open its collected contract and notice timeline, suppliers, lots and available financial/period facts | Published IDs take precedence; same-name grouping is limited to source and jurisdiction; no fuzzy entity merge |
| Click a record title | Compare the selected requirement with related awarded contracts | Each match explains its basis; a shared capability does not establish a predecessor contract |
| Filter Awarded | Search suppliers and actual award-date ranges | Notice publication/update dates do not substitute for missing award dates |
| Set search intent | Choose exact text or text plus capabilities, and all/any/phrase matching | Original text and available translations are searchable; language aliases are curated, not general query translation |
| Save a named view | Restore its complete filter state and remove individual filter chips | Stored in this browser; no team notes or commercial data are published |
| Drag the separator | Give the opened record more room, or adjust it with arrow/Home/End keys | Width is clamped for readable panes; mobile retains its drawer |
| Arrange markets | Pin, reorder or move market groups to More | Preferences persist locally; All deduplicates records across the included countries |

Buyer history contains all linked **collected** notices, with progressive display for long timelines. It is not a claim to know all of a buyer's purchases. Where OCDS identifies the awarded lots, partial awards preserve the other open lots. TED awards do not retire a whole admission system merely because they share its procedure identifier. Unpaired Spanish tender results retain the existing conservative availability policy; this batch cannot infer which remaining lots are open. Source documents, amendments and identifiers remain linked; incomplete or uncertain fields stay visibly unknown.

## Market groups and collection

**DACH** contains Germany, Austria and Switzerland. **Benelux** contains Belgium, the Netherlands and Luxembourg. Country identifiers and country-specific URL filters remain intact. Grouping is a browsing preference, not a merger of source records. Nordics remains Sweden, Finland, Denmark, Norway and Iceland. All sits immediately after UK in the default market row; the far-right More and pencil controls expose and arrange the other markets.

The additional European countries use the official TED API. Germany and Spain retain their existing national collectors, and existing UK/US collectors remain active. TED coverage does not imply comprehensive national or below-threshold coverage. Switzerland's separate national portal is not enabled without its own access requirements being established.

The reviewed market vocabulary and national-source assessment from [PR #8](https://github.com/Anthrion/anthrion-signal/pull/8) are incorporated into this release. Precise software aliases are retained; broad human-service phrases are not treated as software requirements. The [source assessment](free-apis-market-expansion-2026-09-18.md) distinguishes primary documentation from contributor-reported API observations. Additional national-source registry entries remain disabled. Existing country-specific URLs keep their original meaning.

A new TED inventory looks for still-open tender, participation and expression-of-interest dates without imposing a recent-publication cutoff. It supplements fresh notices and amendments rather than replacing them. Two requests per scheduled TED collection are reserved from the existing page budget. The lane persists a frozen date boundary, unique publication-number order, continuation cursor and observed IDs; invalid, repeated or truncated pages cannot be reported as complete. It respects retry windows and a completed-cycle cooldown. Deadline-free early engagement and historical awards continue through their existing collection lanes.

The release's bounded official inventory recovered all four targeted source-reference controls from the earlier platform comparison. Those four controls are a coverage regression check, not a measurement of total market recall. The original snapshot and receipt remain with the audit working files; no Hermix account data replaces an official public source.

## Documents and source facts

The first document-retrieval policy covers official TED notice PDFs whose host and URL path match the reviewed reuse policy. Each run considers at most two permitted documents. Downloads are streamed with a 4 MB limit; extraction has an 80-page/160,000-character ceiling, a subprocess timeout, PDF decompression limits and Linux resource limits. Redirects must satisfy the same policy. Login-only documents are not bypassed, and unsupported/scanned files retain their source link rather than inventing extracted text.

The cache records source URL, retrieval time, content hash, revision, page text and previous revision references. Binary files are ignored by Git; only permitted attributed text and metadata can be published. A changed hash produces a new revision. Other attachments remain linked; automated OCR and unrestricted downloads from third-party procurement portals are outside this batch. See [document evidence and reuse policy](document-evidence.md).

Grants.gov organisation fields are separated from named contacts using authoritative cached fields where available. Ambiguous legacy names are retained as conflicting source facts rather than promoted to a buyer. Source text and exact-hash English overlays remain separate. No AI fit score, invented company certification or inferred permission to subcontract is introduced.

## Loading and consistency

The publisher writes content-hashed market search indexes, full-record files and buyer-history files before replacing the root manifest. Search indexes include full original/translated searchable text, even though the readable description loads on selection. All loads every required nonoverlapping market index. Request concurrency and caches are bounded; old in-flight results cannot overwrite the selected market.

Manifest, path, identity and record-count validation prevents a partial shard from silently becoming a complete feed. A stale deployment can refresh its manifest or fall back to the full `current.json` feed. The selected record and buyer history have explicit loading/retry states. Legacy direct links, saved IDs, personal Hide and the original full-feed format remain supported.

On the same production build and 5,529-record dataset, three cold UK loads per mode gave a median **3.62 seconds** to visible records using indexes versus **9.47 seconds** using the full-feed fallback (62% faster). JavaScript heap fell from **77.44 MB to 27.36 MB**. Decoded data fell from **70.28 MB to 8.80 MB**, while observed compressed data transfer fell from **8.98 MB to 1.31 MB**. The search-input/two-frame proxy was 625 ms versus 760 ms. No browser errors occurred.

These measurements used headless Chromium at 390×844, fourfold CPU throttling, 60 ms latency, 1.6 MB/s download and a fresh context/cache per run against local Vite preview. They are an emulated comparison, not physical-phone or production-network percentiles. The measured snapshot preceded the final narrow multilingual scope corrections. See [the measurement receipt](audits/research-workspace-2026-09-18/performance.json).

The production build copies the complete manifest-referenced publication and rejects an inconsistent or oversized site. Superseded local generated files are not shipped; referenced history is never discarded to meet the size limit. Canonical storage omits only default-valued enrichment fields introduced in this batch, which model validation restores exactly. Populated facts, older fields and nested documents retain their representation. This reduces unnecessary growth near GitHub's file limit, but retained history is not an unlimited storage service. See [the publication and size guard](public-data-build.md).

## Relevance evaluation

The regression gate measures precision and recall separately across reviewed cases, with source/language/type breakdowns and uncertainty intervals. Related procurement aliases and buyer identifiers stay within one evaluation split. A deterministic stratified queue supports blind review of accepted and rejected records; labels are never copied from the classifier. A separate agent reviewed 60 of 180 queued cases; primary adjudication preserved plausible specialist software and sparse mixed-scope notices. Confirmed policy examples moved into regression fixtures. This is not human ground truth or a population accuracy result. See [the benchmark workflow](relevance-benchmark.md).

The prior purchased-scope audit remains a separate reproducible release: [audit report](purchased-scope-audit-2026-09-18.md). This batch does not relax those scope guards to populate new markets.

The final fixed-input replay covers **81,186 retained records**, including rejected and historical records, with identical source text and exact-hash translations before and after classification. It removes 23 candidate classifications supported only by unrelated services or licence purchases, restores seven explicit software or uncertain IT candidates, and corrects eight displayed capability classifications. Five of the removals affect the current feed; six affect awards, with three historical awards restored. These counts precede publication identity reconciliation and are not final feed totals. All changed decisions were inspected against their retained source passages. See the [comparison](audits/research-workspace-2026-09-18/retained-replay-comparison.json) and [frozen replay metadata](audits/research-workspace-2026-09-18/retained-replay-summary.json).

The final labelled regression benchmark contains 397 determinate cases and six uncertain or unlabelled cases. The determinate set has 155 retained positives, 242 excluded negatives and no disagreements. These are reviewed regression examples, including cases used to improve the rules; the result is not evidence of perfect performance on unseen tenders. Native-language controls protect mixed software lots, migration, application maintenance, negative statements and later affirmative statements in the same notice. See the [benchmark receipt](audits/research-workspace-2026-09-18/relevance-benchmark.json).

One sparse TED amendment had retained a numeric value while losing its original meaning and source. The offline repair restores the supported estimated value from the retained original notice and records the original provenance; its source text, raw hash, surviving amount, currency and fingerprint remain unchanged. Future sparse revisions preserve these facts as a unit. See the [repair receipt](audits/research-workspace-2026-09-18/sparse-amount-repair.json).

Cached Grants.gov corrections are applied after rejected-notice reconciliation as well as before it. An equal-timestamp older normalization can otherwise reintroduce a contact as the buyer or an artificial midnight deadline, prematurely hiding a grant on its closing day. The integration regression exercises both rescore and publication recovery on the source closing date. Seventeen retained, currently excluded grant records received only the proved buyer/deadline corrections and their derived hashes; their source text, raw hashes, provenance, classification and current availability are unchanged.

Release reconciliation compares archived records with their original canonical ancestor when retention has moved them between files. It rejects conflicting source facts and mixed financial fields for review. A replacement price carries its bounds, currency, meaning and source together; an unchanged legacy price preserves its previously supported meaning. Source revisions with reused release IDs remain distinct by URL and raw-content hash, while identical content keeps its latest retrieval. The existing 60-version provenance bound remains in place.

The pre-refresh validated publication contains **5,522 current records and 17,265 awards**, with all displayed capability labels supported by retained passages. Its 7,795 buyer pages contain all 48,759 linked collected history entries. All four official-source reference opportunities are present. Relative to the pre-review current snapshot, the seven missing entries comprise five inspected scope exclusions and two genuinely passed deadlines; no other current entries were lost. These are snapshot counts, which will change as collection and deadlines advance. See the [publication checks](audits/research-workspace-2026-09-18/enhancement-public-verification.json), [current membership comparison](audits/research-workspace-2026-09-18/final-current-membership-delta.json) and [retained source-integrity checks](audits/research-workspace-2026-09-18/final-source-integrity.json).

The **19 September release reconciliation** incorporates the subsequent scheduled collections and translations. All **87,073 combined retained IDs** survive, with no lost source/provenance members or incoherent amount fields. Its validated publication has **5,571 current records and 17,831 awards**; 7,894 buyer pages retain all 51,105 linked history entries. The current-feed difference is 58 additions and nine source-marked expired records, all still retained. Fourteen raw-source reference refreshes point to more recently retrieved versions without changing source text or publication metadata. The classification policy and the latest translation, quota and publication checkpoints remain intact. All 1,484 local Python tests and Ruff pass. See the [reconciliation and publication receipt](audits/research-workspace-2026-09-18/release-reconciliation-2026-09-19.json).

## Deferred by agreement

Shared Working flags, private notes and company-evidence confirmations wait for authenticated Salesforce integration. Salesforce creation/opening, AI PR reviews, Slack delivery and calendar synchronisation remain separate work. The Gmail draft and one-time calendar actions continue without those integrations. No company-wide GitHub settings, paid services or translation quota increases are part of this release.
