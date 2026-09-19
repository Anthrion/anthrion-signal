# Anthrion Signal

Public procurement and commercial opportunity discovery for Anthrion's sales team. The React/TypeScript console reads a static, validated dataset. Python collectors run locally or in GitHub Actions. Collection requires neither a language model nor a paid tender-data subscription.

## Workspace

The console opens on **Live Opportunities**, ordered by recent publication. Salesforce, CRM and clearly related platform implementations appear first, including combined platform/AI projects. Standalone AI follows, then other relevant opportunities. Each group retains the selected recency, update, deadline or value order. There are no score thresholds or model assessments.

The five refiners are **All Signals**, **Live Opportunities**, **Pre-market**, **Closing Soon**, and **Added today**. Pre-market combines requests for information, market engagement, pipeline and genuine future buying intent; these are not presented as open tenders. Unknown deadlines do not enter Closing Soon. Added today means first collected on the current Europe/London calendar date, not recently updated or published. Frameworks and funding remain available through notice-type filters without separate refiner cards.

The default market row contains UK, All, US, Italy, Nordics, DACH, Spain and Greece. **DACH** combines Germany, Austria and Switzerland; **Benelux** combines Belgium, the Netherlands and Luxembourg. Nordics groups Sweden, Finland, Denmark, Norway and Iceland. More opens the additional European markets, and the pencil control saves each browser's preferred order and pinned markets. Country identifiers and existing country-specific links remain separate underneath the groups. All searches every current market index and deduplicates notices. A healthy source does not imply complete market coverage or confirmed bidder eligibility; new European coverage uses TED, not an assertion that every national or below-threshold portal is included.

The dark glass console uses a measured virtual list: scrolling reveals records without pagination while only nearby rows remain mounted. Desktop has independently scrolling records and details; narrow screens use document scrolling and a detail drawer. The record panel places compact notice facts and capabilities above the complete source description. A vertical integration rail sits beside those facts: Gmail opens a compose window with the selected record's displayed title, buyer, source facts and direct links, without sending a message. Salesforce and Slack are disabled until their integrations are available. Full details and Open source notice stay in a bottom dock outside the scrolling content, including on mobile. The expanded detail view retains its own source action and a Back to record control. Arrow keys and Home/End navigate record selectors. Reduced-motion preferences pause decorative animation.

Save and Hide remain in the results list and are not duplicated in the opened record or Full details view. The small, unboxed icon immediately before a record's deadline also opens a prefilled Google Calendar event titled "Deadline for tender: [title]", with the buyer and record/source links. The three integration buttons are vertically centred between the facts area's divider lines. Timed deadlines retain their exact instant; date-only deadlines use an all-day entry. The user chooses their calendar and reminders and saves the event in Google Calendar. Saved events do not automatically follow later changes to a notice's deadline.

Search, filters and sort sit between the brand and saved opportunities in the desktop header. They wrap within the header on smaller screens. Export is centred beside the glass refiners. The repeated list heading is visually hidden but retained for screen readers. A 57px action dock, compact market spacing and tighter description margins preserve more reading room without shrinking record typography; both dock actions retain 44px interaction targets.

Refiner reflections share one continuous animation phase. Scrolling a separate record list or description does not redraw stationary glass or reset its lighting. Relevant document scrolling, carousel movement and resizing still update geometry; decorative lighting remains capped at 25 updates per second and pauses offscreen, in hidden tabs and for reduced motion.

Records show source descriptions, buyers, dates, typed amounts, capability evidence, participation checks, original notices, documents and timelines. Click a capability to inspect its supporting passage; source requirements remain **needs checking**, never a declaration that the company is eligible. Click the buyer to browse all its collected notice and contract history, or the record title to compare the selected opportunity with related awards. Each comparison states whether the link is a published procurement identifier, buyer identity or shared capability. Award-date and supplier filters do not invent missing dates or imply a renewal is open.

The desktop separator resizes the results and record panes by pointer or keyboard and remembers the width. Search supports exact source text or text plus capabilities, all words, any word and exact phrases. It searches original text and available English translations; native capability aliases are deterministic, not automatic translation of arbitrary queries. Active filter chips remove individual constraints, and named saved views restore the complete filter state. Saved views, market arrangement, pane width, bookmarks and hidden records are browser-local. Hide remains personal and is never a global relevance label. Shared Working flags and notes are deferred until the Salesforce identity integration; this public discovery tool publishes no private team workspace.

## Collection and Availability

Official APIs and permitted public listings feed bounded collectors with overlapping windows, checkpoints and retries. Source facts are normalized, deduplicated using procedure identifiers and aliases, checked for availability, and ordered by delivery priority and publication recency. Validated public JSON is built with Vite and published through GitHub Pages.

Awards, inferred incumbent renewals, cancellations, withdrawals, expired response windows and explicitly unavailable routes are excluded from results, saved opportunities and exports. Canonical terminal records remain internally so later awards or cancellations can retire earlier leads. Ambiguous bidder eligibility is not invented; inspect the source before pursuing.

Capability classification uses explicit phrases, translated aliases, functional needs and CPV codes. Context-only words do not promote standalone AI into the platform-first group. Supplier-portal hostnames do not count as Salesforce implementation requirements. The company profile retains supplied public facts without assuming framework memberships, certifications or overseas delivery presence.

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

