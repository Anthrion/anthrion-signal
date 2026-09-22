"""Run capped private translation tests or build a static translation sidecar.

This does not collect, deploy, call Gemini from the browser, or overwrite source records.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from anthrion_signal.discovery import is_public_award, is_public_opportunity
from anthrion_signal.models import Dataset
from anthrion_signal.translation import (
    DEFAULT_MODELS,
    GeminiTranslator,
    QuotaLedger,
    RunFinished,
    TranslationQueue,
    field_key,
    translation_lock,
)
from anthrion_signal.utils import atomic_bytes, atomic_json, atomic_retained_json, read_json, read_retained_bytes, jsonl_lines


def translation_records(root, now):
    if (root / "config/capabilities.yaml").exists():
        from anthrion_signal.award_history import prepare_awards
        from anthrion_signal.cli import prepare_current

        data, canonical, config = prepare_current(root, save_cache=True)
        awards = prepare_awards(root, canonical, config, now)[0]
        candidates = data.signals
    else:
        candidates = Dataset.model_validate(read_json(root / "data/current.json", {})).signals
        awards = [signal for signal in candidates if is_public_award(signal, now)]
    current = [signal for signal in candidates if is_public_opportunity(signal, now)]
    return current, awards


def notice_coverage(queue, groups, reviewed=()):
    return {name: {"records": len(records),
                   "complete": sum(signal.id in reviewed or bool(queue.overlay([signal])["signals"])
                                   for signal in records)}
            for name, records in groups.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "benchmark", "records"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--models", default=",".join(m.name for m in DEFAULT_MODELS))
    parser.add_argument("--max-calls", type=int, default=60)
    parser.add_argument("--max-seconds", type=int, default=480)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--github-checkpoint", action="store_true")
    args = parser.parse_args()
    budgets = {m.name: m for m in DEFAULT_MODELS}
    names = args.models.split(",")
    if len(set(names)) != len(names) or not set(names).issubset(budgets):
        parser.error("Only unique, explicitly verified translation models are allowed")
    if not 1 <= args.max_calls <= sum(budgets[name].rpd for name in names) or not 1 <= args.max_seconds <= 1800:
        parser.error("Use a positive call count within the selected models' daily limits and a 1-1800 second run budget")
    root = args.root.resolve()
    if args.github_checkpoint and (args.mode != "records" or os.getenv("GITHUB_ACTIONS") != "true"):
        parser.error("GitHub checkpoints are only for the records job in GitHub Actions")
    output = args.output_dir or (root / "artifacts/translation-benchmark/gemini" / "+".join(names) / "benchmark"
                                 if args.mode == "benchmark" else root / "data/translation")
    load_dotenv(root / ".env")
    records, corpus, groups, reviewed = [], [], {}, {}
    with translation_lock(root / "data"):
        queue = TranslationQueue(output / "cache.json")
        if args.mode == "benchmark":
            path = root / "artifacts/translation-benchmark/float32/results.jsonl"
            corpus = [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]
            ids = {entry["id"] for entry in corpus}
            buyers = {record["id"]: record.get("buyer_name")
                      for line in jsonl_lines(read_retained_bytes(root / "data/signals.jsonl").decode("utf-8"))
                      if (record := json.loads(line))["id"] in ids}
            for entry in corpus:
                queue.add(entry["source"], [buyers.get(entry["id"])])
        else:
            now = datetime.now(UTC)
            current, awards = translation_records(root, now)
            groups = {"current": current, "awards": awards}
            records = current + awards
            queue.prepare(current, awards=awards)
            from anthrion_signal.translation_reviews import prioritize_unreviewed_translations
            reviewed = prioritize_unreviewed_translations(root, records, queue)
        characters = sum(sum(len(part["source"]) for part in queue.state["fields"][key]["parts"])
                         for key in queue.active if queue.completed(key) is None)
        print(json.dumps({"mode": args.mode, "unique_fields": len(queue.active),
                          "pending_characters": characters, "models": names,
                          "notice_coverage": notice_coverage(queue, groups, reviewed)}), flush=True)
        if args.mode == "plan":
            return
        ledger = QuotaLedger(root / "data/translation_quota.json")
        models = [budgets[name] for name in names]
        pending = any(next(queue.pending(model), None) for model in models)
        key = os.getenv("GEMINI_API_KEY")
        if pending and not key:
            if args.mode == "records":
                atomic_retained_json(output / "translations.en.json", queue.overlay(records))
            raise SystemExit("GEMINI_API_KEY is missing; existing translations retained")
        if args.github_checkpoint and pending:
            identifier = f"{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}"
            try:
                ledger.allocate(identifier, models, args.max_calls, minimum_calls=2)
            except RunFinished as exc:
                atomic_retained_json(output / "translations.en.json", queue.overlay(records))
                print(json.dumps({"stop_reason": exc.reason, "api_calls": 0}), flush=True)
                return
            for command in (
                ["git", "config", "user.name", os.getenv("SIGNAL_GIT_NAME", "github-actions[bot]")],
                ["git", "config", "user.email", os.getenv(
                    "SIGNAL_GIT_EMAIL", "41898282+github-actions[bot]@users.noreply.github.com")],
                ["git", "add", "data/translation_quota.json"],
                [sys.executable, str(Path(__file__).with_name("automation_git_guard.py")), "staged"],
                ["git", "commit", "-m", "Reserve private translation quota [skip ci]"],
                [sys.executable, str(Path(__file__).with_name("automation_git_guard.py")), "unpushed"],
                [sys.executable, str(Path(__file__).with_name("push_data.py"))],
            ):
                subprocess.run(command, cwd=root, check=True)
            ledger.activate(identifier)
        translator = GeminiTranslator(key if pending else "unused", ledger,
                                      max_calls=args.max_calls, max_seconds=args.max_seconds)
        try:
            summary = queue.run(translator, models,
                                progress=lambda value: print(json.dumps(value), flush=True))
        finally:
            translator.close()
        ledger.finish_allowance()
        summary.update(input_characters=sum(sum(len(p["source"]) for p in queue.state["fields"][key]["parts"])
                                            for key in queue.active), models=names,
                       finished_at=datetime.now(UTC).isoformat(),
                       notice_coverage=notice_coverage(queue, groups, reviewed))
        if corpus:
            rows = [{**entry, "previous_english": entry["english"],
                     "english": queue.completed(field_key(entry["source"]))} for entry in corpus]
            atomic_bytes(output / "results.jsonl", ("\n".join(json.dumps(row) for row in rows) + "\n").encode())
        else:
            atomic_retained_json(output / "translations.en.json", queue.overlay(records))
        previous = read_json(output / "summary.json", {})
        # Idle checks should not create timestamp-only commits every fifteen minutes.
        def meaningful(value):
            return {k: v for k, v in value.items() if k != "finished_at"}
        if summary["api_calls"] or meaningful(summary) != meaningful(previous):
            atomic_json(output / "summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
