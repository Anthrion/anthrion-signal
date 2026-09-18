# Free procurement sources for the European market expansion — 18 September 2026

Assessment of free, official, programmatically reachable notice sources for **France, Belgium,
Netherlands, Luxembourg, Austria and Switzerland**, against the bar `AGENTS.md` sets: interface,
reuse terms, lifecycle, deadline and supplier-access checks before anything is activated.

Every source below was reached and read during the assessment. Figures marked **(verified here)**
were re-queried directly against the live API while writing this document; the rest come from the
source's own documentation or from the research pass and are attributed as such. "Unknown" is used
in preference to a guess.

## What this document changes, and what it does not

**Changed:** France, Belgium, Netherlands, Luxembourg, Austria and Switzerland are now selectable
markets, served by the **existing** TED collector. No new collector is activated.

**Not changed:** every national source below is registered in `config/sources.yaml` as a disabled
placeholder. Three are recorded as unusable or blocked. Nothing here should be enabled without the
legal sign-off noted against it.

## Switzerland is in TED — the assumption to discard first

Switzerland is neither an EU nor an EEA member, so the natural assumption is that it is absent from
TED and needs a dedicated collector before it can be a market at all. That is wrong. Switzerland
publishes to TED under the 1999 EU–Switzerland procurement agreement (Decision 2002/309/EC,
Euratom, in force 2002-06-01), which extends the WTO GPA.

**703 Swiss notices between 1 and 18 September 2026 (verified here.)** Buyers returned are
unambiguously Swiss — SBB CFF FFS, Swissgrid, Flughafen Zürich, Kanton Zürich.

So Switzerland becomes a market by configuration, exactly like the other five. simap.ch is still
needed, but only for **below-threshold** work — the `invitation` and `direct` procedures that never
reach TED.

## What TED already gives these six markets

Notice volumes for 1–18 September 2026, `buyer-country` (verified here):

| Market | TED notices, 18 days |
| --- | --- |
| France | 4,284 |
| Netherlands | 1,363 |
| Belgium | 1,142 |
| Switzerland | 703 |
| Austria | 604 |
| Luxembourg | 125 |

≈ **8,200 notices per 18 days**, before the CPV gate and relevance filtering. For comparison the
whole current feed admits ~264 new published records a day. This expansion is not free in capacity
terms: it competes for the TED page budget, the keyword-lane rotation and the translation quota.
Watch `sources_succeeded` and the TED "catching up" message after enabling.

⚠️ `buyer-country` inflates Belgium and Luxembourg with EU institutions headquartered there. Use
`place-of-performance-country-lot` when measuring genuine national demand.

## The licence picture, which decides more than the interface does

This is the finding that matters most. Interface quality and legal reusability are almost inverted
across these six countries.

| Source | Reuse licence | Verdict |
| --- | --- | --- |
| **TED** | Commission Decision 2011/833/EU — freely reusable, commercial or not. Metadata CC0 1.0 | ✅ Unambiguous |
| **BOAMP** (FR) | Licence Ouverte / Etalab | ✅ Unambiguous |
| **DECP** daily drops (FR) | Licence Ouverte v2.0 | ✅ Unambiguous |
| **TenderNed** (NL) | CC0 1.0, declared in the OpenAPI spec | ✅ Unambiguous |
| **simap.ch** (CH) | API GTC §4 **expressly permits** commercial reuse and redistribution | ✅ With three obligations, below |
| **Austrian Kerndaten** | CC-BY 4.0 (45 of 46 audited) | ✅ With attribution |
| **Amtsblattportal / SHAB** (CH) | "freely accessible for anyone to use"; no licence tag | ⚠️ No explicit grant |
| **PLACE** (FR) | Conditions of use prohibit *"toute reprise totale ou partielle"* without written authorisation | 🚩 Blocked |
| **BDA** (BE) | BOSA claims IP over "fichiers de données"; no reuse grant | 🚩 Blocked |
| **PMP** (LU) | Any copy requires MMTP authorisation | 🚩 Blocked |
| **OpenTender** (AT/BE/CH/LU) | CC BY-**NC**-SA 4.0 | 🚩 Non-commercial — unusable, and frozen at 2024 |

The three best *national* interfaces in this set — PLACE, BDA and PMP — are the three that cannot be
redistributed without clearance. That is the central constraint of this expansion.

## Per-country findings

### France

**BOAMP is the one to build.** Licence Ouverte, no authentication, a documented 2,000,000
requests/day allowance, and roughly **35,600 below-EU-threshold notices a year** that TED never
carries. Deadlines are populated on ~97% of tender notices. Lifecycle chains through
`contractfolderid`, so an award or cancellation can retire the original notice — which is what this
pipeline's dedupe already expects.

