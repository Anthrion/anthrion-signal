# Repository storage incident — 31 October 2026

## Verified cause and impact

All four failed collection/deployment runs received this server rejection:

> Repository is above its size quota. Contact GitHub Support for further assistance.

Runs: [41205812066](https://github.com/Anthrion/anthrion-signal-archive-2026-11-03/actions/runs/41205812066),
[41207698218](https://github.com/Anthrion/anthrion-signal-archive-2026-11-03/actions/runs/41207698218),
[41226656475](https://github.com/Anthrion/anthrion-signal-archive-2026-11-03/actions/runs/41226656475),
[41231375513](https://github.com/Anthrion/anthrion-signal-archive-2026-11-03/actions/runs/41231375513).

The last accepted main commit is `fe4f28eb1a4191193884c3b702a686e1dfe56eef`.
The last successful workflow finished at 08:50 UTC on 31 October. The failure is
repository persistence, not a Pages output-size error or failing data validator.
The latest failed run completed collection, public-data validation, packaging and
the validated export cache; its canonical-data push failed and publication was
correctly skipped. Earlier attempts also could not save translation quota
reservations, so the translation worker stopped before making unreserved calls.

The repository API reports `size: 105343227` KiB, approximately **100.5 GiB**.
The current tree is **731,977,277 bytes (698.1 MiB)**. The API's repository figure
and current-tree total measure different things; the first includes Git history.
Do not confuse either with the size of the deployed Pages site.

Current tracked-file distribution:

| Group | MiB | Share of current tree |
| --- | ---: | ---: |
| Discovery records and classification caches | 499.6 | 71.6% |
| Canonical signals | 74.4 | 10.7% |
| Translation state and English text | 57.0 | 8.2% |
| Retained archive | 23.6 | 3.4% |
| Current publication candidates | 13.1 | 1.9% |
| Source checkpoints | 7.2 | 1.0% |
| Dedupe index | 5.4 | 0.8% |
| Other files | 17.8 | 2.5% |

Repeated updates of compressed generated snapshots are the identified growth
mechanism: small logical changes can change large compressed blobs, and Git keeps
earlier committed versions. Current-file compression previously reduced checkout
and publication size; it does not remove earlier Git objects. Exact historical
bytes by category have not been measured, so the table is not a history breakdown.

A local recovery archive now preserves all **305 tracked retained-data files**
from that accepted commit, totaling **718,177,744 bytes**. Every file was checked
against its Git blob ID; the completed archive was read back and checked against
per-file SHA-256 hashes. This is a verified backup of the latest retained state,
not a complete backup of the approximately 100 GiB of Git history.

## Containment patch

The accompanying code recognizes the explicit repository-quota response, keeps
Git's diagnostic, and stops the three ineffective rebase/push attempts. It does
not force-push, delete records or alter repository protection. Normal transient
errors keep the existing bounded retries, and all existing data-only, conflict
and validated-code checks remain in force.

Within the same Actions attempt, an optional translation step that encounters
this repository block records a small local marker. Subsequent checkpoint pushes
and the pre-export check stop promptly. A different run or rerun does not inherit
that stop, so recovery can be checked normally. The marker contains no credentials
or source records and is not committed. This prevents avoidable export work after
a confirmed persistence failure; it **does not clear GitHub's quota block**.

## Durable recovery recommendation

1. Preserve the latest complete canonical data, original notices, retained
   timelines, translation caches, source cursors, dedupe indexes and quota ledger.
   Verify a backup against a file inventory and hashes before any cleanup.
2. Move frequently changing generated data out of Git. Keep source code, reviewed
   configuration and small trusted state references in Git. A versioned snapshot
   store must verify bytes before restore, publish its reference only after upload
   succeeds, retain a previous usable snapshot, and preserve the existing serial
   writer and remote-before-call translation quota rules. Caches alone are not
   durable canonical storage.
3. GitHub release assets are a possible route using the existing account; an
   object store is another. GitHub documents release files below 2 GiB, up to
   1,000 assets per release and no total release-size or bandwidth limit. This is
   not an unlimited-service guarantee. Keep a bounded retention policy and preserve
   the canonical procurement timelines within each snapshot. The current retained
   state fits below the documented per-asset limit. No release storage migration
   has been implemented or activated by the containment patch.
4. Contact GitHub Support about the active write block and the supported cleanup
   process. Deleting files in a new commit does not remove their historical blobs.
   Do not assume a small PR or an alternative write API can bypass the block.
5. Any history rewrite needs a separately approved migration: it changes commit
   hashes, affects signatures and existing clones, and conflicts with the current
   force-push protection. Preserve original signed source/timestamp evidence and
   coordinate working copies before that operation. This patch does not rewrite
   history, relax protection, or discard historical source evidence.
6. After GitHub permits writes and the approved storage change is installed, run
   one collection, verify its durable checkpoint and translations, complete the
   normal public-data checks, and confirm the Pages deployment and receipt.

Official references:

- [Repository size guidance](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)
  recommends storing programmatically generated files outside Git.
- [Release storage limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas).
- [History rewrite side effects](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository#side-effects-of-rewriting-history).

## Prepared GitHub Support request

Subject: Repository write block — Anthrion/anthrion-signal storage recovery

Our public repository Anthrion/anthrion-signal began rejecting pushes on
31 October 2026 with “Repository is above its size quota. Contact GitHub Support
for further assistance.” The repository API reports size 105343227 KiB. Its
current tracked tree is approximately 698 MiB; frequently updated compressed
generated-data snapshots have accumulated in Git history.

We intend to move generated state out of Git and preserve the current procurement
records and signed source evidence. Please advise on the supported process to
lift the write block for recovery and reclaim historical storage, including any
repository-network/PR references that would keep obsolete data objects reachable.
We have not force-pushed, deleted repository history, or disabled protections.

Example failed run: https://github.com/Anthrion/anthrion-signal-archive-2026-11-03/actions/runs/41231375513

This request is prepared for the owner; it has not been sent.
