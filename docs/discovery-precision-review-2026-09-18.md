# Discovery precision review — 18 September 2026

An independent review of the collection and relevance mechanism against its stated goal: surface
Salesforce-ecosystem work and anything deliverable on Salesforce, plus standalone AI, LLM and agent
implementations, without being so narrow that real opportunities are lost or so broad that the feed
fills with noise.

The conclusion is that **recall is working and precision is not**. The guards that protect against
false positives are careful and effective; the admission rule underneath them is not, because a
procurement classification code on its own is enough to publish a notice.

## What was measured

- The exported public feed at the 18 September baseline: **2,835 records**, with translations
  attached for 2,830 of them, so matching ran against English text for effectively the whole feed.
- **36,477 unique retained rejections** across the four stored daily partitions.
- The 12,602 canonical records in `data/signals.jsonl`.
- Decisions were reproduced by running `prefilter` itself, not by re-implementing it.

Precision was assessed by stratified manual review of random samples drawn from each admission
route. Recall was assessed by probing every retained rejection for high-confidence in-scope
evidence and reading each hit. Both are estimates from samples, not exhaustive census.

## Finding 1 — a classification code alone publishes a notice

`prefilter` scores a CPV match at 12 points and `minimum_candidate_score` is 12, so a notice whose
CPV code starts with a listed prefix reaches the publication threshold with no other evidence at
all. Verified against the real code:

| Notice | Score | Published |
| --- | --- | --- |
| "Beschaffung von Gartenmöbeln" (garden furniture), CPV 72000000 | 12 | yes |
| "PR Agency Services", CPV 79416000 | 12 | yes |
| "Palo Alto Erweiterung" (firewall capacity), CPV 48000000 | 12 | yes |
| "Salesforce implementation partner", no CPV | 70 | yes |
| "AI assistant for citizen enquiries", no CPV | 44 | yes |

**2,185 of 2,835 published records (77%) carry `Relevant CPV classification` as their only
evidence.** 2,287 records have no capability tag at all — a number the 18 September audit already
records as `untagged_after`, without treating it as a defect.

Splitting that bucket by whether the notice text contains any software, platform or delivery scope:

| Bucket | Records | Share of feed |
| --- | --- | --- |
| Addressable delivery stated | 93 | 3% |
| Software vocabulary only | 824 | 29% |
| No textual evidence whatsoever | 1,268 | 45% |

A blind sample of 40 from the zero-evidence bucket read as roughly 60–65% clear noise —
Eurobarometer surveys, multi-function printer frameworks, occupational health services, defence
accommodation, business incubator management — and 35–40% genuinely relevant work that the
vocabulary simply does not cover, including website development, patient record management,
an AI interpreter RFI and several "implementation, development, migration and support" contracts.

That mix is the important part. **The CPV route is not acting as a filter; it is acting as a
catch-all that compensates for vocabulary gaps, and it pays for that with a majority of noise.**
Tightening it without first widening the vocabulary would discard real opportunities.

## Finding 2 — four CPV prefixes both admit and exclude

`config/search_terms.yaml` granted relevance to `7931` (market research), `7941` (business and
management consultancy) and `7512`/`7513` (public administration services). `procurement_scope.py`
uses those same prefixes as corroborating evidence for its `survey_execution`, `business_promotion`,
`property_valuation` and `financial_audit` exclusions. A code cannot be evidence for and against
relevance at once.

247 published records were admitted solely by those prefixes. Reviewing the 47 admitted by `7931`
without any `48`/`72` code found no relevant record among them: swimming pool remedial surveys,
post-construction bird and bat monitoring, environmental surveys, laboratory services, company
health services, business incubator management.

## Finding 3 — Italian legal prose matched as the AI acronym

The `ai` capability accepts the bare acronym when it appears in uppercase, on the reasoning that
case separates the acronym from an ordinary word. In an all-capitals notice title that distinction
disappears, and the Italian preposition *ai* ("to the") matched instead:

> GARA APERTA **AI SENSI** DELL'ART.71 DEL D.LGS. 36/2023 PER L'AFFIDAMENTO …

Four published records were promoted into the AI delivery tier this way.

## Finding 4 — research funding occupies a third of the AI tier

**45 of the 140 records in the AI tier were US federal research funding announcements** whose only
evidence was a topical mention of artificial intelligence — NSF and NIH programme statements,
postdoctoral fellowships, centre grants. These are not buyers procuring an AI implementation, and
they displace genuine AI tenders in the tier that matters most.

## Finding 5 — recall is genuinely strong

Every retained rejection was probed for high-confidence in-scope evidence after stripping URLs and
supplier-portal hostnames. The probes are largely language independent for the strongest terms.

