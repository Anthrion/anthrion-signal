# Private Gemini Translation Evaluation

## Status

Implemented and tested a private translation worker. It produces saved English text;
it does not expose Gemini to site visitors, restore AI scoring,
overwrite source records, or change billing. The production workflow now runs the
worker after collection and publishes the saved output with an EN/Original selector.

This is a technical evaluation, not a certification of Google's interpretation of
the term "API Client". The architecture is a private publishing job, not an
interactive Gemini feature in the browser.

## Live Test

The final test used the same historical multilingual corpus as the Argos and
LibreTranslate evaluations, including examples subsequently removed from the
public feed. That is deliberate: it permits comparison on identical source text.
The actual records command translates only currently available public opportunities.

| Language | Passages | Source characters |
| --- | ---: | ---: |
| Danish | 23 | 17,825 |
| German | 23 | 16,116 |
| Greek | 22 | 15,269 |
| Spanish | 22 | 12,404 |
| Finnish | 22 | 20,112 |
| Italian | 22 | 9,425 |
| Norwegian Bokmal | 1 | 354 |
| Swedish | 22 | 9,546 |
| Total | 157 | 101,051 |

- All 157 passages completed the mechanical validation checks.
- 21 HTTP requests: 11 token-count requests and 10 generation requests.
- Gemini 3.5 Flash-Lite supplied 110 final passages; 3.1 Flash-Lite supplied 47.
- One oversized batch was detected before generation and split.
- One translation introduced an additional numeric expression and was rejected;
  a later valid translation completed that passage.
- No provider 429 was observed in this run. Rate-limit recovery was tested with
  mocked provider responses, not by deliberately exhausting the live project.
- The earlier four-request smoke test is additional to the 21 requests above.

The initial smoke test changed a Swedish organisation into the wrong museum name.
The worker was then changed to mask known buyer names, numbers, selected product
names, URLs and email addresses, and to verify exact restoration. The final full
test used this protected version. The original museum name was preserved.

Manual spot checks covered 15 seeded samples across all eight languages, plus
financial, procurement-stage, support-obligation and organisation-name edge cases.
The Finnish total exceeding the EU threshold retained its correct meaning; the
Greek final maintenance/support requirement was present; Danish software
interfaces were translated correctly; non-binding market exploration remained
non-binding. Some wording is literal or awkward, but these checks did not find
another comparable material error after the protection change.

This is encouraging for English discovery, not a measured accuracy percentage or
professional certification. Norwegian has only one short sample; Icelandic was
not covered. Numerical preservation cannot detect every semantic error, such as
a value attached to the wrong clause. Source notices remain authoritative.

## Quotas And Capacity

The Anthrion Signal project's AI Studio page showed 15 RPM, 250,000 input TPM and
500 RPD for each of the two Flash-Lite models. These are project-specific observed
limits, not universal or permanent guarantees.

The initial worker used 6 HTTP requests/minute, 100,000 estimated input tokens/minute
and 350 HTTP requests/Pacific day. The September 13 follow-up rechecked the actual
Anthrion Signal project in AI Studio and removed that extra headroom: the worker now
uses 15 RPM, 250,000 input TPM and 500 RPD per model. Existing usage is retained, not
reset. A 61-second sliding window, conservative full-request input estimates,
exact token counts and provider backoff protect the request limits. Token-count
calls and failed requests are still conservatively charged alongside generation;
we have not assumed that those calls are exempt from this project's quota.
Failed or interrupted calls never receive an automatic refund. Activity elsewhere
in the same Google project is not visible to the ledger, so provider-error handling
is essential even though there is no separate daily reserve. The scheduler considers
the next batch's token needs before choosing a model, avoiding unnecessary waits
when the other model is ready. A spent daily quota is reported separately from a
bounded run ending, and an unusable last counting-only call no longer causes an
empty reservation commit.

The release snapshot, after merging the newer GitHub collections with the local
record corrections, contains 3,158 unique eligible title/description fields
totalling 2,307,239 characters, including English text. At the benchmark's
observed ratio that is roughly 480 HTTP requests, across both models, before
allowing for different passage lengths, retries and changed records. This is a
planning estimate, not a guaranteed completion time or universal daily capacity.

Official references:

