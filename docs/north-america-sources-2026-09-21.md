# North American sources and the remaining European gaps — 21 September 2026

Continues [`free-apis-market-expansion-2026-09-18.md`](free-apis-market-expansion-2026-09-18.md) and
[`research-handover-2026-09-18.md`](research-handover-2026-09-18.md), which stopped before Canada, the
United States, and two open questions.

**This document adds no collector and enables no source.** It records what was verified so the next
build decisions rest on measurements rather than assumptions. Every endpoint quoted was called; where
a claim could not be verified it says so.

## Deduplication against the market-expansion build

Research began before the market-expansion work landed on `main`. Four of its intended
recommendations are already shipped and are **not** repeated as proposals:

| Researched as a proposal | Already on `main` |
| --- | --- |
| Build a CanadaBuys collector | `canada_buys` collector, `CA` market enabled |
| Build a North America tab | `NORTHAMERICA` group (`US` + `CA`) in `app/src/lib.ts` |
| Close the US federal gap with the keyless S3 extract | `sam_csv` collector — **already uses that exact URL** |
| Add Poland, Ireland and Portugal as markets | all three enabled, plus EE, LV, LT, CZ, RO |

The Swedish registry note was also corrected independently and now cites the same Konkurrensverket
decision this research reached. Nothing here needs changing.

What remains is additive: a measured relevance defect that affects both North American markets, the
provincial Canadian assessment, national-source routes for the newly enabled European markets, and
the licence and robots position for each.

## 1. The finding that matters most: relevance has no classification signal outside Europe

The discovery gate scores a CPV match at +12, which is exactly `minimum_candidate_score`. Outside
Europe that contribution is always zero, measured against the live dataset:

| Market | Live signals | carrying `cpv_codes` |
| --- | --- | --- |
| Canada | 16 | **0** |
| United States | 244 (186 from SAM) | **0** |

`NAICS` appears nowhere in `discovery.py` or `capability_matching.py`. Both markets therefore rest
entirely on text evidence — visible in `prefilter_matches`, which shows keyword hits like
`'system integration'`, `'middleware'`, `'artificial intelligence'` and nothing else.

That would be acceptable if the source data lacked codes. It does not:

- **CanadaBuys** publishes `unspsc` on **84.7%** of open notices (column 15 of the CSV the collector
  already parses). `canada_buys.py` references neither `unspsc` nor `gsin`.
- **SAM.gov** publishes `NaicsCode` and `ClassificationCode` (PSC) on every row.
  `sam_opportunities.py` reads both, but emits them as a display label —
  `categories=[f"NAICS {row['NaicsCode']}"]` — which no scoring rule consumes.

And the text-only fallback is measurably weak:

- On Canadian notices, a keyword gate recovered 59 records carrying no UNSPSC at all, but used alone
  it over-fired to **25%** of the file and missed **42%** of UNSPSC-confirmed IT.
- On US notices the vocabulary pack is worse: **`BUSINESS_OBJECTS` matched 46 of 463 open
  software/IT leads — 10% recall — and only 3 in the title.** A US-flavoured term list reached 31%.
  Without an `en_US` vocabulary pass the North America tab surfaces roughly 46 leads where 463 exist.

### 1.1 The obvious fix is a trap

Mapping native codes into `cpv_codes` would be actively harmful, because the prefix rules carry CPV
semantics and the schemes are **inverted**, not merely different:

| Prefix | CPV | UNSPSC | US FSC/PSC |
| --- | --- | --- | --- |
| `48` | software packages | Service Industry Machinery | **Valves** (1,156 notices) |
| `72` | IT services | Building & Facility Construction and Maintenance | — |

Pulling the 109 Canadian notices whose UNSPSC begins `72` returns gates, barriers, detention-facility
construction, electrical equipment, building maintenance and office furniture. Not one is IT. The
same reuse on US data would admit valves as software.

### 1.2 What to do instead — native selection per scheme

No crosswalk is needed; each scheme is selected in its own terms.

**Canada / Quebec / Alberta — UNSPSC** (one adapter serves all three, because all three use it):

- segment **43** — Information Technology Broadcasting and Telecommunications (`4323` Software,
  `4319` Communications Devices)
- family **8111** — Computer services: software maintenance and support, data services, application
  programming, systems integration
- family **8116** — IT Service Delivery, including cloud SaaS. Easy to miss, worth ~31% extra recall.
- **never select at segment-81 level** — `8110` is architectural, civil, marine and naval
  engineering; `8114` is mixed, so filter at class level only.

Measured yield: 52 of 898 open Canadian notices carry `4323` or `8111` (5.8%); 144 carry a segment
`43` or `81` code (16.0%).

**United States — NAICS leading, PSC supplementing:**

- NAICS tier 1: **541511, 541512, 541513, 541519, 518210, 513210**, and **511210** (a 2017 code still
  actively submitted)
- PSC: the only live IT families are **`7A`–`7J`** (products) and **`DA`–`DK`** (services). All `70xx`
  and `D3xx` codes were retired 2020-10-29 and still appear in the data.
- PSC adds 824 records that NAICS alone misses, but is applied noisily (`DK10` on body-worn cameras),
  so **NAICS must lead**.

