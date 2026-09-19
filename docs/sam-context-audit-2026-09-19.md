# SAM bootstrap and administrative-context audit

The [first successful collection](https://github.com/Anthrion/anthrion-signal/actions/runs/35452932660) processed 3,000 SAM notices from a verified public extract, leaving 80,951 new or changed notices in its resumable backlog. This partial status describes coverage still being processed. The run published 5,644 current records and 19,430 awards across all sources, passed desktop/mobile data checks, and completed in 21m 11s from job start to publication recording. This is one observed run, not a guaranteed runtime.

The retained canonical file was 19,882,634 bytes after compression. The temporary SAM CSV is not committed. The public site was 609.9 MiB before the subsequent research-history metadata release; total publication size still needs monitoring as coverage grows.

## Review finding

All 42 admitted SAM candidates were checked for the new context issue. Five clearly unrelated notices were being admitted by incidental text:

| Notice | Incidental match | Correct interpretation |
| --- | --- | --- |
| TSA Breakroom Appliance Replacement and Upgrade | Reporting in a dated acquisition-clause heading | Compliance clause, not an analytics deliverable |
| CONVERTER,VIDEO | CRM in a pipe-delimited contact-role/telephone row | Contact metadata, not a CRM requirement |
| ARS Electronic Security Systems amendment | AI Phone in visitor-entry instructions | Use of an entry intercom, not an AI implementation |
| Winter Snow Removal Hill AFB | Software Engineering Group receiving building services | Recipient organisation, not the work being purchased |
| RRS/DFAS Grounds Maintenance and Snow Removal | Personnel contact details entered in an emergency notification system | Contractor administration, not delivery of that system |

The correction masks these syntactic contexts only in matching text. It does not blacklist their tender IDs, titles, countries or industries. Original text and source records remain intact. Recipient context is identified before sentence splitting, so OCR punctuation in a numbered organisation does not detach its technical name from the surrounding role. Exact source spans remain available for evidence.

## Preservation checks

- The affected-candidate comparison across retained canonical records changed only those five candidates, reducing their discovery scores below the inclusion threshold. The other 37 admitted SAM records were preserved. Preservation is not a claim that every remaining record is commercially suitable.
- Regression cases retain a separately requested CRM, AI, reporting or software component, including software work in the same notice as the administrative language. A requirement to provide a software engineering team remains eligible.
- 862 focused classification, multilingual, mixed-scope, cache and SAM tests passed; Ruff passed.
- The separate labelled benchmark retained all 155 relevant examples and rejected all 242 irrelevant examples. Six uncertain/unlabelled cases are excluded from those metrics. This is a sample result, not an internet-wide accuracy claim.

The normal full CI and validated publication process still gates deployment. A classifier change intentionally invalidates its derived cache so retained source evidence is evaluated consistently; later unchanged runs reuse the new decisions.
