import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ARTIFACT = {"id": 123, "name": "github-pages-456-1", "expired": False}


@pytest.fixture
def check(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/wait_pages_artifact.py"
    spec = importlib.util.spec_from_file_location("wait_pages_artifact", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "sleep", lambda delay: None)
    return module


def test_uploaded_artifact_may_become_visible_after_an_empty_listing(check, monkeypatch):
    responses = iter([None, [], [ARTIFACT]])
    calls = []

    def list_artifacts(command, **kwargs):
        calls.append(command)
        artifacts = next(responses)
        if artifacts is None:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return SimpleNamespace(stdout=json.dumps({"artifacts": artifacts}))

    monkeypatch.setattr(check.subprocess, "run", list_artifacts)
    check.wait_for_artifact("owner/signal", "456", ARTIFACT["name"], "123")
    assert len(calls) == 3 and all(c[2:4] == ["--method", "GET"] for c in calls)
    assert all(c[-1] == f"name={ARTIFACT['name']}" for c in calls)


@pytest.mark.parametrize("artifacts", [
    [{**ARTIFACT, "id": 999}],
    [{**ARTIFACT, "expired": True}],
    [ARTIFACT, {**ARTIFACT, "id": 999}],
])
def test_stale_expired_or_ambiguous_artifact_cannot_reach_pages(check, monkeypatch, artifacts):
    calls = []

    def list_artifacts(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(stdout=json.dumps({"artifacts": artifacts}))

    monkeypatch.setattr(check.subprocess, "run", list_artifacts)
    with pytest.raises(ValueError, match="did not become visible"):
        check.wait_for_artifact("owner/signal", "456", ARTIFACT["name"], "123")
    assert len(calls) == 6
