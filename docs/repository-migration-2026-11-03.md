# Repository recovery and limits audit

Migration started 3 November and completed 4 November 2026. The replacement is
live at the original address. The storage block no longer prevents updates.

## Outcome and evidence

The replacement uses the same `Anthrion/anthrion-signal` address and starts with
fresh source history. The original repository is preserved as
`Anthrion/anthrion-signal-archive-2026-11-03`. Its old commits, PRs and run history
remain there. Website record IDs and the Pages address are unchanged.

The accepted original head was `fe4f28eb1a4191193884c3b702a686e1dfe56eef`. The
previously prepared storage-error handling was also included. Comparing source
inventories found no missing tracked source files. The exact original public TLS
certificate was restored after an initial staging check caught its omission from
the fresh import; TLS verification was not weakened.

All **299 retained data files** were uploaded, downloaded into a separate folder
and compared byte for byte: 296 records/state files totalling 658,282,673 bytes,
plus three translation files totalling 59,751,395 bytes. The separate current quota
ledger remained unchanged during restore. This migration did not discard notice
history, reviews or completed translations.

The first complete staging run collected 15,325 source records, added 899 canonical
signals, identified 389 new public candidates and applied 312 material updates.
The export from that first run contained 8,997 current records and 42,791 awards. These counts
refer to different pipeline stages; public-candidate counts are not a claim that
all candidates became visible records. The run passed 2,277 Python tests, 182
frontend unit tests, 189 browser regression tests and ten real-data browser tests.
The complete website was 563.6 MiB.

The final source passed **2,281 Python tests**, 182 frontend unit tests, 189 browser
regression tests and ten real-data browser tests. Its validated export contains
8,994 current records and 42,791 awards. The final publication reused that verified
export, rebuilt for the original site path, and passed the frontend unit tests and
all ten real-data desktop/mobile tests again. It did not repeat the full data suite.

