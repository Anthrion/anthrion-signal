# Anthrion Signal

Public procurement and commercial opportunity discovery for Anthrion's sales team. The React/TypeScript console reads a static, validated dataset. Python collectors run locally or in GitHub Actions. Collection requires neither a language model nor a paid tender-data subscription.

## Workspace

The console opens on **Live Opportunities**, ordered by recent publication. Salesforce, CRM and clearly related platform implementations appear first, including combined platform/AI projects. Standalone AI follows, then other relevant opportunities. Each group retains the selected recency, update, deadline or value order. There are no score thresholds or model assessments.

The five refiners are **All Signals**, **Live Opportunities**, **Pre-market**, **Closing Soon**, and **Added today**. Pre-market combines requests for information, market engagement, pipeline and genuine future buying intent; these are not presented as open tenders. Unknown deadlines do not enter Closing Soon. Added today means first collected on the current Europe/London calendar date, not recently updated or published. Frameworks and funding remain available through notice-type filters without separate refiner cards.

The default market row contains All, UK, North America, Italy, Nordics, DACH, Spain, Greece, Benelux and France. A plain site visit starts in the UK. All and individual countries can be pinned and reordered independently alongside the groups. **North America** combines the United States and Canada; **DACH** combines Germany, Austria and Switzerland; **Benelux** combines Belgium, the Netherlands and Luxembourg. Nordics groups Sweden, Finland, Denmark, Norway and Iceland. More opens the individual countries and additional European markets, and the pencil control saves each browser's preferred order and pinned markets. Country identifiers and existing country-specific links remain separate underneath the groups. All searches every current market index and deduplicates notices. A healthy source does not imply complete market coverage or confirmed bidder eligibility; new European coverage uses TED, not an assertion that every national or below-threshold portal is included.

The dark glass console uses a measured virtual list: scrolling reveals records without pagination while only nearby rows remain mounted. Desktop has independently scrolling records and details; narrow screens use document scrolling and a detail drawer. The record panel places compact notice facts and capabilities above the complete source description. A vertical integration rail sits beside those facts: Gmail opens a compose window with the selected record's displayed title, buyer, source facts and direct links, without sending a message. Salesforce and Slack are disabled until their integrations are available; Salesforce is hidden on awarded or unavailable records. Full details and Open source notice stay in a bottom dock outside the scrolling content, including on mobile. The expanded detail view retains its own source action and a Back to record control. Arrow keys and Home/End navigate record selectors. Reduced-motion preferences pause decorative animation.

Save and Hide remain in the results list and are not duplicated in the opened record or Full details view. The small, unboxed icon immediately before a record's deadline also opens a prefilled Google Calendar event titled "Deadline for tender: [title]", with the buyer and record/source links. The three integration buttons are vertically centred between the facts area's divider lines. Timed deadlines retain their exact instant; date-only deadlines use an all-day entry. The user chooses their calendar and reminders and saves the event in Google Calendar. Saved events do not automatically follow later changes to a notice's deadline.

Search, filters and sort sit between the brand and saved opportunities in the desktop header. They wrap within the header on smaller screens. Export is centred beside the glass refiners. The repeated list heading is visually hidden but retained for screen readers. A 57px action dock, compact market spacing and tighter description margins preserve more reading room without shrinking record typography; both dock actions retain 44px interaction targets.

Refiner reflections share one continuous animation phase. Scrolling a separate record list or description does not redraw stationary glass or reset its lighting. Relevant document scrolling, carousel movement and resizing still update geometry; decorative lighting remains capped at 25 updates per second and pauses offscreen, in hidden tabs and for reduced motion.

