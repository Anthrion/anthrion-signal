# Lossless public-data compression

The 24 September collection reached the 900 MiB public-data budget. Publication
stopped during release packaging, after tests, instead of deploying an oversized
site. Retained source facts and completed translations were checkpointed separately.

Market indexes, individual records, shared buyer histories and the complete-feed
fallback now use deterministic gzip. Historical buckets were already compressed.
The bootstrap manifest remains JSON. Compression changes transport bytes and file
references, not source text, IDs, translations, guidance, search scope or retention.

The browser, worker data client, Python evidence validator, Vite publication builder,
release cache and offline audit commands accept the new files. Plain older exports
and development fixtures remain readable. Hosts that already decode HTTP gzip are
handled without decompressing twice. Failed downloads still reject incomplete search
results; cancellation and cache eviction retain their previous behavior.

Content hashes continue to describe decoded JSON. Public paths, complete manifest
membership, source evidence, record identities, counts and translations are validated
before publication. Stored bytes determine the Pages budget. The complete cache is
bounded by the same 900 MiB ceiling because compressed members cannot be expected to
shrink again inside its archive; cache pruning still applies its existing retention
budget. The site build retains its 950 MiB ceiling and the cache its 100,000-file ceiling.

Historical buckets retain the 16 MiB download/decode guard. Individual records and
buyer timelines use that guard too. Market indexes and the complete fallback were
previously unbounded plain JSON; they have a separate 256 MiB guard so existing large
indexes remain readable. These are failure guards, not truncation rules. Bounded index
shards and shared procedure histories are the next scaling steps; no record is silently
removed to meet a limit.

## Retained record inventory

Read-only inventory of main `af5c3d0e37c31a4e285804fdd42a3f634e420dff`,
evaluated at 2026-09-24 08:05 UTC, using production retained-history precedence:
latest rejected/archive version per ID, then canonical records override older versions.

| Lifecycle | Distinct notice IDs |
| --- | ---: |
| Awarded | 74,577 |
| Open | 29,003 |
| Early engagement | 1,327 |
| Future intent | 23,345 |
| Expired | 42,893 |
| Closed | 15,149 |
| Cancelled | 927 |
| Withdrawn | 45 |
| Unknown | 1,105 |
| **Total** | **188,371** |

The underlying files contain 314,362 rows including repeated versions. These counts
cover retained notices, including irrelevant/rejected notices saved for re-evaluation;
they are neither a count of qualified leads nor of unique procurement procedures.
No source, archive, rejection, translation or review records are deleted by this change.

## Further capacity options

Compression is an immediate capacity improvement, not unlimited storage. Separate
project repositories can each publish a Pages site, but a second repository does not
increase the existing site's 1 GB allowance. Data split across deployments needs
cross-site references, coordinated versions and compatible access rules. Dedicated
object storage is a better eventual fit for growing immutable data.

Further lossless savings include referencing country indexes from grouped markets,
storing repeated procedure histories once, and keeping award search summaries separate
from lazily loaded detail. Index chunking would bound individual decode costs. Source
version deduplication should preserve distinct amendments and replay evidence.

A future retention policy should keep known ongoing contracts/extensions and treat
missing or ambiguous dates conservatively. The preceding audit found that a one-year
award cutoff saved only about 1.8% even using publication dates as proxies; protecting
ongoing contracts saves less. Retention alone therefore does not resolve the current
growth pattern, and no age/relevance deletion policy is introduced here.

References: [Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
[project sites](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).