Measured yield: **5,397 of 81,512 rows (6.6%)**.

This is a change to relevance scoring, which `AGENTS.md` places on its own review path, and the
market-expansion build is actively working in that area. It is therefore documented here rather than
implemented, and is offered as a separate change with tests.

## 2. United States — the federal route is already the right one

`sam_csv` already fetches
`s3.amazonaws.com/falextracts/Contract Opportunities/datagov/ContractOpportunitiesFullCSV.csv`.
Independent verification confirms that choice was correct and worth recording, because the
alternatives are all worse:

- **236,153,815 bytes, HTTP 200, default User-Agent, no key, no account, no Referer**, no rate
  limiting across six rapid calls. Rebuilt nightly ~03:30 UTC.
- **47 columns with full descriptions inline** — 69,337 of 81,512 rows carry description text. The
  documented v2 API returns `description` as a *link requiring a second keyed call per record*.
- **Rows are strictly date-descending — 0 violations across all 81,512 rows.** Last 3 days = 4.0 MiB,
  last 7 days = 23.4 MiB, so a daily ranged GET replaces a 225 MB pull.
- **`If-None-Match` → 304 verified.** `If-Modified-Since` is *ignored* — use the ETag.
- Per-fiscal-year backfill files exist keylessly with an identical 47-column schema (FY2026 = 920 MB).
- It is the **sanctioned** path: SAM's terms name `open.gsa.gov/api/` and `sam.gov/data-services` as
  the two automated-access routes and prohibit gathering outside them.

### 2.1 The documented API is a dead end

`api.sam.gov/opportunities/v2/search` returned an **empty-bodied 404 to every request** — no key, bad
key, `X-Api-Key` header, browser UA, `/prod/` variant, and via a second HTTP client. The TLS peer is
genuinely GSA (DigiCert EV, `CN=api.sam.gov`, verify ok), so this is the real gateway rather than a
proxy artefact. **Whether a valid key changes that is unverified** — no registration was performed.

Its own documentation gives no rate-limit numbers; sibling SAM docs state *"Rate limit for Non-Federal
User is 10 requests/day"* against *"Federal User is 1000 requests/day"*. Ten requests a day cannot
serve a pipeline, which is why the extract is the correct choice.

A keyless incremental endpoint (`sam.gov/api/prod/sgs/v1/search`) does exist and works well —
`modified_date.from`, `size=1000`, `naics=` filtering, 1,101 notices/day, plus a keyless detail route
with attachments. **It sits outside SAM's enumerated access paths, so it is reported and not
recommended.** No RSS or ATOM exists; rss-shaped paths return 200 SPA shells.

### 2.2 `Active = Yes` is meaningless — and the shipped note already says so

All 81,512 rows carry `Active = Yes`. **1,586 of 2,241** lead-type IT notices have a deadline that has
already passed, because `ArchiveType: auto15` keeps a notice live for 15 days past its deadline.

The honest figures: **~463 open software/IT opportunities at any moment, ~356 after set-asides**, from
~1,040 new notices a day.

The `sam` source note on `main` already states *"Listed status does not establish an open response
window"*, which covers this correctly. Worth keeping when that note is next edited.

### 2.3 Set-asides close a quarter of the open leads

**23% of open IT leads are legally closed** to a firm without the relevant status — small business,
SDVOSB, WOSB, 8(a) — and 37% file-wide. `sam_opportunities.py` already surfaces this as
`eligibility_text = "Set-aside: …"`, which is the right treatment: `AGENTS.md` forbids inventing
eligibility, so it must be shown rather than inferred.

### 2.4 Awards-only, and one genuine blind spot

**USAspending** is keyless but carries no solicitations — verified, zero solicitation endpoints. Worth
wiring for incumbency intelligence only (largest IT award in a three-month window: Oracle Health,
$2.12bn). **FPDS-NG** is also awards-only and hard-capped at 10 records per page — 38,490 records for
three days would need 3,849 requests.

**GSA eBuy is a real blind spot.** It is login-gated and many Schedule RFQs never reach SAM at all.
There is no free route.

### 2.5 States — build none

Only **Texas ESBD** (POST JSON, 62,686 records) and **Virginia eVA** (open Solr, 291,832 documents,
with a real `lastupdatedate` cursor) have good keyless feeds — and both serve
**`robots.txt: Disallow: /`**, independently re-verified, as does Pennsylvania eMarketplace. New York
prohibits *"the copying of any protected materials … without written permission"* **and** inbound
linking. Florida's bid system has a broken TLS certificate (`CN=myflorida.com`, no SAN).
Washington's documented host is NXDOMAIN.

The productive step is not engineering: an owner email to Texas CPA and Virginia DGS requesting
written permission would unlock the two best state feeds in the country.

**Unverified:** Massachusetts, Georgia and California terms (403/503/403 respectively).

## 3. Mexico — exclude it, on licence grounds

North America should mean **US + Canada**, which is what the shipped `NORTHAMERICA` group already
does. Mexico was assessed and fails on licence before any engineering question arises.

