# Public data publication and build size

The frontend loads `data/manifest.json`, the selected current-market indexes, and
individual record or buyer-history pages on demand. Current indexes retain full
original and verified English search text. The legacy `data/current.json` remains
available as a complete current-record fallback. Award-market pages and complete
collected buyer histories remain available through the same captured publication.

The Python exporter writes content-addressed dependencies before replacing the
root files. Previous generated dependencies can remain in `app/public/data` while
an existing browser still references them. An export does not delete history or
change the meaning of source records to reduce file size.

## Production copy

`app/build/publicData.mjs` replaces Vite's unconditional public-directory copy for
production builds. Development continues to serve the normal public directory.
The production plugin captures `current.json` and `manifest.json`, checks that
their metadata describes one completed publication, and copies only:

- Those captured root files.
- Every referenced current-market and award-market page.
- Every current and award record detail in the captured record manifest.
- Every referenced buyer-history page, with all of its published rows.
- All public assets outside `data/`, alongside Vite's application bundle.

The copy checks safe relative paths, regular files, supported schemas, content
hashes, record identities, market counts, buyer-history counts and complete record
coverage. Linked directories and files are rejected. The public source directory
and production destination cannot overlap. Root files are written to the output
last. Missing files, mixed publication roots, altered content or unsafe paths fail
the build; an incomplete output must not be deployed. A legacy current-only
fixture without the optional lazy feed remains buildable.

Hash validation preserves the exported JSON's numeric and string tokens. It
normalizes only insignificant whitespace to the Python exporter's canonical
format. This avoids changing values such as `1200.0` or `1e-07` while checking a
hash, and retains Unicode and escaped source text. The regular Python public-output
validator remains responsible for the detailed public evidence schema.

## Size guard and retained history

The complete production output, including bundled application assets and the
legacy fallback, must stay at or below **950 MiB (996,147,200 bytes)**. The build
fails with an explicit size error above that limit. This leaves a small margin
below GitHub Pages' documented [1 GB published-site limit](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).
The copier never drops referenced records or truncates history to pass the limit.

Generated public files are ignored by Git. A clean hosted workflow does not carry
unreferenced files across runs, but collection and translation can produce several
generations during one run. The allowlist prevents those superseded generations
from inflating the deployed site. It does not impose a permanent bound on the
current publication: retained award and buyer histories can grow. If the guard
fails, reduce repeated payloads or review the storage design before publishing.

Detached tests cover complete graph copying, original-file preservation, legacy
fixtures, Vite production/development integration, Python-compatible float and
Unicode hashing, missing or modified dependencies, identity/count mismatches,
unsafe links and paths, and the total size limit. They do not rewrite the active
development or production data directories.