- Endpoint: `https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records`
- Use **v2.1**; v2.0 returns a deprecation header, and data.gouv.fr's own dataservice entry still
  points at the deprecated version.
- Use `/exports/json` rather than `/records` for bulk: `/records` caps `limit` at 100 and rejects
  `offset+limit > 10000`, while one `/exports/json` call returned a whole month.
- CPV is not a top-level field — it sits inside the `donnees` blob, but
  `where=search(donnees,"45000000")` filters server-side.
- ⚠️ `api.dila.fr` and `api.dila.gouv.fr` **do not exist**; both fail DNS. Any documentation
  pointing there is stale.
- ⚠️ `robots.txt` carries a stock `Disallow: /api/`, while the same dataset is published as an
  official open API on data.gouv.fr under an open licence. A judgement call, flagged not resolved.

**A coverage ceiling no engineering fixes.** Below €60,000 French buyers need not publish at all;
between €90,000 and the EU threshold they may choose BOAMP *or* a newspaper. BOAMP is therefore
structurally non-exhaustive in exactly the band where below-threshold work lives, and every
aggregator that does cover all of France is paid.

**PLACE is excellent and unusable.** RSS plus a JSON-LD API, 45% of its consultations below
threshold — and conditions of use that forbid reproduction without written authorisation. It is
also a rolling window, not an archive: a 2020–2022 query returns 16 records against 2,236 live, so
history is lost permanently if polling lapses.

**DECP is award data, not opportunities.** It has no submission deadline field — it is the contract
register, published after award. Useful for incumbent and competitor intelligence only. The AIFE
daily drops (~190 KB/day) are the incremental route; `decp-v3-marches-valides` on
data.economie.gouv.fr is superseded, with content stopping in 2023 behind current-looking metadata.

### Belgium — the largest below-threshold gap, and the hardest to access legally

Belgium has **no national OCDS publication**, and data.gov.be carries no live notices — only
retrospective Brussels award inventories (CC0, useful for buyer/supplier history, useless for
discovery).

The Bulletin des Adjudications is the only free route to Belgian below-threshold notices, and the
gap it fills is large. Two independent measurements of the same September window disagree on the
magnitude — 1,475 and 2,947 BDA notices against **1,142 in TED (verified here)** — so the multiple
is somewhere between roughly 1.3× and 2.6×, and is not settled here. What both agree on is
direction: the E-series below-threshold subtypes are essentially absent from TED while making up a
substantial share of BDA volume.

🚩 **Two blockers, one of them a security matter.**

1. BOSA asserts intellectual property over the site's data files and grants no reuse licence.
2. The search API requires a bearer token minted from a Keycloak **client secret that BOSA has
   published in plaintext in the site's own JavaScript**. Using a credential exposed by a
   misconfiguration is not sanctioned access, it will rotate without notice, and it should not go
   near this pipeline. **No token or secret has been recorded in this repository.** The supported
   path is to ask BOSA for a sanctioned route.

A platform release is scheduled for 2 October 2026; expect breakage in anything built against the
current shape. The undocumented throttle is real — rapid bursts return 403, ~2 s spacing does not.

### Netherlands — the cleanest source in the set

**TenderNed PAPI.** CC0 1.0 declared in the official OpenAPI spec, no authentication, a date-range
cursor, and deadline plus CPV on the records that matter. Roughly **20,500 below-threshold notices**
of a 145,000 corpus. Terms of use carry no anti-automation clause and `robots.txt` does not disallow
the API path.

- `https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties`
- ⚠️ Unknown query parameters are **silently ignored** — always validate a filtered count against an
  unfiltered baseline, or you will believe a filter works when it does not.
- Hard caps `size ≤ 100`, `page ≤ 99` ⇒ 10,000 records per query. Fine at ~110 notices/day; a
  full-year slice does not fit.
- The XML API is waitlisted — *"nieuwe aanvragen … voorlopig niet verwerkt"*. Do not design around it.
- Below-threshold *open* procedures are mandatory on TenderNed; *onderhandse* (invited) procedures
  are not published anywhere.

### Luxembourg

**PMP** is the only machine-readable route to Luxembourg below-threshold notices, ~30% of its
volume, with deadline and CPV populated on essentially every record and a full backfill in about 13
requests. Unlike PLACE it is a real archive.

🚩 Blocked on terms: any copy requires MMTP authorisation. Also: no award or cancellation lifecycle
(`typeDecision` is null throughout), the endpoint is undocumented so it needs defensive version
pinning, and **test records with sentinel deadlines of 2050 and 2999 are present in the corpus** and
must be filtered.