Records show source descriptions, buyers, dates, typed amounts, capability tags, documents and timelines. Capabilities appear as compact tags; duplicate source-text and decision-brief panels are removed. Qualification is checked against the source notice manually. Click the buyer to browse all its collected notice and contract history, or the record title to open Context: the selected record, related current signals and related awards. Each related column has search and compact date/value and buyer/supplier filters. Related matching combines published procurement/buyer relationships, shared capabilities and distinctive source/English terms in a browser worker. Buyer and supplier names link to their collected timelines, with Back returning to the previous page. Research pages reuse the main logo and source-button components. English/Original persists across every page and reuses cached translations. Timeline and related-record titles open full retained details with Back navigation. Award-date and supplier filters do not invent missing dates or imply a renewal is open. See [Context and Canada](docs/context-and-canada-2026-09-21.md).

The desktop separator resizes the results and record panes by pointer or keyboard and remembers the width. Search supports exact source text or text plus capabilities, all words, any word and exact phrases. It searches original text and available English translations; native capability aliases are deterministic, not automatic translation of arbitrary queries. Active filter chips remove individual constraints. Saved views is removed; validated browser-local memory restores the last search, filters, view and sort on a plain visit, with UK as the starting market. Explicit URLs take precedence. Market arrangement, pane width, bookmarks and hidden records remain browser-local. Hide remains personal and is never a global relevance label. Shared Working flags and notes are deferred until the Salesforce identity integration; this public discovery tool publishes no private team workspace.

## Collection and Availability

Official APIs and permitted public listings feed bounded collectors with overlapping windows, checkpoints and retries. Source facts are normalized, deduplicated using procedure identifiers and aliases, checked for availability, and ordered by delivery priority and publication recency. Validated public JSON is built with Vite and published through GitHub Pages.

Awards, inferred incumbent renewals, cancellations, withdrawals, expired response windows and explicitly unavailable routes are excluded from results, saved opportunities and exports. Canonical terminal records remain internally so later awards or cancellations can retire earlier leads. Ambiguous bidder eligibility is not invented; inspect the source before pursuing.

Capability classification uses explicit phrases, translated aliases, functional needs and CPV codes. Context-only words do not promote standalone AI into the platform-first group. Supplier-portal hostnames do not count as Salesforce implementation requirements. The company profile retains supplied public facts without assuming framework memberships, certifications or overseas delivery presence.

Unchanged classification inputs reuse a discardable gzip cache. Source scope, buyer, notice type, CPV, translation and policy/engine changes invalidate the decision. Deadlines, cancellation and availability are evaluated afresh; a cached relevant record does not stay open after its deadline. Evicting a cache entry recomputes its decision and never deletes a source record.

Gemini-based scoring, its SDK dependency and score-based product features have been retired. Historical canonical analysis and offline validation helpers remain for migration/history, but public serialization strips model analysis, recommendations and scores. Gemini is used separately for private, cached English translation only. Old score-filter URLs migrate to source-only views. Legacy `--no-ai` remains accepted; nonzero `--max-ai` is rejected.

## Sources

| Source | Interface and safeguards |
| --- | --- |
| Find a Tender | Official OCDS; six-hour windows, cursor resume, overlap, persistent Retry-After deferral and bounded enrichment |
| Contracts Finder | Official OCDS; daily windows, pagination, overlap and bounded record enrichment |
| Public Contracts Scotland | Official monthly OCDS; resumable rotation across months and notice types |
| Sell2Wales | Official OCDS currently has upstream errors; a permitted public-listing fallback provides explicitly partial coverage |
| GOV.UK | Official Search API; rotating buying-intent queries, excluding general directory/profile content |
| Digital Outcomes | Public listing/detail pages; paginated collection, cached details and explicit submission deadlines |
| GCA Upcoming Agreements | Public listings/details; framework stages, approximate timing and official links |
| TED Europe | Official v3 Search API; CPV/keyword discovery, lifecycle mapping and a resumable inventory of older notices with current response windows, sharing the existing request budget |
| German Public Procurement | Official paired daily OCDS/eForms exports; completed days, national-only notices and TED aliases |
| Spanish Public Procurement | Official PLACSP Atom/CODICE; bounded pending pages, terminal updates and source-local deadline safeguards |
| NYC City Record | Official DCAS/Socrata API; daily current/recent notices, stable cursor and New York timezone handling |
| LA RAMP | Official public solicitation listings; bounded detail retrieval, source deadlines and availability checks |
| Grants.gov | Official funding search/details; actual detail-call budget and reuse of unchanged facts |
| CanadaBuys | Anonymous official federal CSVs; new/open notices, current fiscal-year tenders and awards, resumable revisions and fixed UTC−05:00 deadlines |
| SAM.gov | Anonymous daily public CSV on GSA's AWS distribution; streamed, snapshot-verified and resumed in batches of 3,000 changed notices, without a SAM API key |

