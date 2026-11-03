import importlib
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def writers(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = importlib.import_module("push_data")

    def git(root, *args, check=True):
        return subprocess.run(["git", *args], cwd=root, check=check, capture_output=True, text=True)

    remote = tmp_path / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare", "--initial-branch=main")
    first, second = tmp_path / "collector", tmp_path / "publisher"
    git(tmp_path, "clone", str(remote), str(first))
    git(first, "config", "user.name", "Test bot")
    git(first, "config", "user.email", "test@example.invalid")
    git(first, "config", "commit.gpgsign", "false")
    (first / "data").mkdir()
    (first / "data/state.json").write_text("{}")
    (first / "pipeline.py").write_text("original")
    git(first, "add", ".")
    git(first, "commit", "-m", "Initial")
    git(first, "push", "origin", "main")
    git(tmp_path, "clone", str(remote), str(second))
    git(second, "config", "user.name", "Test bot")
    git(second, "config", "user.email", "test@example.invalid")
    git(second, "config", "commit.gpgsign", "false")

    def commit(root, path, value):
        (root / path).write_text(value)
        git(root, "add", path)
        git(root, "commit", "-m", "Change")

    return module, first, second, remote, git, commit


def test_parallel_publication_and_quota_reservation_preserve_both_and_unstaged_progress(writers):
    module, collector, publisher, remote, git, commit = writers
    commit(collector, "data/translation_quota.json", '{"reserved":20}')
    # Collection can have outstanding work while its quota reservation is pushed.
    (collector / "data/state.json").write_text('{"new_notice":true}')
    commit(publisher, "data/publication_state.json", '{"published":true}')
    module.push(publisher)
    module.push(collector)
    assert git(remote, "show", "main:data/translation_quota.json").stdout == '{"reserved":20}'
    assert git(remote, "show", "main:data/publication_state.json").stdout == '{"published":true}'
    assert (collector / "data/state.json").read_text() == '{"new_notice":true}'
    assert git(remote, "show", "main:data/state.json").stdout == '{}'


def test_concurrent_conflicting_data_is_not_silently_overwritten(writers):
    module, first, second, remote, git, commit = writers
    commit(first, "data/state.json", '{"version":1}')
    commit(second, "data/state.json", '{"version":2}')
    module.push(second)
    with pytest.raises(subprocess.CalledProcessError):
        module.push(first)
    assert git(remote, "show", "main:data/state.json").stdout == '{"version":2}'


def test_source_changes_after_validation_cannot_be_claimed_by_an_old_receipt(writers):
    module, collector, human, remote, git, commit = writers
    proof = {"data_code": module.data_digest(collector)}
    commit(collector, "data/validated_data.json", json.dumps(proof))
    commit(human, "pipeline.py", "new validator")
    git(human, "push", "origin", "main")
    with pytest.raises(RuntimeError, match="Pipeline changed"):
        module.push(collector, validated=True)
    assert git(remote, "cat-file", "-e", "main:data/validated_data.json", check=False).returncode != 0


def test_data_writer_cannot_push_an_unreviewed_source_change(writers):
    module, first, _, remote, git, commit = writers
    commit(first, "pipeline.py", "unreviewed")
    with pytest.raises(subprocess.CalledProcessError):
        module.push(first)
    assert git(remote, "show", "main:pipeline.py").stdout == "original"


@pytest.mark.parametrize("in_actions", [False, True])
def test_storage_quota_stops_retries_and_preserves_unpublished_work(writers, monkeypatch, in_actions, capsys):
    module, collector, _, remote, git, commit = writers
    if in_actions:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_RUN_ID", "1234")
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    else:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    commit(collector, "data/translation_quota.json", '{"reserved":20}')
    (collector / "data/state.json").write_text('{"new_notice":true}')
    original = module.subprocess.run
    pushes = []

    def reject_push(command, **kwargs):
        if command[:2] == ["git", "push"]:
            pushes.append(command)
            return subprocess.CompletedProcess(command, 1, stdout="", stderr=(
                "remote: error: Repository is above its size quota. "
                "Contact GitHub Support for further assistance.\n"))
        return original(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", reject_push)
    with pytest.raises(module.RepositoryStorageBlocked, match="above its size quota"):
        module.push(collector)
    assert len(pushes) == 1
    assert "Contact GitHub Support" in capsys.readouterr().err
    assert git(remote, "cat-file", "-e", "main:data/translation_quota.json", check=False).returncode != 0
    assert git(collector, "show", "HEAD:data/translation_quota.json").stdout == '{"reserved":20}'
    assert (collector / "data/state.json").read_text() == '{"new_notice":true}'
    marker = collector / module.STORAGE_BLOCK
    assert marker.exists() == in_actions
    if in_actions:
        assert json.loads(marker.read_text()) == {"attempt": "1234:1", "reason": "repository_size_quota"}
        with pytest.raises(module.RepositoryStorageBlocked):
            module.check_storage_block(collector)
        with pytest.raises(module.RepositoryStorageBlocked):
            module.push(collector)
        assert len(pushes) == 1


@pytest.mark.parametrize("run_id,attempt", [("1234", "2"), ("5678", "1")])
def test_storage_block_does_not_prevent_a_fresh_workflow_attempt(writers, monkeypatch, run_id, attempt):
    module, collector, _, remote, git, commit = writers
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", run_id)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", attempt)
    marker = collector / module.STORAGE_BLOCK
    marker.parent.mkdir()
    marker.write_text(json.dumps({"attempt": "1234:1", "reason": "repository_size_quota"}))
    commit(collector, "data/translation_quota.json", '{"reserved":20}')
    module.check_storage_block(collector)
    module.push(collector)
    assert git(remote, "show", "main:data/translation_quota.json").stdout == '{"reserved":20}'


def test_transient_push_failure_retains_bounded_retry(writers, monkeypatch):
    module, collector, _, remote, git, commit = writers
    commit(collector, "data/state.json", '{"new_notice":true}')
    original = module.subprocess.run
    pushes = []

    def temporary_failure(command, **kwargs):
        if command[:2] == ["git", "push"]:
            pushes.append(command)
            if len(pushes) == 1:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="remote: HTTP 503\n")
        return original(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", temporary_failure)
    module.push(collector)
    assert len(pushes) == 2
    assert git(remote, "show", "main:data/state.json").stdout == '{"new_notice":true}'
    assert not (collector / module.STORAGE_BLOCK).exists()
