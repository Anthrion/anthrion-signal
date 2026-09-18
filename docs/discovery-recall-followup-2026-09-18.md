# Discovery recall follow-up — 18 September 2026

Companion to [the precision review](discovery-precision-review-2026-09-18.md). That review found
that a CPV classification alone publishes a notice, and that the bucket riding on it is roughly
60–65% noise and 35–40% real work the vocabulary does not cover. This is the vocabulary work, plus
two checks that came out of the review's own recommendations.

**Held local deliberately.** Nothing here is proposed for merge yet; the point is a measurable
before/after to look at.

## 1. Vocabulary gaps

Rather than guess, the 1,268 published records with a CPV code and no textual evidence were mined
for recurring wording, using translated titles where available. Three patterns dominated.

**English compounds naming a system.** `has_software` recognises German and Nordic single words
that end in *-system* (`Verwaltungssystem`, `järjestelmä`) through a suffix rule, and lists
"information system" explicitly, but English names its systems as two words. "Content Management
System", "Learning Management System", "Enterprise Architecture Management System", "Resource
management system" and 29 others were therefore invisible. Added: `management system`, `IT system`,
`digital system`, `web application`, `IT solution`, `software solution`, `web portal`,
`online portal`, `internet portal`.

`digital solutions` and `computer system` were deliberately **not** added — reviewed decisions
already hold that neither establishes a technology scope on its own, and the second is how the
`ai`/`genai` guards recognise hardware for running models.

**Web estate and named business systems.** Website build, relaunch, redesign, maintenance and
hosting; CMS and LMS; records, asset, notification, ordering, booking, ticketing and contract
management systems. These join `generic_digital_scope`, the recall route that records quoted
evidence without inventing a capability tag, so the records stay in the general tier rather than
displacing Salesforce or AI work. Industrial control (SCADA, telemetry) is deliberately absent.

**Short AI notices.** "RFI AI Interpreter — an AI interpreter for recording, transcription and
translation" matched nothing. The `ai` contextual tier requires surrounding technical vocabulary,
which a three-word title does not have. A title-position acronym now counts on its own; the
all-capitals case test still separates it from Italian legal prose, and the research-funding guard
still applies.

Reviewing the 18 records this promoted showed three were GPU and inference-server procurements, so
the existing hardware guard — which already covers "computer system for running" and "laptop for
processing" — was extended with `gpu computing resources`, `gpu cluster`, `inference workloads` and
`compute resources`. Capacity to run a model is a different purchased object from the model.

### What had to come back out

Checking what the additions actually recovered caught three terms matching bidding boilerplate
rather than a deliverable, and they were removed:

| Term | What it matched |
| --- | --- |
| `procurement system` | "the SINTEL ELECTRONIC PROCUREMENT SYSTEM" — the e-tendering platform |
| `online portal` | German pharma rebate notices' submission instructions |
| `intranet` | publication channels ("published on the intranet") |

`web portal` and `internet portal` stay, being specific to a built thing. Writing the test for this
then caught a duplicate `online portal` entry the first removal had missed. This is the reason to
look at *what* a vocabulary change recovers rather than only at how much.

Checking the resulting AI tier found one more of the same kind, unrelated to the additions:
**"AI Bietercockpit" is a German e-tendering client**, and the product name in a submission address
had put a reservoir masterplan and a waterway-maintenance contract into the AI delivery tier. It now
joins the submission boilerplate the text filter already strips, alongside the
`atamis-*.my.salesforce-sites.com` supplier portals.

Worth recording the near-miss: *"Web hosting and professional support for the Quality Seal for
Sustainable Buildings"* looks like the same false positive and is not. Its description asks for
"hosting and further development of an AI-based, self-learning chatbot", so the AI tier is right.

### Measured

Both feeds exported from the same canonical data at the same time, so notices expiring between
runs cannot confound the comparison:

| | Without | With |
| --- | --- | --- |
| Published feed | 2,597 | 2,601 |
| Platform tier | 360 | **360** |
| AI tier | 96 | **111** |
| Records whose only evidence is a CPV code | 1,942 | **1,865** |
| Records removed | — | **0** |

