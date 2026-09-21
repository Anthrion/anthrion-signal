# Relevance follow-up — 21 September 2026

This follow-up recognises two specific kinds of software opportunity that were retained but did not reach the candidate threshold, and suppresses an evidenced physical-cleaning oversight notice. It is separate from the Context/Canada release. It changes neither source data nor publication timing.

## Confirmed gaps

| Source evidence | Previous result | Change |
| --- | --- | --- |
| [NIWC Pacific's UNACORN GraphRAG call](https://sam.gov/opp/ad6623cf19b4469c8c115be188715232/view) | Three retained postings of the same call scored 0. The existing `RAG` word boundary does not recognise `GraphRAG`. | Recognise `GraphRAG` and `Graph RAG` as generative-AI needs. Each posting scores 44; its existing pre-market classification and response deadline remain unchanged. |
| [Senate of Canada call-queue management RFI](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-659-77090606) | Explicit replacement of a call-queue platform scored 0 despite its stated connection to Teams telephony and bilingual caller experience. | Recognise precise call-queue management system/solution phrases as digital scope. The record scores 12 and remains early engagement, without invented capability tags or a live-tender label. |

The related communications-software vocabulary also covers media monitoring, social-media management/listening and press-office management systems. These are concrete software objects, rather than generic matches on communications, media, management or telephony. Existing negation, operational-use and mixed-lot safeguards apply. A new safeguard covers contractors required to have their own instance of these tools.

The [Senedd media-monitoring procurement](https://www.find-tender.service.gov.uk/Notice/087296-2026) initially looked missing in a sparse Sell2Wales source version. The canonical, fuller Find a Tender record already scored 44 and was correctly surfaced. It is **not** counted as a newly recovered opportunity. The additional vocabulary helps recognise similarly sparse future source descriptions.

[Microsoft's GraphRAG documentation](https://microsoft.github.io/graphrag/) supports the technical alias. Procurement scope, dates and buying stage come from the official source records, not from this technical documentation. None of these matches confirms Anthrion's bidder eligibility.

## Confirmed noise case

[Crous de Nice Toulon's cleaning-contract oversight notice](https://ted.europa.eu/en/notice/-/detail/566653-2026), `sig_6c82bc947b012fa5be86`, was admitted through a broad consultancy classification. Its retained official description commissions supervision of physical cleaning and preparation of the next cleaning procurement, with no digital delivery. A narrow rule now requires both the specific French oversight title and corroborating cleaning-contract scope. It preserves the original record underneath.

Explicit digital delivery, a software/IT classification, or even a sparse stated software component prevents this new exclusion. This is deliberately conservative: a cleaning, catering or care-service domain does not itself make a software purchase irrelevant. Six current UK notices with those domain words were checked and retained because their scope includes operational systems, ordering or scheduling. Two Italian qualification notices also retain their separately listed software and ICT categories.

## Replay and validation

- Inspected canonical records, monthly archives and retained rejections across the available markets. An initial scan covered 208,847 stored versions and reclassified 468 scope-like candidates. This was a discovery aid, not a manually labelled census.
- Resolved source versions to 149,459 unique retained IDs, including the separately collected Canadian snapshot. Scanned original text and valid cached English text for every newly introduced phrase.
- Replayed all 11 affected records with both the merged baseline and this change, using the same 21 September 2026, 12:00 UTC availability cutoff. Admissions increased from 7 to 11: the three US postings of one call, and the Canadian RFI. No previously admitted affected record was lost; original text, IDs, source links and lifecycle results were identical. Unaffected records were not all manually reviewed.
- A separate scan of the 146,558 retained IDs in the baseline found six French cleaning-related titles. Replaying all six changed only the confirmed Crous oversight notice; the other five already had physical-service exclusions. No source facts or lifecycle results changed. The new rule does not impose a general cleaning-industry exclusion.
- The existing benchmark passed all 397 reviewed cases: 155 true positives, 242 true negatives, no false positives or false negatives. Six uncertain/unlabelled cases remain outside those metrics. These results do not establish perfect recall across every market.
- The vocabulary revision passed all 1,619 Python tests locally and its full PR check. The final revision passed 10 focused recall/noise cases locally, including negation, suppliers using their own tools, mixed software/equipment lots and both detailed and sparse software scope in cleaning-related contracts. Ruff and whitespace checks passed. The complete Python suite also runs on the final PR revision. The earlier local pytest cache warning concerned a Windows cache-directory permission; it did not affect test execution.

The existing discovery signature includes both policy contents and classifier source. After this change is merged, the next collection invalidates the classification cache and replays retained rejections before reconciling the latest source updates. A newly recognised notice therefore does not need to be newly published or rediscovered by a source query. Normal availability and terminal-status checks still apply. Original and English source evidence is preserved.

## Further evidence to investigate

[CIPO IT Modernization Phase 3](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/ws5534243802-doc5823087373) is a separate, confirmed description gap. Its public CSV is sparse; the [official anonymous SAP Business Network preview](https://portal.us.bn.cloud.ariba.com/dashboard/public/appext/comsapsbncdiscoveryui#/RfxEvent/preview/1110021099?anId=ANONYMOUS) describes client-facing digital development and enterprise integration. Both the CSV-only record and an in-memory replay with that richer preview scored 0. Fixing it needs bounded source enrichment **and** careful recognition of its functional wording, not just a new generic keyword. Supplier-country and security conditions also require review. Account-only attachments were not accessed. This PR does not claim to fix that separate gap.

Other investigated apparent gaps included expired notices, human case-management services and suppliers' internal quality systems. Those findings did not justify loosening the existing safeguards. No valid source records were deleted by this audit.
