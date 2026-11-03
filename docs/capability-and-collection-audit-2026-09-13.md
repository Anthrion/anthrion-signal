# Capability and Collection Audit

Date: 13 September 2026. Investigation only: no production rules, records, translations, schedules, IDs, browser preferences or live publication were changed. The only additions are this report, a read-only audit script and its tests.

## Conclusion

There are genuine precision and capability-recall problems, not just an aesthetic issue with empty labels. Keep collection broad, improve the evidence required for capability labels, and remove only demonstrably unrelated scope from publication. Do not remove all untagged records or require a Salesforce brand mention.

The catalogue already covers 24 capability families, including CRM, case management, portals, contact centres, data, integration, field service, marketing, revenue, industry solutions and AI. The largest immediate improvement is recognising supported functional requirements accurately in every source language, rather than inventing more product labels.

## Snapshot and Method

The local exported snapshot matched the live site's record totals and generation time when checked:

- Generated: `2026-09-13T14:07:52+00:00` (15:07:52 UK time).
- Content digest: `32ba68dbbafb4486df759b608a67ce1ad8056827a8cf06dd0f9ceb869d45dc98`.
- Public records: **1,668**. Records without capabilities: **1,253 (75.1%)**.
- All 1,253 untagged records have only the broad CPV match recorded as discovery evidence. This is **not** a finding that all 1,253 are irrelevant.
- Of the untagged records, 270 have descriptions of at most 180 characters, and 107 repeat their title as the description. These groups overlap.
- The Greek market contains 37 records including one multi-country notice; 34 have no capabilities. Greece-only records are 36 total, 33 untagged.

The automated comparison examined all 1,668 records and their existing, source-hash-matched English overlays. It ran the existing matcher on deep copies, not on production records. Manual review examined the Greek summaries and selected positive/negative examples from other markets. It did not inspect every attachment or establish complete supplier eligibility for every record.

| Market assignment | Public records | No capabilities |
|---|---:|---:|
| Germany only | 528 | 445 |
| Spain only | 263 | 229 |
| UK only | 230 | 97 |
| Norway only | 190 | 138 |
| Sweden only | 139 | 128 |
| Finland only | 105 | 89 |
| Italy only | 61 | 52 |
| US only | 58 | 0 |
| Denmark only | 43 | 29 |
| Greece only | 36 | 33 |
| Iceland only | 8 | 6 |
| Multi-country | 7 | 7 |

Reproduce the comparison without source collection, model requests or data writes:

```powershell
G:\Anthrion\signal\.venv\Scripts\python.exe G:\Anthrion\signal\scripts\audit_discovery.py --record sig_8fe3b85be9d056c5976b --record sig_f8ae74998e3e5212bd22
```

## Confirmed Findings

### 1. Broad CPV Codes Alone Admit Unrelated Work

In [discovery.py](G:/Anthrion/signal/pipeline/anthrion_signal/discovery.py:166), a matching procurement classification contributes 12 points. The configured minimum is also 12 in [capabilities.yaml](G:/Anthrion/signal/config/capabilities.yaml:13). No functional requirement is therefore needed to publish a CPV-only record.