- [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Token counting](https://ai.google.dev/api/tokens)
- [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
- [Gemini API terms](https://ai.google.dev/gemini-api/terms)

## Worker Behaviour

- New/changed text is prioritised by last material update. A hash of the source
  text, target language and translation version prevents repeated translation
  when only collection timestamps or other metadata change.
- Only complete title-and-description pairs are emitted in the English sidecar.
  Partial output, incorrect IDs, missing numbers and incomplete generations are
  never represented as completed translations.
- Exact token counts cover the full request, including instructions and schema.
  Output capacity is reserved for translation expansion. Oversized requests split
  first by batch, then by contiguous source passages at sentence/word boundaries.
- Source splitting is lossless. Unbroken identifiers are not arbitrarily cut.
- Minute limits cause a wait or an eligible alternative model. Daily limits pause
  that model until the next Pacific midnight, with DST handled explicitly.
- Provider retry delays are respected, repeated failures back off, and every run
  has request and wall-clock ceilings. A failed model cannot create an unbounded
  retry loop. Safety-blocked output is not retried on another model.
- A quota reservation is saved before each HTTP call; validated translations are
  saved after each batch. Interrupted jobs resume from saved progress.
- Exhausting every model's budget leaves outstanding work in the cache. It does
  not delete opportunities or change source IDs, hidden-record storage, sorting,
  deadlines, amounts, availability decisions, or other source facts.

## Running Locally

From the repository root with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/translate_records.py plan
.\.venv\Scripts\python.exe scripts/translate_records.py benchmark --max-calls 60
.\.venv\Scripts\python.exe scripts/translate_records.py records --max-calls 60 --max-seconds 480
```

`GEMINI_API_KEY` is loaded privately from `.env`; it is sent in an HTTP header,
never a URL, public JSON, log message or browser bundle.

- Project-wide quota reservations: `data/translation_quota.json`.
- Stable record translation cache: `data/translation/cache.json`.
- Complete record output: `data/translation/translations.en.json`.
- Benchmark evidence: `artifacts/translation-benchmark/gemini/`.

Use one worker/ledger for this Google project. The local exclusive lock prevents
overlapping local workers, not workers on different computers. Do not delete the
ledger or run separate uncoordinated copies to obtain a fresh quota budget.
After an abrupt process kill, confirm the process stopped before removing its
stale `data/.translation.lock` file. Keep cached quota state across restarts.

## Production Integration

The hourly `:50` workflow runs a bounded translation pass after collection, with
at most 150 HTTP attempts and five minutes per pass, matching the two verified
models' combined minute capacity. Translation-only checks also run at :05, :20
and :35, including overnight. The per-day project ledger still applies across all
runs; this is not 150 new calls regardless of prior usage.
Before the first HTTP request, a run commits and pushes its entire allowance.
A lost runner therefore leaves those calls accounted for. Normal completion
returns only the unused allowance. Actual requests are never refunded.

Cache and quota checkpoints are independent of subsequent build/test failures.
Translation failures do not bypass mandatory collection validation, tests or
public-output checks, and do not prevent original-language opportunities from
being published. Cached complete pairs require an exact current source-text hash;
changed or incomplete pairs fall back to the original text. Translation-only
changes trigger deployment, while quota bookkeeping alone does not.

The EN/Original selection is stored separately from saved and hidden records.
English is the default; both languages are searchable. Source titles and
descriptions remain canonical for eligibility and ranking. CSV and source links
retain original source facts. No visitor action calls Gemini.

Do not run a local translation worker concurrently with the deployed workflow.
For maintenance, pause the workflow, wait for any active run to finish, fetch the
latest committed ledger, then commit the updated ledger/cache before re-enabling.
Hourly schedules remain best-effort GitHub scheduling, not a minute-exact SLA.

The initial benchmark passed 338 Python tests, including 34 translation-specific
tests. Production integration adds crash-accounting, source-hash, publication,
bilingual search and browser regression tests. Expand the thin Norwegian sample
and test Icelandic before claiming equal coverage for every Nordic language.

## Release Backfill

The reconciled release snapshot contains 1,668 public records and 3,158 unique
nonblank title/description fields (2,307,239 source characters). All fields and
record pairs completed before publication. The three bounded production passes
used 597 HTTP attempts in total, including token-count requests and rejected
attempts. Re-exporting the completed cache required no API calls.

The prompt was clarified to copy already-English text verbatim and avoid adding
digit-based abbreviations for spelled-out terms. Rejected fields received one
bounded retry under that clarification; safety blocks were not reset. One Greek
passage still substituted `3D` for a spelled-out source term. An assistant source
review corrected that terminology and preserved the original procurement
acronyms. The cache records the review; all completed parts passed the unchanged
validation rules. This is automated validation and a limited assistant review,
not a professional certification of translation accuracy.

Release verification: 349 Python tests, 30 frontend unit tests, 103 production
Chromium browser checks, and eight focused WebKit desktop/mobile checks passed.
One desktop-specific screenshot test is intentionally skipped on mobile.
