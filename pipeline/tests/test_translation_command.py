import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from anthrion_signal.translation import QuotaLedger, TranslationQueue
from anthrion_signal.utils import atomic_json, read_json


@pytest.fixture
def command(tmp_path, monkeypatch, signal):
    path = Path(__file__).resolve().parents[2] / "scripts/translate_records.py"
    spec = importlib.util.spec_from_file_location("translate_command", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    signal.deadline_at = "2099-01-01T00:00:00Z"
    atomic_json(tmp_path / "data/current.json", {
        "generated_at": signal.first_seen_at, "data_updated_at": signal.first_seen_at,
        "profile_version": "test", "scoring_version": "test", "run": {},
        "sources": [], "capabilities": [], "markets": {}, "evidence_catalog": {},
        "signals": [signal.model_dump()],
    })
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setattr(sys, "argv", [str(path), "records", "--root", str(tmp_path), "--github-checkpoint"])
    return module


def test_missing_secret_does_not_spend_or_commit_allowance(command, tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(command.subprocess, "run", lambda *a, **k: pytest.fail("Must not commit without a key"))
    with pytest.raises(SystemExit, match="GEMINI_API_KEY is missing"):
        command.main()
    assert not (tmp_path / "data/translation_quota.json").exists()
    assert not (tmp_path / "data/.translation.lock").exists()


def test_remote_reservation_failure_cannot_make_api_calls(command, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[1] == "push":
            raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(command.subprocess, "run", run)
    monkeypatch.setattr(command, "GeminiTranslator", lambda *a, **k: pytest.fail("No API client before remote checkpoint"))
    with pytest.raises(subprocess.CalledProcessError):
        command.main()
    ledger = QuotaLedger(tmp_path / "data/translation_quota.json")
    assert sum(ledger.state["allocations"]["123-1"]["limits"].values()) == 60
    assert not ledger.state["allocations"]["123-1"].get("started")
    assert not (tmp_path / "data/.translation.lock").exists()
    assert calls[-1] == ["git", "push", "origin", "HEAD:main"]


def test_idle_translation_checks_make_no_requests_or_timestamp_only_commits(command, tmp_path, monkeypatch):
    records = command.Dataset.model_validate(read_json(tmp_path / "data/current.json", {})).signals
    queue = TranslationQueue(tmp_path / "data/translation/cache.json")
    queue.prepare(records)
    for key in queue.active:
        for part in queue.state["fields"][key]["parts"]:
            part["result"] = {"text": part["source"], "language": "en"}
    queue.save()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(command.subprocess, "run", lambda *a, **k: pytest.fail("Idle work must not reserve quota"))
    monkeypatch.setattr(command.GeminiTranslator, "translate", lambda *a, **k: pytest.fail("Idle work must not call the API"))
    command.main()
    before = {file.name: file.read_bytes() for file in (tmp_path / "data/translation").glob("*.json")}
    command.main()
    after = {file.name: file.read_bytes() for file in (tmp_path / "data/translation").glob("*.json")}
    assert before == after


def test_spent_daily_quota_does_not_make_empty_reservation_commits(command, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    ledger = QuotaLedger(tmp_path / "data/translation_quota.json")
    for model in command.DEFAULT_MODELS:
        ledger.allocate(model.name, [model], model.rpd - 1)
    before = ledger.path.read_bytes()
    monkeypatch.setattr(command.subprocess, "run", lambda *a, **k: pytest.fail("No usable quota to reserve"))
    monkeypatch.setattr(command, "GeminiTranslator", lambda *a, **k: pytest.fail("No API requests without quota"))
    command.main()
    assert ledger.path.read_bytes() == before
    assert '"stop_reason": "daily_budget"' in capsys.readouterr().out