The selected Greek [Growthfund infrastructure notice](https://ted.europa.eu/en/notice/-/detail/606655-2026), `sig_8fe3b85be9d056c5976b`, describes IT infrastructure supply and commissioning. Its classifications include computer/network servers, backup, storage and clustering. The available text provides no CRM, case-management or AI implementation requirement. The empty capabilities are appropriate; the weak relevance comes from admission based on classification alone.

This is not unique to Greece:

- [German two-server purchase](https://oeffentlichevergabe.de/ui/de/notices/25816388), `sig_458a648e267b39146032`: hardware-only supply, admitted under `48820000`.
- [UK YGC chiller replacement](https://www.find-tender.service.gov.uk/Notice/086463-2026), `sig_e027de93726b960c50ed`: a physical purchase with an additional broad IT code. Its short submission instructions provide no addressable application scope.
- [Greek Microsoft licence supply](https://ted.europa.eu/en/notice/-/detail/614992-2026), `sig_e10818612c90c89d8c43`: a list of Microsoft licence quantities, not a stated CRM/integration implementation.

The `48` family is not exclusively software: it includes servers. `7931` is market research, and `7941` is business/management consultancy. These are reasonable discovery routes, but not proof of relevance. [Official TED CPV definitions](https://docs.ted.europa.eu/eforms/latest/reference/code-lists/cpv.html).

The current exclusions are largely English-language and do not cover these distinctions consistently. Mixed classifications also defeat the all-codes non-technical check. Merely adding every observed bad title to an exclusion list would be brittle.

### 2. Genuine Capabilities Are Missed in Both Foreign and English Text

[Matching](G:/Anthrion/signal/pipeline/anthrion_signal/discovery.py:139) uses original title/description text. The English overlay is currently display-only. [Language aliases](G:/Anthrion/signal/config/discovery_languages.yaml:69) are loaded, but Greek has only five small capability groups, and exact phrase matching does not handle the observed grammatical forms.

Examples worth protecting:

- [Greek 1555 citizen-service upgrade](https://ted.europa.eu/en/notice/-/detail/626507-2026), `sig_f8ae74998e3e5212bd22`: explicit ticketing, self-service, knowledge and AI-agent work, but no tags. Greek genitive forms such as `τεχνητής νοημοσύνης` do not match the configured nominative phrase; mixed Greek/Latin AI lettering creates another gap.
- [Greek citizenship case-system upgrade](https://ted.europa.eu/en/notice/-/detail/612808-2026), `sig_bc3377947986f123910d`: only analytics is tagged, while the original describes case handling and application workflows. The case-management alias is missing the observed `διαχείρισης υποθέσεων` form.
- [Rovaniemi customer information SaaS](https://ted.europa.eu/en/notice/-/detail/623280-2026), `sig_67956aa59caf2a7e9356`: a customer information system, but the Finnish compound is absent from the vocabulary.
- [Liverpool social-housing allocation implementation](https://www.find-tender.service.gov.uk/Notice/086483-2026), `sig_42db4c2311e7c3cf9e2d`: an English-language functional gap. Potential public-service application work, not proof that a particular Salesforce solution meets all requirements.
- [Heraklion digital applications](https://ted.europa.eu/en/notice/-/detail/585275-2026), `sig_136b15a0c5ba770c90eb`: includes a visitor chatbot and application development alongside media/equipment. Do not reject the entire procurement because it contains physical items.

Simply matching English overlays would assign some tags to 187 currently untagged records, including 11 Greece-only records. **137 of those 187 would rely solely on contextual vocabulary.** The other 50 include explicit/functional phrase matches or the existing relationship-database inference, not 50 verified sales leads. These numbers are diagnostic, not a claim of validated recovered opportunities.

### 3. Weak Context and Negation Can Produce False Capabilities

The matcher currently allows a contextual word anywhere in a notice to become a visible capability if a generic technical word appears elsewhere. Examples demonstrate why translation-aware matching must not be switched on unchanged:

| Example | Current or counterfactual error |
|---|---|
| Greek SIEM/support-licence notice, `sig_3c0929d8cf24a9326d56` | Already labelled enterprise-system connections solely because it mentions Microsoft. No integration delivery is established by that match. |
| Greek university equipment notice, `sig_d6e940e47e720e3dfa20` | Already labelled AI agents/assistants from an AI-capable computer purchase. Running AI software is not the same scope as building an agent. |
| Greek Microsoft licence supply | English matching adds analytics from Power BI and integration from Microsoft, without implementation evidence. |
| Greek school-admissions systems, `sig_d4b3bb2658f98ccda497` | English matching assigns contact-centre capability from a sentence explicitly excluding end-user helpdesk operation. The application-maintenance scope should still be retained. |
| Greek civil-protection equipment, `sig_f3c796e6dff288e6a5c5` | English matching mistakes ordinary volunteer teams for the Microsoft Teams product. |
| German central backup, `sig_88fe649111a131b35915` | English matching maps storage deduplication to customer-data governance. Even a configured functional term needs the correct subject. |

There is a separate whole-document co-occurrence problem in [relationship_database](G:/Anthrion/signal/pipeline/anthrion_signal/discovery.py:148). The US Young Investigator research grant, `sig_03fee59f618258543f29`, receives a relationship-database tag by combining a researcher's residency condition with separate research-data/database-management requirements. It is not asking for a resident-management database. In contrast, the NYC Strengthening Communities Database, `sig_5afac06e525074351e97`, explicitly asks for a database managing community relationships and should retain the match.

### 4. Capability Vocabulary Does Not Reach Every Collector

Adding a capability's `queries` entries currently expands GOV.UK queries in [config.py](G:/Anthrion/signal/pipeline/anthrion_signal/config.py:23). It does not expand all API searches.

TED's [retrieval query](G:/Anthrion/signal/pipeline/anthrion_signal/collectors.py:618) is restricted to `48*`, `72*`, `7931*` and `7941*`. German and Spanish collection have their own preliminary keyword gates. A useful notice classified outside the requested TED categories could never reach the capability matcher. This is a coverage risk demonstrated by the code, not a measured count of missed notices.

Use a bounded, resumable keyword search in addition to category retrieval where the API supports it. Share reviewed keyword families with the national preliminary gates. Preserve award/cancellation retrieval for tracked opportunities regardless of whether those updates repeat relevant keywords. Do not promise extra collected leads until a trial has measured unique, available results.

## Salesforce-Related Vocabulary Worth Adding

These are proposed functional search/matching improvements, not additions to Anthrion's proven delivery credentials. Retain vendor-neutral language and map it to the appropriate existing capability where possible.

| Search family | Concrete gaps | Required distinction |
|---|---|---|
| Benefits, grants and public-service administration | Benefit/entitlement systems, eligibility determination, grantmaking, **grants** management, social-housing applications/allocation | Software/process implementation, not paying benefits, conducting generic grant research or delivering housing services. Singular grant management and some beneficiary terms already exist. |
| Licensing, inspections and compliance workflows | Inspection-management software, licence/permit renewals, regulatory inspections workflow | The management application, not carrying out physical inspections or renewing software licences. Some licensing terms already exist. |
| Appointment services | Salesforce Scheduler, Lightning Scheduler, customer/citizen appointment booking and service queues | Customer-service scheduling, not generic project timetables or transport scheduling. |
| Document and rules automation | Omnistudio Document Generation, correspondence automation, document assembly, business-rules/decision engines | Automating organisational documents and decisions, not print hardware or merely supplying mandatory tender documents. |
| Customer identity and onboarding | Customer identity/CIAM, citizen self-registration, portal SSO, customer onboarding workflows | Customer-facing application identity/integration, not any firewall, identity-card equipment or security appliance. Salesforce Identity is already recognised by name. |
| Existing families in source languages | Reviewed Greek case/AI inflections; Finnish customer-information compounds; plural grants and local-language service/portal/admissions variants | Whole phrases or reviewed bounded word forms, not unrestricted stems or matching every occurrence of AI, Teams or system. |

Salesforce's own documentation establishes plausible platform routes for [public-sector benefits, licensing and inspections](https://help.salesforce.com/s/articleView?id=sf.psc_admin_understand_whats_included.htm&language=en_US&type=5), [grantmaking](https://trailhead.salesforce.com/content/learn/modules/public-sector-solutions-design/put-public-sector-solutions-to-work-for-you), [appointment scheduling](https://help.salesforce.com/s/articleView?id=ls_overview.htm&language=en_US&type=5), [document generation](https://help.salesforce.com/s/articleView?id=psc_omnistudio_document_generation.htm&language=en_US&type=5), [business-rules automation](https://help.salesforce.com/s/articleView?id=ind.psc_set_up_business_rules_engine.htm&language=en_US&type=5) and [customer identity](https://help.salesforce.com/s/articleView?id=sf.identity_about_customers_partners.htm&language=en_US&type=5). These sources do not prove that every tender in those domains fits Salesforce or Anthrion's eligibility.

## Recommended Implementation Order

1. **Repair evidence matching first.** Curate source-language variants; separate weak discovery hints from displayable capabilities; check phrase context, negation, product ambiguity and the requested delivery. Retain the supporting source passage/field and lot when available. Do not assign a Salesforce brand label just because a vendor-neutral requirement could run on that platform.
2. **Add validated translation-assisted positive matches carefully.** Only exact-current-source-hash overlays, with the same context checks as originals. Source-language matching continues before translation arrives. Tagging must not depend on a visitor selecting English. Translation failure, quota exhaustion or a short description must never make a notice disappear. Machine translation is useful supporting evidence, not independent proof of meaning or eligibility.
3. **Improve sparse evidence where feasible.** Fetch official detailed notice/lot text selectively, with caching and strict request budgets. Preserve the current record if details are unavailable. Do not fabricate capabilities from CPV, the buyer's industry or a possible technology solution.
4. **Run narrow publication exclusions in report-only mode.** Identify clear hardware-only purchases, unrelated consultancy and licence-only scope outside the team's service offering. Every proposed removal gets a reason and source evidence. Keep uncertain notices and mixed procurements with a separately addressable relevant software/AI lot; do not reject all renewals, all installed competitor products or all documents containing equipment terms.
5. **Review a balanced regression set before applying removals.** Protect the Greek 1555/citizenship/chatbot cases, Finnish customer SaaS, UK housing application and NYC relationship database. Include explicit exclusions, negated helpdesk, storage deduplication, research grants, hardware, licence-only work, mixed lots, sparse notices and non-CRM standalone AI as controls. Review the full before/after record-ID diff by market/source, not only overall totals.
6. **Expand retrieval independently.** Trial the new functional query families as an additive search path with checkpoints, deduplication and existing request budgets. Share vocabulary instead of maintaining inconsistent collector-specific subsets.

Operational safeguards: preserve canonical source text, record IDs, hidden IDs, bookmarks and source history. Recompute derived tags without retranslating unchanged text. Do not run new AI scoring or introduce a model call on page load. The existing charter version also controls historical backfill reset in `collect_with_backfill`; a vocabulary-version change must be separated from or deliberately budgeted for collection backfill to avoid an accidental year-wide replay. If retrieval changes, its checkpoint identity must include the changed query rather than silently reusing an incompatible cursor.

No rule set can guarantee zero false positives and zero missed opportunities. The conservative approach is to retain ambiguity, prove narrow exclusions against a reviewed sample, and measure the exact impact before deployment. No live tightening was applied in this audit.

## Verification

- Read-only audit completed against all 1,668 current records; no stale English overlays were used.
- 106 tests passed across the audit helper, discovery rules and opportunity-publication checks.
- Ruff passed for the new script and tests.
- Git status confirms only this report, the audit script and its tests were added. Production data and application code remain unchanged; nothing was pushed.