The data is real. CompraNet's old hosts are NXDOMAIN; the live platform is ComprasMX on
`buengobierno.gob.mx`, and an undocumented keyless bulk CSV was verified —
`Expedientes_ComprasMX_2026.csv`, **200, 81,956,364 bytes, 73,118 rows**, latin-1, with **692 open
notices** carrying future bid-opening dates, clarification-meeting dates, buyer emails and deep links.

But `gob.mx/terminos` — verified independently, twice — authorises download *"solamente para su uso
personal y no para un uso comercial"* and states the user *"no deberá modificar, reproducir o mostrar
pública o comercialmente los materiales, ni podrá distribuir o utilizarlos con algún propósito público
o comercial"*. "Libre Uso MX" is retired (404). For a product that publishes a public dataset, that
is decisive.

It would also lose on the merits: only **~56 of 73,118 rows are software/IT**; descriptions have a
**median of 137 characters** against SAM's 1,974, which is too thin for `addressable_delivery()`;
there is **no ETag, no `Last-Modified`, and `Range` is ignored** (78 MiB per poll), and `HEAD` returns
403. CUCoP is a fourth classification scheme to model. Federal OCDS is abandoned — the only national
republisher is flagged "no longer updated" with data ending March 2022 and NXDOMAIN API hosts.
datos.gob.mx is alive (1,751 datasets) but carries no tender-notice dataset and disallows `/api/`.

## 4. Canada federal — verification of the shipped route, and its ceiling

`canada_buys` fetches the right file. Recording what was measured, because several properties are not
obvious and two of them are load-bearing.

