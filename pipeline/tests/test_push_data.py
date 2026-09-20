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
