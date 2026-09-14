# Live translation audit — 14 September 2026

The live snapshot published at 07:26 UTC contained 1,901 records and 1,899 complete
English title/description pairs. The two missing pairs had exhausted their bounded
quality attempts on both configured models. The latest translation pass stopped
with `needs_review`, not exhausted daily quota. The last scheduled workflow visible
during the initial audit started at 07:11 UTC; scheduled retry times are requests,
not a guarantee that GitHub will start a run every fifteen minutes.

## Findings and repairs

- Italian notice `sig_385fb26148b2325dfc3a`, [Fondimpresa information-system services](https://ted.europa.eu/en/notice/-/detail/629600-2026),
  was first collected at 01:46 UTC. Its title and description contained numeric HTML
  character references. The worker masked character codes such as `8217` and `224`
  as procurement numbers inside Italian words, and rejected the generated output
  when those placeholders were not restored. Complete character references now
  become their text characters before masking and validation. Actual amounts,
  dates, identifiers and legal-reference numbers retain their original checks.
- German notice `sig_6843844a50b42fe77e59`, [breeding and resting bird surveys](https://oeffentlichevergabe.de/ui/de/notices/35077e7d-d9ed-4c64-bf16-1f07afbcaccd),
  was first collected at 23:40 UTC on 13 September. Its long list of named sites
  triggered the foreign-prose detector after translation. Source labels paired
  with explicit German site identifiers and area measurements are now protected,
  including when a source passage splits between a name and its area. This is a
  narrow source-structure rule, not an exemption for arbitrary lot descriptions.
  Review of the first repair pass caught a further fragment-level error: German
  `Los`, `DE` and `ha` were interpreted as Spanish words, producing `The`, `OF`
  and `has`. That deployment was cancelled before publication. Complete site
  identifiers and hectare quantities are now protected and checked, and the
  structured lot labels are validated. Each fragment receives a language hint
  estimated from the complete unmasked source to avoid losing that context.
  Repeated structural labels, site identifiers and hectare quantities are excluded
  from language detection while retaining their separate integrity checks. The
  final list-only fragment was also reviewed against its exact source: only the
  24 German `Los` labels became `Lot`; all names, codes, quantities and units were
  copied unchanged. Its cache entry records `assistant-source-review` provenance,
  and the completed passage passes the same production validation without an
  additional provider request.
- A broader entity scan found 11 otherwise translated records containing named
  references such as `&amp;`, `&reg;` or `&rsquo;`. Their existing cache text is decoded
  and revalidated without retranslating. A dry run preserved all 1,899 completed
  pairs through both cache validation and public export.

The source records, IDs, hashes, dates, eligibility and browser saved/hidden choices
are retained. The existing shared quota ledger and serialized workflow remain in
use; no separate local provider worker or quota reset is needed for this repair.
The updated retry profile gives outstanding quality failures a bounded retry while
retaining safety blocks and all provider limits.

## Ongoing verification

`scripts/audit_translations.py` checks all published records for complete pairs,
current source hashes, nonempty fields, encoded output, remaining foreign prose,
and mechanical translation validation. It reports coverage by country and lists
outstanding record IDs. Production workflow summaries now include these counts,
separate from optional organisation-name renderings. `--require-complete` can be
used for strict maintenance verification without making ordinary collection depend
on every new translation completing in the same run.

These are automated language and integrity checks plus a focused review of the
affected notices. They do not establish professional translation accuracy for all
1,901 records. Official organisation and location names may intentionally remain
in their source language.

## Deployed result

[Production workflow 34846781656](https://github.com/stevostar1234/anthrion-signal/actions/runs/34846781656)
completed successfully. A fresh download and browser verification at 13:12 UTC
(14:12 UK time) confirmed **1,886 / 1,886 published records** with complete,
validated English title/description pairs, including **73 / 73 Italian records**.
No published pair failed the strict coverage audit. The 15 records present in the
morning snapshot but absent from this release all had response deadlines that
passed between 08:00 and 13:00 UTC; they were not lost through translation.

- 469 pipeline tests, 32 frontend unit tests and 107 production browser checks
  passed. One desktop-specific check was intentionally skipped on mobile.
- The independent GitHub test workflow also passed. Ten focused local browser
  checks covered every market, translation controls, search, refresh and hidden IDs.
- Both repaired notices were checked directly on the deployed site in desktop and
  mobile browsers: complete English paragraphs, original titles, language switching,
  correct source links, no page errors and no browser requests to translation APIs.
- The final production pass used zero additional provider requests. The preceding
  two repair passes used 22 and 16 attempts respectively, retained in the shared
  quota ledger. No consumed requests were refunded or quota history reset.
- Nine supplementary organisation-name renderings remain held by quality checks.
  Their original official buyer names remain visible; no notice translation is
  waiting on those optional renderings.

Local evidence is retained in `artifacts/translation-audit-2026-09-14/`, including
the before/after live datasets, audit output, source-list review script and desktop/
mobile screenshots. Original titles, descriptions, IDs, dates, amounts and source
URLs were preserved. Existing classification can use the newly available English
text; two records gained derived capability annotations during export.
