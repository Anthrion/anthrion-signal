# Reliability Update

Implementation and local verification on 12 September 2026. This follows the
read-only `team-feedback-audit-2026-09-12.md`; its earlier snapshot figures remain
historical evidence, not the current local counts. No GitHub publication was made
as part of this update. Publication confirmation is outstanding.

## Availability Cleanup

The initial public feed contained 1,653 records. Rechecked 1,253 TED publication
numbers associated with 1,188 canonical records against the official Search API.
Every requested publication number was returned.

- Suppressed 104 direct-award transparency notices from the sales feed.
- Recovered participation-request / expression-of-interest deadlines and
  suppressed a further 248 records whose response deadlines had passed.
- Added five relevant LA RAMP listings. The resulting local public feed contains
  **1,306 records** at `2026-09-12T21:32:04Z` (rounded completion time).

Structured source evidence determines these removals. There is no blanket age
limit on pre-market signals, and an openly competed renewal is not excluded just
because its title contains "renewal". A multi-lot record remains available while
another recovered response deadline is still open. The next remaining date is
used consistently in display, sort, filters, CSV and calendar exports.

The metadata repair preserves canonical IDs and first-seen history. Unavailable
records are retained internally for reconciliation/retention rather than erased
from all history. Its apply mode takes an exclusive data lock, checks that the
input has not changed and creates a backup before replacing canonical data.

Remaining limitation: TED search fields flatten lot arrays. Multiple dates and
times are not paired by guesswork. Exact lot-specific cutoffs and award links can
require full notice XML. Explicit notice-amendment references now link identities;
a general reference to a previous procedure is deliberately not treated as proof
that an award closes every lot or an entire dynamic purchasing system. This is
not a guarantee that every eligibility ambiguity in every source has been resolved.

## Collection Reliability

TED page-budget exhaustion now persists the unfinished fixed date range and its
continuation token. Subsequent collections resume that range. A rejected token
replays only the unfinished small window within the existing request budget;
it does not restart the whole expanding backlog. Completed ranges alone advance
the watermark. The fresh and historical collection lanes remain separate.

Access-denied responses receive a cooldown. Monthly sources stop after the first
401/403 rather than repeatedly requesting more partitions. GOV.UK's fresh lane
uses the configured initial lookback, with the existing historical lane retained.
The hourly `:50` workflow schedule and browser refresh behavior are unchanged.

Upstream limitations remain real: the tested Scotland and Wales API requests
returned HTTP 403, and Spain's national export was stale. Previously collected
data is retained, and Wales's existing public-listing fallback remains partial.
No authentication or TLS controls were bypassed. Faster scheduling cannot repair
operator-side access failures or make a daily/stale export current. A successful
workflow does not imply complete coverage of every provider.

## LA RAMP

Enabled the official anonymous Los Angeles open-opportunity dataset with a
24-hour collection cadence. A completed probe returned 409 source rows and five
relevant public records:

- Artificial Intelligence (AI)-Powered Pre-Plan Check (AIP-PPC) Assistant
- Consolidated Criminal History Reporting System (CCHRS) Services
- Civil Case and Matter Management System
- Cannabis Licensing System RFP
- RFP2241293798 ENTERPRISE DOCUMENT MANAGEMENT SYSTEM

The connector verifies source revision before and after retrieval, the expected
row count, required identifiers/statuses and official source URLs. Failed,
incomplete or stale snapshots do not erase prior records. A previously listed
record is suppressed only after absence in two independently revised complete
snapshots; absence is not mislabelled as an award. Reappearance restores it.
The current bounded snapshot limit is 5,000; exceeding it reports incomplete
coverage rather than silently truncating and removing records.

The dataset contains titles, not full procurement descriptions. It is a discovery
source; the original RAMP notice remains necessary for bidder qualification.
The column metadata explicitly identifies its dates as UTC.
[Official dataset](https://data.lacity.org/resource/hf3r-utnq.json),
[metadata](https://data.lacity.org/api/views/hf3r-utnq.json).

A task order commissions work under an existing contract, so finding its notice
does not establish that a new supplier can bid. LA task-order notices are held
back until participation rights are confirmed; the Salesforce eSourcing example
was not presented as freely available. Partner/subcontract routes would need
separate verification. [Federal ordering explanation](https://www.acquisition.gov/far/16.505).

Hilma and SAM.gov remain disabled and are listed in `docs/api-backlog.md` for later
access setup. Neither is counted as active coverage.

## Hidden Records

Hide and Unhide now write their intent to browser storage immediately, before
the visual departure animation. Outgoing rows have separate temporary visual
state. Counts, selection and exports use the saved decision immediately.
Reloading during either animation no longer loses the user's choice.

Stable hidden IDs survive feed refreshes and redeployments on the same origin and
browser profile. Storage is still personal to that browser: clearing site data,
using another profile/device or changing domains is not cross-device persistence.
Sequential cross-tab synchronization is tested; localStorage is not a distributed
transaction store for simultaneous conflicting writes.

## Verification

- 304 pipeline tests passed.
- 29 frontend unit tests passed.
- 99 Playwright tests passed across desktop/mobile; one desktop-only screenshot
  test was intentionally skipped on mobile.
- TypeScript, Vite production build, Ruff and public-output validation passed.
- Browser checks cover reload during Hide/Unhide, virtual-list behavior, search,
  markets, filters, export, source links, compact layouts, accessibility and glass
  motion. No translation widget is present in the production frontend.

See `docs/translation-evaluation-2026-09-12.md` for the separate Argos,
LibreTranslate, GTranslate and WEB-T evaluation and its deployment decision.
