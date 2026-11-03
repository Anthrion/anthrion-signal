# Market coverage estimates — 23 September 2026

The workspace menu's map shows, for each monitored country, an estimate of how much of that
country's publicly listed procurement Signal's enabled sources reach. It is a planning figure for
source investment (a paid API, a data purchase, or a new free collector), not a completeness claim.

## Definition

**Coverage ≈ opportunity notices in the sources Signal collects ÷ all opportunity notices publicly
listed for the country**, per year (Sep 2025 – Aug 2026 where measured, otherwise the latest full
year of official statistics).

- The universe is the de-duplicated union of notices listed anywhere a company could find them:
  official national portals and bulletins, regional and buyer platforms, TED, and notices only
  obtainable through paid aggregators. Unadvertised and word-of-mouth contracts are out of scope.
- Opportunity notices are calls for competition, including national below-threshold notices and
  prior-information notices used as calls for competition. Award notices, corrigenda,
  modifications and direct awards without competition are excluded.
- It measures source reach, not relevance: Signal's own capability filtering and page budgets are
  ignored. A source that is enabled but failing still counts at its structural reach; see Spain.
- Each figure is a single rounded estimate. Where the evidence gave a range, the midpoint is used.

## TED counts

TED's search API counts competition notices per buyer country. In eForms a change notice keeps its
original form type, so `form-type=competition` alone overcounts by roughly 15–60%. The corrected query:

```
buyer-country=XXX AND form-type=competition AND NOT change-notice-version-identifier=*
  AND publication-date>=20250901 AND publication-date<=20260831
```

The corrected counts matched national statistics where both exist (Romania: 9,092 on TED against
9,137 SEAP notices flagged as sent to the OJEU; Sweden: 11,211 against 10,881 directive
procurements). For Belgium and Luxembourg, EU institutions (`buyer-legal-type=eu-ins-bod-ag`)
are excluded.

## Estimates

