"""Read-only capability audit; English matching is a counterfactual, not a classifier."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from anthrion_signal.config import load_config
from anthrion_signal.discovery import discovery_text, prefilter, search_text
from anthrion_signal.models import Signal
from anthrion_signal.utils import digest


def inspect_dataset(root, path, record_ids=()):
    body = path.read_bytes()
    data = json.loads(body)
    config = load_config(root)
    originals = [Signal.model_validate(row) for row in data["signals"]]
    by_id = {row.id: row for row in originals}
    if len(by_id) != len(originals):
        raise ValueError("Duplicate signal IDs in the snapshot")

    missing = [row for row in originals if not row.matched_capabilities]
    translated = []
    stale = []
    for row in originals:
        overlay = data.get("translations", {}).get(row.id)
        if not overlay:
            continue
        if overlay.get("source_hash") != digest([row.title, row.description]):
            stale.append(row.id)
            continue
        translated.append(row.model_copy(deep=True, update={
            "title": overlay["title"], "description": overlay["description"],
        }))

    prefilter(translated, config["company_profile"], config["search_terms"], config["capabilities"])
    tests = {row.id: row for row in translated}
    added = [row for row in translated if not by_id[row.id].matched_capabilities and row.matched_capabilities]
    # The generated relationship-database hit also counts as a needs inference
    # in the production matcher, although it is not a configured literal phrase.
    scope_terms = {search_text(term) for cap in config["capabilities"]["capabilities"]
                   for term in cap.get("explicit", []) + cap.get("needs", []) + cap.get("aliases", [])}
    context_only = []
    for row in added:
        text = discovery_text(row.title + " " + row.description)
        if (not any(term in text for term in scope_terms)
                and "relationship-management database" not in row.prefilter_matches):
            context_only.append(row)

    markets = defaultdict(lambda: {"total": 0, "untagged": 0, "new_english_matches": 0})
    sources = defaultdict(lambda: {"total": 0, "untagged": 0})
    added_ids = {row.id for row in added}
    cpv_groups = Counter()
    for row in originals:
        market = markets[",".join(row.countries) or "unknown"]
        market["total"] += 1
        market["untagged"] += not bool(row.matched_capabilities)
        market["new_english_matches"] += row.id in added_ids
        sources[row.source]["total"] += 1
        sources[row.source]["untagged"] += not bool(row.matched_capabilities)
        if not row.matched_capabilities:
            prefixes = tuple(config["search_terms"]["cpv_prefixes"])
            cpv_groups.update({code[:2] if code.startswith(("48", "72")) else code[:4]
                               for code in row.cpv_codes if code.startswith(prefixes)})

    samples = []
    for identifier in record_ids:
        row = by_id[identifier]
        test = tests.get(identifier)
        samples.append({
            "id": identifier,
            "source_url": row.primary_source_url,
            "title": test.title if test else row.title,
            "source_capabilities": row.matched_capabilities,
            "source_matches": row.prefilter_matches,
            "english_test_capabilities": test.matched_capabilities if test else None,
            "english_test_matches": test.prefilter_matches if test else None,
            "english_test_exclusions": test.exclusion_reasons if test else None,
        })

    if path.read_bytes() != body:
        raise RuntimeError("Snapshot changed during audit; rerun against a stable snapshot")
    return {
        "generated_at": data["generated_at"],
        "content_digest": data["run"]["content_digest"],
        "records": len(originals),
        "untagged": len(missing),
        "untagged_all_cpv_only": all(row.prefilter_matches == ["Relevant CPV classification"] for row in missing),
        "untagged_description_at_most_180_characters": sum(len(row.description) <= 180 for row in missing),
        "untagged_description_equals_title": sum(row.description.strip() == row.title.strip() for row in missing),
        "english_overlays_tested": len(translated),
        "stale_overlays_skipped": stale,
        "new_english_matches": len(added),
        "new_english_context_only_matches": len(context_only),
        "cpv_groups_for_untagged_overlapping": dict(cpv_groups),
        "markets_disjoint": dict(markets),
        "sources": dict(sources),
        "records_reviewed": samples,
        "note": "Matches are diagnostic, not verified relevance or supplier eligibility. No production data is written.",
    }


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=root / "app/public/data/current.json")
    parser.add_argument("--record", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(inspect_dataset(root, args.snapshot, args.record), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
