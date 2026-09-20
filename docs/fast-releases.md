# Release paths and test audit

UI changes should not wait for procurement collection or reclassify unchanged source records. Collection and publication now have separate queues. Both keep a 120-minute emergency ceiling; this is not a runtime target.

| Change | Required work |
| --- | --- |
| Presentation/components, styles, static assets, interaction tests | Compatible verified data restore; frontend units, production build, desktop/mobile interaction and real-data integration tests |
| Data contracts/loaders, dependencies, collectors, classification, export, automation, unknown paths | Full Python suite, relevance benchmark, lint, data export/evidence/translation validation, frontend and browser checks |
| New source data or translations | Validate changed inputs, build, frontend units and real-data integration; full regression daily or when its code changes |
| Identical inputs and application | Reuse the exact compatible validation result; no new site publication unless the signature changes |
| Missing, evicted, invalid or incompatible cache | Recompute and verify; never publish unchecked data |

The existing required PR status is still `test`. The redundant `Tests` run on a main push is removed because the production workflow verifies the code it actually publishes. A cold first rollout still needs the full path to seed a trusted cache. Warm release timings must be measured after that rollout; 5–10 minutes is a target, not a guarantee.

## Cache boundaries

`data/validated_data.json` binds a compressed public export to its SHA-256, data-code fingerprint, input fingerprint and monotonically increasing generation. Only the validated dependency graph enters this cache, not older unreferenced assets or canonical/private inputs. Extraction rejects unsafe paths, links, duplicates, missing roots and excessive sizes. PRs select a receipt from their trusted base commit and cannot certify their own proposed data changes.

Data-code fingerprints include pipeline scripts/tests, validation, dependencies, workflows, data contracts and every unclassified source path. Presentation files are excluded because their frontend checks still run. Source data, retained histories and translation changes invalidate input reuse; quota reservations and publication bookkeeping do not. Raw download/model caches are not public export inputs.

The archive limit is 250 MiB compressed and 900 MiB expanded. Cache cleanup retains at most eight dedicated public-data entries within a 1 GiB budget, while protecting the current validated and published receipts. Other caches are untouched. Existing pip/npm caches remain; Chromium binaries are cached by runner OS and exact dependency lock. No organization setting, App access, paid tier or larger runner changes are required.

## Publication and concurrency

The collector keeps the existing `anthrion-signal-production` lock, preserving exclusivity with an older workflow during migration. Quota must still be committed remotely before a translation request. Each write phase gets a fresh Signal-scoped token.

The publisher acquires `anthrion-signal-publication`, checks out latest main, restores compatible validated data, builds and tests one artifact, deploys that same artifact and records its signature before releasing the lock. It refuses data generations older than the last successful publication. An obsolete collector cannot deploy its earlier UI checkout. If newer pipeline code needs validation, publication waits for its compatible export.

Normal guarded rebases preserve independent collection and publication commits. Conflicting edits fail rather than overwrite either side; a pipeline change during validation prevents an old receipt from claiming the new code passed. The successful publication marker is written only after Pages confirms deployment. Failure leaves the last deployed site intact.

## Test audit decisions

Reviewed the Python test inventory, assertion/exception paths, duplicate-body candidates, frontend unit suites and browser scenarios. Repeated classifier test bodies use different inputs: physical services, mixed software lots, source languages, negation, sparse scope and lifecycle revisions. They protect different false-positive and false-negative boundaries and remain.

Removed or separated work with no additional release protection:

- The screenshot-only record-panel case moved to `npm run capture:record`.
- Unasserted design captures are opt-in through `SIGNAL_CAPTURE_DESIGN=true`; actual pixel/motion assertions and failure screenshots remain.
- An unused legacy assessment fixture was deleted.
- Interaction tests no longer download the entire roughly 78 MB feed merely to obtain a sample record or metadata.
- The duplicate main-push Tests workflow is replaced by the production gates.

Retained: full-corpus market and award checks, source/translation correspondence, filtering and sorting, failure recovery, keyboard and accessibility checks, CSP, responsive layouts, motion preferences, large-list virtualization, collection recovery, quota safety, source retention and private timestamp verification. Browser `@data` cases read the real export; the default full browser command still includes them. Fast interaction cases use controlled fixtures, including the legacy fallback; research tests and real-data integration exercise the current manifest/detail format.

New tests cover cache integrity and safe extraction, cache invalidation and trusted PR receipts, publication generations, cache storage bounds, workflow gates, and real concurrent Git writes. They target the risks introduced by separating the queues.

## Commands

```sh
npm test
npm run build
SIGNAL_TEST_PREVIEW=true npm run test:e2e:ui
SIGNAL_TEST_PREVIEW=true npm run test:e2e:data
# Optional design artifact, outside the release test suite:
npm run capture:record
```

The production build must finish before starting preview-based tests. Local external-drive file I/O can be much slower than a GitHub runner; record CI timings separately.

Actionlint 1.7.12 has stale schemas for `concurrency.queue` and the App action's `client-id`. Lint suppresses only those known diagnostics after checking [GitHub concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) and the [actual v3 action inputs](https://github.com/actions/create-github-app-token/blob/v3/action.yml); other diagnostics remain failures.
