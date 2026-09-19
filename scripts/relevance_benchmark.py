"""Reviewable relevance benchmarks, blind sampling and independent collection controls.

No provider calls. Labels are explicit review decisions, never inferred from the classifier.
Curated regression accuracy is not population precision or internet-wide recall.
"""
import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from anthrion_signal.config import load_config
from anthrion_signal.discovery import discovery_signature, prefilter
from anthrion_signal.models import Signal
from anthrion_signal.utils import atomic_json


def stable(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def group_cases(cases):
    """Keep related procedures AND repeated buyers together to prevent leakage.

    Exact names are conservative split boundaries, not assertions of legal identity.
    In particular, do not use this grouping to merge production records.
    """
    parents = list(range(len(cases)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        parents[max(a, b)] = min(a, b)

    seen = {}
    for i, case in enumerate(cases):
        s = case["signal"]
        tokens = [f"id:{s['id']}"]
        if s.get("ocid"):
            tokens.append(f"ocid:{s['ocid']}")
        # Namespaced notice aliases link national and TED copies of one notice.
        tokens.extend(f"external:{v}" if ":" in v else f"external:{s.get('source')}:{v}"
                      for v in s.get("external_ids", []))
        tokens.extend(f"procedure:{v}" for v in s.get("procedure_identifiers", []))
        tokens.extend(f"buyer:{v}" if re.match(r"(?:[A-Z]{2}-[A-Z0-9]+|grants-agency):", v)
                      else f"buyer:{s.get('source')}:{','.join(sorted(s.get('countries', [])))}:{v}"
                      for v in s.get("buyer_identifiers", []))
        if s.get("buyer_name"):
            name = " ".join(s["buyer_name"].casefold().split())
            tokens.append(f"buyer-name:{','.join(sorted(s.get('countries', [])))}:{name}")
        for token in tokens:
            if token in seen:
                union(i, seen[token])
            else:
                seen[token] = i
    members = defaultdict(list)
    for i, case in enumerate(cases):
        members[find(i)].append(case["signal"]["id"])
    keys = {root: stable("|".join(sorted(ids)))[:20] for root, ids in members.items()}
    return [keys[find(i)] for i in range(len(cases))]


def assign_splits(cases, newer_than=None):
    groups = group_cases(cases)
    reserved = {group for case, group in zip(cases, groups)
                if newer_than and (case["signal"].get("published_at") or "")[:10] >= newer_than}
    result = []
    for case, group in zip(cases, groups):
        # Already used to tune policy: never relabel a regression fixture as held out.
        split = "regression" if case.get("used_for_policy", False) else (
            "holdout" if group in reserved or int(group[:8], 16) % 5 == 0 else "development")
        result.append({**case, "group": group, "split": split})
    # A reviewed/training case prevents the whole related group being called unseen.
    contaminated = {c["group"] for c in result if c["split"] == "regression"}
    for case in result:
        if case["group"] in contaminated:
            case["split"] = "regression"
    return result


def wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    rate, denominator = successes / total, 1 + z * z / total
    middle = (rate + z * z / (2 * total)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [max(0, middle - half), min(1, middle + half)]


def metrics(rows):
    reviewed = [r for r in rows if r["expected"] in {"retain", "exclude"}]
    counts = Counter((r["expected"], r["predicted"]) for r in reviewed)
    tp, fn = counts["retain", "retain"], counts["retain", "exclude"]
    fp, tn = counts["exclude", "retain"], counts["exclude", "exclude"]
    return {"reviewed": len(reviewed), "unlabelled_or_uncertain": len(rows) - len(reviewed),
            "true_positive": tp, "false_negative": fn, "false_positive": fp, "true_negative": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "precision_wilson_95": wilson(tp, tp + fp), "recall_wilson_95": wilson(tp, tp + fn)}


def evaluate(cases, root):
    from anthrion_signal.translation import source_language_hint
    config = load_config(root)
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    rows = []
    for case in cases:
        s = Signal.model_validate(case["signal"])
        prefilter([s], config["company_profile"], config["search_terms"], config["capabilities"],
                  {s.id: case["translation"]} if case.get("translation") else {})
        language = case.get("language")
        if not language or language == "not_recorded":
            language = source_language_hint(f"{s.title}\n{s.description}"[:3000])
        rows.append({"id": s.id, "source": s.source, "countries": s.countries,
                     "notice_type": s.signal_type, "language": language,
                     "language_basis": "Reviewed label or offline estimate of original text; inspect mixed-language cases",
                     "split": case.get("split", "regression"), "group": case.get("group"),
                     "expected": case.get("expected"),
                     "predicted": "retain" if s.prefilter_score >= threshold and not s.exclusion_reasons else "exclude",
                     "source_url": s.primary_source_url, "rationale": case.get("rationale", "")})
    breakdowns = {}
    for field in ("source", "language", "notice_type", "split"):
        values = sorted({r[field] for r in rows})
        breakdowns[field] = {v: metrics([r for r in rows if r[field] == v]) for v in values}
    return {"schema_version": "1.0", "engine": discovery_signature(config),
            "scope": "Labelled benchmark only; not a population or internet-wide recall estimate.",
            "interval_note": "Wilson binomial intervals describe this sample; they do not correct selection bias or related-case dependence.",
            "metrics": metrics(rows), "strata": breakdowns, "records": rows}


def sample_queue(signals, public_ids, known_cases, size=180, seed="signal-review-v1", newer_than=None):
    """Blind queue: exclude previously reviewed buyer/procedure groups, not just IDs."""
    existing = [{**c, "used_for_policy": True} for c in known_cases]
    pool = [{"signal": s.model_dump(), "expected": None, "rationale": "", "reviewer": "",
             "language": "not_recorded", "used_for_policy": False} for s in signals]
    combined = assign_splits(existing + pool, newer_than)
    candidates = [c for c in combined[len(existing):] if c["split"] != "regression"]
    buckets = defaultdict(list)
    for case in candidates:
        s = case["signal"]
        stratum = (s["source"], ",".join(sorted(s["countries"])), s["signal_type"],
                   "published" if s["id"] in public_ids else "retained_not_published",
                   "sparse" if len(s["description"]) < 250 else "detailed",
                   "mixed_lots" if len(s.get("lot_ids", [])) > 1 or re.search(r"\b(?:lot|los|lote|lotto)\s*\d", s["description"], re.I) else "unspecified")
        # Blind labels: no current score, tag, exclusion reason or model suggestion.
        case["signal"] = {k: v for k, v in s.items() if k not in {
            "analysis", "prefilter_score", "prefilter_matches", "matched_capabilities", "capability_evidence",
            "scope_evidence", "exclusion_reasons", "discovery_families", "delivery_priority", "recommendation",
            "fit_score", "score_components", "score_explanation", "confidence_score", "known_weight",
            "categories", "delivery_role", "discovery_version", "lifecycle_reason", "ai_status",
            "ai_scored_at", "ai_model", "analysis_cache_key"}}
        case["sampling_stratum"] = list(stratum)
        buckets[stratum].append(case)
    for bucket in buckets.values():
        bucket.sort(key=lambda c: stable(f"{seed}:{c['signal']['id']}"))
    ordered = sorted(buckets, key=lambda key: stable(f"{seed}:{key}"))
    chosen, used_groups = [], set()
    while len(chosen) < size and any(buckets.values()):
        for key in ordered:
            while buckets[key]:
                case = buckets[key].pop(0)
                if case["group"] not in used_groups:
                    chosen.append(case)
                    used_groups.add(case["group"])
                    break
            if len(chosen) >= size:
                break
    return chosen


def collection_controls(signals, controls):
    """Match verified source references/explicit aliases; never guess from titles."""
    index = defaultdict(set)
    for s in signals:
        facts = [s.primary_source_url, *s.source_urls, *s.external_ids]
        for fact in facts:
            for number, year in re.findall(r"(?<!\d)(\d{1,8})-(20\d{2})(?!\d)", fact):
                index[f"{int(number)}-{year}"].add(s.id)
    rows = []
    for c in controls:
        ids = set().union(*(index.get(ref, set()) for ref in [c["notice"], *c.get("aliases", [])]))
        rows.append({**c, "collected": bool(ids), "record_ids": sorted(ids),
                     "interpretation": "Exact official reference/alias match" if ids else "Not found by reference; inspect official amendments before confirming a gap"})
    return {"scope": "Known positive source controls, not market-wide collection recall.",
            "matched": sum(r["collected"] for r in rows), "total": len(rows), "records": rows}


def load_regressions(root):
    cases = []
    for name in ("relevance_review.json", "relevance_review_2026_09_18.json", "purchased_scope_review_2026_09_18.json",
                 "multilingual_scope_review_2026_09_18.json"):
        cases.extend(json.loads((root / "pipeline/tests/fixtures" / name).read_text(encoding="utf-8")))
    # Multiple revisions of one ID may legitimately be separate tests. Keep them
    # in the same split, but do not pretend they are independent observations.
    return [{**c, "used_for_policy": True} for c in cases]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["evaluate", "sample", "coverage"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--newer-than", help="ISO date reserving newer buyers/procedures as holdout")
    parser.add_argument("--size", type=int, default=180)
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()
    if args.size < 1 or args.size > 10000:
        parser.error("size must be between 1 and 10000")
    root = args.root.resolve()
    if args.command == "evaluate":
        cases = json.loads(args.input.read_text(encoding="utf-8")) if args.input else load_regressions(root)
        result = evaluate(assign_splits(cases, args.newer_than), root)
    else:
        from audit_relevance import retained_records
        data_root = (args.data_root or root).resolve()
        signals, _ = retained_records(data_root)
        if args.command == "coverage":
            controls = json.loads((args.input or root / "config/relevance_collection_controls.json").read_text(encoding="utf-8"))
            result = collection_controls(signals, controls)
        else:
            from anthrion_signal.translation import source_language_hint
            current = json.loads((data_root / "data/current.json").read_text(encoding="utf-8"))
            result = sample_queue(signals, {s["id"] for s in current["signals"]}, load_regressions(root),
                                  args.size, newer_than=args.newer_than)
            for case in result:
                s = case["signal"]
                case["language"] = source_language_hint(f"{s['title']}\n{s['description']}"[:3000])
                case["language_basis"] = "Offline estimate; reviewer should confirm, including mixed-language text"
    atomic_json(args.output, result)
    if isinstance(result, dict):
        print(json.dumps({k: v for k, v in result.items() if k not in {"records", "strata"}}, ensure_ascii=False))
    else:
        print(f"Saved {len(result)} unlabelled, stratified cases for independent review.")
    if args.command == "evaluate" and args.fail_on_regression and (
            result["metrics"]["false_negative"] or result["metrics"]["false_positive"]):
        raise SystemExit("Reviewed relevance regression: inspect the benchmark report.")


if __name__ == "__main__":
    main()
