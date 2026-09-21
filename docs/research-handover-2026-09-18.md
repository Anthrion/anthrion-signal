# Research handover — session of 18 September 2026

Durable record of a review-and-expansion session, written so the work can be resumed without
re-deriving anything. Kept on its own branch rather than folded into the open pull requests.

Figures marked **(verified)** were queried directly against the live API during the session.
Everything else came from a research pass and is attributed as such. "Unknown" means unknown.

---

## 1. Status

### Pull requests open

| PR | Branch | Base | State |
| --- | --- | --- | --- |
| [#1](https://github.com/Anthrion/anthrion-signal/pull/1) | `fix/discovery-precision` | `main` | CI green. **Needs a decision** — see §2 |
| [#2](https://github.com/Anthrion/anthrion-signal/pull/2) | `feature/vocabulary-recall` | `fix/discovery-precision` | Stacked; review #1 first |
| [#8](https://github.com/Anthrion/anthrion-signal/pull/8) | `feature/market-expansion-europe` | `main` | Independent, for deduplication against the in-flight market build |

### Work not finished

- **Canada / North America sources** — research stopped before reporting. Nothing verified beyond:
  CanadaBuys replaced buyandsell.gc.ca, and open.canada.ca runs CKAN under the Open Government
  Licence – Canada 2.0. **No endpoints confirmed.** A North America tab was the user's goal.
- **Does a paid feed actually close Sweden?** The test of whether commercial aggregators carry
  Swedish *below-threshold* notices from the registered annonsdatabaser was stopped mid-run.
  Unresolved and material: if a provider only resells TED, paying adds nothing.
- **Sweden-specific annonsdatabas pricing** (e-Avrop, KommersAnnons, Mercell Annonsdatabas,
  Konstpool, Clira) — not gathered.
- **Best Fit curated view** — designed and agreed, not built. See §5.

---

## 2. The one open decision

`pipeline/tests/fixtures/relevance_review.json`, id **`sig_1ee047eb41c952cf8874`** — *"Servicio de
elaboración de informes sobre indicadores clave de rendimiento en seguridad vial. 5 lotes."*

PR #1 flips it from `retain` to `reject`. Its retention rested entirely on CPV **79315000** (social
research services), which `procurement_scope`'s `survey_execution` rule simultaneously uses as
*exclusion* evidence. The five lots are roadside speed measurement and non-participatory
observation fieldwork; the lot 1 deliverable is a dashboard.

This is the only human-reviewed decision the change reverses. Rationale is recorded in the fixture's
`review_basis`.

---

## 3. What the review found

### Recall was already good

36,477 retained rejections probed for high-confidence in-scope evidence after stripping URLs and
supplier-portal hostnames; every hit read individually.

| Probe | Rejections containing it | Genuine misses |
| --- | --- | --- |
| Salesforce / Agentforce / MuleSoft | 34 | **0** — all `atamis-*.my.salesforce-sites.com` bidding portals |
| CRM | 1 | **0** — "CrM" is a Spanish railway depot code in an HVAC contract |
| AI agent / chatbot / LLM / generative AI | 33 | **0** — policy pages, research grants, "LLM" as a law degree |
| Case management / casework | 117 | **0** — social-care casework, GOV.UK caseworker guidance |

### Precision was the problem, structurally

A CPV match scores 12 and `minimum_candidate_score` is 12, so **a classification code alone reached
the publication threshold**. Verified against the real code: *"Beschaffung von Gartenmöbeln"*
(garden furniture) with CPV 72000000 scored exactly 12 and published; a Salesforce implementation
scored 70.

**2,185 of 2,835 records (77%)** carried `Relevant CPV classification` as their only evidence.
**1,268 (45% of the feed)** had no software, platform or delivery wording anywhere in their text.
A blind sample of 40 from that bucket read as 60–65% noise, 35–40% genuinely relevant work the
vocabulary did not cover.

### Bugs fixed

| Bug | Effect | Fix |
| --- | --- | --- |
| Four CPV prefixes both admitted and excluded (`7931` market research, `7941` management consultancy, `7512`/`7513` public administration) | 247 records admitted solely by them; of the 47 admitted by `7931` alone, **none** relevant | Removed from `cpv_prefixes`; collection breadth preserved separately in `collection_cpv_prefixes` |
| Italian preposition *ai* read as the AI acronym — "GARA APERTA **AI SENSI**" | 4 records promoted into the AI tier | `acronym_case_evidence` judges each occurrence in its local window; all-capitals passages need a supporting AI term |
| Research funding occupied a third of the AI tier | 45 of 140 were NSF/NIH programme statements | A topical AI mention in a `FUNDING` notice no longer claims a delivery tier |
| GPU / inference-server procurement promoted as AI | 3 records | Existing hardware guard extended |
| "AI Bietercockpit" — a German e-tendering client — read as AI scope | 2 records (a reservoir masterplan, a waterway maintenance contract) | Added to submission boilerplate; the product appears as `AI Bietercockpit`, `AI_Bietercockpit` **and** `AI-Bietercockpit`, and the underscore form defeats a word boundary |

### Measured effect of #1 and #2 together

Both feeds exported from the same canonical data at the same moment:

| | Baseline | After #1 | After #1+#2 |
| --- | --- | --- | --- |
| Published feed | 2,835 | 2,597 | 2,600 |
| Platform tier | 361 | 360 | **360** |
| AI tier | 140 | 96 | **109** |
| Evidence is only a CPV code | 2,185 | 1,942 | **1,865** |

#1 removes 236 noise records (PR consultancy, staffing, accommodation, company health services) with
**zero loss from the platform tier**. #2 gives 77 records quoted evidence, moves 15 into the AI tier,
recovers 4 from the rejection store, and drops one — a CPV 45 construction notice whose only
evidence was a bidding-client product name.

### Two of my own earlier claims were wrong and are corrected in the repo

1. **The scope-exclusion rules already read translated titles.** `prefilter` builds segments from
   both the original and the exact-hash English translation, and `scope_exclusion` tests every title
   segment. The German occupational-safety notice cited as evidence is not in the feed at all — it
   only appeared to survive because the analysis had read `data/current.json`, which is the
   **pre-export** file and carries no translations. The real fragility is narrower: the rules depend
   on the exact English phrasing a machine translation happens to return.
2. **Switzerland is in TED.** See §6.

### The honest limit on vocabulary work

A second round of additions moved the CPV-only count by only 31. The remainder is a long tail of
one-off phrasings — "Competition Implementation Tool (KGV)", "Configuration management … the EKIN
desktop", "Open Referral Tool". Even after #2, enabling `cpv_requires_corroboration` would still drop
~950 records of which perhaps a quarter to a third read as relevant.

**Decision taken: leave `cpv_requires_corroboration` off.** Handle noise by ordering and labelling,
not removal.

---

## 4. Checking what a vocabulary change recovers matters more than how much

Three added terms matched bidding boilerplate rather than a deliverable and were removed again:

| Term | What it actually matched |
| --- | --- |
| `procurement system` | "the SINTEL ELECTRONIC PROCUREMENT SYSTEM" — the e-tendering platform |
| `online portal` | German pharma rebate notices' submission instructions |
| `intranet` | publication channels ("published on the intranet") |

Writing the test for those caught a duplicate `online portal` entry the first removal had missed.
Reading the resulting AI tier record by record then surfaced the Bietercockpit bug. None of this was
visible from aggregate counts.

One near-miss recorded because it looks identical and is not: *"Web hosting and professional support
for the Quality Seal for Sustainable Buildings"* asks in its description for "hosting and further
development of an AI-based, self-learning chatbot". The AI tier is correct there.

---

## 5. Best Fit — the curated view, designed not built

**Name agreed: "Best Fit".** Internal naming stays neutral (`curation.json`, `curation_version`) so
the label can change without a migration.

**Runs on the Claude Code GitHub Action with a subscription**, not an API key. Confirmed from
[the docs](https://code.claude.com/docs/en/github-actions): `claude_code_oauth_token` accepts an
OAuth token from `claude setup-token` on Pro, Max, Team and Enterprise plans; automation mode runs on
any GitHub event including cron; *"If you authenticate with an OAuth token, runs use your Claude
subscription instead of API billing."*

**Cadence: once or twice daily, not hourly.** Only ~38 new public records arrive per collection run,
a churning list loses trust, and hourly would be 24× the token cost.

### Architecture — keep the agent's job narrow

The codebase is built on replay (`discovery_signature`, content-hash caches, rejection replay), and
an agentic session is the least reproducible thing that could be dropped into it. So:

1. Pipeline deterministically writes `data/curation/input.json` — candidates, trimmed, stable order.
2. The scheduled run writes `data/curation/verdicts.json` — verdict, route, reason, verbatim quote.
3. Pipeline validates **without** the model: quote must be a literal substring of the notice, verdict
   in enum, no eligibility language (`AGENTS.md` rule). Fail → not curated, record untouched
   elsewhere.
4. Both files committed. The run replays from them.
5. Frontend: a sixth refiner card. Absent from the map ⇒ absent from that view only.

Package the procedure as a skill in `.claude/skills/curate-best-fit` invoked via
`prompt: "/curate-best-fit"` with `--max-turns` capped, so the schema lives in version control.

### Verdict shape — this is what makes it useful

Not "relevant / not relevant" but **the delivery route**:

- `core` — Salesforce ecosystem, or standalone AI/agent implementation
- `adjacent` — deliverable on Salesforce / Experience Cloud / Heroku with an upsell path
  ← **web hosting and web-estate work lands here**
- `pass` — not addressable

Default the view to `core` with an "include adjacent" toggle. For someone checking a phone between
meetings, *"portal build — could run on Experience Cloud"* beats a relevance score. It also resolves
the web-hosting question properly: those records are labelled with the route to pitch, not filtered
out.

### Token budget (measured)

Median **264 new** + **114 materially updated** published records/day = **~378 to score**. Mean
title+description 707 characters (~177 tokens) trimmed; 1,200-char cap ⇒ ~300.

| | Tokens/day |
| --- | --- |
| Record text | ~67k |
| Batch preambles (~15 batches of 25) | ~12k |
| **Payload input** | **~80k** (worst case ~125k) |
| Output | ~30k |
| One-off backfill of all 2,600 records | ~460k, once |

Agent overhead is the real cost: ~10–20k per session for system prompt, `AGENTS.md` and the skill,
plus context accumulation across turns. Budget **~300k/day** if the workflow runs several short
sessions, **~800–900k/day** if one long session accumulates. Versus ~110k for a direct API call —
a 4–8× multiplier, and the argument for daily rather than hourly.

**Lever:** only 28% of the feed carries any quoted evidence. Gating Best Fit to those gives ~105
records/day and ~100k tokens all-in.

### Gotchas specific to this repo

- Scheduled runs are attributed to whoever last edited the `cron` line, and the action **rejects bot
  actors** unless listed in `allowed_bots`. This repo has bot data commits.
- Public repos disable scheduled workflows after 60 days without activity.
- The Claude GitHub App's permission set is broad (Contents, Issues, PRs, Actions **and Workflows**
  read-write). Given the signing and force-push rules in `AGENTS.md`, pass
  `github_token: ${{ secrets.GITHUB_TOKEN }}` instead — that avoids installing the app *and* stops
  the curation commit re-triggering collection.
- The OAuth token is tied to one person's subscription. Bus factor for a company tool.
- `PUBLICED_EXCLUDE` currently strips every model-derived field (`fit_score`, `recommendation`,
  `score_explanation`). Publishing curation output reverses a deliberate policy — the README records
  that Gemini scoring "and score-based product features have been retired". Needs an explicit
  decision.

### Two data licences constrain this feature specifically

- **Finland — Hilma.** Terms permit commercial value-added services but state the user **may not
  modify the substantive content** of a notice, and personal data must not be used for **direct
  marketing**. An AI step that rewrites notice text is a content modification.
- **Austria — ANKÖ** (`ogd.ankoe.at`, `vergabeportal.at`). `Content-Signal: ai-train=no, ai-input=no`
  plus `Disallow: /` for ClaudeBot, anthropic-ai, GPTBot, CCBot. `ai-input=no` objects to
  inference-time use.

Neither blocks the product. Both point the same way: **quote source text, link to the notice, do not
rewrite it** — which the grounded-quote design already does for independent reasons.

---

## 6. Market expansion

### Switzerland is in TED

The natural assumption — non-EU, non-EEA, therefore absent — is wrong. Switzerland publishes under
the 1999 EU–Switzerland procurement agreement (Decision 2002/309/EC, Euratom, in force 2002-06-01),
which extends the WTO GPA. **703 Swiss notices 1–18 September 2026 (verified.)** Buyers are
unambiguously Swiss: SBB CFF FFS, Swissgrid, Flughafen Zürich, Kanton Zürich.

simap.ch is still needed, but only for below-threshold `invitation` and `direct` procedures.

### TED volumes, 1–18 September 2026 (all verified)

| Country | Notices | | Country | Notices |
| --- | --- | --- | --- | --- |
| Germany | 8,822 | | Norway | 699 |
| Poland | **6,931** | | Ireland | 681 |
| France | 4,284 | | Greece | 643 |
| Spain | 3,673 | | Austria | 604 |
| Italy | 2,098 | | Denmark | 480 |
| Netherlands | 1,363 | | Luxembourg | 125 |
| Sweden | 1,178 | | Iceland | 62 |
| Belgium | 1,142 | | UK | 6 (post-Brexit) |
| Portugal | 861 | | | |
| Finland | 813 | | **All TED** | **46,628** |
| Switzerland | 703 | | | |

### Coverage of TED (verified)

| | Notices | Share of all TED |
| --- | --- | --- |
| Before (IT, SE, FI, DK, NO, IS, DE, ES, GR) | 18,435 | **39.5%** |
| Six new markets | 8,198 | 17.6% |
| **After #8** | 26,624 | **57.1%** |
| + Poland, Ireland, Portugal | 35,083 | **75.2%** |

The expansion adds **+44% more notice volume**. France alone exceeds Italy. **Poland is the largest
untapped market in Europe** — bigger than France, second only to Germany — and its national bulletin
is keyless and 100% below-threshold.

This is not free in capacity terms: it competes for the TED page budget, the keyword-lane rotation
and the translation quota.

⚠️ `buyer-country` inflates Belgium and Luxembourg with EU institutions headquartered there. Use
`place-of-performance-country-lot` for genuine national demand.

### Estimated coverage within each market

Share of *nationally published* notices reachable. Confidence varies; ranges and "uncertain" are
deliberate.

| Market | Now | Gap source | Status |
| --- | --- | --- | --- |
| UK, Germany, Spain | ~90–95% | national sources already collected | ✅ |
| Netherlands | ~86% | TenderNed | buildable |
| Denmark | ~80% | udbud.dk | buildable |
| France | ~71% | BOAMP | buildable |
| Luxembourg | ~70% | PMP | 🚩 clearance |
| Belgium | ~39–77% | BDA | 🚩 blocked |
| Italy, Greece | ~20–50% | ANAC / KIMDIS | buildable |
| Sweden | TED only | **none exists** | 🚩 paid or nothing |
| Austria, Switzerland, Iceland, Finland, Norway | uncertain | USP, simap, Hilma, Doffin | mixed |
| **United States** | **very low** | SAM.gov bulk extract | ⚠️ biggest single gap |

**The US is the weakest market.** Config says it plainly — *"Live federal tenders are not
connected."* Grants.gov, LA RAMP and NYC City Record are connected; federal solicitations are not.

### Grouping decided

Nine tabs. **DACH** = DE + AT + CH. **Benelux** = BE + NL + LU (Luxembourg alone is 125 notices per
18 days). Three things moved together:

- `markets` in `app/src/lib.ts`
- `normaliseFilters` migrates `?market=DE` → `DACH`, following the existing `pipeline`→`early` and
  `updates`→`today` redirects. Without it every shared Germany link lands on an empty market.
- `award_history.MARKETS` uses the same grouping, or per-market award files are never written for the
  new countries.

### Vocabulary

French **7 → 22 families, 141 terms**; Dutch **5 → 22 families, 123 terms**. Both now exceed German
(67) and Spanish (60). Terms these markets actually use, not translations of the English list:
*tierce maintenance applicative*, *assistance à maîtrise d'ouvrage*, *dématérialisation des
procédures*, *téléservices*, *reprise de données*; *zaakgericht werken*, *zaaksysteem*, *digitaal
loket*, *DigiD-koppeling*, *functioneel beheer*, *sociaal domein*.

Replaying over the existing 2,594-record corpus: **zero tier changes, zero new family matches.**

Austria is covered by the existing `de` pack; Luxembourg publishes mainly in French and German, so
`fr` + `de` cover it.

---

## 7. Source technical appendix

Kept because these details are expensive to rediscover. Everything registered in
`config/sources.yaml` as disabled; see also `docs/free-apis-market-expansion-2026-09-18.md`.

### Cleanly licensed, worth building

**BOAMP (France)** — the single highest-value collector available.
`https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records`
Licence Ouverte / Etalab. No auth. `x-ratelimit-limit: 2000000`/day. ~35,600 below-threshold
notices/year. Deadlines on ~97% of tender notices. Lifecycle chains on `contractfolderid`.
- Use **v2.1** — v2.0 returns a deprecation header and data.gouv.fr still points at it.
- Use `/exports/json`, not `/records`: the latter caps `limit` at 100 and rejects
  `offset+limit > 10000`. One `/exports/json` call returned a whole month.
- CPV is inside the `donnees` blob, but `where=search(donnees,"45000000")` filters server-side.
- ⚠️ `api.dila.fr` and `api.dila.gouv.fr` **do not exist** (DNS failure). Stale docs point there.
- ⚠️ `robots.txt` has a stock `Disallow: /api/` while the same dataset is an official open API.
- Raw XML alternative: `https://echanges.dila.gouv.fr/OPENDATA/BOAMP/YYYY/MM/DD/`, schemas in
  `/Schemas/`.
- **Ceiling:** below €60,000 no publication required; €90,000→EU threshold may go to BOAMP *or* a
  newspaper. Structurally non-exhaustive where below-threshold work lives.

**TenderNed (Netherlands)** — cleanest interface found.
`https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties` · detail `/{publicatieId}`
**CC0 1.0**, declared in the OpenAPI spec. No auth. ~20,500 below-threshold of 145,756.
- ⚠️ **Unknown query parameters are silently ignored** — always validate a filtered count against an
  unfiltered baseline.
- Caps: `size ≤ 100`, `page ≤ 99` ⇒ 10,000 records/query. ~110 notices/day, so daily slices fit; a
  full year does not.
- Cursor: `publicatieDatumVanaf` / `publicatieDatumTot`.
- XML API is **waitlisted indefinitely** — do not design around it.
- OCDS bulk for backfill; also mirrored at `data.open-contracting.org` publication 133.

**udbud.dk (Denmark)** — best free source found anywhere in the study.
`POST https://udbud.dk/soegning/public/soegeresultat` · **published OpenAPI** at `/soegning/api-docs`
No auth. eForms-native. Notices in Danish **and** English (`dataDa`/`dataEn`).
- **True changed-since cursor**: `filterDto.systemFilter.registreretTidFra/Til` (index time).
- `formularType` spans `FORVENTET_INDKOEB` (forward pipeline), `MARKEDSDIALOGER`,
  `FORHAANDSMEDDELELSER`, `EU_UDBUD`, `NATIONALE_UDBUD`, `DIREKTE_TILDELINGER`, `TILDELINGER`,
  `KONTRAKTAENDERINGER`, `KONTRAKTAFSLUTNING`.
- Licence: reproduction with attribution; the authority **explicitly permits commercial tender
  intermediaries**.

**KIMDIS (Greece)** — `https://cerpp.eprocurement.gov.gr/khmdhs-opendata`, OpenAPI at `/v3/api-docs`
**CC BY 4.0.** No auth. Registration mandatory from **€1,000**, so coverage is very deep.
- ⚠️ Max **180-day** query window, silently clamped. Documented **350 req/min**, but persistent 429s
  were observed from shared cloud egress — plan backoff, ideally a dedicated IP.
- Full cancellation lifecycle: `cancelled`, `cancellationDate/Type/Reason`.

**simap.ch (Switzerland)** — only route to Swiss below-threshold.
`https://www.simap.ch/api` · OpenAPI 3.0.3 at `/api/specifications/simap.yaml`
No auth for publication data. API GTC §4 **expressly permits commercial reuse and redistribution**.
- **`publicationTed` boolean = deterministic TED dedup key.** Also `correction.correctionDiffKeys`
  naming which fields changed.
- Cursor: `newestPublicationFrom/Until` plus a rolling `lastItem` cursor (`20260918|42963`), 20/page.
- ⚠️ **Three binding obligations (§5):** data unaltered and visually distinct carrying *«Dies ist
  keine amtliche Veröffentlichung…»*; **an embargo — nothing surfaced before 08:00 Europe/Zurich on
  publication day**; corrections propagated.
- ⚠️ General site GTC §9.1 forbids reproduction; API GTC §2 is *lex specialis*. Consume via the API,
  never scrape HTML. Worth a legal sign-off.
- ⚠️ Airlock WAF redirects to `/cookie-check` after ~15 rapid requests. Persistent cookie jar +
  follow redirects.

**EU SEDIA** — `POST https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA`
`apiKey=SEDIA` is **officially documented**, an index selector not a credential. Reusable under
Commission Decision 2011/833/EU. Portal T&C contain no clause restricting automated access.
- ⚠️ **`type=0` is calls for tenders; `type=1` is grant topics.** Easy to invert.
- ⚠️ The `query` multipart part **must** carry `;type=application/json` or the API returns HTTP 500.
- ⚠️ Range filters need a **full ISO datetime** — `{"gte":"2026-09-01"}` is silently ignored.
- ⚠️ Without `{"terms":{"language":["en"]}}` every record duplicates ~15×.
- ⚠️ `pageSize` caps at 100; deep paging hard-stops at 10,000. Slice by year.
- Status: `31094501` Forthcoming, `31094502` Open, `31094503` Closed.
- Below-threshold ex-ante publicity: `procedureType=47396214` + `cftEXARegistrationDeadline`, 326
  records in 2026, some as low as €65,000. **These publish as Forthcoming with `cftPlannedDate`, not
  `deadlineDate`** — filtering only on `deadlineDate` misses the entire low-value channel.
- `grantsTenders.json` (124 MB) is the only code→label dictionary but its **tender half is frozen at
  2024-07-03** — do not use it for tenders.
- `etendering.ted.europa.eu` now **301s into the portal**; it is not a separate system.
- ECB is absent entirely — it runs SAP Ariba. EIB stopped publishing there after 2024-12.

**Poland BZP** — `GET https://ezamowienia.gov.pl/mo-board/api/v1/notice`
No auth; the official Regulamin states no access application is required and the service is free.
**100% below-threshold** (`isTenderAmountBelowEU` true on 500/500 sampled) — a pure TED complement.
- `NoticeType` accepts only `ContractNotice` and `TenderResultNotice`.
- Carries `tenderId` as an OCDS `ocid`.
- ⚠️ **Heavy payload:** 500 records = 16.5 MB because `htmlBody` is inlined. Page smaller.
- ⚠️ The endpoint in the 2023 regulations PDF now serves the Angular app.
- Licence: free to use; a specific reuse licence is **not stated**.

**Ireland eTenders** — the only live route is an **undocumented keyless CSV export**:
```
POST https://www.etenders.gov.ie/epps/viewCFTSAction.do
mode=search&isFTS=true&type=cftFTS&isExport=true
&publicationFromDate=17/09/2026&publicationUntilDate=18/09/2026
```
Works from a cold session, no cookie. 5,596 rows for 2026 to date; `SUBMISSION_DEADLINE` on 98%;
**60% below threshold**.
- 🚩 **Licence gap** — eTenders publishes no terms and no reuse licence; `/epps/viewInfo.do?section=legal`
  returns an empty content area. Resolve with the OGP.
- The award-notice equivalent export is broken (header row only).
- The data.gov.ie bulk CSV is **CC-BY-4.0** but ~80 days stale; only 0.65% of rows have a future
  deadline. Intelligence, not discovery.
- ⚠️ Advertising thresholds are **€50,000** goods/services and **€200,000** works (Circular 05/2023).
  The commonly cited €25,000 is the *award-publication* threshold.

**Portugal dados.gov.pt** — `https://dados.gov.pt/api/1/datasets/` (udata, **not** CKAN — `/api/3/`
404s). Licence **`other-pd` (public domain)** — the most permissive in the study. Keyless, weekly,
~7-day lag. Anúncios carry `DataLimitePropostas`.
- ⚠️ Contracts JSON is inside ZIPs, not bare `.json`.
- 🚩 base.gov.pt runs AQTRONIX WebKnight: a modest burst returned **`HTTP/1.1 999 No Hacking`** then
  an IP block lasting 20+ minutes. Its terms also reserve the right to throttle automated searches
  09:00–18:00 and cap 2,000 records/session, and redirect bulk users to dados.gov.pt.
- DRE Parte L is an OutSystems SPA — every path returns an identical 2,346-byte shell. But the
  dados.gov.pt anúncios JSON already carries direct per-announcement DR PDF URLs.

**Austria USP + Kerndaten** —
`https://ausschreibungen.usp.gv.at/at.gv.bmdw.eproc-p/public/api/tenderlist` (undocumented JSON,
`fromdate`/`todate` verified, deadline in the list response; **detail pages incl. CPV are HTML only**).
Statutory KDQ feeds are **CC-BY 4.0** with a mandatory deadline field; XSDs at
`https://ausschreibungen.usp.gv.at/schema/latest/`.
- 🔴 **eForms mandatory nationally, including below threshold, from 2026-10-01** (BGBl I 8/2026).
  Parse both the legacy `KD_*` schema and eForms.
- ⚠️ USP is **not** a superset of TED — 3,169 USP notices 2026 YTD vs 4,382 Austrian TED contract
  notices. Both needed.
- ⚠️ USP Impressum asserts public use requires consent → use USP as a discovery index, fetch the
  record of record from the KDQ.
- ⚠️ KDQ server-side `?from=` is ignored; fetch the full index (~9 MB) and diff locally.
- 🚩 ANKÖ hosts exclude AI crawlers — source the same records from USP or BBG.
- BBG open data is **awards only, no deadlines** — useless for forward discovery.

**Switzerland Amtsblattportal / SHAB** — `https://www.amtsblattportal.ch/api/v1/publications`,
docs `/docs/api/`. No auth for published data. Genuinely cantonal below-threshold rubrics including
`OB-TI65` (explicitly outside the GATT/WTO agreement) and `OB-AR47` Freihändige Vergabe.
- ⚠️ **No CPV; deadlines are free text inside the HTML body.**
- Page size cap 3000 (docs say 2000 — stale).
- ⚠️ `robots.txt` is `Disallow: /` on both hosts while the API is documented as open. Use the API.

**US SAM.gov bulk extract** — the fix for the biggest coverage gap.
`https://falextracts.s3.amazonaws.com/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv`
Keyless, ~246 MB, refreshed daily, **sorted newest-first so a range request gets just the head**.
Carries `ResponseDeadLine`, NAICS, `ClassificationCode`, `SetASide`, `Active`, award fields.
~726 NAICS 5415* notices/month. No delta file — diff on `NoticeId`.
- ⚠️ The **Get Opportunities API is 10 requests/day** for non-federal users. Useless at that tier.
- ⚠️ SAM.gov terms prohibit "systematic access (electronic harvesting)" and "automated data
  gathering, web scraping tools". Reads as scoped to the website rather than the published extracts,
  but broad enough to warrant a legal read.
- FPDS-NG ATOM works but **GSA announced retirement "later in FY 2026"** — do not build on it.
- Free state solicitations: **Georgia** `POST https://ssl.doas.state.ga.us/gpr/eventSearch`,
  **Virginia eVA** Solr (⚠️ `robots.txt: Disallow: /`), **Delaware**
  `https://data.delaware.gov/resource/2hnj-zwix.json`. Texas, Pennsylvania, Maryland all
  `Disallow: /`; NY NYSCR expressly prohibits copying.

### Blocked, and why

**PLACE (France)** — `https://www.marches-publics.gouv.fr` · RSS + `/api/v2/consultations`, no auth,
45% of consultations below threshold. Technically excellent.
🚩 Conditions of use: *"toute reprise totale ou partielle est interdite sans l'autorisation expresse
et écrite du directeur de la publication."*
🚩 Also a **rolling window, not an archive** — a 2020–2022 query returns 16 records against 2,236
live. Miss a poll and that history is gone permanently.
- One adapter covers five Atexo "LOCAL TRUST MPE" platforms with identical endpoints: PLACE,
  Maximilien, Mégalis Bretagne, Demat-AMPA and Luxembourg's PMP. Cursor
  `dateMiseEnLigneCalcule[after]`. On PLACE the API returns the buyer only as an unresolvable
  reference (`/api/v2/referentiels/*` → 401 JWT) while the RSS denormalises `Organisme_nom` —
  they join on the RSS link's `?id=N` ↔ API `id`.

**Bulletin des Adjudications (Belgium)** — the only free route to Belgian below-threshold notices,
and the gap is large. Two independent measurements disagree: **1,475** and **2,947** BDA notices
against **1,142 in TED (verified)** for the same September window. Direction is clear, magnitude is
not.
🚩 BOSA asserts IP over "fichiers de données" and grants no reuse.
🚩 **Security:** the search API needs a bearer token minted from a Keycloak **client secret BOSA
publishes in plaintext in the site's own JavaScript** (`env.config.js`, realm `supplier`, client
`frontend-public`). Using a credential exposed by a misconfiguration is not sanctioned access and it
rotates without notice. **No token or secret was recorded in this repository.** Ask BOSA for a
supported route.
- Also requires a `BelGov-Trace-Id` header that must be a valid v4 UUID.
- Serves raw eForms UBL XML itself via `versions[].notice.xmlContent` on
  `/api/dos/publication-workspaces/{id}` — SDK 1.13.
- ⚠️ Undocumented throttle: ~13 rapid POSTs → 403 on everything; ~2 s spacing restores 200s.
- ⚠️ Platform release **2 October 2026** — expect breakage.
- Belgium has **no national OCDS**; data.gov.be carries no notices (only retrospective Brussels
  award inventories, CC0, useful for supplier history).

**PMP (Luxembourg)** — `https://pmp.b2g.etat.lu/api/v2/consultations`. No auth, ~30% below-threshold,
deadline and CPV on essentially every record, **full 12,492-record backfill in ~13 requests**, and a
real archive unlike PLACE.
🚩 Site terms: any copy requires MMTP authorisation.
- ⚠️ No award/cancellation lifecycle (`typeDecision` null throughout).
- ⚠️ **Test records with sentinel deadlines of 2050 and 2999 are in the corpus** — filter them.
- ⚠️ `order[...]` is silently ignored; use the date filter as cursor. All sibling endpoints 401.

**Sweden** — 🚩 **no free national source exists, structurally.** Under Lagen (2019:668) notices are
advertised in privately-operated *registered annonsdatabaser*; Konkurrensverket is only the registry
authority. All five operators are commercial: e-Avrop (Antirio AB), KommersAnnons.se (Antirio System
AB), Mercell Annonsdatabas, Konstpool, Clira. Upphandlingsmyndigheten publishes annual aggregate
statistics only — no notices, no deadlines.

**OpenTender** (opentender.eu) — 🚩 **CC BY-NC-SA 4.0**, non-commercial, and frozen at end-2024 for
every country checked. Recorded as unusable so nobody adds it later.

### Uncertain but usable

**Norway Doffin** — `POST https://api.doffin.no/webclient/api/v2/search-api/search`. No auth. Filters
nest under `facets` as `{checkedItems:[...]}`. **`sentToTed`** boolean gives the threshold side.
⚠️ `numHitsAccessible` caps at **1,000/query** — slice by date. **Licence unknown.**

**Italy ANAC Pubblicità Legale** — `https://pubblicitalegale.anticorruzione.it/api/v0/avvisi`
No auth. 70,526 notices/30 days all types; 1,856 open calls with `codiceScheda=2,4`.
⚠️ **CPV is Italian free text with no numeric code.** No server-side CPV or keyword filter — pull by
date, filter locally. **No published terms → licence unknown.**
- ANAC OCDS bulk is ~6 months stale **and** has a licence conflict: CKAN says CC-BY-4.0, the data
  file declares CC-BY-**SA**-4.0.
- PCP/BDNCP is **PDND-gated to public bodies** — not available to a private vendor.

**Finland Hilma** — `https://api.hankintailmoitukset.fi`, docs at
`github.com/Hankintailmoitukset/hilma-api`. Free self-service subscription key. Uniquely includes
**procurement plans** (`isPlan`). See §5 for the terms that constrain AI use.

**Iceland** — `utbodsvefur.is` is WordPress. `/feed/` and `/wp-json/wp/v2/posts` are keyless but
return only title, date and link; `content` and `meta` come back empty. Effectively HTML-only.

---

## 8. Commercial providers — published pricing

Researched because free coverage has one real hole (Sweden). Prices from vendor pricing pages during
the research pass, not independently re-verified.

| Provider | API? | Monthly | Annual | Redistribution |
| --- | --- | --- | --- | --- |
| TenderBase | No | £19–£41 | £225–£495 | UK/IE only |
| BidStats Standard | No | ~£29 | £350 | ✗ |
| BidStats Pro | No | ~£67 | £800 | ✗ |
| Tenders Direct Basic | CRM push | ~£113 | £1,359 ex-VAT | ✗ |
| GlobalTenders Regular | No | $137 | ~$1,644 | ✗ |
| Tenders Direct Core | CRM push | ~£170 | £2,044 ex-VAT | ✗ |
| GlobalTenders Premium | No | $334 | ~$4,008 | ✗ |
| **Open Opportunities API** | **Yes** | **~£417** | **£5,000** | **negotiable — invites resellers** |
| BidStats Insights | Yes | from ~£417 | from £5,000 | ✗ |
| Tussell API | Yes | ~£950 | £11,400 (G-Cloud rate card) | not stated |

Not published, sales call required: **Hubexo** (all brands), **BiP/Tracker**, **TendersInfo**
international, **Tender Impulse**, **Spend Network**, **TenderTiger** core.

**The decisive finding: every provider except one contractually forbids redistribution**, which is
exactly what Signal does. BiP: *"Reselling of BiP's information included in this Service is expressly
prohibited."* Tenders Direct: *"not entitled to… pass on any information supplied, to a third
party."* TendersInfo, GlobalTenders and BidStats carry equivalent clauses.

Meanwhile TED **explicitly permits commercial redistribution** and Find a Tender is **OGL v3.0**. The
free sources grant the right the paid ones withhold.

**Open Opportunities** (Ticon UK Ltd, co. no. 04962733, same group as Spend Network) is the only
realistic paid option: £5,000/yr flat, unlimited users, REST/JSON, 180+ countries, 1,050+ sources,
and the only vendor that openly says *"If you're an aggregator, reseller… we'll agree pricing."*
Portal seats separately: Solo £120/user/mo, Team £259/team/mo.

Two corrections that would mislead a buying decision: **Tenders Direct is owned by Proactis
(Proactis Tenders Limited, SC115090), not Hubexo**, and **"Opportunity Desk/DTS" does not exist** as
a tender service.

**Recommendation: £0 for now.** 57% of TED after #8; the cheapest route to 75% is three config lines
for Poland, Ireland and Portugal. BOAMP, TenderNed and udbud.dk are free, cleanly licensed, and each
worth more than anything on that table. Sweden is a genuine hole, but it is one market — and it is
unverified whether any paid provider actually carries Swedish *below-threshold* notices rather than
just reselling TED.

---

## 9. Compliance flags, consolidated

| Flag | Where | Implication |
| --- | --- | --- |
| Exposed client secret | Belgium BDA | Do not mint tokens from it. Request a sanctioned route. |
| `ai-input=no` for ClaudeBot/GPTBot | Austria ANKÖ | Route via USP or BBG instead |
| No content modification; no direct marketing | Finland Hilma | Quote, don't rewrite; no outbound from harvested contacts |
| 08:00 Europe/Zurich embargo + attribution + correction propagation | Switzerland simap | Implementation work, not boilerplate |
| Reproduction prohibited | France PLACE | Blocked without written AIFE clearance |
| Authorisation required for any copy | Luxembourg PMP | Blocked without MMTP clearance |
| IP claimed over data files, no reuse grant | Belgium BDA | Legal sign-off before republishing |
| No terms, no licence published | Ireland eTenders | Resolve with the OGP |
| CC BY-**NC**-SA | OpenTender (all countries) | Unusable commercially |
| Anti-harvesting wording | US SAM.gov | Legal read before automating |
| `Disallow: /` vs documented open API | CH Amtsblattportal, SHAB | Use the API, never crawl |
| `Disallow: /` | US Virginia eVA, Texas, Pennsylvania, Maryland | Avoid |
| Copying expressly prohibited | US NY NYSCR | Avoid |
| WAF IP-blocks on modest bursts | Portugal base.gov.pt | Use dados.gov.pt |
| CC-BY vs CC-BY-SA conflict | Italy ANAC OCDS | Resolve before commercial use |

---

## 10. Operational notes

- **Research agents wrote downloaded HTTP responses into the repository root** (`portal.html`,
  `main.js` at 4 MB, `ted.json`, `facet.json`, `odterms.html`, `nx.xml`, `ocp.out`). They were swept
  into a commit and removed. `.gitignore` cannot catch arbitrary filenames — instruct agents to use
  the system temp directory.
- `pytest` needs `--basetemp` pointed somewhere writable in this environment; the default
  `%TEMP%/pytest-of-*` raises `PermissionError` and produces 92 spurious errors.
- A full `export` with a changed `discovery_signature` replays the whole rejection store and
  reclassifies ~29,000 award notices — 15–20 minutes. Budget for it.
- `data/current.json` is the **pre-export** file and carries no translations;
  `app/public/data/current.json` is the published artefact with translations attached. Analysing the
  former silently produces wrong conclusions about the matcher — this caused one wrong finding this
  session.
- Flag PNGs in `app/public/assets/flags/` are referenced nowhere in the frontend. Minor cleanup.