Failures preserve previous records and completed checkpoints. Budget-limited results are partial, not complete coverage. Retries are bounded and TLS verification stays enabled. Source-specific reuse terms remain applicable; linked documents do not automatically share a dataset's licence.

USAspending is disabled because it supplies awards rather than new competitions. Regional national-portal and multilateral registry placeholders are not active coverage. France and Benelux currently use TED; their dedicated national adapters are not yet enabled. See [collection coverage and build changes](docs/collection-and-build-2026-09-19.md).

- [European free APIs](docs/free-europe-apis-2026-09-11.md)
- [US/global APIs and GitHub budget](docs/free-us-global-apis-actions-budget-2026-09-11.md)
- [Source repairs and remaining limits](docs/source-reliability-2026-09-11.md)
- [Source-only local trial and verification](docs/source-only-discovery-2026-09-11.md)

## Local Development

Python 3.12+ and Node 22 are recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[test]'
Copy-Item .env.example .env
.\.venv\Scripts\python -m anthrion_signal.cli ingest --days 7 --max-pages 12
cd app
npm ci
npm run dev -- --host 127.0.0.1 --port 4174
```

The local route is `http://127.0.0.1:4174/anthrion-signal/`. `VITE_BASE_PATH` overrides the repository path. Collection does not require a model key. English translation uses the private `GEMINI_API_KEY` environment variable. Keep credentials out of frontend variables, public data and Git.

`python -m anthrion_signal.cli rescore` is the compatibility command for rebuilding source classification and publication without contacting providers. `export` copies validated public data into the frontend. On Windows, stop a preview process that holds the output JSON open before an atomic dataset update, then restart it.

Use `--refresh-daily` for a deliberate bounded recheck of a daily snapshot after changing discovery rules. It skips the local daily refresh interval, not provider Retry-After limits; normal scheduled runs leave it off.

## English and Value Controls

The market row offers English (default) and Original in a keyboard-accessible glass menu. English titles and descriptions are translated privately during collection, saved by source-text hash, and included in the static public dataset. In English mode, completed buyer-name renderings appear in brackets after the unchanged official name. These are machine renderings, not asserted official aliases. Shared names are translated once, and a changed official name invalidates its old rendering without discarding the notice translation. Search matches both languages. Translation never changes source IDs, eligibility, the CRM/Salesforce-first priority, original CSV facts, saved records or hidden-record storage. Pending or rejected translations leave the original opportunity visible.

Translation work alternates country buckets so large imports do not put every other market behind their entire backlog; recent notices stay first within each bucket. France, Benelux and DACH members use the same existing translation process. All reuses those country records. Translation checks are requested at minutes 05, 20, 35 and 50 every hour, including overnight; only the :50 run collects procurement data, then immediately attempts new translations. GitHub's scheduler can delay or skip runs, so these are requested times, not a latency guarantee. Each verified Flash-Lite model uses the full project limits observed in AI Studio on 2026-09-13: 15 HTTP attempts/minute, 250,000 estimated input tokens/minute and 500 HTTP attempts/Pacific day. Counting and failed requests are conservatively included; there is no extra daily reserve. The worker chooses a ready backup using the next batch's token requirements. Each pass has up to 150 attempts and five minutes, matching both models' combined minute capacity without holding up publication indefinitely. It commits that run reservation before any API request so a lost GitHub runner cannot forget its quota usage, and refunds only unused reservations on normal completion. Completed text is checkpointed separately from build/test success. Oversized passages split, temporary failures back off or use the verified backup model, and exhausted daily quotas leave work queued until reset. Notice content takes priority over supplementary names. Repeated quality failures get one additional retry round after an hour, then wait for the next Pacific quota day; safety-blocked content is never automatically unblocked. Other clients using this Google project share its limits; provider backoff remains necessary because their usage is not visible to this ledger.

