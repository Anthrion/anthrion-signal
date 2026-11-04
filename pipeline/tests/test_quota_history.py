import copy
import gzip
import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from anthrion_signal.translation import ModelBudget, QuotaLedger, RunFinished


@pytest.fixture
def history(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("quota_history")


def ledger(root):
    state = {"version": 1, "allocations": {
        "interrupted-old": {"day": "2026-10-25", "limits": {"gemini-test": 150}, "used": {}, "closed": False},
        "completed-old": {"day": "2026-09-25", "limits": {"gemini-test": 150}, "used": {"gemini-test": 20}, "closed": True},
        "current": {"day": "2026-11-03", "limits": {"gemini-test": 150}, "used": {}, "closed": False},
        "recent": {"day": "2026-11-01", "limits": {"gemini-test": 30}, "used": {"gemini-test": 30}, "closed": True},
    }, "models": {"gemini-test": {"days": {"2026-09-25": 20, "2026-10-25": 150, "2026-11-01": 30, "2026-11-03": 500},
        "recent": [], "blocked_until": 0, "usage": {"promptTokenCount": 123456}}}}
    path = root / "data/translation_quota.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(state), encoding="utf-8")
    return path, state


def test_archival_preserves_exhausted_quota_recent_reservations_and_all_history(history, tmp_path):
    path, original = ledger(tmp_path)
    # UTC has rolled forward; the provider's Pacific quota day is still Nov 3.
    now = datetime(2026, 11, 4, 7, tzinfo=UTC)
    assert history.archive_quota_history(tmp_path, now)
    current = json.loads(path.read_text())
    assert set(current["allocations"]) == {"current", "recent"}
    assert current["models"]["gemini-test"]["days"] == {"2026-11-01": 30, "2026-11-03": 500}
    assert current["models"]["gemini-test"]["usage"] == original["models"]["gemini-test"]["usage"]
    budget = ModelBudget("gemini-test", rpd=500)
    quota = QuotaLedger(path, clock=lambda: now.timestamp())
    assert quota.daily_remaining(budget) == 0
    with pytest.raises(RunFinished):
        quota.allocate("another-run", [budget], 1)
    reconstructed = copy.deepcopy(current)
    for archive in (tmp_path / "data/translation/quota-history").glob("*.json.gz"):
        saved = json.loads(gzip.decompress(archive.read_bytes()))
        reconstructed["allocations"].update(saved["allocations"])
        for model, days in saved["model_days"].items():
            reconstructed["models"][model]["days"].update(days)
    assert reconstructed == original
    assert not history.archive_quota_history(tmp_path, now)


def test_conflicting_history_never_rewrites_the_live_quota(history, tmp_path):
    path, original = ledger(tmp_path)
    target = tmp_path / "data/translation/quota-history/2026-09.json.gz"
    target.parent.mkdir(parents=True)
    target.write_bytes(gzip.compress(json.dumps({"version": 1, "allocations": {
        "completed-old": {"conflicting": True}}, "model_days": {}}).encode()))
    with pytest.raises(ValueError, match="conflicts"):
        history.archive_quota_history(tmp_path, datetime(2026, 11, 4, 7, tzinfo=UTC))
    assert json.loads(path.read_text()) == original
    assert not (target.parent / "2026-10.json.gz").exists()


def test_archive_write_failure_keeps_the_original_live_quota(history, tmp_path, monkeypatch):
    path, original = ledger(tmp_path)
    def fail(*args):
        raise OSError("storage unavailable")
    monkeypatch.setattr(history, "_atomic", fail)
    with pytest.raises(OSError):
        history.archive_quota_history(tmp_path, datetime(2026, 11, 4, 7, tzinfo=UTC))
    assert json.loads(path.read_text()) == original
