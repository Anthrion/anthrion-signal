"""Reclassify a frozen public snapshot without touching canonical data or checkpoints."""
import argparse
import json
from collections import Counter
from pathlib import Path

from anthrion_signal.config import load_config
from anthrion_signal.discovery import prefilter
from anthrion_signal.models import Signal
from anthrion_signal.utils import atomic_json, digest, read_retained_bytes, retained_path


def compare(path, root):
    path = retained_path(path)
    source = path.read_bytes()
    data = json.loads(read_retained_bytes(path))
    old = {s["id"]: s for s in data["signals"]}
    signals = [Signal.model_validate(s) for s in old.values()]
    config = load_config(root)
    prefilter(signals, config["company_profile"], config["search_terms"], config["capabilities"], data.get("translations", {}))
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    retained = [s for s in signals if s.prefilter_score >= threshold and not s.exclusion_reasons]
    retained_ids = {s.id for s in retained}
    def entry(s):
        original = old[s.id]
        english = data.get("translations", {}).get(s.id, {})
        return {"id": s.id, "source": s.source, "countries": s.countries,
                "title": english.get("title", s.title), "description": english.get("description", s.description),
                "original_title": s.title, "original_description": s.description, "url": s.primary_source_url,
                "before": original["matched_capabilities"], "after": s.matched_capabilities,
                "score": s.prefilter_score, "reasons": s.exclusion_reasons, "evidence": s.capability_evidence}
    result = {"snapshot": data.get("generated_at"), "snapshot_hash": digest(data),
              "before": len(signals), "after": len(retained),
              "untagged_before": sum(not s["matched_capabilities"] for s in old.values()),
              "untagged_after": sum(not s.matched_capabilities for s in retained),
              "newly_tagged": sum(not old[s.id]["matched_capabilities"] and bool(s.matched_capabilities) for s in retained),
              "countries_before": dict(Counter(c for s in signals for c in s.countries)),
              "countries_after": dict(Counter(c for s in retained for c in s.countries)),
              "removed": [entry(s) for s in signals if s.id not in retained_ids],
              "changed": [entry(s) for s in retained if old[s.id]["matched_capabilities"] != s.matched_capabilities]}
    assert path.read_bytes() == source
    assert all(old[s.id][key] == getattr(s, key) for s in signals for key in
               ("title", "description", "content_hash", "raw_source_hash", "first_seen_at"))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--snapshot", type=Path, default=Path("app/public/data/current.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/discovery-release-audit.json"))
    args = parser.parse_args()
    report = compare(args.snapshot, args.root)
    atomic_json(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("removed", "changed")}, indent=2))
    print(f"Review {len(report['removed'])} removals and {len(report['changed'])} tag changes in {args.output}")
