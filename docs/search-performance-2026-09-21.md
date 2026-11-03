# Search and Context performance audit — 21 September 2026

All-market search was repeatedly normalizing each notice, constructing word sets, and scanning/normalizing the full capability catalogue for every record and every keystroke. Context rebuilt a string-heavy similarity index, repeated the same similarity calculation for both columns, and could reload award shards even though its merged result still held them.

The changes preserve complete original/translated matching text, query modes, result identities and ordering, similarity scores, eligibility checks, source details, and freshness validation. They do not add a persistent whole-feed text cache or retain background research workers after closing the page.

## Measurements

Sequential headless Chrome comparisons used the same local public-data snapshot, a 1600 × 1100 viewport, reduced motion in both versions, and a fixed reference time of 21 September 2026 at 14:00 UTC. There were 6,080 available records and 28,836 combined current/awarded records in the All-market benchmark. Times are local measurements, not guarantees on every machine or network.

| Interaction | Before | After |
| --- | ---: | ---: |
| All: search `salesforce`, input to painted results | 1.66 s | 0.44 s |
| All: five searches, mean | 1.68 s | 0.46 s |
| All: first Context opening | 7.25 s | 5.73 s |
| All: reopen Context | 7.82 s | 3.25 s |
| UK: first Context opening | 1.87 s | 1.87 s |
| UK: reopen Context | 0.76 s | 0.59 s |
| All: retained similarity-index heap, separate Node/V8 measurement | 153.0 MiB | 99.3 MiB |

The index heap figure measures the increment after forced garbage collection around index creation; it is not the total browser footprint. Reopening All made no further award-shard requests. First openings still include downloading/parsing awards and building the full similarity index.

A separate comparison with Chrome's 4× main-thread CPU throttle reduced All-market `salesforce` search from 8.02 s to 2.01 s. First Context opening improved from 15.11 s to 11.78 s and reopening from 6.97 s to 4.69 s. This is a CPU stress check, not a simulation of RAM exhaustion or operating-system paging; the user's reported 25-second wait cannot be predicted from it.

## Implementation

- Compile query terms and relevant capability aliases once per filtering operation. Replace per-record word sets with equivalent boundary checks, preserving the special short-token semantics.
- Apply Unicode normalization/classification to non-ASCII spans; ASCII portions use the equivalent simpler expression. Curly punctuation no longer forces expensive Unicode classification over a whole English notice.
- Store each similarity term once and refer to terms/documents using numeric IDs. Replace sets of repeated source IDs with numeric posting arrays, precompute frequency/factor values, and compute both result columns from one similarity pass.
- Avoid the duplicate initial worker request, temporary per-field projection arrays, and copying analysis/translation fields the matcher does not consume. Eligibility statuses and all actual matching text remain present.
- Reuse the existing merged award result when market, content-addressed paths, and manifest counts agree. Changed manifests and explicit retry still trigger validation/loading. Cache capacity is unchanged.
- Only serialize duplicate signal IDs when checking merged pages for incompatible versions; unique records do not need a duplicate version string.

## Validation

- 110 frontend unit tests passed; TypeScript and production build passed with the full snapshot (42,749 published data files, 698.8 MiB site).
- 63 targeted desktop/mobile browser checks passed; five existing device-specific skips. This includes release-critical journeys, search, related results, translations, original/full records, and a new regression exercising more shards than the existing cache can hold, reopening without downloads, and rejecting changed manifest counts.
- All 36 measured main-search result sequences matched the baseline. All 12 measured related searches matched result IDs, order, relationship labels, capability/term evidence, and numeric scores.
- An additional local equivalence audit covered all 1,114,112 Unicode code points in mixed ASCII/combining-mark context. The representative cases are retained in the unit suite; the exhaustive audit is not added to CI.
- Browser comparisons reported no page errors.

`app/scripts/benchmark-search.mjs` is an optional reproducible CPU/memory/result-fingerprint benchmark. Run from `app/` with `node --expose-gc scripts/benchmark-search.mjs`; provide an app root and output path to compare checkouts. Keep the same exported dataset and `SIGNAL_BENCHMARK_NOW` value between versions. It is not part of CI or the release test path.

## Further options requiring discussion

- A persistent prebuilt browser index could make subsequent Context openings faster, but would retain significant memory across closed pages. It was not added, given the team's busy browsers.
- Server-side search could further reduce browser CPU/memory requirements, but introduces a hosted service, operating cost, and service availability considerations.
- Publishing a precomputed similarity index may shorten first-opening computation, but needs a measured storage/download and parsing comparison before adopting it.

No result caps, text truncation, reduced market coverage, disabled translations, relaxed validation, or visual-effect changes are used for this optimization.