77 records exchange "Relevant CPV classification" for quoted evidence, 15 move into the AI tier,
4 are recovered from the rejection store, and **nothing is dropped**. Vocabulary only adds
evidence, so the change is monotonic by construction; the export confirms it.

Two records did leave the feed on an earlier comparison run, which is worth recording because it
looked alarming: both had response deadlines between the two exports and simply expired. Neither
was affected by the vocabulary. That is the reason the final comparison re-exported both sides
together.

### The honest limit

A second round of additions moved the CPV-only count by only 31. Reading what still fails, the
remainder is a long tail of one-off phrasings — "Competition Implementation Tool (KGV)",
"Configuration management ... the EKIN desktop", "Open Referral Tool", "Patient and Colleague
Notification System" — with no shared vocabulary to capture.

Of the ~950 records that would still be dropped by tightening, perhaps a quarter to a third still
read as relevant. **Keyword vocabulary cannot get this to zero loss.** If the requirement is that no
relevant record is ever dropped, `cpv_requires_corroboration` should stay off and the noise should
be handled by ordering and labelling in the console rather than by removing records from the feed.
The tiering already does most of that work: platform and AI records sort above the rest.

## 2. The scope rules already read translated titles

The precision review recommended running `procurement_scope.RULES` against translated titles. That
recommendation was wrong and has been corrected in place. `prefilter` builds segments from both the
original and the exact-hash English translation, `scope_exclusion` receives all of them and tests
every title segment, so the rules already reach non-English notices. The German occupational-safety
notice cited as evidence is not in the published feed — it is excluded exactly as intended, and it
appeared to survive only because the earlier pass read `data/current.json`, which is the pre-export
file and carries no translations.

The real fragility is narrower: the rules depend on the exact English phrasing a machine translation
happens to produce. `occupational_safety` matches "occupational safety specialist" but not
"specialist for occupational safety", and nothing guarantees which form a given run returns. Phrasing
those title patterns as unordered term requirements rather than fixed word sequences would remove
the dependency. Not changed here — it alters exclusion behaviour, and every newly excluded record
would need individual review first.

## 3. TED's collection CPV gate is narrower than it looks, but not by much

TED supplies most of the feed and its primary query gates on
`classification-cpv IN (48* 72* 7931* 7941*)`, hardcoded in `collectors.py`. Anything classified
outside those families depends on the secondary keyword lanes, which run on a reserved fifth of the
page budget and which source health reports as still catching up.

UK sources are collected with no CPV gate at all, so they act as a control:

| | Platform/AI records with a CPV | Outside 48/72/7931/7941 |
| --- | --- | --- |
| UK sources (ungated) | 91 | 12 (13%) |
| TED (gated + keyword lanes) | 260 | 19 (7%) |

The raw gap suggests a blind spot, but it mostly closes on inspection: several of the 12 UK records
are mis-tagged rather than relevant (*High Voltage Equipment*, *Uniform and PPE*, *Dolwen
Residential Care Home*). Discounting those puts the true ungated rate near 6–7%, which is what TED
already achieves. **The keyword lanes appear to be doing their job, and no TED query change is
recommended.**

Two things are worth doing anyway, neither of them a filter change:

- The CPV list is hardcoded in `collectors.py` while the admission list lives in
  `config/search_terms.yaml`. `collection_cpv_prefixes` now holds the collection breadth
  explicitly; the TED filter should read from it so the two cannot drift silently.
- The genuine out-of-gate examples are worth knowing by name — *Replacement of Corporate Telephony
  and Contact Centre Environment* (CPV 64210000), *Enterprise Fraud and Financial Crime Tooling*
  (79212400), *AVT AI TRIAL* (85100000). Telephony, financial-crime tooling and health CPVs carrying
  genuine platform work is a pattern worth watching in the keyword lanes.

## Verification

```
python -m pytest -q                       794 passed
python -m ruff check pipeline             clean
```
