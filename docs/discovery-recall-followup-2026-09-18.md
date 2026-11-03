# Discovery vocabulary and regression review — 18 September 2026

PR #2 contains useful coverage improvements, reviewed together with
[PR #1's admission changes](discovery-precision-review-2026-09-18.md). The final implementation
keeps wider evidence vocabulary while preserving the broad classification fallback.

## Behaviour retained

English compounds such as content management system, learning management system, records
management system and named website delivery work now supply digital-scope evidence. This can
retain a candidate without inventing a Salesforce capability. A short title such as **RFI AI
Interpreter** can establish an AI service even without a long technical description.

## Corrections made before merge

| Risk in the proposed code | Corrected behaviour |
| --- | --- |
| All-capitals AI titles lose their evidence | Judge individual acronym occurrences, preserving uppercase English scope and excluding Italian prepositional clauses. |
| Any title containing MCP/RAG becomes AI | The short-title shortcut applies only to AI with functional context. MCP joint prostheses and red/amber/green training do not gain AI tags. |
| A GPU/inference phrase suppresses an entire segment | Capacity-only purchases stay outside the AI tier, while affirmative AI application delivery in the same segment survives. |
| A Bietercockpit name deletes the whole sentence | Mask the named bidding client in matching text while retaining CRM or other deliverables beside it. Original source text stays unchanged. |
| Quality certification appears to be software | A quality-management process alone is not software; SaaS/platform/software delivery still counts. |
| Physical warning equipment appears to be a business system | Siren/loudspeaker-only notification systems do not establish digital scope; separate software delivery survives. |
| An existing tender portal becomes purchased scope | Submission/document-access boilerplate does not qualify. Building a portal still does, including mixed sentences. |
| A supplier ordering tool or framework name becomes purchased software | Check the phrase's role in the purchase. Ordering books through a supplier's system and buying hardware through a Digital Workplace framework do not buy those systems. Explicit development and maintenance still count. |
| A booking-system title hides a venue-hire purchase | Corroborating physical-service scope prevents the software inference. Actual booking software and sparse system notices remain candidates. |
| Funding to build AI software loses its AI tier | Affirmative application delivery counts; explicitly negated implementation/procurement remains only a topical hint. |
| Broad CPV removal hides genuine software work | Restore the broad fallback and original reviewed dashboard fixture; keep stricter corroboration disabled. |

These changes are **not monotonic**: correcting false acronym or boilerplate matches can remove
tags or, without other evidence, admission. Counts alone cannot demonstrate safety.
Independent positive and negative controls cover these boundaries, and a frozen replay compares
all 66,866 retained records at the same source timestamp with unchanged source hashes.

## Verification and limitations

The original stacked PRs passed 797 tests. An initial independent 32-case regression set
exposed 21 failures, covering false exclusions and false capability claims. The independent
set now contains 49 cases, including supplier tools, framework routes, cross-sentence
certification context and positive controls for real software delivery. Full-suite, export
validation and final replay results are recorded in the pull-request review before merge.

The combined release with the source-security and JSON Lines repairs passed **875 Python
tests**, lint and **40 frontend unit tests**. The separate security release also passed the
complete production browser suite: 121 passed, one intentional mobile skip.

The final frozen replay retained the same **66,866 source records with unchanged hashes**.
These are record-level eligibility counts at `2026-09-18T11:53:56+00:00`, before the exporter
reconciles procurement identities; they are not a claim about the current live-site counts.

| Frozen replay | Main baseline | Corrected combined changes |
| --- | ---: | ---: |
| Eligible opportunity records | 2,900 | 2,901 |
| Eligible historical award records | 16,302 | 16,310 |
| Opportunity records in the platform tier | 370 | 370 |

Three opportunities are newly retained: as-needed website design, an LMS options notice,
and a learning/talent/performance platform. Two records lose admission: clinical test-control
supplies whose only AI match was `AI SENSI`, and waterway maintenance whose only AI match was
the bidding client's name. The three removed historical awards likewise relied on `AI SENSI`
in a legal clause, without separate evidence of AI or a business-application deliverable.
Eleven historical candidates are added. Some, such as market research about a proposed web
portal, remain exploratory buyer context rather than confirmed implementation opportunities.

Fifty-seven existing opportunity records change tags or priority. The original platform-tier
records remain in that tier; most demotions remove false AI evidence or distinguish topical
research funding from AI delivery. Positive AI tool-development funding controls remain retained.
Every changed admission was inspected; counts alone were not used as the acceptance test.

Existing exact-hash translation, original-text preservation, mixed-lot, quantum-scope, award
history, collection-state and publication safeguards remain part of verification. No live
collection, paid provider request, frontend feature or GitHub policy change is introduced here.

## Follow-up research, outside this change

- Measure collection recall with externally found notices, rather than only searching the current
  rejection store. Different countries and sources are not interchangeable control populations.
- Derive the TED collection CPV expression from explicitly reviewed collection configuration
  before changing its breadth. The independent field is currently used by Germany.
- Add labelled examples for unfamiliar wording and translated scope. Do not replace evidence-local
  exclusions with whole-sector or single-word blacklists.
