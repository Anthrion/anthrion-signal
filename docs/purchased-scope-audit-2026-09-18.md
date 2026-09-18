# Purchased-scope relevance audit — 18 September 2026

The Thames Water **Pump Optimisation and Aeration Efficiency Analysis** notice buys on-site testing and engineering analysis of pumps and aeration assets. Its reference to “ongoing enhancement” had incorrectly promoted it as managed application work. The **White Horse Reservoir Independent Technical Advisor** notice buys construction and engineering assurance. Neither notice states a separate software, CRM or AI deliverable in the retained published scope.

The separate Thames Water **Data of Last Resort Data Collection** opportunity remains: it explicitly describes a backup collection tool, deployment requirements and audit trails for operational-technology assets. Relevance is based on the purchased work, not the buyer or the water sector.

## Scope and method

- Frozen input: repository `6c80ec383c78e5610c798f823c6f4b7a6edfbf2d`, generated at `2026-09-18T19:14:50+00:00`.
- 2,964 published opportunities and 74,820 unique retained notices, including canonical records, archived notices and previously rejected records.
- Compared the old and new classification at the same timestamp, using original source text and only cached translations whose hashes match that source text. No translation or model calls were made for this audit.
- Compared live-candidate and awarded-history decisions separately. Publication also applies identity reconciliation and lifecycle checks, so pre-publication candidate counts are not the number of cards on the website.
- Checked all changed published decisions, mixed-scope counterexamples and historical changes. Saved source-backed regression cases independently of the classifier output.
- Verified that IDs, source hashes, original descriptions, source URLs, CPVs and available translated text are unchanged between the policy replays. The filters change eligibility and evidence labels; they do not rewrite procurement facts.

## What changed

| Previous behaviour | Revised behaviour | Retained counterexample |
| --- | --- | --- |
| “Ongoing enhancement” could count as application support in an engineering contract. | An ambiguous support phrase needs software context. Physical engineering exclusions require a purchased-scope title plus corroborating scope or classification. | Pump optimisation software or an analytics-platform lot. |
| Spanish **informática** and generic Italian **informatica** could count as the Informatica vendor. | Vendor tagging requires an unaccented vendor name plus product/service evidence. Native-language IT support and information-system interfaces have a separate discovery route. | Informatica PowerCenter; Spanish IT support; a laboratory information-system connection. |
| AI-Vergabemanager, supplier account instructions and notification subscriptions could supply AI/CRM evidence. | Procurement-platform names and existing bidder instructions do not count as the buyer’s technical requirement. | Building an AI assistant or implementing a supplier portal. |
| A buyer’s name or a previous report’s topic could create an apparent digital requirement. | Complete buyer identities are masked only in matching text, and explicitly contrasted historical topics are disregarded. Original source text remains visible. | A separate current CRM/digital delivery requirement. |
| Broad classification codes admitted some clear physical supply, fieldwork, human service and industry-representation contracts. | Conservative purchased-work categories filter those cases where no separate relevant digital scope is stated. | Sparse IT notices, selectable software categories in mixed DPS notices, SaaS implementations and mixed support contracts. |
| A published “TEST” notice could enter the feed because it contained genuine technology words. | A test-labelled title plus multiple explicitly placeholder procurement fields excludes the notice. | A genuine test-automation procurement with substantive requirements. |
| Clinical staff entering information into existing tools could count as IT delivery. | Operational record entry is distinguished from building or supporting the application itself. | Implementing a clinical case-management system. |

## Recall safeguards

No buyer, country or whole industry is blacklisted. Broad IT classification routes remain available, including sparse notices without a vendor name. The new rules retain separately stated business applications, software interfaces, data platforms, AI delivery and plausible mixed software lots.

Specific safeguards cover an AI startup **incubator** versus laboratory incubation equipment; computer-system **support** versus buying desktop computers; printed material plus software teaching aids; and professional/managed services alongside licence subscriptions. An unrelated licence resale is still distinct from implementing or migrating software.

Retained means the notice merits qualification, not that Anthrion is eligible, has every required skill, or can deliver the whole contract as prime contractor. Where a plausible component remains uncertain, preservation takes priority over a tidier count.

## Measured results

| Fixed-snapshot measure | Result |
| --- | ---: |
| Unique retained notices replayed | 74,820 |
| Published snapshot records evaluated | 2,964 |
| Published records newly excluded | 88 |
| Published records preserved | 2,876 |
| Retained published records with corrected capability labels | 46 |
| Previously ineligible live candidates restored before identity reconciliation | 1 |
| Historical award notices newly excluded / restored | 30 / 4 |
| Independently reviewed real-notice regression cases | 163 |

The source/translation preservation comparison passed for all 74,820 IDs. The reviewed controls include 39 retained notices and 124 exclusions; these are regression controls, not an estimate of precision across the entire corpus.

See the [summary](audits/purchased-scope-2026-09-18/summary.json), [decision changes](audits/purchased-scope-2026-09-18/changed-decisions.csv), [reviewed controls](audits/purchased-scope-2026-09-18/reviewed-controls.csv) and [inspectable notebook](audits/purchased-scope-2026-09-18/audit.ipynb).

## Verification and evidence

The accompanying comparison summary, reviewed-decision ledger and notebook record the measured results. The regression corpus is in `pipeline/tests/fixtures/purchased_scope_review_2026_09_18.json`; synthetic mixed-scope, language and negation controls are in `pipeline/tests/test_scope_audit.py`.

The tests cover the real pump and reservoir notices, the retained Thames Water backup-software notice, CRM work, mixed IT lots, native-language interfaces, SaaS implementation, AI data-space work and explicitly non-digital purchases. Existing relevance, lifecycle, archive-recovery, translation, publication and automation checks also run.

## Limits

This is a census of the retained corpus, not proof of perfect global procurement coverage or a measured precision/recall score against an independently exhaustive ground-truth dataset. The stored notice may omit detail in buyer attachments. Some broad or sparse records deliberately remain for qualification. Rules run again when notice content or matching translations change, and rejected source evidence remains available for recovery.

The audit does not change collection quotas, company settings, signing, bot permissions, timestamping or deployment safeguards.
