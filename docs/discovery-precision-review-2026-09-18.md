# Discovery precision review — 18 September 2026

Reviewed together with the [vocabulary follow-up](discovery-recall-followup-2026-09-18.md).
PR #1 correctly identifies that a classification code can admit a record without proving
Salesforce, business-application or AI scope. This is a conservative discovery fallback:
a classification match must never be presented as a verified delivery capability.

## Decision after independent review

Keep the broader CPV fallback and keep `cpv_requires_corroboration` **false**. Removing the
7931, 7941, 7512 and 7513 families is not safe simply because irrelevant work also uses them.
The same code can corroborate a narrowly evidenced exclusion while retaining a sparse notice.
Real buyers also classify software under consultancy and public-administration codes.

The frozen replay used main revision `6ca021f`, its dataset timestamp, the same 66,866
retained source records, and exact-hash validated cached translations. It made no provider calls.

| Version before corrections | Public candidates | Public awards | Public records removed vs baseline |
| --- | ---: | ---: | ---: |
| Main baseline | 2,900 | 16,302 | — |
| Original PR #1 | 2,657 | 14,821 | 243 |
| Original PR #1 + #2 | 2,660 | 14,870 | 244 (and 4 added) |

The removals included **IT Development Services applied to the improvement of the Logistics
Processes of the National Police Clothing Service** (`sig_2807b213b9b655c3d738`, CPV 79411000)
and **HR, PAYROLL, EMPLOYEE SCREENING SERVICES AND SOFTWARE** (`sig_3489f3ddbf8025940216`,
CPV 79414000). These are counterexamples to safe wholesale removal, not exceptions to hardcode.
The road-safety KPI/dashboard fixture is restored to its original conservative retained decision:
the excerpt alone does not establish that its dashboard lot is irrelevant.

## Improvements retained and corrected

- Disambiguate `AI SENSI` and `AI FINI` locally as Italian prose. Capitalisation percentages
  cannot decide relevance: `PROCUREMENT OF AN AI PLATFORM` must work. A separate real AI
  occurrence in the same title remains usable evidence.
- Treat a funding programme's topical AI mention as a discovery hint rather than a confirmed
  AI implementation. Keep the record reviewable. Affirmative procurement, implementation and
  building an operational AI application still qualify; explicitly negated delivery does not.
- Keep the optional CPV corroboration mechanism disabled. It is available for a future measured
  policy decision, not an automatic next step.
- Keep collection breadth independently configurable; the German collector uses
  `collection_cpv_prefixes`. No collection window, API budget or translation quota is expanded.

## What the evidence does and does not establish

The initial review's probes found no clear missed CRM/AI work among a narrow set of retained
keyword matches. That cannot establish overall recall: it misses unfamiliar wording, records
never collected, and gaps in source coverage. An untagged notice is not necessarily irrelevant.
Do not turn a small sample's estimated noise rate into a measured precision score.

Further tightening requires a labelled, varied corpus containing sparse records, different
languages, historical awards, mixed lots and notices found outside Signal. Inspect new removals
before release; use tiering to manage uncertainty in the meantime.

The accompanying follow-up records regression controls and final combined validation.