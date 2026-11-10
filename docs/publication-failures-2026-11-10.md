# Signal publication failures, 9–10 November 2026

Three scheduled runs ([04:22](https://github.com/Anthrion/anthrion-signal/actions/runs/42755443031),
[13:03](https://github.com/Anthrion/anthrion-signal/actions/runs/42821087772) and
[20:37](https://github.com/Anthrion/anthrion-signal/actions/runs/42897152327), UTC)
validated the retained dataset, then failed writing `current.json.gz`. The
duplicate copy of all current notices and translations exceeded its 256 MiB
decoded limit. Each notice and its English translation were already exported
in smaller record files. New releases publish only the matching plain and
compressed bootstrap manifests and their validated dependencies. Browser and
archive readers still accept older exports. To audit complete notices offline,
run `python scripts/audit_translations.py` against the manifest and its shards.

The validator checks the decoded limits, hashes, exact market membership,
counts, identity, source evidence and translation pairs of the data served by
the site. The build copies only the verified graph. Canonical retained data
and quota checkpoints keep their existing format.

Two other runs uploaded valid Pages artifacts of about 543–546 MB, then
stalled in GitHub Pages' file sync
([9 Nov](https://github.com/Anthrion/anthrion-signal/actions/runs/42714580274),
[10 Nov](https://github.com/Anthrion/anthrion-signal/actions/runs/42887103310)).
A [successful run](https://github.com/Anthrion/anthrion-signal/actions/runs/42809265408)
took about a minute in Pages with a comparable artifact. The retries
reused the first deployment ID: one was cancelled immediately and the other
timed out again. Publish now calls the official action once and records a
receipt only after confirmed success. If Pages stalls, the validated export
is still available to a later run and the previous site remains live.
GitHub's [ten-minute Pages limit](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
still applies.
