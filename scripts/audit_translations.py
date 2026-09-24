"""Audit a published dataset without changing records, cache state or provider quotas."""

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from anthrion_signal.translation import (
    VERSION,
    translation_text,
    untranslated_prose,
    validate_translation,
)
from anthrion_signal.utils import digest, read_json


def audit_dataset(dataset):
    translations = dataset.get("translations", {})
    countries = defaultdict(Counter)
    outstanding = []
    for signal in dataset["signals"]:
        entry = translations.get(signal["id"])
        problems = []
        if not entry:
            problems.append("missing_pair")
        else:
            source = [signal["title"], signal.get("description", "")]
            if entry.get("version") != VERSION or entry.get("source_hash") != digest(source):
                problems.append("stale_source")
            for field, original in zip(("title", "description"), source):
                text = entry.get(field)
                if not isinstance(text, str) or (original.strip() and not text.strip()):
                    problems.append(f"{field}:missing_text")
                elif original.strip():
                    names = [signal.get("buyer_name")]
                    if translation_text(text) != text:
                        problems.append(f"{field}:encoded_characters")
                    elif untranslated_prose(text, names, original):
                        problems.append(f"{field}:foreign_prose")
                    elif not validate_translation(original, {"text": text, "language": "mul"}, names):
                        problems.append(f"{field}:failed_validation")
        for country in set(signal.get("countries", [])):
            countries[country]["records"] += 1
            countries[country]["complete"] += not problems
        if problems:
            outstanding.append({
                "id": signal["id"], "title": signal["title"], "countries": signal.get("countries", []),
                "first_seen_at": signal.get("first_seen_at"), "problems": problems,
                "source_url": signal.get("primary_source_url"),
            })
    return {
        "generated_at": dataset.get("generated_at"), "records": len(dataset["signals"]),
        "complete_records": len(dataset["signals"]) - len(outstanding),
        "outstanding_records": outstanding, "by_country": dict(sorted(countries.items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("app/public/data/current.json"))
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    audit = audit_dataset(read_json(args.dataset, {}))
    print(json.dumps(audit, ensure_ascii=True, indent=2))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(f"## Published English coverage\n\nComplete titles and descriptions: "
                         f"**{audit['complete_records']} / {audit['records']}**. "
                         "Supplementary organisation renderings are counted separately from notice coverage.\n\n")
            for record in audit["outstanding_records"]:
                stream.write(f"- `{record['id']}` ({', '.join(record['countries'])}): "
                             f"{', '.join(record['problems'])}\n")
    if args.require_complete and audit["outstanding_records"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