| Country        | Coverage | Confidence | Collected / year | Universe / year | Largest uncollected listings (access, notices/year)                                                                                                                                                                                                                                                                                                                               |
| -------------- | -------- | ---------- | ---------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Germany        | ~93%     | medium     | 155,738          | 167,438         | National notices never sent to the Bekanntmachungsservice (municipal sites, Amtsblätter and newspapers, unconnected platforms, utilities) (free web / paid, ~11,700)                                                                                                                                                                                                              |
| Netherlands    | ~86%     | medium     | 7,914            | 9,164           | TenderNed national notices (free API, ~850); Public notices only on other platforms (Mercell/Negometrix, CTM, Aanbestedingskalender) (free web / paid, ~400)                                                                                                                                                                                                                      |
| United Kingdom | ~85%     | low        | 26,900           | 31,700          | Buyer e-tendering portals only (In-tend, ProContract/Proactis, Delta, Jaggaer, Atamis, MultiQuote, school and NHS portals) (free web / paid alerts, ~3,000); eTendersNI (Northern Ireland below-threshold notices from £30k) (free web, ~1,800)                                                                                                                                   |
| Spain          | ~80%     | medium     | 147,217          | 183,317         | Regional platforms aggregated into PLACSP (Catalonia PSCP, Euskadi, Madrid, Andalucía, Galicia, Navarra, La Rioja), notices below TED thresholds (free API, ~36,100)                                                                                                                                                                                                              |
| Denmark        | ~71%     | low        | 3,181            | 4,481           | Works (Tilbudsloven) and voluntary tenders advertised only on buyer sites, platforms or in the press (collected by Byggefakta, Udbudsvagten) (paid, ~800); udbud.dk national notices (NATIONALE_UDBUD) (free API, ~500)                                                                                                                                                           |
| Luxembourg     | ~70%     | medium     | 1,594            | 2,270           | PMP national notices (Livre I procedures) (free web / restricted, ~676)                                                                                                                                                                                                                                                                                                           |
| Sweden         | ~58%     | high       | 11,407           | 19,541          | Registered notice databases, below-threshold notices (Mercell ~56%, e-Avrop ~23%, Kommers Annons ~17%, Clira ~4%) (free web, ~7,134); Advertised direct awards in the registered databases (free web, ~700); Direct-award adverts on buyer websites (free web, ~300)                                                                                                              |
| Norway         | ~57%     | high       | 6,186            | 10,913          | Doffin national and voluntary below-EEA-threshold notices (free API, ~4,227); Below-national-threshold competitions on buyer platforms (Mercell, TendSign) or websites (free web, ~500)                                                                                                                                                                                           |
| Ireland        | ~55%     | medium     | 5,292            | 9,642           | eTenders below-threshold calls (undocumented CSV export; terms unverified) (free web, ~3,950); Other buyer portals (semi-state bodies, universities) (free web, ~400)                                                                                                                                                                                                             |
| Austria        | ~53%     | low        | 5,053            | 9,553           | National (Unterschwellen) notices on buyer platforms and Kerndaten (ANKÖ, auftrag.at, vergabeportal.at, Länder platforms) (free web / paid, ~4,500)                                                                                                                                                                                                                               |
| Switzerland    | ~48%     | medium     | 5,604            | 11,704          | simap.ch national (non-treaty) tenders (free API, ~5,750); Cantonal Amtsblatt-only notices (free web, ~350)                                                                                                                                                                                                                                                                       |
| Finland        | ~47%     | medium     | 6,122            | 13,122          | Hilma national notices (AVP-Read API, free key) (free API, ~6,400); Small procurements on buyer websites and tendering systems (Tarjouspalvelu, Cloudia) (free web, ~600)                                                                                                                                                                                                         |
| Hungary        | ~45%     | medium     | 3,113            | 6,900           | EKR national-regime procedures (Kbt. Part Three, incl. section 115 calls) (free web, ~3,500); Sub-threshold voluntary buyer calls (free web, ~300)                                                                                                                                                                                                                                |
| Iceland        | ~43%     | medium     | 319              | 750             | Útboðsvefur national-only tenders (free web, ~331); Tenders on buyers' own portals or websites (e.g. Reykjavík) (free web, ~100)                                                                                                                                                                                                                                                  |
| Belgium        | ~41%     | low        | 7,703            | 18,703          | BDA / e-Procurement national notices (free web / restricted, ~11,000)                                                                                                                                                                                                                                                                                                             |
| Slovenia       | ~41%     | medium     | 3,418            | 8,280           | Portal javnih narocil (e-JN) small-value (NMV) and other national-only notices (free web, ~4,860)                                                                                                                                                                                                                                                                                 |
| France         | ~39%     | low        | 49,321           | 125,887         | BOAMP national notices (90k€ to EU thresholds, MAPA under 90k€, DSP) (free API, ~38,566); MAPA and JAL notices only on buyer profiles and regional platforms (PLACE, Maximilien, Mégalis, AWS; resold by Vecteur Plus, Marchés Online, DoubleTrade) (free web / paid, ~38,000)                                                                                                    |
| Portugal       | ~38%     | medium     | 7,637            | 20,000          | Diário da República Série II Parte L / Portal BASE national-only announcements (dados.gov.pt open data) (free API, ~11,613); Calls listed only on e-procurement platforms or buyer sites (free web, ~750)                                                                                                                                                                         |
| Romania        | ~37%     | medium     | 9,092            | 24,670          | SICAP simplified-procedure notices (SCN) (free web, ~12,257); SICAP open tenders not sent to the OJEU (free web, ~2,024); EU-funded private-beneficiary tender notices (free web, ~1,000)                                                                                                                                                                                         |
| Bulgaria       | ~36%     | medium     | 7,504            | 20,900          | CAIS EOP public competitions (publichno sastezanie) (free web, ~6,500); CAIS EOP collection of offers with announcement (sabirane na oferti s obyava) (free web, ~5,437); UMIS/ISUN beneficiary contractor-selection notices (free web, ~1,500)                                                                                                                                   |
| Latvia         | ~33%     | medium     | 4,293            | 13,000          | IUB publication system / EIS national-only procurements (Section 9 small procurements, below-EU PIL procedures) (free web, ~8,700)                                                                                                                                                                                                                                                |
| Cyprus         | ~32%     | low        | 874              | 2,724           | eprocurement.gov.cy below-threshold calls (search behind CAPTCHA) (free web, ~1,850)                                                                                                                                                                                                                                                                                              |
| Italy          | ~31%     | medium     | 15,815           | 50,309          | ANAC PVL indagini di mercato (calls for expressions of interest before negotiated procedures) (free web, ~17,978); ANAC PVL national-only bandi, PINs and qualification systems (free web, ~14,516); Notices outside PVL (MePA open RdO, albo pretorio) (restricted / paid, ~2,000)                                                                                               |
| Czechia        | ~28%     | low        | 10,410           | 37,200          | VZMR open calls on buyer profiles (E-ZAK, NEN, Tender Arena and other e-tools; aggregated by Hlidac statu, TenderMonitor) (free web, ~20,000); Simplified below-threshold (ZPR) calls on buyer profiles (free web, ~7,000); VVZ notices not forwarded to TED (free web, ~1,000)                                                                                                   |
| Estonia        | ~24%     | medium     | 2,085            | 8,640           | Riigihangete register national-only procurements (lihthange, vaikehange, national procedures) (free web, ~6,100); Subsidy-recipient purchases in the register (free web, ~455)                                                                                                                                                                                                    |
| Croatia        | ~18%     | medium     | 3,317            | 18,200          | EOJN RH below-EU (male vrijednosti) procedures (free web, ~11,900); Jednostavna nabava calls on buyer websites (free web, ~3,000)                                                                                                                                                                                                                                                 |
| Slovakia       | ~18%     | low        | 2,315            | 12,900          | EKS / Elektronicke trhovisko orders (eks.sk) (free web, ~8,000); UVO Vestnik below-threshold (podlimitne) calls (free web, ~1,581); Buyer profiles, Josephine and EVO small-contract calls (free web, ~1,000)                                                                                                                                                                     |
| Lithuania      | ~16%     | low        | 5,738            | 35,700          | CVP IS published low-value surveys (skelbiama apklausa) (free web, ~25,000); CVP IS simplified (national) procurements (free web, ~5,000)                                                                                                                                                                                                                                         |
| Poland         | ~15%     | low        | 38,269           | 261,000         | BZP e-Zamowienia (national below-EU contract notices) (free API, ~135,000); Buyer platforms and BIP pages for sub-threshold RFQs (platformazakupowa.pl/Open Nexus, e-ProPublico, SmartPZP, Logintrade, Marketplanet; aggregated by paid services such as Oferent, BiznesPolska) (free web, ~60,000); Baza Konkurencyjnosci (EU-funds competitiveness notices) (free web, ~28,000) |
| Malta          | ~13%     | medium     | 1,023            | 7,723           | ePPS national calls (departmental tenders and calls for quotations ≥€5,000; search behind CAPTCHA) (free web, ~6,700)                                                                                                                                                                                                                                                             |
| Greece         | ~12%     | medium     | 4,134            | 35,000          | KIMDIS/ESIDIS national tenders (open and simplified procedures below EU thresholds) (free API, ~25,866); Open requests for quotations for direct awards (KIMDIS invitations, Diavgeia, buyer websites) (free web, ~5,000)                                                                                                                                                         |
| United States  | ~10%     | low        | 132,930          | 1,360,000       | State, county, city, school and special-district bid portals and websites (bulk route: GovSpend, BidPrime, BidNet, Periscope/ConstructConnect) (paid, ~697,000); DLA DIBBS (Defense Logistics Agency small-purchase RFQs) (free web, ~520,000); Other federal boards and agency sites (NECO, Unison Marketplace) (free web, ~10,000)                                              |
| Canada         | ~7%      | low        | 6,200            | 93,200          | Ontario: Ontario Tenders Portal, bids&tenders, Biddingo, MERX and municipal sites (free web, ~33,400); SEAO (Quebec) (free API, ~18,500); BC Bid, CivicInfo BC and BC municipal and broader-public-sector sites (free web, ~11,900)                                                                                                                                               |

