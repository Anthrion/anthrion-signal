# Translation Evaluation

## Argos Translate

Tested Argos Translate 1.11.0 in an isolated Python environment, not in the app or
its production requirements. The corpus contains 101,051 source characters from
157 passages across 103 existing records. Source text, model versions and output
are retained in `artifacts/translation-benchmark/` locally.

| Language | Source characters |
| --- | ---: |
| Danish | 17,825 |
| German | 16,116 |
| Greek | 15,269 |
| Spanish | 12,404 |
| Finnish | 20,112 |
| Italian | 9,425 |
| Norwegian Bokmal | 354 |
| Swedish | 9,546 |

These are source-character counts, not a percentage-accuracy score. There is no
human-translated reference corpus, and this was a technical/qualitative review,
not professional certification. The Norwegian sample is too small to establish
general quality. Generic Norwegian (`no`) needs explicit dialect/language mapping;
an `nb` model exists. No direct Icelandic-to-English model was available in the
tested package index.

Two runs used the same corpus:

- CPU int8, two intra-op threads: 327 seconds of translation, excluding downloads.
- CPU float32, two intra-op threads: 394 seconds, excluding downloads.

The initial int8 Spanish model produced repetitive invalid output. Repeating the
full benchmark in float32 corrected that failure, so it should not be described
as an unavoidable Spanish-language limitation of Argos. Other material quality
problems remained at full precision:

- A Danish software-interface term became "cutting surfaces".
- A Greek recruitment/onboarding project became an incoherent programme title;
  another passage dropped its final maintenance/support requirement after the
  numbered heading.
- A Finnish notice's total procurement value became the amount *by which* it
  exceeded the EU threshold, changing the financial meaning.
- Finnish named national services and Italian procurement terminology were
  inconsistently rendered. German and Swedish examples were generally more usable.

**Decision: not approved as the site's default English presentation.** No source
originals, IDs, search fields, deadlines or hide choices were replaced with these
translations. No translation dependency or model downloads were added to the
hourly workflow. This is an evaluation of the tested model versions and settings,
not a claim that every future Argos model will have the same quality.

Reproduce with the isolated environment and
`python scripts/benchmark_translation.py --compute-type float32`.
The library is [maintained here](https://github.com/argosopentech/argos-translate).

## Additional Website Options

Translation quality alone is insufficient: an integration must also preserve
React rendering, virtualized rows, filtering, source links and durable hidden IDs.
These checks did not install a widget, translation dependency or secret in the
production application, or start a paid subscription.

### LibreTranslate

Installed LibreTranslate 1.9.6 in a second isolated environment. Its dependency is
`argos-translate-lt` 1.12.1, not the Argos 1.11.0 release above. Tested the actual
`POST /translate` route through its Flask test client, using explicit source
languages, English output, float32 CPU inference and the current published model
versions. The models were checked against the current package index before use.

All 157 passages / 101,051 characters completed successfully in 360 seconds, with
no HTTP errors. 154 outputs were textually identical to the earlier float32 run;
this is an output-comparison count, not an accuracy percentage. The Danish
interface error, Greek missing requirement and recruitment-title error, and
Finnish financial-meaning error remain. It does not pass the default-English
quality gate for procurement qualification.

Results: `artifacts/translation-benchmark/libretranslate/`. Reproduce with
`tmp/libre-venv/Scripts/python.exe scripts/test_libretranslate.py` after installing
`libretranslate==1.9.6` into that isolated environment.

Self-hosting is possible, including batch use on a runner rather than a permanent
server, but compute and model maintenance are not costless. The managed service
requires a purchased API key. Its operator notes that hosted models can differ
from the public index: this local benchmark is **not** a quality assessment of
every model on the paid hosted service. [Official documentation](https://docs.libretranslate.com/),
[hosted-service and model differences](https://docs.libretranslate.com/guides/faq/).

### GTranslate

Tested the official dropdown widget on an isolated localhost page with **22
passages / 14,463 source characters** across Danish, German, Greek, Spanish,
Finnish, Italian, Norwegian and Swedish. For each source-language page, selected
English using the visible widget. These were small qualitative tests, not a
100,000-character GTranslate benchmark or a professional reference-based score.
Icelandic and translation into other target languages were not evaluated.

The sampled output was materially better than the tested open-source models:

- Danish software interfaces retained the correct technical meaning.
- The Greek maintenance requirement was preserved rather than dropped, and the
  recruitment/onboarding project title was understandable.
- The Finnish total procurement value and threshold relationship were retained.
- Named Kanta services, dates and amounts were generally better preserved in
  these examples. This does not establish error-free translation of every notice.

Deployment and compatibility do not yet pass:

- Current terms explicitly permit internal testing, but prohibit commercial use
  of the free tier. Anthrion's sales tool should not be deployed on that tier.
  A paid plan or written permission would be needed. No trial was started.
- With the page's original language set to English, selecting English left all
  14,463 foreign-language characters unchanged. The widget's original-language
  setting is not the same as detecting each procurement record's language.
- A separate test against the real local React app initially hit a library-load
  race (`__GT is not defined`). Waiting for the library before selecting a
  language avoided it. Under that setup, German text translated and hide/unhide
  preserved its stored ID without a React error.
- The short infinite-scroll check still showed a mixture of translated and
  untranslated newly rendered titles. This was not an exhaustive compatibility
  certification, and the paid proxy product was not tested.
- DOM-only translation does not automatically add English text to our JSON-based
  search index. A language-specific subdomain would also have a different browser
  storage origin; personal hidden records must not be silently separated.

Results and screenshots: `artifacts/translation-benchmark/gtranslate/`. Test
scripts: `scripts/test_gtranslate.cjs` and `scripts/test_gtranslate_app.cjs`.
Only public procurement passages were sent by the official widget in fresh test
browser profiles. No real user preferences, credentials or private notes were used.

**Decision:** promising translation quality, but not approved as a free drop-in
production widget. [Current terms, section 6](https://gtranslate.io/terms),
[official widget configuration](https://gtranslate.io/website-translator-widget).

### WEB-T

WEB-T Universal requires both its JavaScript client and a hosted Translation Hub,
plus an eTranslation or compatible provider account. It is an integration and
translation-management layer, not an independent translation engine. GitHub Pages
cannot host its server component. No eligible eTranslation credentials or hosted
hub were available, so **translation quality was not tested** and it was not added.
The eTranslation eligibility/callback investigation remains in the earlier audit.
[Official architecture and prerequisites](https://website-translation.language-tools.ec.europa.eu/solutions/universal-plugin_en).

### Recommended Integration

Keep the existing original-language presentation until a suitable provider passes
the quality and access checks. A cached per-record API translation remains the
better fit than a page-rewriting widget: preserve original text and stable IDs,
index English translations for search, and retain the source language separately
from the selected market. Collection must continue even when translation is
unavailable or its budget is exhausted.

Azure remains the first managed API to benchmark once access is arranged. It has
not been tested in this evaluation. A future compact EN / Original selector can
be extended to other target languages after testing them and accounting for each
target's translation volume. No nonfunctional language selector has been added.