Failures preserve previous records and completed checkpoints. Budget-limited results are partial, not complete coverage. Retries are bounded and TLS verification stays enabled. Source-specific reuse terms remain applicable; linked documents do not automatically share a dataset's licence.

USAspending is disabled because it supplies awards rather than new competitions. Registry placeholders for SAM.gov, regional supplier portals and multilateral procurement are not active coverage. Activate additions only after interface, reuse, lifecycle, deadline and supplier-access checks.

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

Translation checks are requested at minutes 05, 20, 35 and 50 every hour, including overnight; only the :50 run collects procurement data, then immediately attempts new translations. GitHub's scheduler can delay or skip runs, so these are requested times, not a latency guarantee. Each verified Flash-Lite model uses the full project limits observed in AI Studio on 2026-09-13: 15 HTTP attempts/minute, 250,000 estimated input tokens/minute and 500 HTTP attempts/Pacific day. Counting and failed requests are conservatively included; there is no extra daily reserve. The worker chooses a ready backup using the next batch's token requirements. Each pass has up to 150 attempts and five minutes, matching both models' combined minute capacity without holding up publication indefinitely. It commits that run reservation before any API request so a lost GitHub runner cannot forget its quota usage, and refunds only unused reservations on normal completion. Completed text is checkpointed separately from build/test success. Oversized passages split, temporary failures back off or use the verified backup model, and exhausted daily quotas leave work queued until reset. Notice content takes priority over supplementary names. Repeated quality failures get one additional retry round after an hour, then wait for the next Pacific quota day; safety-blocked content is never automatically unblocked. Other clients using this Google project share its limits; provider backoff remains necessary because their usage is not visible to this ledger.

An offline language detector checks output independently of Gemini's self-reported language. It checks passages separately, rejects copied foreign prose, and revalidates existing cache entries. Exact protected buyer names and English context reduce false positives from acronyms, legal references and foreign proper names. A second check runs at public export. Detection is conservative and probabilistic, not a proof of language or semantic accuracy; originals remain the source of truth. No detector or model runs in the browser. See the [evaluation and operating instructions](docs/gemini-translation-evaluation-2026-09-13.md). Do not run a local worker concurrently with GitHub using an independent quota ledger.

Complete HTML character references are decoded before translation and literal validation; canonical source text and its cache hashes remain unchanged. Existing encoded English cache entries are decoded and revalidated without provider calls. Named German conservation sites explicitly paired with site codes and area measurements are protected as source labels, including across split passages. Site-code prefixes, hectare quantities and structured lot labels are also validated. A language hint estimated from the complete source helps interpret fragments after splitting and masking. Other lot descriptions and surrounding requirements still pass the normal language checks.

`python scripts/audit_translations.py --dataset app/public/data/current.json` checks complete notice pairs, source hashes, remaining foreign prose, character references and literal validation across every country. Add `--require-complete` for a strict maintenance check. Each production workflow reports notice coverage separately from supplementary organisation renderings; incomplete new notices continue to publish in their original language.

Highest value, Lowest value and the adjacent minimum/maximum inputs use the published numeric amounts in the selected market. No currency conversion is applied. The currency selector lists supported currencies plus any additional codes present in the feed; select a currency for like-for-like comparisons in mixed-currency markets. Ranges persist when changing market. Unknown values sort last within each team-priority group and do not match a numeric range.

## Scheduling and Budget

The workflow requests collection **at XX:50 every hour, day and night**, with `Europe/London` timezone handling. This replaces all previous slots, including 08:55. It supports manual collection and existing-data deployment. Main-branch code pushes rebuild; source-state commits do not recursively trigger collection. It runs independently of website visitors, without an external scheduler.

The repository is currently public, so standard GitHub-hosted runner use is free. External procurement requests do not consume GitHub REST API quota. Hourly scheduling means approximately 720-744 cycles per month, not a monthly API-call entitlement. Providers impose separate limits: daily sources skip completed snapshots, partial work resumes, caches avoid needless detail fetches, and Retry-After delays are respected. Storage, larger runners and any future private-repository allowance are separate. See the cited budget report.

Every run validates the public dataset. Every collection and publication runs the pipeline test suite. Every publication builds the dashboard, runs frontend unit tests and checks the production build in desktop/mobile browsers. Data-only publications use focused real-data smoke tests covering every market, record/source links, search, filters and reload. Full browser regressions run on code changes and on the first successful run of each London calendar day; failures do not mark that day's checks complete. Manual runs can force the full suite. The tested code fingerprint excludes data-only bot commits.

Unchanged data skips unnecessary frontend builds and deployment after that day's freshness publication, while collection checkpoints are still persisted. Production runs are serialized using GitHub's `queue: max` setting: up to 100 pending runs can wait without a newer translation check replacing an older waiting collection. This remains one worker, not concurrent access to the data or Gemini quota ledger. A queued scheduled run skips recollection if another collection with at least one healthy source finished less than 30 minutes ago. Manual collection is not suppressed by this guard. Existing overlapping lookbacks, resumable pagination, request budgets and provider backoff remain unchanged.

Publication is recorded only after deployment succeeds. Times are scheduled starts, not guaranteed completion times: GitHub can delay or drop scheduled runs under load and disables public scheduled workflows after 60 days without repository activity. Overlapping checkpoints protect continuity, but cannot guarantee completeness during provider outages or unavailable source history. Local edits do not publish until deliberately pushed/deployed. See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Retention and Verification

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