An offline language detector checks output independently of Gemini's self-reported language. It checks passages separately, rejects copied foreign prose, and revalidates existing cache entries. Exact protected buyer names and English context reduce false positives from acronyms, legal references and foreign proper names. A second check runs at public export. Detection is conservative and probabilistic, not a proof of language or semantic accuracy; originals remain the source of truth. No detector or model runs in the browser. See the [evaluation and operating instructions](docs/gemini-translation-evaluation-2026-09-13.md). Do not run a local worker concurrently with GitHub using an independent quota ledger.

Complete HTML character references are decoded before translation and literal validation; canonical source text and its cache hashes remain unchanged. Existing encoded English cache entries are decoded and revalidated without provider calls. Named German conservation sites explicitly paired with site codes and area measurements are protected as source labels, including across split passages. Site-code prefixes, hectare quantities and structured lot labels are also validated. A language hint estimated from the complete source helps interpret fragments after splitting and masking. Other lot descriptions and surrounding requirements still pass the normal language checks.

`python scripts/audit_translations.py --dataset app/public/data/current.json` checks complete notice pairs, source hashes, remaining foreign prose, character references and literal validation across every country. Add `--require-complete` for a strict maintenance check. Each production workflow reports notice coverage separately from supplementary organisation renderings; incomplete new notices continue to publish in their original language.

Highest value, Lowest value and the adjacent minimum/maximum inputs use the published numeric amounts in the selected market. No currency conversion is applied. The currency selector lists supported currencies plus any additional codes present in the feed; select a currency for like-for-like comparisons in mixed-currency markets. Ranges persist when changing market. Unknown values sort last within each team-priority group and do not match a numeric range.

## Scheduling and Budget

The workflow requests collection **at XX:50 every hour, day and night**, with `Europe/London` timezone handling. This replaces all previous slots, including 08:55. It supports manual collection and existing-data deployment. Main-branch code pushes rebuild; source-state commits do not recursively trigger collection. It runs independently of website visitors, without an external scheduler.

The repository is currently public, so standard GitHub-hosted runner use is free. External procurement requests do not consume GitHub REST API quota. Hourly scheduling means approximately 720-744 cycles per month, not a monthly API-call entitlement. Providers impose separate limits: daily sources skip completed snapshots, partial work resumes, caches avoid needless detail fetches, and Retry-After delays are respected. Storage, larger runners and any future private-repository allowance are separate. See the cited budget report.

UI releases reuse an immutable, validated public-data export when the pipeline and data contracts match. Missing or corrupt caches, dependency changes, schema changes and unknown files take the full verification path. Changed source data still passes dataset, evidence, dependency and translation validation; identical inputs can reuse their previous result. Full pipeline regression runs after pipeline changes and on the first successful collection/check of each London day. A manual run can force it.

Every publication builds the dashboard, runs frontend unit tests and tests the real exported records in desktop/mobile browsers. The interaction suite uses small source-shaped fixtures; it runs for changed application code and daily publications. Large-list virtualization keeps its explicit 2,000-record case. Optional design screenshots run with `SIGNAL_CAPTURE_DESIGN=true` or `npm run capture:record`; they are not correctness gates. The existing required PR check remains `test`. Production verification replaces the redundant second push-triggered Tests workflow. See [release paths and test audit](docs/fast-releases.md).