- [Completed final-source validation](https://github.com/Anthrion/anthrion-signal/actions/runs/41744668913).
- [Successful original-address deployment](https://github.com/Anthrion/anthrion-signal/actions/runs/41801337404).
- [Verified private source timestamp](https://github.com/Anthrion/anthrion-signal/actions/runs/41801342035).
- [First successful collection in the replacement](https://github.com/Anthrion/anthrion-signal/actions/runs/41736557170).
- [Fresh post-cutover collection dispatched](https://github.com/Anthrion/anthrion-signal/actions/runs/41803275284).

The live site's asset paths use `/anthrion-signal/`; its manifest matches the tested
export byte for byte. A cold-cache download of the durable public export passed
its SHA-256 check. Restoring records and translations after the rename also passed
all inventory checks without changing the current quota ledger. Manual production
checks verified an existing record deep link, 39 All-market Salesforce search
results, English/Original text, 108 related signals, 644 related awards and the
unchanged Salesforce sandbox prefill. No Lead was created by these checks.

The measured audit was captured at 08:52 UTC on 4 November. Full local evidence is
retained in `G:/Anthrion/signal-migration-2026-11-03/`; public run links above provide
the deployment and verification trail without publishing private settings exports.

## Storage behavior

Source and eight small control files remain in Git. Generated notices, archives,
source checkpoints and translation caches are checksummed Release assets. The
validated public export is also durable; Actions cache is only an optional fast
copy. Browsers continue to read the same static Pages data, without a GitHub token
or direct Release download.

Uploads must pass size and SHA-256 checks before an accepted pointer changes.
Restores reject malformed archives, unsafe paths, links and wrong bytes. Concurrent
writers cannot replace a newer accepted snapshot with an older one. Public exports
referenced around recent pointer changes are protected while deployment is running.

The limits audit also found a growing translation quota ledger. Historical
reservations now move losslessly into compressed monthly snapshot files, leaving
current/recent quota accounting and cumulative usage unchanged. An isolated check
of the real ledger reduced its live size from 134,187 to 1,450 bytes and retained
all 456 old allocation records in two archives totalling 6,361 bytes. Reconstructing
the original allocation and daily-usage maps matched exactly. The upload and
accepted-pointer sequence makes those archives durable before the smaller live
ledger is committed.

Retention preserves current and previous states, the published and validated
exports, six hours of recent uploads/referenced exports, daily checkpoints within
seven days and weekly checkpoints within 28 days. Older duplicate backups expire;
the notice-version history inside the retained state remains. Consequently, a very
old Git control-file commit is not a promise that its superseded Release backup
still exists. See [restore and recovery instructions](release-storage.md).

## Limits

| Area | Measured usage | Boundary and response |
|---|---:|---|
| Original Git history | 105,343,227 KiB reported by GitHub, about 100.5 GiB | GitHub rejected writes. Recompressing the latest files did not remove older Git objects. The original is preserved, not rewritten. |
| New Git history | 4,812,800 bytes, about 4.6 MiB | Only source and small controls. Warn at 500 MiB; each bot control file must remain below 256 KiB. GitHub recommends repositories remain below 10 GB on disk and blocks individual files above 100 MiB. |
| Retained canonical data | 726,236,662 bytes, about 692.6 MiB, across 301 files; largest file 74.0 MiB | Snapshot parts target 1 GiB. Internal limits are 1 GiB per retained file, 4 GiB and 10,000 files per component; warn earlier at 2 GiB total and 7,500 files. These are processing safeguards, not GitHub account quotas. |
| Release attachments | 7 releases, 3,260,185,088 bytes total (3.04 GiB); largest asset 635.8 MiB; one asset per release | Each attachment stays below GitHub's 2 GiB limit; at most 1,000 attachments are allowed per release. Recovery retention bounds repeated backup copies. Warn at 40 GiB aggregate Release storage. |
| Published website | Complete build 563.6 MiB; public data 588,418,328 bytes across 71,435 files | Pages permits a 1 GB site. Warn at 750 MiB/85,000 files, validate public data below 900 MiB/100,000 files and cap the complete build at 950 MiB. The file-count budget is Signal's own safeguard. |
| Pages bandwidth | Not exposed by this audit | GitHub documents a soft 100 GB/month limit. Site size and visitor bandwidth are separate; Release storage does not expand Pages capacity. |
| Actions cache | 1,664,215,105 bytes (1.55 GiB), five entries; configured maximum 10 GB | Same seven-day retention and 10 GB size limit as the original. No paid expansion. Public-export cache cleanup targets about 1 GiB while preserving the current/published copies. Cache eviction falls back to verified Release assets. |
| Actions artifacts/logs | Three Pages artifacts, 1,717,073,817 bytes (1.60 GiB) | Tested Pages artifacts last one day; browser-failure diagnostics last three days. The existing 90-day repository log/default retention remains. |
| Runner resources | 89,033,744,384 bytes free in the final data run, about 82.9 GiB | Standard public Ubuntu runners document 4 CPUs, 16 GB RAM and 14 GB SSD; observed free disk is not a guarantee for future runners. Warn below 3 GiB free disk. Signal jobs allow 120 minutes; GitHub's hosted-job ceiling is six hours. |
| API and queues | A few snapshot assets per refresh | Installation tokens generally start at 5,000 REST requests/hour; workflow tokens allow 1,000/hour per repository. Existing serialized data and publication queues remain, with at most 100 waiting runs per group. |
| Private timestamp archive | 275 KiB reported at the audit | Existing private repository, trust root and credentials retained. Source timestamps remain independent of deployment. |

Official references: [repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits),
[Release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases),
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
[runner resources](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[Actions limits](https://docs.github.com/en/actions/reference/limits),
[REST limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

All monitored measures are below their early warning thresholds. The preserved
original still occupies about 100.5 GiB: this migration reduces the active
repository's footprint, not the organization's total historical storage.

The immediate history-growth failure is removed: each refresh no longer adds
hundreds of megabytes of compressed datasets to Git. Pages capacity remains the
main growth constraint. There is no justified permanent capacity guarantee or
forecast without measuring future net dataset growth. Review the storage summary
regularly and plan further public-data compression or separate dataset hosting
before reaching the 750 MiB warning. Warnings are Actions annotations and summaries;
they do not automatically send a separate message or delete useful data.

Public standard runners and Release assets require no new paid service for this
design. No billing, LFS, larger-runner or cache-expansion setting was enabled.
GitHub documents no total size or bandwidth limit per release, but that is not an
unlimited-service guarantee. Existing organization subscriptions and provider
quotas remain separate. See [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

## Settings and handover

The two existing teams, two direct collaborator roles, three repository rules,
inherited release-tag rule, main-only Pages environment, Actions policy, variables
and credentials were reproduced. Existing Signal automation and Codex installations
include the replacement; Claude already covered all repositories. No new team,
human account, signing key, provider subscription or company-wide permission was
created. The temporary staging-name organization-rule exception was removed after
the name exchange. The original production-name exception remains. The final
comparison confirmed all three rule definitions and bypass lists, both team roles,
both direct collaborator roles, workflow permissions, variable values and secret
names. Public certificate comparison accounts for Windows versus Unix line endings;
the existing trusted certificate fingerprint is unchanged.

The copied translation credential successfully read metadata for both configured
Flash-Lite models. This checked authentication and model availability without
submitting notice text or generating output. It does not claim unused provider
quota; the normal reservation and backoff controls still apply. There were no open
PRs on the original repository when the migration handover was checked.

Existing private timestamp manifests remain untouched. For a pre-migration source
SHA or PR number, resolve the original Git objects and PR against the preserved
archive. Their hashes and timestamp evidence do not change when a repository is
renamed; the fresh repository is not a copy of those earlier commit objects.

The original site's Pages deployment was unpublished after the replacement passed
production verification; its repository and history remain intact. The old
repository's workflows remain disabled. The replacement resumes the existing
collection and translation schedules. Individual public-source outages still use
the existing retry/checkpoint behavior; successful repository recovery does not
prove complete coverage of every market.

The first collection reported eight fully healthy sources, ten partial sources and
three failed sources. Several partial results are deliberately resumable collection
budgets. Find a Tender returned HTTP 429 after supplying 212 records; Sell2Wales had
a connection failure after retaining its listing; LA RAMP returned an incomplete
snapshot; the Caribbean Development Bank returned HTTP 403; and Dominican DGCP
returned HTTP 500. Cached records were retained. These upstream issues remain
visible in source health and should be reviewed separately from the resolved Git
storage incident.

Use a **fresh clone** for development. Do not merge or force-push the old history
into the replacement. Existing local old worktrees are pointed at the archive;
the active local workspace is `G:/Anthrion/signal-next`, with its own `.venv`.
Restore retained data with the documented snapshot command before local collection.

Old PR numbers, issues, commit URLs, stars, forks and watch subscriptions remain
with the archived repository. Historical project-document links are updated to
that archive. Contributors who want notifications from the new repository should
watch it. Website bookmarks, signal IDs and browser-local settings keep the same
site origin. Reusing the original name deliberately ends GitHub's automatic
redirect to the renamed archive; see [GitHub's rename behavior](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).