| File | Bytes | Records |
| --- | --- | --- |
| `newTenderNotice-nouvelAvisAppelOffres.csv` | 17,542 | 3 (that day's new notices) |
| `openTenderNotice-ouvertAvisAppelOffres.csv` | 6,450,455 | **898** |
| `2026-2027-TenderNotice-AvisAppelOffres.csv` | 17,549,777 | **2,911** |
| `tenderNoticeComplete-avisAppelOffresComplet.csv` | 183,077,895 | complete, 2022-08-08 → |
| `2009-2022-tenderNoticeHistorical-…csv` | 558,413,231 | legacy archive |

**The open and fiscal-year files are disjoint.** Measured intersection on `referenceNumber` is
**exactly 0**; the union is 3,809. Neither file is the whole picture. This produces a convincing false
alarm: the FY file holds only 2 records from the last 7 days against 151 in `openTenderNotice`, which
looks like stale data and is not.

Refresh is documented — the new-notices file *"will be updated every 2 hours each day, from 6:15 am
until 10:15 pm (UTC-0500)"*, everything else *"once daily, between 7:00 am and 8:30 am (UTC-0500)"*.
Conditional GET works (`If-Modified-Since` and `If-None-Match` both **304**) and `Range` returns
**206**. One documented latency caveat matters for a discovery product: *"New notices that are
published through PSPC's SAP Ariba system will only be included the following day."*

**Bilingual in the same row**, on all 67 columns — measured **898/898** French titles and **884/898**
French descriptions. Canada federal needs no translation budget, unlike Quebec.

**Volume** (IT-relevant = UNSPSC segment 43, or family 8111/8116):

| Window to 2026-09-21 | Notices | IT-relevant | Share |
| --- | --- | --- | --- |
| 7 days | 151 | 9 | 6.0% |
| 21 days | 381 | 31 | 8.1% |
| 21 days, open ∪ FY deduped | 438 | 38 | 8.7% |
| FY2026-27 (1 Apr – 15 Sep) | 2,911 | 216 | 7.4% |

**≈125–145 federal notices a week, ~10–13 relevant.** Federal Canada is a breadth play, not a volume
driver.

### 4.1 Licence, and the robots decision taken

`license_id: ca-ogl-lgo` — **Open Government Licence – Canada 2.0**, expressly permitting commercial
redistribution: a *"worldwide, royalty-free, perpetual, non-exclusive licence to use the Information,
including for commercial purposes"*. Attribution required.

canada.ca's general terms say *"You may not reproduce materials on this site … for the purposes of
commercial redistribution without prior written permission"*, but that is qualified by "Unless
otherwise specified", and the open-data files **are** otherwise specified. The files are commercially
reusable; the website is not.

**`canadabuys.canada.ca/robots.txt` ends with `User-agent: *` / `Disallow: /`.** So the openly
licensed files sit on a host that tells every automated client to stay out, while `open.canada.ca` —
where those files are advertised — does not disallow `/api/`.

**Decision taken by the repository owner, 21 September 2026: use the open-data files.** The reasoning
recorded for future reviewers is that fetching a named, documented open-data distribution is a data
download governed by the OGL grant, not a crawl of the website. It does **not** extend to sources with
no reuse grant, nor to sources that name Anthropic agents specifically (§6).

### 4.2 An undocumented API exists and should not be used

CanadaBuys runs Drupal and exposes an unauthenticated JSON:API: `/en/jsonapi` returns 268 resource
types, a genuine cursor works via `>=` on `field_tender_publication_date` with `links.next`, and it
exposes `field_tender_documents` — attachments, which the CSVs leave empty. It would fix the Ariba
lag and the missing amendment cursor at once.

It is recommended against: it is website content rather than an open-data distribution, it is
undocumented with no stability guarantee, and the site returns **403 to `python-urllib/3.11`** while
serving `curl` — user-agent blocking that was not spoofed. Worth asking PSPC for if a conversation
ever opens.

### 4.3 Federal data is federal only

Notices visible on the website — *Service Alberta and Red Tape Reduction*, an LHSC RFP, a hospital
surgical-tools notice — are **absent from all 3,809 CSV records**, while federal ones are present. The
words `Alberta`, `Hospital`, `Municipal`, `City of` and `University` appear nowhere in CSV buyer
names, and the documented scope is *"all Schedule I, Schedule II and Schedule III departments,
agencies, Crown corporations…"* — federal instruments.

**Provincial coverage cannot arrive as a by-product of the federal integration.** The size of the
federal-vs-total gap on CanadaBuys is **unverified**; measuring it required paginating past the
user-agent block.

### 4.4 Gotchas

1. **Every coded value carries a literal leading asterisk** — `*43230000`, `*N7030`. Its meaning is
   documented nowhere. `canada_buys.py` already handles this for `regions` via `lstrip("*")`; any new
   code path needs the same.
2. **Multi-value fields are newline-separated *inside* quoted CSV fields.** `wc -l` reports 58,416
   "lines" for 898 records. `unspsc` and `unspscDescription-eng` are parallel newline lists that must
   be zipped positionally, and their lengths are not guaranteed equal.
3. **Never construct blob filenames — resolve them from CKAN.**
   `openTenderNotice-appelOffresOuvert.csv` 404s; the real name is
   `openTenderNotice-ouvertAvisAppelOffres.csv`. The bilingual halves follow no inferable order.
4. **`referenceNumber` has three incompatible formats** from three upstream systems:
   `MX-443841357513` (MERX), `cb-544-27650487` (native), `WS5885557102-Doc5895002657` (Ariba).
   `solicitationNumber` is **not unique** — 885 unique across 898 records.
5. **`noticeURL` is empty for 474 of 898 (53%)** and otherwise points off-site — Ariba 266, MERX 101.
   **There is no stable CanadaBuys permalink in the data**, so for half of all notices there is no
   link to show a salesperson. A UX decision, not a parsing detail.
6. **Two of three federal hosts fail TLS, differently** — `donnees-data.tpsgc-pwgsc.gc.ca` gives
   "self signed certificate in certificate chain", `sosa.canadabuys.canada.ca` "unable to get local
   issuer certificate". Behaviour depends on the client's trust store. Do not repair with
   `verify=False`.
7. **`robots.txt` is served gzipped even without `Accept-Encoding`** — without `--compressed` you get
   binary and may conclude there is none.
8. **CKAN is the resolver, not a source.** `datastore_search` returns 404 — the DataStore is not
   enabled, so there is no row-level or SQL API. `package_search?q=tender+notice` returns count 8.
   robots.txt does not disallow `/api/`; `Crawl-delay: 20` applies.

There is **no production OCDS** federally — only `60f22648-…`, *"Archived, Pilot of the Open
Contracting Data Standard (250 contract records)"*, `frequency: not_planned`. No RSS or ATOM either;
seven candidate paths all 404 and the legacy buyandsell.gc.ca feeds did not carry over.

## 5. Canada provincial — one source worth building

Federal data is federal only, so each province is a separate build. Ten routes were assessed.

### 5.1 Quebec — SEAO is the best procurement source in Canada

Données Québec CKAN, dataset `d23b2e02-085d-43e5-9e6e-e1d558ebfdd5`. The weekly file is a **valid
OCDS 1.1 release package**, verified directly:

```
"version": "1.1",
"extensions": ["…/ocds_lots_extension/v1.1.5/extension.json"],
"publisher": {"name": "Secrétariat du Conseil du trésor"},
"license": "https://www.donneesquebec.ca/fr/licence/#cc-by"
```

**Licence CC-BY 4.0** — the licence page permits others to *"distribuer, remixer, arranger et adapter
votre œuvre, même à des fins commerciales"*. Commercial redistribution explicitly permitted with
attribution: the cleanest licence of any source in Canada, and better than the three best national
interfaces in Europe. No auth. `If-Modified-Since`/`If-None-Match` → **304**, `Range` → **206**.

Measured on 4,256 releases for 2026-09-14 → 20: `tender` (new notices) **294**, `tenderUpdate` 1,832,
`contract` 713, `tenderCancellation` 88. 1,160 releases `tender.status: "active"`, **740 with a close
date still in the future**. ~288 new open notices a week.

**Classification is UNSPSC and clean** — all 4,099 items carry `classification.scheme: "UNSPSC"` with
an 8-digit id (1,198 distinct in one week), alongside SEAO's own 52-value category code. This is why
the UNSPSC adapter in §1.2 is one piece of work rather than three: **federal Canada, Quebec and
Alberta all use UNSPSC.**

**The weekly files are deltas, not snapshots** — and the obvious reading is wrong. Two consecutive
weeks: 3,890 then 4,256 releases, but **ocid overlap only 554**. Of the prior week's active-and-open
tenders, **493 are absent from the latest file, 267 of them with a future close date** (verified:
`ocds-ec9k95-20116426` closing 2026-10-08, `…20144980` closing 2026-10-21, `…20153066` closing
2026-11-12). A file holds only what *changed* that week, each as a full-state release. A collector
must **accumulate weeklies, keep the latest release per `ocid` by `date`, and expire on
`tenderPeriod.endDate`.** Active tenders run a median 31 days, p90 61, max 226, so ~12 months of
weeklies is a safe working window (1.03 GB; all 308 weeklies are 4.15 GB).

SEAO fits **neither** existing collector: `ocds_monthly` is hardwired to the Scotland/Wales
`dateFrom`/`noticeType`/`outputType` shape against one URL, and `ocds_cursor` needs date params plus
cursor pagination. The saving is that `releases(package)` already parses OCDS, so only fetching and
delta-merging are new.

Costs, stated plainly: **French only** (`language: "fr"` on 4,256 of 4,256 — translation budget
required); **up to 7 days of latency** with no daily file, which may force scraping the fresh tail;
and **no description field** — `tender.title` plus UNSPSC codes, with only 46 of 4,256 carrying
`value`.

Gotchas: the short download path `/recherche/resource/<id>/download/<file>` **404s** — the working
form is `/recherche/dataset/<slug-or-uuid>/resource/<id>/download/<file>`, and the file's own `uri`
field gives the correct shape. **`release.id` changes on every republish** (551 of 554 overlapping
ocids) — dedupe on `ocid`. Files are **UTF-8 with BOM**. `datastore_active: false` everywhere, so no
server-side filtering. And **robots.txt disallows `/recherche/api/` and `/api/`** with
`Crawl-Delay: 10` while allowing resource downloads — so pin resource URLs and poll them with
`HEAD`/`If-Modified-Since` rather than calling `package_show` each run, which is also the cheaper
design. `seao.gouv.qc.ca` itself has no public API: `/avis-du-jour`, `/rss`, `/api` and
`/sitemap.xml` all return **200 with the same 2,337-byte SPA shell**, and the internal
`api.seao.gouv.qc.ca` is undocumented and unsanctioned. **Monthly-vs-weekly equivalence for backfill
is unverified.**

### 5.2 Saskatchewan — excellent data, no licence at all

`sasktenders.ca` has **no robots.txt** (404 at apex and www), no CAPTCHA, no auth, no rate limiting.
`GET /Search?statusId=&pageSize=200&pageNumber=N` returns **fully expanded records inline** — no
second request per tender.

Measured: **58,014 competitions** back to 11 June 2009 — Open **274**, **Awarded 23,201** with winning
vendor, city, dollar value and award date. Scope exceeds the province: City of Saskatoon, Regina,
University of Saskatchewan, school divisions. Agreement Type usefully encodes trade-agreement coverage
(NWPTA / CFTA / CETA / WTO-GPA). `pageSize` **silently clamps at 200** — 500 and 1000 both yield
exactly 200 unique GUIDs, and counts reconcile exactly (116 × 200 + 1 = 23,201). No changed-since
cursor; sort `opendate` descending and stop at the first known GUID.

**The blocker is an absence, not a prohibition.** `/Terms`, `/TermsOfUse` and `/Copyright` all 404.
The only legal page is `/Disclaimer`, substantively a warranty disclaimer: *"This website and all of
the information it contains is provided strictly 'as is' and without warranty of any kind."* Grepping
every legal and about page for reproduce/redistribute/commercial/reuse/scrape/licence returned **zero
matches** — no grant, no reuse clause, no anti-scraping clause, so **Crown copyright applies by
default**. No permissive clause can be quoted because none exists; this needs written permission from
SaskBuilds and Procurement.

Classification is three proprietary vocabularies with **no UNSPSC, NAICS or GSIN**, so the shared
adapter does not help. English only. Saskatchewan has no CKAN — `open.saskatchewan.ca` and
`data.saskatchewan.ca` are both **NXDOMAIN**.

### 5.3 Nova Scotia — awards only, licence unverified

Socrata `m6ps-8j6u`, **33,435 rows**, 2010-04-01 → 2026-09-15, monthly, no auth, full SoQL with a
`$where` cursor on `awarded_date` and `X-SODA2-Truth-Last-Modified` for cheap polling. Coverage is
broad — Halifax Regional Municipality 3,880, Dalhousie 1,524.

Two limits. Classification is three `Y`/`N` flags plus free text — no UNSPSC. And **the licence could
not be read**: `license_id` is `OGL_NOVA_SCOTIA` but `novascotia.ca/opendata/licence.asp` redirects to
a host that refused connections from two clients (`ECONNREFUSED 64.15.52.84:443`). NS OGL is generally
a Canadian-OGL-2.0 derivative permitting commercial use, but that is **not asserted here**.

Open NS notices are effectively blocked: an F5 WAF returns **`Request Rejected` as HTTP 200** — a block
disguised as success — the client handles a real **429** per-session cap, and the page carries
`noindex, nofollow`. The WAF blacklisted the client after ~6 requests.

### 5.4 Blocked, and why

| Source | Obstacle |
| --- | --- |
| **BC Bid** | `robots.txt: Disallow: /`; public browse runs `window.ivCaptcha.solve()` and returns zero rows without it. The one relevant dataset is licensed **"Access Only"** — *"reproduction is not permitted without written permission"* |
| **Alberta APC** | `Disallow: /` with `Allow: /` only for Googlebot, Bingbot, DuckDuckBot, Applebot. An undocumented anonymous `POST /api/opportunity/search` is reachable and disclosed its own contract, but **~15 well-formed payloads all returned HTTP 500 with an empty body** — no record retrieved. `open.alberta.ca` is unreachable (403, `CF-Mitigated: challenge`), terms **unverified** |
| **Ontario** | `ontariotenders.app.jaggaer.com/robots.txt` is `Disallow: /esop` — and `/esop` **is** the whole application. data.ontario.ca has no tender notices: `q=procurement` returns 95 datasets, all inventory stubs with `num_resources: 0` bar a 2018–2020 vendor-of-record CSV. Supply Ontario offers per-vendor email alerts only |
| **Manitoba** | No provincial portal; tendering outsourced to MERX — see §6 |
| **bids&tenders** | `opportunities.bidsandtenders.com/bid-opportunities/Embed` returns **1,004 open opportunities** as server-rendered HTML with no JS, the easiest scrape found anywhere. But `robots.txt` disallows the `/bid-opportunities/search` paging endpoint, and ToS clause 13 states *"Use of any automated system or software… to extract any data from this website for commercial purposes ('screen scraping') is strictly prohibited"* |

**Ontario is the largest Canadian gap with no free route.** Since bids&tenders carries much of the
Ontario municipal volume that Ontario's own portal denies, a commercial data agreement with
bids&tenders (owned by GHD) is the realistic path — a commercial conversation, not engineering.

**No western or prairie province publishes tender notices as open data**, validated with controls:
`organization:{bc,ab,sk,mb}` with `q=tender` on the federal CKAN returns 0, 0, 0 and 3 (highway
keyword noise), while `organization:yk` returns 7 genuine tender datasets and `organization:ab` with
`q=contract` returns 13. The method works; the data is not there.

## 6. Two sources refuse Anthropic agents by name

A compliance boundary, not a preference. **MERX** (`www.merx.com/robots.txt`, verified directly) lists
under a heading about blocking AI scrapers:

```
User-agent: anthropic-ai
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Claude-Web
Disallow: /
```

alongside GPTBot, CCBot, PerplexityBot and Bytespider. For `User-agent: *` it disallows **`/ws/`** —
the SOAP web services, so the only machine-readable interface is closed to every agent — and traps
`/*?*page=` and `/*?*pageSize=`. `www.gov.mb.ca/robots.txt` independently names the same three agents.

No content was fetched from either host beyond `robots.txt`, so **MERX's terms-of-use text is
unverified** — deliberately, because reaching it via a sibling host would circumvent a signal the
operator stated plainly on the primary host.

Several third-party "MERX API" products exist (Apify, Anakin.io, Parse.bot) selling scraped MERX data.
**These are a risk, not an option** — they resell data from a site whose robots.txt forbids exactly
that. Much of what MERX carries for Quebec is the same SEAO data available free under CC-BY, and its
federal content duplicates CanadaBuys open data.

## 7. National sources for the newly enabled European markets

Poland, Ireland and Portugal are now enabled as TED-only markets. All three have verified national
routes carrying below-threshold volume TED never sees. Ranked by build value: **Ireland → Poland →
Portugal.**

### 7.1 Poland — the biggest prize, with two silent traps

The widely cited `mo-client-board/api/notices/` **is not an API** (200 with HTML). The real endpoint
is keyless:

```
GET https://ezamowienia.gov.pl/mo-board/api/v1/notice
    ?NoticeType=ContractNotice&PublicationDateFrom=…&PublicationDateTo=…&CpvCode=72&PageSize=500
```

**~404 notices a day**, and of 486 sampled for 1–18 September, **486 were `isTenderAmountBelowEU:
true` — 100%**, so Poland is almost purely additive to TED. 484 of 486 carry a submission deadline.

**Trap 1 — `PageSize` caps at 500 and truncation is invisible.** A single day with no CPV filter
returns **exactly 500**. `PageSize=1000` returns HTTP 400 with the server's own message: *"Wartość
pola 'Page Size' musi być równa lub mniejsza niż '500'"*. There is **no pagination parameter at all**
— `PageNumber`, `Page`, `Offset` and `Skip` are silently ignored, and a truncated response is an
ordinary `200`. **Assert on `len == 500` and fail loudly.**

**Trap 2 — `CpvCode` is a substring match, not a prefix match.** Of the 486 records returned for
`CpvCode=72`:

| | records | share |
| --- | --- | --- |
| genuinely carry a 72-prefixed code | 164 | **33.7%** |
| matched on a substring only | 322 | 66.3% |
| no `72` substring anywhere | 0 | — |

Zero records lacking the substring proves the mechanism — `60172000-4` and `31527200-8` both match
`72` mid-code. Recall is safe (substring ⊃ prefix); precision is not.

The traps compound: the filter inflates counts roughly threefold, burning the 500 cap three times
faster than real matches warrant. **Use daily windows, treat the CPV filter as cap relief only, then
re-filter locally on a true prefix.** Verified safe: one day plus `CpvCode=72` returns 71 records, 20
genuinely 72-prefixed.

Payload size is driven by `htmlBody`, not record count — 71 records came to 2.4 MB, ~34 KB each.
`cpvCode` is a comma-joined list of codes **with Polish labels**, averaging 6.3 codes and peaking at
48, so codes must be extracted by regex rather than by splitting a field.

**Licence is the weakest of the three — free to use with no affirmative reuse grant**, worth a legal
sign-off. The authoritative `Załącznik 3` API document **404s at the URL its own integration page
advertises**, so the `NoticeType` enum is undocumented; `ContractNotice` is verified working and five
plausible award-notice names were rejected.

### 7.2 Ireland — build first

The undocumented CSV export is real and was called:

```
POST https://www.etenders.gov.ie/epps/viewCFTSAction.do
→ 200, text/csv, Content-Disposition: attachment; filename="SearchResults.csv"
```

The body is verbatim the hidden inputs of `searchCfTWorkspaceForm` on
`prepareCurrentOpportunities.do`. CPV 72 for 1–18 September returned **22 rows / 16.6 KB** with full
descriptions, in English, live to the minute — ~23 notices a day, 410 in the window. The platform is
**European Dynamics EPPS**, not Jaggaer or EU-Supply (EU-Supply is the legacy platform in historical
rows). The companion data.gov.ie CSV is **CC-BY-4.0**, the only clean licence of the three. English,
so no vocabulary pack is needed.

Two gotchas: **`isQuickSearch=false` is mandatory** or every advanced filter is ignored and you get
the 10,000-row 7.6 MB dump, and `cpvArray` must be paired with `cpvLabels`. And **the data.gov.ie CKAN
metadata claims the dataset was modified today while the data ends 2026-06-30** — trusting it would
put 12-week-stale data into a live pipeline.

### 7.3 Portugal — the previous "blocked" conclusion should flip

`base.gov.pt` is genuinely unreachable: a WebKnight WAF returns `999 No Hacking`, and the block is
**path-pattern based, not user-agent based** (`/robots.txt` 404s cleanly with the same UA). No evasion
was attempted. Its gated API is, in IMPIC's own words, *"não são tão completos… e podem apresentar
algum atraso"*.

But **two keyless routes were never probed last round and both work**:

- **dados.gov.pt** — a 21 MB IMPIC announcements JSON with **100% CPV coverage** and 99.7% direct
  tender-document links, ~77 procedure notices per working day. Licence is an unnamed
  `"Outra (Domínio Público)"`, needing a legal sign-off.
- **Diário da República Série II Parte L RSS** — a live feed that dovetails exactly where the bulk
  file stops, covering the fresh tail.

Portuguese, so **a Portuguese vocabulary pack is required new work** — the pipeline has none.

## 8. Sweden — the gap is free of charge but not free of terms

The carried-over question was whether any paid provider genuinely carries Swedish *below-threshold*
notices or merely resells TED. The answer makes the spend unnecessary but does not make the data
simply available.

**Current state, verified locally:** the dataset holds **321 Swedish signals, every one
`source: ted`**.

**Of eighteen vendors assessed, two genuinely carry Swedish below-threshold notices.** GlobalTenders
(USD 399/mo) carried TED numbers on 7 of 7 samples; Tenders Direct's Swedish coverage is TED;
OpenTender has **no Swedish crawler at all** in DIGIWHIST. More useful than the comparison: the
business model across all five registered annonsdatabaser is **notices free, alerting paid**. e-Avrop
says so outright — *"Att söka upphandlingar är helt gratis"* — and sells the Pabliq monitoring service
instead. **No vendor sells redistribution rights, and Mercell has no API and a 250-row export cap.**

### 8.1 The free route splits three ways

| Route | IT notices/yr | Terms position |
| --- | --- | --- |
| **Kommers Annons** direct | **70** | `allow: /` and **no terms document exists at all** — the cleanest thing found |
| Mercell aggregate | **361** | `Allow: /` plus a nightly notice sitemap, **but ToS §2.5 forbids crawling** |
| e-Avrop direct | 180 | `Disallow: /` **and** Pabliq §2.2 forbids *"bygga upp parallella databaser"* |

Mercell's terms are public after all — *"Terms of Use Mercell Platform"*, effective 21 January 2026 —
and §2.5 reads:

> "Any misuse of the Services, including crawling, automated downloading of information, and similar
> activities … is strictly forbidden"

That contradicts their own `robots.txt` and sitemap, which is precisely why **`Allow: /` is not a
reuse licence**. The contrast with §4.1 is the useful lesson: CanadaBuys carries an explicit OGL 2.0
commercial grant; Mercell carries an explicit prohibition. Robots policy decided neither.

The strongest legal fact in the file points the other way, though. **Konkurrensverket dnr 880/2024**
(closed 2026-03-03) investigated Mercell's annonsdatabas precisely because it hid winner and tenderer
data behind a paid login, specified required changes, and confirmed in early 2026 that *"det numera är
möjligt för fysiska personer att kostnadsfritt söka i databasens utbud av publicerade annonser"*.
Free **human** access is regulator-enforced and durable. Free **machine** access is not covered.

### 8.2 Recommendation

1. **Start with Kommers Annons** — roughly a 34% uplift on the ~203 TED-sourced Swedish IT notices,
   free, and with no legal question to resolve. Cost: CPV arrives as Swedish text labels rather than
   codes, so it needs a label→code map.
2. **Request written permission from Mercell** for the full 361/yr. The case is strong — their own
   `Allow: /`, their sitemap, ToS §3.2, and dnr 880/2024. **This is outbound contact and therefore the
   owner's decision; no such request was made.** Note for whoever writes it: Konkurrensverket
   registers Kommers to *Antirio System AB* while the site credits *Antirio AB*.
3. **Do not crawl e-Avrop or Clira.** e-Avrop is `Disallow: /` and its Pabliq terms forbid parallel
   databases; Clira is operational (`annonser.clira.io` → `public.clira.io/upphandling`, ~346 live
   notices) but its §9 purports to ban *"på annat sätt registrera information"*.

Sizes for planning: e-Avrop is ~**1,400** live notices (an earlier 570–650 estimate was extrapolated
and is withdrawn), roughly twice Kommers. Supplier pricing, for completeness: Pabliq **från 9 900
kr/år**, Mercell **1 070 kr/mån ex moms billed annually**, Konstpool **395 kr/yr** (art sector only),
Kommers **free**, Clira unpublished.

### 8.3 No statutory shortcut

Lag (2019:668) creates **no free-access entitlement**: §7 is silent on cost, §8 runs to the statistics
authority, and §2's accessibility duty attaches to *statistics*. The claim that registered databases
must provide free access was checked and rejected. The EU high-value-datasets regulation
(Reg. 2023/138) covers six categories and **procurement is not one**. Access is a courtesy, so
anything built should **degrade rather than break**, with TED remaining the floor for Sweden.

## 9. Compliance position, consolidated

| Source | Reuse position | Verdict |
| --- | --- | --- |
| SAM.gov extract | US public domain; sanctioned data-services path | ✅ in use |
| CanadaBuys open data | OGL – Canada 2.0, commercial use permitted | ✅ in use, owner decision recorded (§4.1) |
| **SEAO (Quebec)** | **CC-BY 4.0, commercial redistribution explicit** | ✅ best unbuilt source |
| eTenders (Ireland) | data.gov.ie companion CSV is CC-BY-4.0 | ✅ |
| dados.gov.pt | unnamed `"Outra (Domínio Público)"` | ⚠️ legal sign-off |
| BZP (Poland) | free to use, **no affirmative reuse grant** | ⚠️ legal sign-off |
| Kommers Annons | `allow: /`, no terms document exists | ✅ cleanest Swedish route |
| Nova Scotia Socrata | `OGL_NOVA_SCOTIA`, **text unreachable** | ⚠️ unverified |
| SaskTenders | **no licence grant exists**; Crown copyright by default | 🚩 written permission |
| Texas ESBD / Virginia eVA | good keyless feeds, both `Disallow: /` | 🚩 written permission |
| BC Bid | "Access Only" licence; CAPTCHA; `Disallow: /` | 🚩 blocked |
| Alberta APC | `Disallow: /` bar four search engines; API unusable | 🚩 blocked |
| Ontario / Jaggaer | `Disallow: /esop` — the whole application | 🚩 blocked |
| bids&tenders | ToS clause 13 forbids automated extraction | 🚩 blocked |
| **MERX, gov.mb.ca** | **name `anthropic-ai`, `ClaudeBot`, `Claude-Web` under `Disallow: /`** | 🚩 targeted refusal |
| Mercell | `Allow: /` but **ToS §2.5 forbids crawling** | 🚩 permission first |
| e-Avrop, Clira | terms forbid parallel databases / registering information | 🚩 blocked |
| New York state | forbids copying **and** inbound linking | 🚩 blocked |
| ComprasMX (Mexico) | personal, non-commercial use only | 🚩 blocked |

## 10. Suggested order

1. **The classification adapter (§1.2)** — highest value and unblocks everything else in North
   America. Without it Canada and the US score on text alone, which measures at 10% recall on US
   notices.
2. **A `en_US` vocabulary pass** — `BUSINESS_OBJECTS` matches 46 of 463 open US IT leads.
3. **Kommers Annons** (§8.2) — small, free, legally clean.
4. **Ireland eTenders** (§7.2) — CC-BY, English, keyless, verified request in hand.
5. **Poland BZP** (§7.1) — largest volume, but write the `len == 500` assertion first.
6. **SEAO** (§5.1) — best unbuilt source, but needs delta accumulation and French translation.

Owner actions that unlock more than engineering would: permission requests to **Mercell**, **Texas
CPA**, **Virginia DGS** and **SaskBuilds**, and a commercial conversation with **bids&tenders** for
Ontario municipal coverage.