data.public.lu contains **zero** tender notices despite a working API and a clean CC0 site licence.

### Austria — a regime change lands in under two weeks

🔴 **eForms becomes mandatory nationally, including below threshold, on 1 October 2026**
(Vergaberechtsgesetz 2026, BGBl I 8/2026). Any Austrian collector must parse both the legacy `KD_*`
schema and eForms from the outset. The USP portal already marks its own BVergG-2018 documentation
*"ab 01.10.2026 veraltet"*.

**USP Ausschreibungssuche** is the national aggregator and the only Austrian endpoint with
server-side date filtering and deadlines in the list response. Detail pages — including CPV — are
HTML only. Its Impressum asserts that public use of the information requires consent, so it is best
used as a discovery index with the record of record fetched from the statutory **Kerndatenquellen**
feeds, which are CC-BY 4.0 and carry a mandatory deadline field.

⚠️ USP is **not** a superset of TED: 3,169 USP notices in 2026 against 4,382 Austrian contract
notices in TED. The two overlap; both are needed.

🚩 **An AI-crawler restriction that bears directly on the Best Fit curation work.** ANKÖ's hosts
(`ogd.ankoe.at`, `vergabeportal.at`) set `Content-Signal: ai-train=no, ai-input=no` and
`Disallow: /` for ClaudeBot, anthropic-ai, GPTBot and CCBot. `ai-input=no` objects to
inference-time use, which is precisely what an LLM curation step does. The same records are
available from USP or BBG under CC-BY 4.0 — route around it rather than through it.

Austria's commercial portals — auftrag.at (ex-Lieferanzeiger, €864/yr), ANKÖ vergabeportal
(€450/yr), ausschreibung.at — all publish their statutory Kerndaten feed free. Only the document
bodies sit behind the paywall.

### Switzerland

**simap.ch** is the only real route to Swiss below-threshold work, and it is well built: an
OpenAPI 3.0.3 spec, structured deadlines, CPV, lifecycle including revocation and abandonment, a
`correctionDiffKeys` field naming which fields changed, and a **`publicationTed` boolean that gives
deterministic TED deduplication** rather than fuzzy matching.

Its API terms expressly permit commercial reuse and redistribution, which is rare in this set, but
attach three obligations that are implementation work, not boilerplate:

1. Data displayed unaltered and visually distinct, carrying the notice
   *«Dies ist keine amtliche Veröffentlichung. Massgebend sind die auf der Plattform
   www.simap.ch veröffentlichten Daten.»*
2. **An embargo: nothing surfaced before 08:00 Europe/Zurich on publication day.**
3. Corrections propagated.

⚠️ The general site GTC §9.1 forbids reproduction without written consent; the API GTC §2 makes
itself *lex specialis*. Consume via the API, never by scraping HTML — and get the conflict signed
off.
⚠️ Operationally, simap sits behind a WAF that redirects to `/cookie-check` after ~15 rapid
requests. A persistent cookie jar and redirect following are required.

**Amtsblattportal / SHAB** carries genuinely cantonal below-threshold notices that never reach
simap, including rubrics explicitly outside the GATT/WTO agreement. No authentication. But no CPV,
and deadlines are free text inside the HTML body. ⚠️ `robots.txt` is `Disallow: /` on both hosts
while the API is documented as open — use the documented API only.

## The existing markets, assessed in the same pass

TED already serves Italy, the Nordics and Greece above threshold. What follows is what is available
below it.

| Market | Best free national source | Licence | Verdict |
| --- | --- | --- | --- |
| **Denmark** | `udbud.dk` — published OpenAPI, eForms-native, keyless | Reproduction permitted with attribution; KFST explicitly permits commercial tender intermediaries | ✅ **Best free source found anywhere in this study** |
| **Greece** | KIMDIS open data, `cerpp.eprocurement.gov.gr` | **CC BY 4.0**, explicitly | ✅ Registration mandatory from €1,000, so coverage is deep |
| **Norway** | Doffin `api.doffin.no` — keyless, CPV facet, `sentToTed` threshold flag | Unknown | ⚠️ Good interface, unstated licence |
| **Italy** | ANAC `pubblicitalegale.anticorruzione.it` — keyless, very high below-threshold volume | Unknown, undocumented | ⚠️ No CPV codes, Italian free text only |
| **Finland** | Hilma — free key, includes procurement **plans** | Contract, not a licence — see below | 🚩 Terms constrain this product |
| **Sweden** | **None exists** | — | 🚩 Structural, see below |
| **Iceland** | `utbodsvefur.is` — WordPress RSS, titles only | Unknown | ⚠️ Effectively HTML-only |

