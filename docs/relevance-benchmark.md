# Relevance and collection benchmark

Signal now measures two different failure modes: a collected notice being classified incorrectly, and a relevant official notice never being collected. Technical relevance remains separate from lifecycle and bidder eligibility.

## Release regression gate

```powershell
$env:PYTHONPATH='pipeline'
python scripts/relevance_benchmark.py evaluate --output artifacts/relevance-benchmark.json --fail-on-regression
```

The reviewed real-notice fixtures supply the labels. The report includes false negatives, false positives, precision and recall with their different denominators, sample sizes, and breakdowns by source, original language, notice type and evaluation split. Language can be an offline estimate and remains reviewable. Unknown labels do not become negatives. Every disagreement links to the source.

These fixtures were used during policy development. They are explicitly **regression** cases, never called an independent holdout. Wilson intervals describe only the labelled sample and do not correct its deliberate selection or correlations between notices. A high result on these cases is not a population accuracy claim.

## Independent review queue

```powershell
python scripts/relevance_benchmark.py sample --size 180 --newer-than 2026-09-18 --output artifacts/blind-review.json
python scripts/relevance_benchmark.py evaluate --input artifacts/reviewed-holdout.json --output artifacts/holdout-results.json
```

Sampling is deterministic and balances source, geography, notice type, published/unpublished, sparse/detailed and mixed-lot strata. Original-language estimates are recorded for the reviewer. It samples from canonical, archived and rejected records. It does not ask the current classifier to decide the expected labels.

Previously reviewed buyers and related procedures are excluded from the blind queue, including aliases connected by authoritative source identifiers. Cases from one procurement or buyer stay in the same evaluation split. Newer groups are reserved as holdout; a stable hash reserves a further portion. Exact buyer names are conservative boundaries to prevent leakage, not an entity-merging policy.

Reviewers fill `expected` with `retain`, `exclude`, or `uncertain`, add a source-backed rationale and their reviewer identity, and correct estimated language where necessary. Missing attachments or plausible mixed software work should generally remain uncertain/retained for qualification. Do not publish reviewer notes containing private company information. Promote agreed cases into regression fixtures only after evaluating the held-out result; mark them `used_for_policy: true` thereafter.

The initial queue contains 180 cases. A separate Codex agent reviewed 60 without seeing the classifier's labels. This is an agent challenge review requiring human calibration, not human ground truth. The primary review kept plausible specialist software and sparse mixed-scope notices uncertain or retained, and promoted confirmed new policy examples into explicit regression fixtures. The original review and its pre-change result are preserved in the audit working files. The remaining 120 cases are unlabelled. No population precision or recall is claimed from this exercise. Repeat on new buyers, notices and languages as collection expands; do not repeatedly tune against the same holdout.

## Collection controls

```powershell
python scripts/relevance_benchmark.py coverage --output artifacts/collection-controls.json
```

`config/relevance_collection_controls.json` contains independently found, official-source positive controls from the Hermix comparison: Karolinska CRM, Milano-Bicocca admissions CRM, IDA Ireland Salesforce and Istekki's relevant AI/automation components. References are compared against source URLs and explicit aliases, including zero-padded TED numbers. A missing exact reference starts an amendment/procedure investigation; title similarity is not proof of a missing or matching tender.

Record uncollected controls before adding them to the collector or classifier. Refresh their official sources to establish current stage and amendments. The four examples are a small targeted coverage check, not market-wide collection recall. Add an independently sampled set of official search results per source/language; retain source query, date window, sampling method, denominator and judgement evidence with that review. No Hermix data is scraped or used as a replacement public source.

## Release decisions

The automated gate fails on a reviewed false negative or false positive. Investigate each failure, including whether the source has changed, rather than lowering the threshold to make the build pass. Use the full retained-corpus replay for material classification changes. Review affected live records and historical awards separately, preserve exact source facts and translations, and include mixed-lot positive controls. Genuine expiries and corrections must not be counted as relevance losses.
