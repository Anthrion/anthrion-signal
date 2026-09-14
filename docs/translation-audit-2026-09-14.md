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
