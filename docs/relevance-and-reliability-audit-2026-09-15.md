# Relevance and reliability audit — 15 September 2026

The audit identified **123 published notices outside Anthrion's stated delivery focus**, **three closed or awarded notices**, and **four useful candidates that the previous rules missed**. The fixes preserve mixed software and AI procurements, retain future rejected notices for replay, and address the browser-test race behind the 15 September failure email.

## Scope and evidence

The frozen live snapshot was generated at **20:29:20 UTC on 15 September**, containing **2,271 notices**. The replay covered **20,131 unique retained notices**: 8,528 in the canonical store, plus historical archives. Original source text and exact-source validated English translations were evaluated together. Relevance was assessed separately from deadlines, awards, cancellation and eligibility.

This is a complete automated replay of the retained corpus, with title/scope review, review of publication changes, and **160 real-notice regression cases**, supplemented by synthetic mixed-scope counterexamples. It is not a claim that every underlying tender document or attachment received a human commercial assessment. Counts refer to notices; parallel national and TED records can represent the same procurement.

The [decision register](relevance-decisions-2026-09-15.csv) lists every scope removal, lifecycle correction and restored candidate, with source links, reasons and source hashes. Full local replay evidence is in `artifacts/relevance-audit-2026-09-15/final-replay-verified.json`; `all-retained-decisions.csv` makes all 20,131 decisions searchable.

| Change at the frozen snapshot time | Notices |
| --- | ---: |
| Remove from public discovery for scope | 123 |
| Retire explicitly closed or awarded notices | 3 |
| Restore previously suppressed candidates | 4 |
| Net public count at that same time | 2,149 |

The OKSTRA development opportunity passed its deadline during the audit. That ordinary expiry is separate from these relevance changes, so later live totals differ from the frozen-time comparison. Source history is preserved.

## Why irrelevant records were admitted

Broad procurement classifications are useful for recall but weak evidence of deliverable fit. Codes covering consultancy, research, administration or IT products admitted work such as bird surveys, property valuation, construction and licence resale. Generic words such as “system”, “development”, “reporting” and “data quality” then made these notices appear more relevant than their purchased scope justified.

| Purchased scope removed from the public snapshot | Notices |
| --- | ---: |
| Unrelated product licence resale or renewal | 41 |
| Construction and building controls | 23 |
| Physical computing, network or measurement equipment | 14 |
| Execution of surveys or market research | 9 |
| Human service delivery or physical records storage | 7 |
| Physical field surveys or sampling | 6 |
| Advertising, creative agency or public relations services | 6 |
| Maintenance of physical equipment | 5 |
| Physical science, ecology or plant feasibility work | 4 |
| Financial audit or insurance services | 4 |
| Academic degrees or research fellowships | 2 |
| Property valuation | 1 |
| Medical research centre mistaken for an AI product | 1 |

Examples include a breeding-bird survey, sediment coring aboard a research vessel, fermenter maintenance, AI server hardware, and Microsoft/Adobe licence supply without implementation. “Claude D. Pepper Older Americans Independence Centers” matched the word Claude even though the notice concerned medical research. Product-name disambiguation and sentence handling now prevent that match.

These exclusions reflect Anthrion's Salesforce, CRM, business-application and AI implementation focus. They do not assert that an entirely different reseller, construction or clinical business could not bid.

## Useful opportunities restored