## Caveats that change decisions

- **Spain** is ~80% structurally, and its `spain` collector is current: every new PLACSP snapshot
  has been read. It reports "partial" only because the re-reads that follow each discovery-vocabulary
  change (about 42 pages) queue up faster than its three-page budget drains them, so it never
  records a completed run (`last_success` null). PR #25 fixes this. The regional platforms it also
  misses (Catalonia, Euskadi, Madrid and others) are published in PLACSP's own aggregated feed,
  which is open.
- **France** was earlier quoted at ~71% from TED against BOAMP alone. Counting small tenders listed
  only on buyer profiles and regional platforms (the layer paid aggregators resell) gives ~39%.
- **United States**: the Defense Logistics Agency's public bid board (DIBBS) carries more than
  10,000 small-purchase solicitations a week that never reach SAM.gov; without it the estimate
  would be ~18%. State and local volume rests on aggregator figures.
- **Denmark** counts ~800 tenders a year published only outside udbud.dk (a guess); on measured
  sources alone it would be ~86%.
- Low-confidence figures rest on assumptions named in each note below. They are the first to
  re-measure before an investment decision.

## Basis and sources by country

### Austria — ~53% (low confidence)

Measured: TED originals 5,053 (buyer-country=AUT, competition, no change notices). USP Ausschreibungssuche lists only 3,821 Bekanntmachungen for the same year, fewer than TED, so its Kerndaten index is incomplete. Assumed: about 4,500 national-only notices (~0.9x EU volume, from Austrian no-notice thresholds and an ANKÖ sample with 48–65% national notices).

- <https://api.ted.europa.eu/v3/notices/search>
- <https://ausschreibungen.usp.gv.at/at.gv.bmdw.eproc-p/public/tenderlist>
- <https://www.staedtebund.gv.at/fileadmin/USERDATA/aktuelles/dokumente/Oeffentliche_Vergaben_in_Oesterreich.pdf>
- <https://www.bmj.gv.at/dam/jcr:1c176ca8-f720-40a8-a358-de5a946e020f/Rundschreiben_Publikationsverpflichtungen_f%C3%BCr_%C3%B6ffentliche_Auftraggeber_innen_und_Sektorenauftraggebner_innen.pdf>

### Belgium — ~41% (low confidence)

Measured: TED originals 8,101 minus 398 EU institutions (buyer-legal-type=eu-ins-bod-ag) = 7,703. Derived: BOSA reported over 25,000 procedures published on e-Procurement in 16 months (Sep 2023–Jan 2025), about 18.75k a year, leaving about 11k national-only BDA notices. The scope of BOSA's figure is unverified, hence low confidence.