**Denmark is the standout.** `udbud.dk` publishes its OpenAPI spec, needs no key, returns notices in
Danish *and* English, carries CPV codes and deadline arrays, exposes forward-pipeline notice types
(`FORVENTET_INDKOEB`, `MARKEDSDIALOGER`), and — uniquely here — offers a **true changed-since
cursor** on index time rather than publication date. The authority states plainly that it permits
private companies whose business is conveying tenders to retrieve the data commercially. If a second
collector gets built after BOAMP, this is it.

**Sweden has no free national source, and this is structural rather than an oversight.** Under
Lagen (2019:668) notices are advertised in privately-operated *registered annonsdatabaser*.
Konkurrensverket is only the registry authority. All five registered operators — e-Avrop,
KommersAnnons, Mercell, Konstpool, Clira — are commercial. Upphandlingsmyndigheten publishes only
annual aggregate statistics: no individual notices, no deadlines. **Swedish below-threshold coverage
requires a paid feed or nothing.** Worth knowing before anyone spends a week looking.

### Two sources whose terms bite the Best Fit curation work specifically

This is the cross-cutting finding, and it is easy to miss because it appears in two unrelated
countries.

1. **Finland — Hilma.** The Käyttöehdot permit commercial use for exactly this kind of value-added
   service, but also state that **the user may not modify the substantive content of the data**, and
   that personal data must not be used for other purposes, **expressly including direct marketing**.
   An AI step that rewrites or summarises notice text is a content modification, and outbound
   prospecting from harvested buyer contacts is direct marketing. This is a contract, not an open
   licence.
2. **Austria — ANKÖ.** `Content-Signal: ai-input=no` plus `Disallow: /` for ClaudeBot, anthropic-ai
   and GPTBot, as noted above.

Neither blocks the product. Both mean the curated view should **quote** source text rather than
rewrite it, and should link to the notice rather than reproduce it — which is what the grounded-quote
design already does, for independent reasons. Worth confirming with whoever signs off data terms.

### EU institutions

The Funding & Tenders Portal SEDIA Search API is keyless, officially documented, current, includes
below-threshold ex-ante publicity, and is reusable under Commission Decision 2011/833/EU. `type=0`
is calls for tenders — `type=1` is grant topics, which is the natural way to get this backwards.
`etendering.ted.europa.eu` no longer exists as a separate system; it now redirects into the portal.

IT consulting volume is real: CPV 72000000 returns 831 all-time and 54 currently open, with
individual contracts in the millions of euro. The ECB is absent from the portal entirely — it runs
its own tendering on SAP Ariba, with no open API.

## Recommended order

1. **Nothing.** The six markets are live through TED with this change. Measure real volume and
   relevance for a few weeks before adding collectors.
2. **BOAMP (France)** — clean licence, no auth, largest below-threshold gain, lifecycle linkage.
   The single highest-value collector available.
3. **TenderNed (Netherlands)** — CC0, no auth, cleanest interface of all of them.
4. **simap.ch (Switzerland)** — only route to Swiss below-threshold work; budget for the embargo,
   attribution and correction obligations.
5. **USP + Kerndaten (Austria)** — after the 1 October eForms cutover settles, not before.
6. **Belgium** — only once BOSA grants a sanctioned access route and the reuse question is
   answered. Highest value, highest risk.
7. **Luxembourg** — only with written MMTP clearance.

## Do not build

- **OpenTender** (opentender.eu) — CC BY-NC-SA 4.0 blocks commercial use, and coverage is frozen at
  end-2024 for every country here.
- **PLACE** as a redistribution source — terms explicitly prohibit it.
- **`decp-v3-marches-valides`** — superseded; data stops in 2023 behind current metadata.
- **data.public.lu**, **data.gov.be** — no tender notices.
- **Belgian regional portals** — no regional notice system exists; Wallonia's portal has no notices.
- **TenderNed XML API** — waitlisted indefinitely.
- **beschaffung.admin.ch** — retired, redirects to BBL.
- **BBG open data (Austria)** — awards only, no deadlines; useless for forward discovery.

## Open questions

Deliberately unresolved rather than guessed: TenderNed rate limits; TenderKalender licence;
data.gv.at portal-level terms; documented rate limits for any Austrian or Swiss endpoint; the
OffeneVergaben.at data licence; archiv.simap.ch licence; whether Austrian below-threshold notices
start appearing in TED after 1 October 2026; and the true size of the Belgian below-threshold gap,
where two measurements disagree by roughly a factor of two.
