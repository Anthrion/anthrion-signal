# Retained notice history

The canonical store already reconciles incoming updates into one current notice.
The rejected-notice store previously appended full copies to daily gzip files.
It now keeps one full current row for each stable notice ID, with the old values
of changed fields as reverse patches. This is storage compaction, not fuzzy
deduplication: different notice IDs, lots and procurement stages remain distinct.

Each historical patch is relative to its own current row, not another file or a
long chain. Applying `restore` and `remove` reconstructs the complete prior JSON
row. SHA-256 hashes cover every field, including observation metadata, exact
Unicode text and numeric types. Migration validates each reconstructed version
and checks that the selected current records have identical hashes before and
after. Identical JSON copies are stored once. Existing timeline changes remain
untouched; no new timeline UI is introduced.

Files live in `data/discovery/rejected/compact/<bucket>.jsonl.gz`, using the first
two hex digits of SHA-256(notice ID). Each file contains self-contained envelopes
and is atomically replaced. A 90 MiB compressed guard stops growth before Git's
single-file limit; finer partitions can be introduced if ever needed. Current
head precedence remains publisher update date, then last observed row for ties.
Late older releases are retained without becoming current.

As with the old daily writer, repeated collections of unchanged facts within a
UTC day update that day's observation instead of adding hourly copies. This
comparison ignores only collector first/last-seen clocks and provenance retrieval
timestamps; every source and classification field still counts as a change.
Only observations created by the new writer are replaceable in this way, so the
full versions preserved by migration are never retroactively collapsed. Different
days keep separate observations, and material changes always retain history.

The migration writes and verifies all buckets before recording the consumed
legacy files in `format.json`, then removes those files. If interrupted during
cleanup, consumed old files cannot override a newer tied head. Source files that
change during migration cause it to abort before source deletion. No source
checkpoint, original translation or record identifier is rewritten.

## Inactive removal policy

`scripts/maintain_rejected.py prune` defaults to a dry run. Only rejected-only
notices qualify, and **every stored version** must meet all requirements:

- Expired, closed, cancelled or withdrawn; all published/update/response dates
  at least 180 days old. Unknown dates or availability stay retained.
- Zero relevance score and explicit physical/non-technical exclusion, with only
  physical CPV divisions (03, 15, 18, 19, 44, 45). Current discovery rules must
  confirm the decision; absent keywords alone never authorize deletion.
- No award, winner, contract/extension date, renewal hint, framework, relevant
  capability, scope evidence, analysis, enriched attachment or cached translation.
- No current public detail or research-page reference, canonical/archive row,
  reviewed guidance or translation, or shared procurement identity with a kept
  record. Relationships are checked across all versions and transitively.
- Every removed version must already exist in the immutable Git recovery
  revision recorded in the removal inventory. Newly collected observations
  without a committed recovery copy remain retained.

This deliberately retains potentially useful records even when they are old or
closed. Awards are not subject to a blanket age cutoff. A previously rejected
notice can still be reconsidered when discovery rules change. Removed, clearly
irrelevant notices may be collected again if their source republishes them;
there is no permanent suppression tombstone that could conceal changed scope.

Maintenance runs after public-data validation and before its cache receipt is
packaged. Compaction runs once, then incoming writes use the compact format.
Pruning runs at most once per UTC day/policy/discovery signature and does not run
on the cached UI-only release path. Published IDs and all retained head hashes
are verified during removal. A recovery inventory is written before mutation;
completed inventories remain under `data/retention/`.

## Inspection and recovery

Run `python scripts/maintain_rejected.py compact` or `prune` to measure first;
add `--apply` for a verified write. Pruning requires a generated, validated
`app/public/data/manifest.json`. It makes no collector or model calls.

For version inspection, read the notice's bucket with `read_bucket` from
`anthrion_signal.rejected_store`, then iterate `unpack_versions(envelope)`.
The last yielded row is current. Other rows are previous observations, not a
claim of source publication order. The stored source dates and change entries
remain available in each reconstructed row.

The removal inventory lists the IDs, source version hashes and `recovery_commit`.
Read the original daily file or compact bucket from that commit with `git show`;
recover all listed versions before restoring a notice with `pack_versions`.
Do not mix old rows into canonical data without normal reconciliation.

This reduces the current retained snapshot and future repeated writes. It does
not rewrite Git history or reduce existing historical Git objects, and it does
not remove the public records responsible for buyer/award research workflows.

## Initial full-data measurement — 24 September 2026

At source revision `03b70a573d5b5323c65fb13e6da525f683758545`:

| Measure | Before | After compaction |
| --- | ---: | ---: |
| Full rejected rows | 259,220 | 135,188 current rows |
| Distinct recoverable versions | 257,525 | 257,525 |
| Historical reverse patches | 0 | 122,337 |
| Compressed bytes | 229,251,604 | 151,978,446 |

Savings: **77,273,158 bytes (73.7 MiB; 33.7%)**. The 1,695 identical copies
carry no additional facts. This measurement excludes any later inactive pruning
and excludes the separate public-site compression already deployed.