| Opportunity | Source status at audit | Reason to retain |
| --- | --- | --- |
| [Digital and IT Professional Services 2](https://www.gca.gov.uk/agreements/RM6413) | Future | Explicit IT professional-services procurement; a route for Salesforce and related delivery teams. |
| [Quality Assurance and Testing for IT Systems 2](https://www.gca.gov.uk/agreements/RM6148) | Open | IT testing services through a purchasing system described as open to suppliers until 2029. |
| [Resourcing the AI Adoption Programme](https://www.find-tender.service.gov.uk/Notice/087185-2026) | Future | AI adoption, pilots, training and scaling support. |
| [Virtual Wards/Hospital at Home: Digitally Enabled Healthcare Services](https://www.find-tender.service.gov.uk/Notice/085645-2026) | Future | Includes remote patient-monitoring technology; retain for technology-lot/partner review. |

These are candidates, not automatic bid recommendations. Framework access, lot boundaries, dates, partner requirements and clinical obligations still need checking. No assumption is made that Anthrion supplies clinical care.

The historical replay also found **41 archived notices with unknown availability** that pass scope rules. They were already scope candidates under the old rules. They are not four dozen newly recovered live opportunities, and have not been republished without current lifecycle evidence.

## Precision safeguards implemented

1. **Classify the purchased deliverable.** New scope exclusions require a specific title pattern plus corroborating description or a suitable classification. The physical-IT-modernisation rule requires explicit supply-of-items evidence; its title alone is insufficient. A sector name or broad CPV code alone cannot trigger these new exclusions.
2. **Protect separately stated digital work.** Software development, Salesforce, business applications, integration and AI delivery preserve mixed procurements. A bird survey with a separate CRM or AI lot stays discoverable. Local negations such as “not required to develop software” do not manufacture a positive software requirement.
3. **Protect migration and conversion work.** Two SAP subscription notices also describe a system conversion project. Both remain for review. Their presence is not a claim that Salesforce can replace the specified SAP system; it prevents a pure-resale rule from hiding a mixed delivery project prematurely.
4. **Separate recall from labels.** Weak generic language can keep an uncertain candidate available for review without inventing a specific capability tag. Clear vendor-neutral IT services, testing and AI adoption have explicit recall routes.
5. **Make translated decisions stable.** Previously, removing a notice from publication could remove its English display entry, which could cause the original-language notice to reappear on a later classification pass. Classification now reuses completed translations from the private cache, independently of the current display sidecar. Exact source hashes and current validation still apply. This path performs no API calls and does not write the cache. Four previously suppressed infrastructure/licence notices were checked against this failure pattern.
6. **Retain and replay rejections.** Normalised rejected source versions, dates, URLs, hashes, decision versions and reasons are stored in compressed daily partitions. German and Spanish collector pre-filters now pass their rejected records to the common classifier rather than silently discarding them. Policy or engine changes automatically trigger replay using a fingerprint; a manual version bump is no longer required. Older replayed versions do not overwrite newer source updates or get copied wholesale into each new daily partition.
7. **Keep lifecycle independent.** Explicit cancellation headings and German awarded/direct-award headings now override misleading “active” source labels. Sparse records and expired archives are not treated as confirmed open tenders merely because their scope fits.

The intended trade-off is conservative: preserve an uncertain or mixed opportunity for review rather than claim certainty from a keyword. More uncertain notices can therefore remain in discovery. Neither a rule system nor an LLM can prove zero false negatives from incomplete procurement summaries.

## GitHub failures investigated

All six failed runs returned by the repository's failure history were inspected.

| Run | Failure | Treatment |
| --- | --- | --- |
| [15 Sep, 34914886773](https://github.com/stevostar1234/anthrion-signal/actions/runs/34914886773) | Responsive browser test checked a pagination control's visibility, then attempted to click after a resize removed it. The run had 106 passing tests, one skip and one failure. | Fixed the locator to retry against the current responsive controls. Desktop/mobile resize checks passed six consecutive runs. |
| [13 Sep, 34761358846](https://github.com/stevostar1234/anthrion-signal/actions/runs/34761358846) | Public-output validation ran before `app/public/data/current.json` had been generated. | Already fixed in the existing Tests workflow: export precedes validation. |
| [11 Sep, 34629908155](https://github.com/stevostar1234/anthrion-signal/actions/runs/34629908155) | Browser focus assertion. | Existing later UI/test fixes are covered by the current full regression. |
| [11 Sep, 34628644927](https://github.com/stevostar1234/anthrion-signal/actions/runs/34628644927) | Animation-distance assertion missed the observed movement. | Existing animation observer tests capture the whole departure rather than a late sample. |
| [11 Sep, 34627149045](https://github.com/stevostar1234/anthrion-signal/actions/runs/34627149045) | Desktop/mobile animation predicates timed out after 500 ms. | Covered by the same existing observer-based regression. |
| [9 Sep, 34345994827](https://github.com/stevostar1234/anthrion-signal/actions/runs/34345994827) | Mobile comparison checkbox interaction timed out. | That feature was subsequently removed. Current tests verify CSV export and that comparison controls stay absent. |

The next run after the 15 September failure [succeeded](https://github.com/stevostar1234/anthrion-signal/actions/runs/34915433778); subsequent runs inspected before this release also succeeded. The failure email did not mean that a broken build replaced the working site.

The audit's full browser run also exposed a source-link test that inspected a new tab before its first navigation committed. It now waits for the expected URL and verifies the intercepted source page's content, retaining the real keyboard/new-tab interaction check.

Failed browser runs now retain traces and screenshots, and CI uploads their diagnostics for 14 days. Required checks still gate publication; failing tests have not been skipped or hidden behind new test retries.

## Remaining coverage limits and operating recommendations

At the frozen snapshot, **8 of 13 enabled sources were healthy**. Wales reported an upstream HTTP 500 conversion problem and retained listing results with partial coverage. GOV.UK queries, TED additive keyword windows, Spanish historical windows and Grants.gov details had resumable work beyond their per-run budgets. These are separate from the browser build failure. Disabled sources and incomplete backfills are not covered by an “all records” claim.

Rejection retention starts with this release. Notices irreversibly discarded before storage cannot be reconstructed from Git history. Future collection therefore preserves the evidence needed for a meaningful false-negative audit, but this does not retroactively prove historical recall.

Scheduled refreshes are targets, not a guaranteed freshness SLA. GitHub documents that scheduled events can be delayed or dropped under load. The existing off-hour schedules, serial execution and source checkpoints reduce related risks, but cannot remove a host scheduling limitation. If the team later needs guaranteed freshness, use an independently monitored scheduler and an explicit stale-data alert, while retaining the same checkpointed worker. [GitHub scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

For ongoing quality, record a source notice and the actual requested work whenever the team flags a mistake, then add both the failing case and a close counterexample to the regression corpus. Keep new geographic/source coverage separate from scope tightening, so a recall change is attributable. Retain long-term evidence in daily partitions; move older partitions to durable object storage if repository growth becomes material, preserving hashes and replay access rather than silently deleting evidence.

## Reproduce the audit

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/audit_relevance.py --snapshot artifacts/relevance-audit-2026-09-15/live-before.json --output artifacts/relevance-audit-2026-09-15/final-replay-verified.json
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m anthrion_signal.cli export
.\.venv\Scripts\python.exe scripts/check_public_output.py
.\.venv\Scripts\python.exe scripts/audit_translations.py
```

Without `--snapshot`, the replay uses the repository's current dataset and its generation time. The local frozen snapshot and complete audit artifacts are intentionally outside the public-site build. The decision register and regression fixtures are versioned in this repository.

## Verification

Local verification passed: **646 Python tests**, **32 frontend tests**, TypeScript compilation, production build, Ruff, public-output safety checks, and **107 browser tests with one existing intentional skip**. Both corrected browser interactions also passed six repeated desktop/mobile checks.

An isolated check fetched and normalised all 85 records in one German daily export and verified that compressed rejected records reload successfully. Its stored evidence is in `artifacts/relevance-audit-2026-09-15/national-source-check/`. No new current opportunity was established from that sample. A separate one-page Germany/Spain run yielded no records and does not establish Spanish collection coverage.

The approved release, code commit `0cbb556`, passed both [GitHub Tests](https://github.com/stevostar1234/anthrion-signal/actions/runs/35031532640) and [the full build/deploy workflow](https://github.com/stevostar1234/anthrion-signal/actions/runs/35031532586). The production browser run passed 107 tests with one intentional skip; Pages deployment and publication recording both succeeded.

The live dataset was independently fetched at **22:49 UTC on 15 September**. Its rule fingerprint matched the tested code. **All 126 reviewed scope/lifecycle removals were absent and all four recovered candidates were present.** The live feed contained **2,148 notices**, all with complete, exact-source, validated English titles and descriptions. The read-only live translation audit passed with no outstanding notice pairs.

Nine supplementary organisation-name renderings remain for review; the original source organisation names are retained. These are separate from notice-title/description coverage. Live verification evidence is in `artifacts/relevance-audit-2026-09-15/live-verification.json` and `live-after.json`.