- <https://api.ted.europa.eu/v3/notices/search>
- <https://bosa.belgium.be/fr/news/25000-marches-publics-publies-et-50000-entreprises-enregistrees-apres-plus-dun-de-procurement>
- <https://aolytics.cloud/fr/blog/marches-publics-belges-2024-2025-anomalies/>
- <https://www.publicprocurement.be/>

### Bulgaria — ~36% (medium confidence)

TED 7,504/yr measured (same query, BGR; TED 2024 7,326 vs 7,412 EU-type procedures in AOP data). AOP 2024 market report (CAIS EOP): 6,500 national public competitions and 5,437 announced collections of offers, not on TED. EU-funds beneficiary tenders in UMIS ~1.5k assumed. Excluded: 1,489 direct negotiations and 480 invitations to selected persons.

- <https://www2.aop.bg/wp-content/uploads/2025/05/stat-report_MF_for-2024-1.pdf>
- <https://api.ted.europa.eu/v3/notices/search>

### Canada — ~7% (low confidence)

Measured (repo): CanadaBuys 125-145 federal notices a week; a 2026 sample shows 89% are competitive (7.5% ACAN, 3.1% RFI), so ~6,200. Measured or derived: SEAO ~15-22k a year, Alberta APC ≥10,196 postings in 2024, SaskTenders ~3.4k a year, about 2.05 notices per 1,000 residents. Assumed: the same rate elsewhere (~54k) plus ~1,500 federal notices outside CanadaBuys.

- <repo: docs/north-america-sources-2026-09-21.md (branch docs/north-america-sources) §4, §5.1, §5.2, §5.4>
- <https://canadabuys.canada.ca/opendata/pub/2026-2027-TenderNotice-AvisAppelOffres.csv>
- <https://www.donneesquebec.ca/recherche/dataset/systeme-electronique-dappel-doffres-seao>
- <https://adjudica.ca/donnees>
- <https://purchasing.alberta.ca/posting/AB-2024-10196>

### Croatia — ~18% (medium confidence)

TED 3,317/yr measured (same query, HRV; TED 2024 3,112 vs 3,085 national EU-value starts). EOJN RH 2024: 15,984 procedures started, 12,899 below EU thresholds; ~11.9k competitive after removing negotiated-without-notice procedures (~6% assumed). Simple-procurement (jednostavna nabava) calls on buyer websites ~3k assumed.

- <https://www.javnanabava.hr/files/Datoteke/Statisti%C4%8Dko%20izvje%C5%A1%C4%87e%202024.pdf>
- <https://api.ted.europa.eu/v3/notices/search>

### Cyprus — ~32% (low confidence)

Measured: TED (CYP) = 874 (2019: 360, matching 359 awarded above-limit procedures). Measured: Art. 83 reports, eprocurement.gov.cy (mandatory for every notice): 799-1,199 awarded below-limit open or restricted procedures a year (2018-20); below-threshold contracts rose 32% over 2021-23. Assumed: ~1,850 below-threshold notices now. Simplified procedures without notices are excluded.

- <https://ec.europa.eu/docsroom/documents/47759/attachments/1/translations/en/renditions/native>
- <https://ec.europa.eu/docsroom/documents/60837/attachments/1/translations/en/renditions/native>
- <https://publicprocurement.gov.cy/statistika/>

### Czechia — ~28% (low confidence)

