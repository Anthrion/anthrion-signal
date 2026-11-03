# Award translation coverage — 21 September 2026

The reported missing English text affected the Awarded view. The recording showed
English selected, with original-language award titles and descriptions across markets.

The worker reconstructed its queue exclusively from current public opportunities.
Award export already reused completed translations, but historical award text that
had never been a translated current opportunity was never submitted to the worker.
The language control and translation cache were functioning. Earlier checks of the
current feed did not test this coverage boundary.

The live award shards inspected during the incident contained 28 cached title/description
pairs among 3,745 DACH awards, 27 among 2,108 Nordic awards, two among 182 Dutch
awards, and one each among 274 French and 580 Italian awards. These are cached-pair
counts, not counts of foreign-language records: some original notices are already English.

## Repair

- Share award selection between export and translation, preserving the existing
  relevance, lifecycle and canonical-over-archive rules. Cancelled and irrelevant
  retained records are not added to translation merely because they exist in storage.
- Queue current notice content first, followed by published award content, then
  supplementary buyer names. Interleave countries within each group and reuse
  identical completed fields across records.
- Include completed awards in the English sidecar. Existing award, related-record
  and timeline exports consume the same validated cache; no browser model calls or
  source-text replacement are introduced.
- Report current and awarded notice coverage separately. Existing call limits,
  remote quota reservation, checkpoint ordering and safety checks stay in place.
- Use the existing deterministic, atomic gzip format for translation cache and
  sidecar files above 32 MiB. The field cache was already about 33 MB before adding
  the award backlog; readers accept either representation without discarding progress.

Historical translations are a backfill, not an immediate restoration of previously
completed text. Current opportunities remain first in line under the shared quota.
The historical backlog can therefore take multiple quota days to complete.

## Verification

Regression checks cover current-before-award priority, shared field reuse, archive
selection matching the published award set, cancellation and relevance exclusions,
completed award checkpoints without provider calls, and cache/sidecar compression
round trips. Translation, award-history and publication suites also run unchanged.
