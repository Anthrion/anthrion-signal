# Best match and UK exclusion review

The replacement for PRs #51 and #52 adds an optional Best match sort and accepts
51 of the 65 proposed UK exclusions: 47 new decisions and four source-hash
refreshes. Fourteen proposals remain unapplied because the retained descriptions
contain potentially addressable scope or insufficient detail to rule it out.
The [decision receipt](audits/relevance-pr-review-2026-09-30.json) records each
source hash, quotation, reason and review limitation.

## Findings and repairs

- The proposed browser score depended on evidence, descriptions and lots absent
  from production market summaries. The exporter now supplies four compact facts
  per distinct capability match: capability, strength, source field and context.
  They come from validated public evidence and are checked against full details.
- Adding bonuses could promote an incidental mention above a commissioned
  software requirement. Ordered criteria now preserve evidence precedence.
- Raw value bonuses compared unrelated currencies and framework ceilings.
  Description-length penalties penalised sparse notices without proving poor fit.
  Both were removed. Neither affects the new sort.
- Repeated translated evidence and broad discovery families inflated breadth.
  Breadth now counts at most three distinct, specifically evidenced delivery
  capabilities. Original and translated repetitions do not add weight.
- Date-only deadlines now use the existing source-local end-of-day handling.
- Commissioned integration with an existing system remains delivery evidence;
  a description of what an installed system already does does not receive that
  promotion.
- The current-corpus check found "data, cloud" being treated as Data Cloud,
  generic "Education Cloud-based" wording treated as a Salesforce product,
  a prohibition on implementation treated as delivery, and a vendor being
  decommissioned treated as the target platform. Narrow public-evidence repairs
  reduce those claims while preserving genuine product names, affirmative
  implementation/integration and migration to the named platform. These repairs
  change evidence specificity and context, not discovery membership or source text.

## Ranking boundaries

Direct named-platform evidence comes first, then direct functional requirements,
uncertain specific mentions, contextual mentions and classification-only records.
Titles such as "Case Management System" count as direct functional evidence even
without a delivery verb. Installed-system mentions stay weak. Within equal
evidence, team delivery priority and lifecycle precede bounded capability breadth,
title evidence, the next response deadline and publication recency. Stable signal
IDs break any remaining tie.

The sort is deterministic and runs locally with a WeakMap cache of immutable
evidence facts. It calls no model or external service. It does not assert supplier
qualification, change filters, exclude notices or alter awards ordering. The
workspace now uses Best match by default and retains the selected sort and filters
when switching refiners. Existing preferences and explicit URLs keep working.
Older exports without compact facts remain readable; the release data fingerprint
forces a fresh compatible export for this pipeline change.

## Exclusion boundaries

The review read full retained descriptions, lots and eligibility, with independent
review of disputed and potentially mixed cases. It did not treat unextracted
attachments as read. Accepted exclusions cover clearly unrelated deliverables;
uncertain certifications, an existing competing platform, unspecified lots and
possible custom implementation routes are not grounds to hide a notice.

Original records and history remain retained. Source changes invalidate these
decisions, and reviews cannot override lifecycle availability. Existing guidance,
restorations and unrelated exclusions are preserved.

## Verification

The 30 September retained snapshot contains 8,095 current candidates. Applying
the same availability rules and the previous review ledger gives 7,075 available
records; this ledger gives 7,034. All 41 additional removals are among the approved
51 decisions. The other ten decisions do not remove an additional available
record in this snapshot. There are no unexplained removals.

All 7,034 available records were checked for identical Best match ordering between
compact facts and full details, and unchanged result membership versus Most
recent. These are snapshot checks, not a claim of perfect relevance or
internet-wide recall. Source-bound ledger validation, the labelled relevance
benchmark, unit tests, public-export contract tests and desktop/mobile sort
journeys cover the release changes. Publication retains its full-data validation
and browser checks.

One existing data-quality follow-up remains separate: the MoJ reading-education
RFI describes a November 2025 response deadline in prose, without a structured
deadline in the retained record. This change corrects its false Education Cloud
promotion; it does not invent a replacement deadline or declare the entire
future procurement cancelled. Deadline extraction and procurement availability
need a separate source-backed review.
