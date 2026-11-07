# Publication performance, 7 November 2026

The ten-minute failures happened in GitHub Pages after the build and tests had
passed. One deployment stayed queued; another stayed in file synchronization.
The reference production build took 97 seconds, the frontend unit suite about
three seconds, and the ten data-browser checks about six minutes. A retry helps
transient failures but does not reduce this work.

## Reduce publication files

Individual record and buyer-history files dominate file count. Details now use
stable hash partitions and bounded, content-addressed gzip bundles. Each bundle
targets 512 KiB of decoded JSON. An individual larger record stays intact within
the existing 16 MiB detail limit. The writer streams partitions rather than
holding another complete decoded export in memory. Readers select the exact
record or buyer identity from a bundle and retain support for individual files.

A lossless packing experiment on the verified 4 November public snapshot measured:

| Component | Previous files | Bundled files | Previous bytes | Bundled bytes |
| --- | ---: | ---: | ---: | ---: |
| Full records | 51,785 | 1,321 | 146,775,884 | 100,533,774 |
| Buyer histories | 15,412 | 854 | 55,165,095 | 49,540,778 |

Every one of the 67,197 source payloads was read back and checked against its
original canonical hash. Those two components use 96.8% fewer files and 25.7%
fewer compressed bytes. Keeping the other files unchanged would reduce that
71,435-file publication to 6,413 files, a 91.0% reduction. This is a measured
transport experiment, not a claim about an already completed production deploy.
Current publication measurements are recorded in the pull request and run logs.

The bootstrap also gains a gzip representation. The reference plain manifest is
27,261,446 bytes and was downloaded again on browser reloads and market tours.
New clients prefer the compressed manifest; the plain representation and complete
feed remain available. Publication verifies that both manifest representations
contain the same values. Original notices, translations, buyer timelines, record
identities and public evidence remain available.

## Focus recurring browser checks

Regular data-only refreshes use two focused checks, one desktop and one mobile,
covering actual record loading, source links, search, filters and browser refresh.
They avoid repeating full market tours for every data refresh. Application changes,
forced full checks and the existing periodic verification still run all ten data
browser cases and the broader UI regression suite. Python publication validation
continues to verify every referenced file, record, translation/evidence pair,
market count and link before release acceptance.

The fast unit suite stays: its approximately three seconds does not justify
removing useful coverage. The publication lock, integrity and scope checks,
successful-deployment receipt and bounded transient retry remain in place.
GitHub's queue delay is external; fewer files and less repeated test work reduce
the work Signal controls without promising that an external queue cannot stall.
