# Quantum computing scope correction

The Grants.gov record `sig_6908ad36d3cca0926c26` was assigned Digital implementation because a scientific programme name contains “application development”. That phrase does not establish delivery of a business application. The original notice describes developing specialist quantum computing capability.

The phrase is now disambiguated consistently in capability tagging, generic digital discovery and mixed-scope protection. Exclusion additionally requires a quantum title and affirmative hardware-development/scaling evidence. A word such as “quantum”, a CPV classification, or a sparse description cannot independently exclude a record. Explicit CRM, portal, integration and AI delivery remains protected, including mixed lots and requirements in the same sentence. Negated hardware work is not positive exclusion evidence.

Original facts and the retained record are preserved. This changes derived classification rather than deleting source history or adding an ID-specific blocklist. Exact-hash English translations use the same rules. Collection checkpoints and queries are unchanged.

## Evidence and validation

- Official notice: [Grants.gov 363869](https://www.grants.gov/search-results-detail/363869).
- Supporting scope: [DOE announcement](https://www.energy.gov/science/articles/doe-launches-competition-accelerate-development-worlds-first-fault-tolerant), [official RFA](https://science.osti.gov/-/media/grants/pdf/foas/2026/DE-FOA-0003657.pdf).
- Scanned 65,169 retained notices; 36 contain quantum in original or available translated text. Comparing those decisions changes only the identified notice.
- Replayed the frozen 2,839-record public snapshot: only this record is removed; all 2,838 other records keep their capability tags and relevance decisions.
- Compared all 29,328 historical-award classification cache entries after export: no decision changes other than the policy-version label. Historical export remains 16,068 market entries (16,048 unique notice IDs).
- The local export contained 2,836 current-feed records: the single relevance correction plus two naturally expired notices. Deadline expiry is not counted as a classifier removal.
- Added 19 tests covering the original source record, unseen scientific programmes, mixed business/AI scope, sparse notices, post-quantum integration, translations and explicit negation. Existing precision fixtures and mixed-scope controls pass.
- Local checks: 763 pipeline tests before the final negation control; 254 targeted tests after it; Ruff, all 40 frontend unit tests, production build and public-output validation passed. CI reruns the complete final suite before publishing.

These comparisons establish the bounded regression impact. They do not prove exhaustive source collection or that every retained notice is commercially suitable. The separate product-improvement proposals are not included in this release.