| Probe | Rejections containing it | Genuine misses |
| --- | --- | --- |
| Salesforce / Agentforce / MuleSoft | 34 | 0 — all `atamis-*.my.salesforce-sites.com` bidding portals |
| CRM / customer relationship management | 1 | 0 — "CrM" is a Spanish railway depot code in an HVAC contract |
| AI agent / chatbot / LLM / generative AI | 33 | 0 — policy pages, research grants, "LLM" as a law degree |
| Case management / casework | 117 | 0 — social-care casework and GOV.UK caseworker guidance |

The supplier-portal suppression, the negation handling, the `AMBIGUOUS_NEEDS` software requirement
and the GOV.UK buying-intent gate are all doing precisely what they were designed to do. The
rejection store being complete and replayable is a genuine strength: any admission policy can be
changed and re-run over history without losing notices.

## Changes in this pull request

1. **Non-technology CPV prefixes removed** from `cpv_prefixes`, resolving Finding 2.
2. **Acronym evidence judged locally** (`acronym_case_evidence`), resolving Finding 3. An uppercase
   acronym counts when it sits in mixed-case prose; inside an all-capitals passage it needs a
   supporting AI term. Verified: 4 affected records → 0.
3. **Topical AI in a funding notice no longer claims a delivery tier**, resolving Finding 4. Named
   products stay explicit evidence and a funding notice that procures an AI system is unaffected.
   Verified: 45 affected records → 5.
4. **`cpv_requires_corroboration`** added to the discovery policy, off by default. When enabled, a
   notice whose only signal is its CPV code must also state software, platform or delivery scope in
   its own text. The mechanism and its tests ship here so the policy decision in Finding 1 can be
   made on measured numbers rather than on a rewrite.

### Measured effect

Re-exported against the same canonical data, with `cpv_requires_corroboration` left off:

| | Baseline | After | Change |
| --- | --- | --- | --- |
| Published feed | 2,835 | 2,599 | −236 |
| Platform tier | 361 | 361 | **0** |
| AI tier | 140 | 96 | −44 |
| Other tier | 2,334 | 2,142 | −192 |
| Previously rejected records now admitted | — | 0 | — |

No record leaves the platform tier. The 44 leaving the AI tier are the Italian prose matches and
the US research programmes; 43 of them remain published in the other tier rather than disappearing.
The 236 removed records are consultancy, PR, staffing, accommodation, evaluation and construction
notices — a sample is in the pull request.

Enabling `cpv_requires_corroboration` on top would remove a further ~1,268 records with no textual
evidence. That is deliberately not switched on here; see the recommended order below.

One human-reviewed fixture changed expectation. `sig_1ee047eb41c952cf8874` (Spanish road-safety KPI
fieldwork, five lots of roadside speed measurement and non-participatory observation) was retained
only by CPV 79315000. Its rationale is recorded in the fixture. It is the single reviewed decision
this change reverses and it should be confirmed.

## Recommended next, in order

1. **Close the vocabulary gaps before tightening admission.** The zero-evidence bucket is 45% of the
   feed and about a third of it is real. Specific gaps found: website creation and development
   phrasing, "record management solution", HR and asset management systems, short AI notices with no
   surrounding technical vocabulary. Each relevant notice that starts matching on its own evidence
   is one that no longer needs the CPV catch-all.
2. **Then enable `cpv_requires_corroboration`** and re-measure. Rejections stay replayable, so this
   is reversible.
3. **Loosen the scope-exclusion rules' dependence on exact translated wording.**
   `scope_exclusion` already receives the `english_translation` segments and tests every title
   segment, so the rules do reach non-English notices — that part works. What they depend on is the
   exact English phrasing a machine translation happens to produce: `occupational_safety` matches
   "occupational safety specialist" but not "specialist for occupational safety", and the
   translation of a given notice is not guaranteed to land on the listed form. The title patterns
   should be phrased as unordered term requirements rather than fixed word sequences.
4. **Derive TED's collection CPV filter from configuration.** `collectors.py` hardcodes
   `classification-cpv IN (48* 72* 7931* 7941*)`, so the policy now lives in two places. Collecting
   more broadly than you admit is correct, but it should say so deliberately. Note that TED supplies
   63% of the feed and its primary query is CPV-gated: a Salesforce or AI tender classified outside
   those families is reachable only through the secondary keyword lanes, which the source health
   reports as still catching up.
5. **Report an evidence mix in the run metadata** — records admitted by capability evidence versus
   by classification alone — so this ratio is visible every run instead of needing an audit.

## Verification

```
python -m pytest -q                                   774 passed
python -m ruff check pipeline scripts/check_public_output.py    clean
python -m anthrion_signal.cli export
python scripts/check_public_output.py
```
