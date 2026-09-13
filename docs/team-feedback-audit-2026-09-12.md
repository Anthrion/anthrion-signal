# Team Feedback Audit

Date: Saturday 12 September 2026. Read-only investigation of the live publication, local implementation, GitHub run history and official provider documentation. This report is local only; no application code, production data, workflow settings or service subscriptions were changed during the audit.

## Main Decisions

1. Fix confirmed availability errors before expanding collection or translating the historical backlog. More imported records are not necessarily more available leads.
2. Keep the hourly collection design, but distinguish successful workflow execution from complete, fresh source coverage.
3. Save a hide/unhide decision before its animation starts. Normal completed decisions persist; an immediate reload during the animation currently loses the click.
4. Azure's free allowance is plausible for a carefully cached steady-state workload, but not yet a demonstrated monthly fit. Measure new and changed non-English text after the backlog settles.
5. Investigate eTranslation eligibility, but account for its callback-server requirement. Azure is the simpler fit for the current GitHub-only architecture.
6. Prioritize SAM.gov access and Finnish Hilma over miscellaneous low-yield feeds. LA RAMP is a verified candidate, subject to bidder eligibility.

## Translation Volume

### Snapshot and Method

The final measurement was taken from the [live public feed](https://stevostar1234.github.io/anthrion-signal/data/current.json) at 18:55 UTC, after a scheduled collection completed. Its `generated_at` is `2026-09-12T18:48:39+00:00`; its `run.content_digest` is `0ed2b5c65ff555457f2af490dac2a292e12d30188f8d49bdd5a26f4a07dbe555`.

Count Unicode code points, including whitespace, in each record's title and description. Count each public signal once across markets. "Added today" means its `first_seen_at` falls on 12 September in Europe/London, not that the buyer published it today. These are currently published records, not all raw imports or historical records that have since been excluded.

The estimate excludes attachments, procurement documents, already-English interface labels, source metadata, and buyer names that would normally remain proper nouns. It does not include the additional cost of translating amendments to previously collected descriptions. Actual translation billing requires language detection and provider-specific metering; country is not language.

| Measurement | Records | Title + description characters |
|---|---:|---:|
| Entire current public site | 1,653 | 2,302,217 |
| Added today, all markets | 506 | 619,393 |
| Added today, excluding GB/US markets | 493 | 569,704 |
| Entire current site, excluding GB/US markets | 1,381 | 1,682,381 |

Today's all-market total is 37,732 title characters and 581,661 description characters. The non-GB/US title-only subtotal is 36,939. Exact repeated-string deduplication reduces today's non-GB/US title/description total to 563,501, and the full non-GB/US backlog to 1,654,526. Paragraph-level caching could reduce amendments further, but that saving has not been measured.

Non-GB/US is a rough proxy for translation candidates, not a measured non-English total. Some European notices already contain English. Conversely, a UK/US market assignment does not prove that every field is English.

### Today by Market

Multi-country records have their own row to prevent double counting.

| Market assignment | Records | Characters |
|---|---:|---:|
| GB | 13 | 49,689 |
| DE | 202 | 295,435 |
| ES | 69 | 40,770 |
| IT | 18 | 9,404 |
| NO | 75 | 72,972 |
| SE | 56 | 18,441 |
| FI | 39 | 85,399 |
| DK | 24 | 36,763 |
| DK + DE | 2 | 3,926 |
| GR | 4 | 3,979 |
| IS | 2 | 699 |
| NO + DK | 2 | 1,916 |
| Total | 506 | 619,393 |

### Weekend Versus Working Days

387 of today's 506 records were originally published before 2026, contributing 475,810 characters. No record in this first-seen-today cohort has a known publication date of 12 September; seven lack a publication date. Today's increase is largely catch-up collection, not a representative Saturday's new procurement activity.

For a separate, incomplete weekday comparison, grouping the current public dataset by original publication date gives:

| Publication date | Non-GB/US records | Title + description characters |
|---|---:|---:|
| Monday 7 September | 49 | 50,509 |
| Tuesday 8 September | 67 | 85,310 |
| Wednesday 9 September | 79 | 92,540 |
| Thursday 10 September | 66 | 70,369 |
| Friday 11 September | 10 | 3,418 |

These are surviving public records already collected, not complete daily market totals. Source delays, incomplete coverage, expiration and new connectors affect them. Friday's small figure is not evidence of reliably low Friday demand.

### Does 2 Million Fit?

[Azure Translator F0 currently includes 2 million characters per month](https://azure.microsoft.com/en-us/pricing/details/translator/).

- Translating today's entire non-GB/US cohort would consume about 28.5% of that allowance. Repeating that volume for 30 days would require 17.1 million characters, but that is a deliberately naive scenario, not a forecast.
- Translating the entire existing non-GB/US backlog once would consume about 84.1%, leaving 317,619 characters before new records or amendments. Skip already-English text and unavailable notices first.
- The observed Monday-Thursday range, multiplied by 22 working days, is approximately 1.11-2.04 million characters before weekends, revisions and additional coverage. Again, this is an incomplete comparison, not a reliable forecast.
- A 2-million monthly allowance averages about 66,667 characters per day in a 30-day month. A working target around 1.5 million per month leaves roughly 25% headroom.

Recommended implementation: detect language, retain source originals, translate only available records and only new/changed text, cache by source-text hash plus language/provider version, and prioritize CRM/Salesforce records before less relevant material. Keep translation separate from collection so an exhausted translation quota never prevents new opportunities appearing. Enforce a monthly character ledger and hard budget gate. Translate titles before descriptions when capacity is limited. Do not call a translation API on every page refresh and never put its secret key in the public frontend.

Measure at least 7-14 stable days, split weekdays/weekends and first-time translation/amendments, before promising that F0 covers the whole month. This audit did not create a scheduled measurement job.

## Translation Alternatives

| Option | Verified benefit | Constraint and suitability |
|---|---|---|
| Microsoft Azure Translator F0 | 2 million characters/month | Best straightforward managed API fit for GitHub Actions with cached output; quota exhaustion must not block collection. |
| European Commission eTranslation | Officially free with no usage cap for eligible users, including small businesses based in the EU or Digital Europe affiliated countries | Anthrion's stated European presence makes eligibility worth checking, but does not establish qualifying entity/SME status. The documented API is asynchronous and sends completed translations to a callback server, so it is not a drop-in GitHub Pages-only solution. |
| Google Cloud Translation NMT | First 500,000 characters/month covered by a recurring credit | Smaller free allowance than Azure; configure quotas/billing carefully. This is a dedicated translation service, not the previously removed Gemini model. |
| Argos Translate | Open-source offline translation library/CLI, no provider per-character charge | Could run as a batch job on a runner. Benchmark procurement terminology, language coverage, model licenses and CPU/runtime costs; no claim of unlimited free compute or Azure-equivalent quality. |

Sources: [Azure pricing](https://azure.microsoft.com/en-us/pricing/details/translator/), [eTranslation eligibility and no-cap statement](https://translation.ec.europa.eu/tools-and-resources/ai-translation-and-language-tools_en), [official callback example](https://language-tools.ec.europa.eu/assets/pages/05_example_python.html), [WEB-T client/server architecture](https://website-translation.language-tools.ec.europa.eu/solutions/universal-plugin_en), [Google pricing](https://cloud.google.com/products/translate/pricing), [Argos project](https://github.com/argosopentech/argos-translate).

eTranslation's documented support includes the requested European languages, including Norwegian and Icelandic. Its free usage statement is not a request-rate or availability guarantee. The current documentation still requires an application name/password and limits each API request to 20 MB. [Official integration information](https://website-translation.language-tools.ec.europa.eu/automated-translation_en).

For the product, retain an Original/English choice and identify machine translation without changing the underlying source facts, record IDs, hide state, deadline or value. Originals remain the authoritative notice content. Browser-native translation can be a fallback, not the only supported team workflow.

## Hidden Records

### What Already Persists

Hidden IDs are stored in `localStorage` under `anthrion-hidden-v1`, independently from the downloaded feed and saved opportunities. Loading new data does not clear this key, and absent records do not cause their hidden IDs to be pruned. Normal refreshes, rebuilds and redeployments on the same site origin and browser profile therefore preserve completed hidden choices.

Code: [storage hook](G:/Anthrion/signal/app/src/App.tsx:73), [hidden key](G:/Anthrion/signal/app/src/App.tsx:189), [stable ID creation](G:/Anthrion/signal/pipeline/anthrion_signal/normalise.py:41), [merge preserving existing identity](G:/Anthrion/signal/pipeline/anthrion_signal/dedupe.py:49).

Six existing desktop/mobile browser checks passed against the live application with isolated fixture data: reload persistence, hide/unhide effects on results/selection/exports/bookmarks, cross-tab updates, and blocked/malformed browser storage. These checks did not read or change anyone's real browser preferences.

### Confirmed Animation Gap

[The dismiss handler](G:/Anthrion/signal/app/src/App.tsx:370) commits the hidden state only after the departure animation. The hide fallback is 620 ms; the unhide fallback is 2 seconds. An isolated normal-motion test reproduced:

1. Click Hide: stored hidden list is still empty while the animation starts.
2. Immediately reload: the record returns.
3. Click Hide and let the animation finish: the ID is saved and a reload correctly keeps it hidden.

Recommended fix: persist the user's intent immediately, and manage the outgoing visual row separately until the animation ends. Add immediate-reload/close regression coverage for both Hide and Unhide, with normal and reduced motion. This fix was identified but not applied in this audit.

### Limits of Browser-Only State

- Clearing site data, ending a private session, blocked storage, or changing browser profile/device/origin can remove or separate preferences. Local preview and the live GitHub Pages domain have different storage.
- Hiding is personal to that browser profile, not a shared team decision or account-synced setting.
- Same-origin tabs receive storage events, but simultaneous competing writes to the array can still be last-write-wins. Existing tests cover sequential cross-tab changes.
- A genuinely new source ID can look like a new record unless the collector links it to the same procurement. Stable identity across amendments and duplicate portals therefore matters for both availability and hidden-state continuity.

Recommended durability improvement: export/import a small saved-and-hidden preferences backup without altering ordinary opportunity exports. True cross-device or shared-team state would require an authenticated persistence service; do not promise that from static hosting alone.

## Collection Review

### Confirmed Working

The workflow is active on the default branch with an hourly `:50` schedule. A new scheduled run completed during this audit: [run 34712298145](https://github.com/stevostar1234/anthrion-signal/actions/runs/34712298145), created 18:48:23 UTC and completed 18:52:46 UTC. It reported 81 new public signals and increased the public total from 1,572 to 1,653. This was a scheduler event, not a visitor or page-refresh trigger.

The exact intended schedule occurrence associated with that delayed/irregular start was not established. A successful scheduled run proves the trigger is operating; it does not establish dependable hourly delivery. GitHub explicitly documents possible schedule delays and dropped jobs under load. [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Existing useful protections include serialized production work, a job timeout, bounded API budgets, retry/backoff, source checkpoints, retaining previous data when a source fails, validation before publishing, and deploying only meaningful changes. Scheduled source collection and translation should remain independent of website visitors.

### Current Source Health

In the 18:48 UTC feed, 12 sources are enabled: eight healthy, two partial and two failed.

| Source | Latest status | Evidence |
|---|---|---|
| Find a Tender | Healthy | Recovered in the latest run; the earlier run reported HTTP 429. |
| Public Contracts Scotland | Failed | Connection failure; last successful source collection 9 September. |
| Sell2Wales | Partial | Main source connection failed; latest public listing fallback retained. Full coverage is not established. |
| GOV.UK | Partial | Search queries still catching up; offsets retained. |
| Spain PLACSP | Failed | Feed timestamp remains 8 September; newer national coverage is unverified. TED is a separate source. |

A green workflow is not the same as every source being complete. A recent overall feed timestamp is not proof that Scotland, Wales or Spain is current. Do not delete their previously collected records just because the source is temporarily unavailable.

### Priority Findings

**P1: Some closed/direct-award TED notices are still exposed as available signals.** The TED normalizer reads tender-receipt deadlines but not participation-request deadlines. Two live records marked open with no deadline have source XML participation cutoffs in October 2025:

- `sig_2888cbca5782af76ca77`, notice 635159-2025: participation deadline 27 October 2025, 10:00 +01:00. [Official XML](https://ted.europa.eu/en/notice/635159-2025/xml).
- `sig_0ea0ad1d76bb48474a4e`, notice 635426-2025: participation deadline 13 October 2025, 21:59:58 +00:00. [Official XML](https://ted.europa.eu/en/notice/635426-2025/xml).

Also, `sig_2e50f291da4fa9d4af2b`, notice 642137-2025, is shown as pipeline/future. TED identifies it as `dir-awa-pre` / `veat`, and the XML procedure is `neg-wo-call`. This is direct-award transparency, not ordinary pre-market competition for a new supplier. [Official XML](https://ted.europa.eu/en/notice/642137-2025/xml).

The cause is visible in [TED normalization](G:/Anthrion/signal/pipeline/anthrion_signal/normalise.py:231): direct-award pre-information is mapped to planning, non-award status is set active, and only one deadline family is considered. [Lifecycle publication rules](G:/Anthrion/signal/pipeline/anthrion_signal/discovery.py:53) then allow those records through.

491 current records have no recovered deadline and a publication date more than 180 days old. That is an audit queue, not proof that all 491 are invalid: some long-running admission systems can remain genuinely open. Recover source deadlines and procedure/lot lifecycle first; do not blanket-delete every older record.

Fix order: recover participation-request and tender deadlines per lot; distinguish ongoing admission from already-closed framework membership; exclude direct awards; link later cancellation/award/change notices to their actual procedure and lot. Preserve internal terminal records for reconciliation while keeping them out of the sales feed. Existing title/value/deadline fuzzy matching is not a substitute for source procedure identifiers.

**P2: TED pagination can repeatedly restart if its page budget is exhausted.** [The collector](G:/Anthrion/signal/pipeline/anthrion_signal/collectors.py:580) keeps its iteration token only within the current call and advances its watermark only on completion. At a volume above the run budget, subsequent runs can repeat the same expanding window without reaching the remaining pages. This is a code-level risk, not an observed failure in the latest healthy TED run. Prefer fixed, resumable date partitions or adaptive window splitting; do not assume a server iteration token remains valid indefinitely.

**P2: Global freshness can conceal stale source coverage.** [The frontend check](G:/Anthrion/signal/app/src/App.tsx:337) considers the overall generation time and a 26-hour threshold. A run retaining old data can still make the overall timestamp recent. Record and inspect last attempt, last complete coverage, oldest pending partition and publication lag per source. Alert on meaningful sustained failures without flooding the team.

Hourly scheduling cannot make a daily upstream export hourly. Nor can it guarantee no missing records during prolonged source outages or when a fallback only exposes the latest page. Reconciliation and coverage checkpoints are more important than simply increasing request frequency again.

## Additional API Candidates

The current US view has 55 records: 54 funding notices and one procurement RFP. More grant volume is not the same as broader US procurement coverage. Commercial eligibility and a genuine supplier route need checking before treating a grant as an Anthrion lead.

| Source | Verified facts | Recommendation |
|---|---|---|
| US SAM.gov Opportunities | Official public API for solicitations, pre-solicitations and sources-sought notices; API key required and daily quota depends on role | Highest-value US expansion. Obtain the free account/key through the official service, keep it in secrets, and respect the actual assigned quota. Filter awards, sole-source restrictions, expired notices and ineligible set-asides. Not currently enabled. |
| Los Angeles RAMP | Anonymous official Socrata feed `hf3r-utnq`; 409 records returned in the bounded probe | Worth a dedicated connector after eligibility checks. A current Salesforce-based eSourcing notice exists, but it is a task-order solicitation, not proof Anthrion can bid. |
| Finland Hilma AVP-Read | Operator explicitly permits free commercial API use; self-service subscription/key required | Strong national Finnish supplement to TED. Confirm assigned request limits and implement lifecycle-aware collection. |
| Greece KIMDIS Open Data | Free documented read API with notice, award and related-act resources; data refreshed daily | Good national candidate, but a previous bounded production probe timed out. Require a successful response and cancellation/award linkage before enabling. |
| Montgomery County, Maryland | Anonymous Socrata feed `eeq6-nnwe`; 19 active records in today's probe | Do not add now. Three broad technology-keyword hits were code-book subscriptions and barrier-gate maintenance, all marked local-small-business-reserve. No convincing current CRM/Salesforce yield was verified. |
| SBA SUBNet | Official subcontracting service exists | Not a current priority: operator says new opportunity posting is unavailable, and the inspected listing did not establish fresh relevant software work. |

Official sources: [SAM API](https://open.gsa.gov/api/get-opportunities-public-api/), [SAM opportunities](https://sam.gov/opportunities), [LA RAMP dataset](https://catalog.data.gov/dataset/ramp-open-bid-opportunities), [LA Salesforce example](https://www.rampla.org/s/opportunity-details?id=006Ql00000k98OrIAI), [Hilma portal](https://hns-hilma-prod-apim.developer.azure-api.net/), [KIMDIS documentation](https://cerpp.eprocurement.gov.gr/khmdhs-opendata/help), [Montgomery solicitations dataset](https://catalog.data.gov/dataset/solicitations), [Montgomery procurement access](https://www.montgomerycountymd.gov/PRO/solicitations/formal-solicitations.html), [SUBNet](https://www.sba.gov/subnet).

No new connector was enabled during this audit. Germany's national export and Spain PLACSP are already integrated and must not be presented as new discoveries. Doffin, Danish access and Italian national/current exports remain candidates with unresolved production-access or data-freshness questions, not confirmed ready-to-run free additions. Historical award/statistics datasets are not substitutes for open lead sources.

## Recommended Product Priorities

1. Availability correctness: fix the confirmed TED deadline/direct-award defects and reconcile notice lifecycles. This saves sales time and translation budget together.
2. Durable decisions: immediate hide persistence, regression tests and a saved/hidden preference backup. Keep decisions personal unless a deliberate shared-team workflow is introduced.
3. Source reliability: per-source completeness/freshness and actionable failure notifications. The team should know when coverage is stale without seeing internal diagnostics throughout the main interface.
4. Translation: Original/English presentation, persistent source-text caching, budget accounting and English search over translated fields. Do not alter IDs or factual filters based on translated prose.
5. Qualification: surface evidence-backed participation route, deadline certainty, geography/language requirements and relevant platform scope. Avoid invented fit scores and assumptions about framework membership or company certifications.
6. Salesforce handoff: a structured lead/opportunity draft with buyer, source URL, deadline, procurement ID and the user's notes. Do not automatically create CRM records without the team's explicit workflow choice.
7. Relevance feedback: optional hide reasons such as closed, not eligible or wrong scope can reveal systematic collection issues. Keep one-click Hide fast; extra feedback should be optional.

The most valuable next release is a reliability and qualification improvement, not another visual redesign or an unfiltered increase in records.