Runs requiring full regression use the existing English translations and defer new translation calls to the next regular data refresh. This keeps optional translation preparation and provider requests out of the release's verification work. The build job allows up to two hours as a fallback for unusually long work; normal runs should finish sooner. Fresh, Signal-scoped App tokens authenticate translation checkpoints and the final validated data save, so expiration of the initial checkout token does not prevent a long run from publishing. The persistent translation queue, remote quota reservation, free-tier confirmation, call limits and checkpoints remain unchanged; a failed full regression keeps retrying verification before translation resumes.

Unchanged data skips unnecessary frontend builds and deployment after that day's freshness publication, while collection checkpoints are still persisted. Collection/quota writes and publication each have their own serialized job using GitHub's `queue: max` setting: up to 100 pending runs can wait without a newer translation check replacing an older waiting collection. Only one collector can use the Gemini quota ledger. UI releases can publish while collection runs; the publisher checks out the latest main code and compatible verified data after acquiring its own lock, and records the exact tested release only after deployment. Independent generated-data commits rebase normally and refuse conflicts or a changed validator. A queued scheduled run skips recollection if another collection with at least one healthy source finished less than 30 minutes ago. Manual collection is not suppressed by this guard. Existing overlapping lookbacks, resumable pagination, request budgets and provider backoff remain unchanged.

Publication is recorded only after deployment succeeds. Times are scheduled starts, not guaranteed completion times: GitHub can delay or drop scheduled runs under load and disables public scheduled workflows after 60 days without repository activity. Overlapping checkpoints protect continuity, but cannot guarantee completeness during provider outages or unavailable source history. Local edits do not publish until deliberately pushed/deployed. See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Retention and Verification

Growing retained `signals.jsonl`, `current.json` and `source_state.json` snapshots use deterministic, lossless gzip at 32 MiB. Readers accept their legacy plain representation as well. An atomic replacement and byte-for-byte migration check preserve every source fact. Public browser JSON stays unchanged. The automation guard rejects new Git blobs at 95 MiB before pushing, including an oversized intermediate commit later deleted. Compression addresses the immediate file limit; fixed notice-ID partitions and cold monthly archives are the next storage step as the repository grows. See the [measured build and storage report](docs/collection-and-build-2026-09-19.md).

Canonical records retain 180 days of recent updates plus future deadlines or contract ends. Older records move into monthly compressed archives with a matching index; later related notices can restore history. The browser first loads a manifest and content-hashed market search indexes, then fetches full records and buyer history as needed. Original and translated descriptions stay in the search index so lazy loading does not remove text from search. Public `current.json` remains a compatibility fallback; private canonical stores and archive files are not served.

Selected official TED notice PDFs can be retrieved within a separate small document count inside the existing collection budget. Source URLs, hashes, revisions and extracted page text stay linked; inaccessible, unsupported and scanned documents are distinguishable. Other official attachments are linked without bypassing access restrictions. Extraction is bounded and documents never become executable instructions. See [the research workspace release notes](docs/research-workspace-2026-09-18.md) and [relevance benchmark](docs/relevance-benchmark.md) for scope and validation.

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check pipeline scripts/check_public_output.py
.\.venv\Scripts\python -m anthrion_signal.cli validate
.\.venv\Scripts\python -m anthrion_signal.cli export
.\.venv\Scripts\python scripts/check_public_output.py
cd app
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Tests use local fixtures, not paid APIs. Review source-health metadata and Actions summaries for partial coverage. Never disable TLS verification to repair a source. Verify an interrupted collector has stopped before removing its local lock.

See [SETUP.md](SETUP.md) for deployment configuration. Contains public-sector information under the Open Government Licence v3.0 where applicable; other source terms continue to apply. Document binaries and supplied private files are not copied into the public repository. Permitted public notice text may appear as attributed, page-linked evidence.