TED 10,410/yr measured (same query, CZE; VVZ forwards above-threshold and many below-threshold forms to TED). Not on TED (2025): ZPR profile calls ~7k (ISVZ: 6,089 awarded), VZMR open calls ~20k assumed ('otevrena vyzva' ~21% of NEN's 30,184 awards; NEN is one tool of several), VVZ-only ~1k assumed. Ratio is 27% on 12-month TED and 29% on 2025 TED (11,200); ~28% used.

- <https://portal-vz.cz/wp-content/uploads/2013/07/Vyrocni-zprava-o-elektronizaci-a-stavu-VZ-za-rok-2025.pdf>
- <https://cms.vvz.nipez.cz/wp-content/uploads/2024/01/Priloha-c.-2-Metodika-pro-vyplneni-formularu-a-zadosti.pdf>
- <https://www.hlidacstatu.cz/verejnezakazky>
- <https://api.ted.europa.eu/v3/notices/search>

### Denmark — ~71% (low confidence)

Measured: TED (DNK) = 3,181. Measured: udbud.dk public search, NATIONALE_UDBUD Sep 2025-Aug 2026 = 500 (EU_UDBUD 3,841 matches TED including change notices); the Art. 83 report gives 627-665 below-threshold notices a year (2018-20). Assumed: ~800 works (Tilbudsloven) and voluntary tenders advertised only on buyer sites, platforms or in the press.

- <https://udbud.dk/soegning/api-docs>
- <https://ec.europa.eu/docsroom/documents/48655/attachments/1/translations/en/renditions/native>
- <https://statensindkob.dk/seneste-nyt/nyhedsarkiv/2024/maj/annoncering-regler-og-fremgangsmaade/>

### Estonia — ~24% (medium confidence)

TED 2,085/yr measured (same query, EST). Riigihangete register 2024: 8,791 procurements, including 702 without prior publication, so 8,089 announced; ~1,989 of those are on TED (TED 2024), leaving ~6,100 national-only (simplified, small and national). Plus 455 subsidy-recipient purchases run in the register. Purchases below the simplified-procurement thresholds are unregulated and unlisted.

- <https://fin.ee/sites/default/files/documents/2025-06/2024.a%20riigihangete%20valdkonna%20statistika%20ja%20kokkuv%C3%B5te.pdf>
- <https://api.ted.europa.eu/v3/notices/search>

### Finland — ~47% (medium confidence)

Measured: TED (FIN) = 6,122; only 36 national E3 notices reach TED. Measured: the Art. 83 report counts 6,421 below-threshold notices in 2020 (8,418 in 2018); Hilma totals for 2023 (11,855 contract notices) and 2024 (21,534 notices against TED's 14,264) imply ~6,000-6,500 now; 6,400 used. Assumed: ~600 small procurements on buyer sites.

- <https://ec.europa.eu/docsroom/documents/47764/attachments/1/translations/en/renditions/native>
- <https://northpatrol.fi/2024/02/28/julkiset-it-hankintailmoitukset-2023/>
- <https://northpatrol.fi/2025/02/25/julkiset-it-hankinnat-suomessa-2024/>
- <https://www.hankinnat.fi/ajankohtaista/2025/kansalliset-eformsit-tulevat-vuonna-2025-ilmoittaudu-hilman-koulutuksiin>

### France — ~39% (low confidence)

Measured: TED originals 49,321 (buyer-country=FRA, competition, no change notices); BOAMP API Sep25–Aug26: 38,566 national calls (FNS 31,568, MAPA 6,668, DSP/other 330). Assumed: about 38k MAPA/JAL notices only on buyer profiles, from OECP 2024 (223,383 contracts over €40k, 54% MAPA, ~1.6 lots per notice, less the 2026 threshold rises, plus DECP under-reporting). Vecteur Plus's ~187k lot-level 'marchés' agrees.

- <https://api.ted.europa.eu/v3/notices/search>
- <https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records>
- <https://www.weka.fr/actualite/commande-publique/article/recensement-des-marches-publics-les-resultats-2024-sont-connus-212163/>
- <https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053202067>
- <https://www.achatpublic.info/sites/default/files/document/documents/vecteur_plus_-_commande_publique_-_vision_et_tendances_au_s1_-_2024.pdf>
- <https://www.maximilien.fr/media/Actualites/2025/GIP_Maximilien_-_Rapport_dactivite_2024_-_VF.pdf>

### Germany — ~93% (medium confidence)

Measured: TED originals 70,238 (buyer-country=DEU, form-type=competition, NOT change-notice-version-identifier=*, Sep25–Aug26); Bekanntmachungsservice search: about 85.5k national competition notices (79.2k Öffentliche Ausschreibung, 1.4k with Teilnahmewettbewerb, half of 9.7k untyped; 2.2k ex-ante notices excluded). Assumed: 12% of national notices never reach it (eForms-UNS voluntary), about 11.7k.

- <https://api.ted.europa.eu/v3/notices/search>
- <https://oeffentlichevergabe.de/ui/de/search>
- <https://digitale-beschaffung.de/eforms-uns/>
- <https://www.service.bund.de/Content/DE/Service/Ausschreibungsinfos/ausschreibungsinfos_node.html>
- <https://blog.cosinex.de/2026/05/22/vergabestatistik-2021-2024-auswertung/>
- <https://www.deutsches-ausschreibungsblatt.de/>

### Greece — ~12% (medium confidence)

Measured: TED (GRC) = 4,134. Measured: EAADISY monitoring report, 30,506/30,176/32,456 KIMDIS tender declarations in 2018-20 (TED 2020 = 3,250, ~10%). Measured: KIMDIS API, June 2026: 3,823 non-direct-award notice records (~1.6 per procedure, ~29k a year); 30,000 used. Assumed: ~5,000 open requests for quotations for direct awards.

- <https://ec.europa.eu/docsroom/documents/48776/attachments/1/translations/en/renditions/native>
- <https://ec.europa.eu/docsroom/documents/60858/attachments/1/translations/el/renditions/native>
- <https://cerpp.eprocurement.gov.gr/khmdhs-opendata/v3/api-docs>

### Hungary — ~45% (medium confidence)

TED 3,113/yr measured (same query, HUN). KH 2025: 6,923 successful procedures, 15,511 contracts, 35% national regime at ~1.5 contracts/procedure vs 65% EU at ~3.0; so national-regime procedures are ~1.1-1.2x the EU-regime count, ~3,500/yr derived. These are published only on EKR, including Kbt. 115 calls (public, but only invited firms may bid). Sub-threshold voluntary calls ~300 assumed.

- <https://www.kozbeszerzes.hu/media/documents/gyorsjelentes-2025.pdf>
- <https://kozbeszerzes.hu/media/documents/Utmutato__Kbt_115__szerinti_eljaras.pdf>
- <https://api.ted.europa.eu/v3/notices/search>

### Iceland — ~43% (medium confidence)

Measured: TED (ISL) = 319. Measured: útboðsvefur.is carried 607 tenders in 2024 and 538 by 17 Oct 2025 (Alþingi answer 157/299), including Landsvirkjun, Isavia and Landsnet; ~650 a year used, ~331 of them national-only. Assumed: ~100 tenders only on buyers' own portals or sites (Reykjavík's count there halved from 2024).

- <https://www.althingi.is/altext/157/s/0299.html>
- <https://api.ted.europa.eu/v3/notices/search>

### Ireland — ~55% (medium confidence)

Measured: TED (IRL) = 5,292. Measured (repo): eTenders ~8,000 calls a year (5,596 rows 2026 year to date; ~23 a day in September), ~60% below threshold, so its non-TED share is 3,100-4,800; midpoint 3,950 used (assumed). Assumed: ~400 on other buyer portals. Art. 83 report: below/above awarded contracts ≈1.6:1 (2021-23), consistent.

- <repo: docs/north-america-sources-2026-09-21.md (branch docs/north-america-sources) §7.2>
- <repo: docs/research-handover-2026-09-18.md (branch docs/research-handover) §7>
- <https://ec.europa.eu/docsroom/documents/63797/attachments/1/translations/en/renditions/native>

### Italy — ~31% (medium confidence)

Measured: TED originals 15,815 (buyer-country=ITA, competition, no change notices). ANAC PVL API, Sep25–Aug26: 29,865 bandi (~60% EU forms, sampled), 160 PIN calls, 306 qualification systems, 17,978 indagini di mercato (counted as opportunities). Assumed: about 2k outside PVL. Excluding indagini, coverage would be about 49%.

- <https://api.ted.europa.eu/v3/notices/search>
- <https://pubblicitalegale.anticorruzione.it/bandi>
- <https://www.anticorruzione.it/documents/91439/307867242/Anac+-+Relazione+annuale+2025+su+attivit%C3%A0+2024.pdf/f5053514-6745-8516-c8df-5bb0e4b2dfbd?t=1747731265787>
- <https://www.lavoripubblici.it/news/relazione-anac-2026-appalti-pubblici-affidamenti-diretti-pnrr-37911>

### Latvia — ~33% (medium confidence)

TED 4,293/yr measured (same query, LVA; 3,518 in 2024). IUB: 11,421 procurements announced in 2024, covering PIL procedures and Section 9 small procurements, all published by IUB. That gives 31% on TED in 2024, or 35% if national-only volume stayed flat while TED grew; midpoint used. Purchases below EUR 10k/20k are unpublished.

- <https://www.iub.gov.lv/lv/jaunums/iepirkumu-uzraudzibas-biroja-paveiktais-2024-gada>
- <https://api.ted.europa.eu/v3/notices/search>

### Lithuania — ~16% (low confidence)

TED 5,738/yr measured (same query, LTU; 6,193 in 2025). VPT: 9,671 international and simplified procedures completed in 2025, so ~5k national simplified. Low-value buys above EUR 15k must generally be published surveys in CVP IS; ~25k/yr assumed from a monitoring firm's (dated) figure of 120-200 notices a day. Low confidence.

- <https://infoerdve.lt/skelbiami-skaiciai-gniauzia-kvapa-kur-dingsta-milijardai/>
- <https://viesujupirkimu.lt/viesieji-pirkimai/viesieji-pirkimai-verslui/>
- <https://api.ted.europa.eu/v3/notices/search>

### Luxembourg — ~70% (medium confidence)

Measured: TED originals 1,780 minus 186 EU institutions = 1,594. MMTP activity report: 2,247 procedures put online on the PMP in 2024 (2,223 in 2023), taken as the national universe (about 2,270 on trend), so about 680 are national-only. If PMP counts include unpublished procedures, coverage is higher.

- <https://api.ted.europa.eu/v3/notices/search>
- <https://gouvernement.lu/dam-assets/publications/rapport-activite/minist-mobilite-travaux-publics/2024/rapport-activite-2024-mmtp.pdf>
- <https://pmp.b2g.etat.lu/>

### Malta — ~13% (medium confidence)

Measured: TED (MLT) = 1,023. Measured: Malta's Art. 83 report counts ePPS calls for competition (mandatory for every call ≥€5,000, including calls for quotations and departmental tenders): 5,864/5,819/6,136 in 2018-20, of which 510-591 above threshold. TED grew 45% since 2020 (704); below-threshold assumed +20%, to ~6,700.

- <https://ec.europa.eu/docsroom/documents/47779/attachments/1/translations/en/renditions/native>
- <https://www.oecd.org/content/dam/oecd/en/publications/reports/2023/06/public-procurement-in-malta_22d12832/d64e5e05-en.pdf>
- <https://www.maltatenders.com/public-procurement.php>

### Netherlands — ~86% (medium confidence)

Measured: TED originals 7,914 (buyer-country=NLD, competition, no change notices); TenderNed TNS API: 8,439 contract notices Sep25–Aug26, national share ~10% in three 100-notice samples (TenderNed 2025 statistics: 9.1%), about 850 national-only. Assumed: about 400 public notices only on other platforms.

- <https://api.ted.europa.eu/v3/notices/search>
- <https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties>
- <https://www.tenderned.nl/cms/nl/aanbesteden-in-cijfers/jaarstatistieken/2025>
- <https://data.overheid.nl/dataset/aankondigingen-van-overheidsopdrachten---tenderned>

### Norway — ~57% (high confidence)

Measured: TED (same query, buyer-country=NOR) = 6,186. Measured: anskaffelser.no, 10,310 Doffin competition notices in 2025, 41% below the EEA threshold (~4,227; the other ~6,083 match TED). Assumed: ~500 below-national-threshold competitions listed only on buyer platforms or websites.

- <https://www.anskaffelser.no/data-statistikk-og-analyse/kunngjoringer-av-konkurranser>
- <https://api.ted.europa.eu/v3/notices/search>

### Poland — ~15% (low confidence)

TED 38,269/yr measured (query: buyer-country=POL AND form-type=competition AND NOT change-notice-version-identifier=*, 20250901-20260831). BZP ~135k/yr derived (UZP 2025: 142,424 CNs + 3,671 non-Pzp notices; 2026 lower after threshold rose to 170k PLN). Baza Konkurencyjnosci ~28k (546/week, Atlas tracker). Sub-threshold RFQs on platforms/BIP ~60k assumed (Open Nexus alone reported 81,217 RFQs in 2025).

- <https://www.gov.pl/web/uzp/sprawozdanie-prezesa-uzp-z-funkcjonowania-systemu-zamowien-publicznych-w-2025-r>
- <https://atlasprzetargow.pl/blog/ile-przetargow-publicznych-oglasza-sie-w-polsce-rocznie>
- <https://atlasprzetargow.pl/baza-konkurencyjnosci>
- <https://zakupowa.pl/zapytania-ofertowe>
- <https://api.ted.europa.eu/v3/notices/search>

### Portugal — ~38% (medium confidence)

Measured: TED (PRT) = 7,637. Measured (repo): dados.gov.pt IMPIC announcements ≈77 procedure notices per working day ≈19,250 a year, a superset (every concurso público or limitado is announced in Diário da República; EU-level ones also on TED). Assumed: ~750 platform-only calls. IMPIC's monthly swings (1,109 fewer in Nov than Oct 2024) suggest the DR total may be higher.

- <repo: docs/north-america-sources-2026-09-21.md (branch docs/north-america-sources) §7.3>
- <https://dados.gov.pt/pt/datasets/contratos-publicos-portal-base-impic-anuncios-de-2012-a-2026/>
- <https://www.impic.pt/impic/assets/misc/relatorios_dados_estatisticos/202411.pdf>
- <https://www.impic.pt/impic/assets/misc/relatorios_dados_estatisticos/RelContratacaoPublica_2024.pdf>

### Romania — ~37% (medium confidence)

TED 9,092/yr measured (same query, ROU). SEAP open data (data.gov.ro, Q3 2025-Q2 2026): 23,670 initiation notices, of which 9,137 were flagged as sent to the OJEU (matches TED). SEAP-only: 12,257 simplified, 2,024 open tenders, 252 concessions/invitations. Direct purchases excluded per brief. EU-funded private-beneficiary tenders ~1k assumed.

- <https://data.gov.ro/dataset/achizitii-publice-2025>
- <https://data.gov.ro/dataset/achizitii-publice-2026>
- <https://api.ted.europa.eu/v3/notices/search>

### Slovakia — ~18% (low confidence)

TED 2,315/yr measured (same query, SVK; UVO 2024 counts 2,211 above-threshold calls, consistent). Not on TED: EKS electronic-marketplace orders ~8k/yr (derived from order numbering: Z20257665 on 3 Dec 2025; orders publicly visible), Vestnik-only below-threshold calls 1,581 (UVO 2024), buyer-profile/Josephine small calls ~1k assumed. Since Aug 2024 most below-threshold procedures are invitation-only, so not listed.

- <https://www.uvo.gov.sk/otvorena-komunikacia/spravy-o-cinnosti-uradu/statistika-procesu-verejneho-obstaravania/rok-2025>
- <https://rokovania.gov.sk/download.dat?id=45733B8EC7D34E649F5C66174FDB37F1-8DD86E8B93F3EE10713A38F3C913B05A>
- <https://portal.eks.sk/SpravaZakaziek/Zakazky/Detail/368544>
- <https://portal.eks.sk/SpravaZakaziek/Zakazky/Detail/360000>
- <https://www.vovpraxi.sk/sk/casopis/verejne-obstaravanie-pravo-a-prax/podlimitne-zakazky-po-novom.m-687.html>

### Slovenia — ~41% (medium confidence)

TED 3,418/yr measured (same query, SVN). MJU 2025 statistical report: 8,869 completed procedures, 8,128 with a prior notice; ~3,650 published in the OJEU, while 4,466 small-value (NMV) and ~160 other procedures appeared only on Portal javnih narocil. NMV initiated ~4,700 assumed (+5% for unsuccessful). Below NMV thresholds, contracts are record-only and not listed.

- <https://www.gov.si/assets/ministrstva/MJU/DJN/Statisticna-porocila/Stat_por_JN_2025.docx>
- <https://ejn.gov.si/direktorat/porocila-in-analize.html>
- <https://api.ted.europa.eu/v3/notices/search>

### Spain — ~80% (medium confidence)

Structural only: `spain` is partial (last_success null, page budget reached, watermark 8 Sep 2026), so live reach is roughly TED's 14%. Measured: OIReScon IAS 2026 lists 183,317 publicised procedures in 2025 (open, simplified, restricted, internal rules and others). Assumed: 25% sit on aggregated regional platforms (regional tables), about 46k, of which ~10k reach TED (TED NUTS counts).

- <https://www.hacienda.gob.es/rsc/oirescon/informe-anual-supervision-2026/ias2026-modulo1.pdf>
- <https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/Paginas/licitaciones_plataforma_contratacion.aspx>
- <https://api.ted.europa.eu/v3/notices/search>

### Sweden — ~58% (high confidence)

Measured: TED query buyer-country=SWE AND form-type=competition AND NOT change-notice-version-identifier=* AND publication-date>=20250901<=20260831 = 11,407. Measured: Upphandlingsmyndigheten 2025, 18,015 advertised procurements, 60.4% directive-governed, so ~7,134 below-threshold notices appear only in registered databases. Assumed: ~700 of 1,084 advertised direct awards are open calls; ~300 buyer-site-only adverts.

- <https://www.upphandlingsmyndigheten.se/statistik/upphandlingsstatistik/statistik-om-annonserade-upphandlingar-2025/drygt-18-000-upphandlingar-annonserades-2025/>
- <https://ec.europa.eu/docsroom/documents/47783/attachments/1/translations/en/renditions/native>
- <https://api.ted.europa.eu/v3/notices/search>
- <https://op.europa.eu/en/web/ted-reusers-workshops/questions_and_answers_2023_10_18>

### Switzerland — ~48% (medium confidence)

Measured: TED originals 5,604 (buyer-country=CHE, competition, no change notices). simap API: 243 first tender publications on 7–13 Sep 2026 against 120 on TED (49%; prior week similar); publicationTed was true on 8 of 16 sampled tenders. So simap carries about 11.35k tenders a year. Assumed: about 350 Amtsblatt-only notices.

- <https://api.ted.europa.eu/v3/notices/search>
- <https://www.simap.ch/api/specifications/simap.yaml>
- <https://www.simap.ch/en/about/legal>

### United Kingdom — ~85% (low confidence)

Measured: Find a Tender new tender notices averaged 66 per weekday (OCDS API, 4 sample days, tag 'tender'), about 16.6k/yr; Contracts Finder legacy opportunities about 6.0k (search API: 2,291 unawarded plus ~10.5% of 35,482 awarded had a live window), 5.5k net of FTS. Assumed: PCS/Sell2Wales below-threshold 4.5k, DOS/GCA 0.3k, eTendersNI-only 1.8k, portal-only 3k.

- <https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages>
- <https://www.contractsfinder.service.gov.uk/apidocumentation>
- <https://www.find-tender.service.gov.uk/Home/NoticeTypes>
- <https://www.open-contracting.org/2026/03/03/the-uk-procurement-act-one-year-on-what-does-the-data-tell-us/>
- <https://www.publiccontractsscotland.gov.uk/search/search_30daysResultsList.aspx>
- <https://psip.co.uk/blog/etendersni-guide>
- <https://www.niauditoffice.gov.uk/publications/html-document/public-procurement-northern-ireland-report>
- <https://procontract.due-north.com/Opportunities/Index>

### United States — ~10% (low confidence)

Measured: range samples of SAM's fiscal-year archives (FY2025 ≈323k notices, FY2026 pace ≈265k), 49% solicitations or combined synopses, so ~130k; NYC City Record 930 solicitations; LA RAMP ~2,000 (from the open snapshot). The universe adds DLA DIBBS ≥520k (HigherGov: >10k a week) and ~700k state and local (assumed from GovSpend's 100-120k open bids). Without DIBBS ≈18%.

- <https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public>
- <https://s3.amazonaws.com/falextracts/Contract%20Opportunities/Archived%20Data/FY2025_archived_opportunities.csv>
- <https://data.cityofnewyork.us/resource/dg92-zbpx.json>
- <https://data.lacity.org/resource/hf3r-utnq.json>
- <https://docs.highergov.com/find-opportunities/dla-opportunities>
- <https://support.govspend.com/data-overview-bids-rfps>
