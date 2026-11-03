# Release storage and recovery

Signal stores source in Git, retained procurement state in Release assets, and the
validated website on Pages. The repository was recreated after GitHub rejected
writes to its approximately 100 GiB history. Recompressing the current tree could
not remove historical compressed blobs. Do not merge that old history into this
repository. Copy selected reviewed source changes instead.

## What is stored where

| Location | Contents | Write rule |
|---|---|---|
| Git | Source, reviewed decisions, configuration, small control files | Human source review; bot control-file allowlist and 256 KiB maximum per control file |
| Records snapshot | Canonical notices, historical versions, archives, rejected notices, source cursors and metadata | Restore the accepted state; upload and verify all bytes before changing the pointer |
| Translation snapshot | Existing cached translations and progress | Separate checkpoint preserves completed translations if later export validation fails |
| Public export snapshot | Exact validated public data graph | Compatible code fingerprint, source-input fingerprint and SHA-256 required |
| Actions cache | Optional copy of the public export | Cache loss falls back to the durable export; it is not a test result or canonical state |
| Pages | Website and compressed public datasets | Build, browser tests and deployment must succeed before recording publication |
| Private Timestamps | Existing source timestamp evidence | Existing independent workflow, credentials and trust root remain in place |

The Release snapshots contain the same public-procurement retained data previously
tracked in this public repository. They must not contain credentials, private company
files or raw document blobs. No browser needs a token or direct Release download.

`data/retained_state.json` identifies the accepted records and translations. Each
descriptor binds a release ID, content-addressed tag, filenames, sizes and SHA-256
checksums. Restore validates archive paths, file types, sizes and content before
replacing retained files. It never overwrites quota reservations or publication
controls. A compare-and-swap check prevents an old collector from overwriting a
newer accepted snapshot. Upload failures leave the accepted pointer unchanged.

## Developer setup

Install Python dependencies and GitHub CLI, authenticate `gh`, then run from the
repository root:

```powershell
python scripts/release_storage.py restore --repo Anthrion/anthrion-signal
python -m anthrion_signal.cli validate
python -m anthrion_signal.cli export
```

A source-only checkout intentionally has no bulk datasets. PR pipeline checks
restore the accepted base commit's pointer; UI-only PRs use their small fixtures.
Do not run a new collection over an empty checkout or commit the restored files.
Local uncommitted work is not automatically published by these commands.

## Recovery and retention

Managed tags start with `signal-data-v1-`. Each release has an exact ownership
marker. Other releases and human `v*` tags are never pruned. Retention keeps:

- Both accepted current components and their immediately previous components.
- The current validated export and the export actually published on Pages.
- Every managed upload younger than six hours, including resumed uploads on old commits.
- Public exports referenced before or after accepted pointer changes in the last six
  hours, so concurrent publication cannot lose an older export it already selected.
- The newest snapshot of each kind on each day in the last seven days.
- The newest snapshot of each kind in each calendar week represented in the last 28 days.

The collector refreshes accepted remote references before pruning. If it cannot
read them, cleanup stops. Failed cleanup is visible in Actions but does not prevent
publication. Incomplete uploads can resume using the same content-addressed tag;
an already uploaded attachment is never silently replaced.

To recover, create an isolated checkout, copy a known-good descriptor from
`previous` or a retained pointer commit, and restore and validate it there. Preserve
the latest quota and publication controls. Recovery requires a reviewed small pointer
change; do not force-push main, delete current snapshots, or reset publication
generation counters. Re-export and run the normal release checks before deploying.

## Limits and monitoring

Release attachment target size is 1 GiB (tar headers can add a small overhead),
below GitHub's 2 GiB per-file limit. A single retained file above 1 GiB or a component
above 4 GiB stops before upload; these are processing safeguards, not a claim that
storage is full. Future growth should use more stable data partitions, not larger
Git blobs. Current snapshots contain only a few assets, far below 1,000 per release.

`storage_health.py` records repository size, retained sizes, Release storage,
public size/file count and runner free disk in Actions summaries. Warnings start
at 500 MiB Git history, 2 GiB retained data, 750 MiB public data, 85,000 public files,
40 GiB Release storage, or less than 3 GiB runner free disk. These are review points,
not automatic deletions. Public validation retains its 900 MiB/100,000-file budgets,
and the complete website build remains capped at 950 MiB, below Pages' 1 GB limit.

No paid cache expansion, LFS, larger runner or external storage service is required.
Release retention bounds backup growth rather than accumulating each refresh forever.
The old archive's history remains in its renamed repository and does not enlarge
the replacement's Git database. Repository PR numbers, GitHub URLs and App grants
are repository-specific; website and record links stay at the original Pages address.

Official limits checked on 3 November 2026:
[Release assets](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases),
[Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
[Actions runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[Actions limits](https://docs.github.com/en/actions/reference/limits).
GitHub documents no total size or bandwidth limit per release, but this is not an
unlimited-service guarantee. Pages site size, bandwidth, runner resources, API limits
and provider quotas still apply. No billing settings are changed by this migration.
