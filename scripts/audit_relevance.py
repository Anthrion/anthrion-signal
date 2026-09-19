"""Replay every retained notice; separate relevance from availability and preserve evidence."""
import argparse
import gzip
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from anthrion_signal.config import load_config
from anthrion_signal.discovery import discovery_signature, is_public_opportunity, lifecycle, prefilter
from anthrion_signal.models import Signal
from anthrion_signal.translation import available_translations
from anthrion_signal.utils import atomic_json, jsonl_lines, parse_date, read_json, retained_path


def retained_records(root):
    records, locations, canonical_ids = {}, Counter(), set()
    canonical = retained_path(root / "data/signals.jsonl")
    paths = [canonical, *sorted((root / "data/archive").glob("*.jsonl.gz")),
             *sorted((root / "data/discovery/rejected").glob("*.jsonl.gz"))]
    for path in paths:
        if not path.exists():
            continue
        body = gzip.decompress(path.read_bytes()).decode("utf-8") if path.suffix == ".gz" else path.read_text(encoding="utf-8")
        for line in jsonl_lines(body):
            if not line.strip():
                continue
            signal = Signal.model_validate_json(line)
            locations[str(path.relative_to(root))] += 1
            if path == canonical:
                records[signal.id] = signal
                canonical_ids.add(signal.id)
            elif signal.id not in canonical_ids:
                previous = records.get(signal.id)
                stamp = parse_date(signal.updated_at or signal.last_seen_at)
                prior = parse_date(previous.updated_at or previous.last_seen_at) if previous else None
                if previous is None or stamp >= prior:
                    records[signal.id] = signal
    return list(records.values()), dict(locations)


def audit(root, at=None, snapshot=None):
    config = load_config(root)
    published = read_json(snapshot or root / "data/current.json", {})
    now = at or parse_date(published.get("generated_at")) or datetime.now(UTC)
    public_ids = {s["id"] for s in published.get("signals", [])}
    signals, locations = retained_records(root)
    translations = available_translations(root, signals)
    threshold = config["capabilities"]["discovery"]["minimum_candidate_score"]
    rows = []
    # Batches keep progress visible without changing evaluation semantics.
    for start in range(0, len(signals), 1000):
        batch = signals[start:start + 1000]
        prefilter(batch, config["company_profile"], config["search_terms"], config["capabilities"], translations)
        for s in batch:
            relevance = "excluded" if s.exclusion_reasons else "candidate" if s.prefilter_score >= threshold else "below_threshold"
            available = is_public_opportunity(s.model_copy(update={"exclusion_reasons": []}), now)
            overlay = translations.get(s.id, {})
            rows.append({"id": s.id, "source": s.source, "countries": s.countries, "title": overlay.get("title", s.title),
                         "original_title": s.title, "description": overlay.get("description", s.description),
                         "source_hash": s.content_hash, "url": s.primary_source_url, "cpv": s.cpv_codes,
                         "published_before": s.id in public_ids, "available": available,
                         "lifecycle": lifecycle(s, now)[0], "relevance": relevance,
                         "score": s.prefilter_score, "tags": s.matched_capabilities,
                         "evidence": s.capability_evidence, "scope_evidence": s.scope_evidence, "reasons": s.exclusion_reasons})
        print(f"Audited {min(start + 1000, len(signals))}/{len(signals)} retained records", flush=True)
    return {"at": now.isoformat(), "version": config["capabilities"]["version"], "signature": discovery_signature(config), "partitions": locations,
            "counts": {"retained": len(rows), "published_before": len(public_ids),
                       "relevance": dict(Counter(r["relevance"] for r in rows)),
                       "published_excluded": sum(r["published_before"] and r["relevance"] != "candidate" for r in rows),
                       "unpublished_available_candidates": sum(not r["published_before"] and r["available"] and r["relevance"] == "candidate" for r in rows)},
            "records": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--at", help="Fixed ISO timestamp for comparable replays")
    parser.add_argument("--output", type=Path, default=Path("artifacts/relevance-audit.json"))
    args = parser.parse_args()
    result = audit(args.root.resolve(), parse_date(args.at), args.snapshot)
    atomic_json(args.output, result)
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
