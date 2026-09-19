"""Re-read structured fields for existing public TED notices; dry-run by default."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from anthrion_signal.collectors import Http, RawRecord, TED_FIELDS
from anthrion_signal.config import load_config
from anthrion_signal.dedupe import merge
from anthrion_signal.discovery import is_public_opportunity, lifecycle, prefilter
from anthrion_signal.models import Signal
from anthrion_signal.normalise import normalise_ted
from anthrion_signal.utils import (atomic_bytes, atomic_json, atomic_retained_bytes, digest,
                                  jsonl_lines, parse_date, read_json, read_retained_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    now = datetime.now(UTC)
    config = load_config(root)
    source = next(s for s in config["sources"]["sources"] if s["id"] == "ted")
    public = read_json(root / "data/current.json", {})
    public_ids = {s["id"] for s in public["signals"]}
    path = root / "data/signals.jsonl"
    original = read_retained_bytes(path)
    previous = [Signal.model_validate_json(line) for line in jsonl_lines(original.decode("utf-8"))]
    targets = {alias[4:]: s for s in previous if s.id in public_ids and s.source == "ted"
               for alias in s.external_ids if alias.startswith("ted:")}
    artifact = root / "artifacts/ted-metadata-repair"
    cache_path = artifact / "notices.json"
    cache = read_json(cache_path, {})
    fetched = parse_date(cache.get("fetched_at"))
    if cache.get("fields_digest") != digest(TED_FIELDS) or not fetched or now - fetched > timedelta(days=1):
        cache = {"fields_digest": digest(TED_FIELDS), "fetched_at": now.isoformat(), "notices": {}}
    pending = sorted(set(targets) - set(cache["notices"]))
    http = Http()
    try:
        for offset in range(0, len(pending), 100):
            batch = pending[offset:offset + 100]
            body = {"query": "publication-number IN (" + " ".join(batch) + ")", "fields": TED_FIELDS,
                    "limit": 100, "paginationMode": "PAGE_NUMBER", "scope": "ALL"}
            response = http.request("POST", source["url"], json=body).json()
            if not isinstance(response.get("notices"), list) or response.get("timedOut"):
                raise ValueError("TED repair returned an incomplete response; no canonical data changed")
            for notice in response["notices"]:
                number = notice.get("publication-number")
                if number not in batch:
                    raise ValueError("TED repair returned an unexpected publication number")
                cache["notices"][number] = notice
            atomic_json(cache_path, cache)
            print(f"Checked {min(offset + 100, len(pending))}/{len(pending)} outstanding notices", flush=True)
    finally:
        http.close()
    replacements = {}
    for number, old in targets.items():
        if number not in cache["notices"]:
            continue
        fresh = normalise_ted(RawRecord(cache["notices"][number], source, now.isoformat(), "ted"))
        if fresh:
            replacements[old.id] = merge(replacements.get(old.id, old), fresh)[0]
    revised = [replacements.get(s.id, s) for s in previous]
    prefilter(revised, config["company_profile"], config["search_terms"], config["capabilities"])
    removed = [{"id": s.id, "title": s.title, "reason": lifecycle(s, now)[1], "url": s.primary_source_url}
               for s in revised if s.id in public_ids and not is_public_opportunity(s, now)]
    report = {"at": now.isoformat(), "public_before": len(public_ids), "ted_notices_checked": len(replacements),
              "missing_notice_numbers": sorted(set(targets) - set(cache["notices"])),
              "newly_suppressed": len(removed), "removed": removed, "applied": False}
    atomic_json(artifact / "report.json", report)
    atomic_bytes(artifact / "signals.candidate.jsonl", ("\n".join(s.model_dump_json() for s in revised) + "\n").encode())
    if args.apply:
        if {s.id for s in previous} != {s.id for s in revised}:
            raise ValueError("Repair must preserve every existing record identity")
        lock = root / "data/.lock"
        with lock.open("x"):
            pass
        try:
            if read_retained_bytes(path) != original:
                raise ValueError("Canonical data changed during the audit; repeat the repair")
            atomic_bytes(artifact / ("signals.before-" + digest(original.hex())[:12] + ".jsonl"), original)
            atomic_retained_bytes(path, ("\n".join(s.model_dump_json() for s in revised) + "\n").encode())
            report["applied"] = True
            atomic_json(artifact / "report.json", report)
        finally:
            lock.unlink()
    print(json.dumps({k: v for k, v in report.items() if k != "removed"}, indent=2))


if __name__ == "__main__":
    main()
