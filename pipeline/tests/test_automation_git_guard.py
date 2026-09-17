import importlib.util
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def guard():
    path = Path(__file__).resolve().parents[2] / "scripts/automation_git_guard.py"
    spec = importlib.util.spec_from_file_location("automation_git_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True).stdout

    git("init")
    git("config", "user.name", "Test bot")
    git("config", "user.email", "test@example.invalid")
    git("config", "commit.gpgsign", "false")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/state.json").write_text("{}")
    (tmp_path / "source.py").write_text("initial")
    git("add", ".")
    git("commit", "-m", "Initial")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path, git


def test_data_checkpoint_can_be_committed_and_pushed(guard, repository):
    root, git = repository
    (root / "data/state.json").write_text('{"updated": true}')
    git("add", "data")
    guard.check_staged(root)
    git("commit", "-m", "Checkpoint")
    guard.check_unpushed(root)


def test_pre_staged_source_change_is_rejected(guard, repository):
    root, git = repository
    (root / "source.py").write_text("unexpected change")
    git("add", "source.py")
    with pytest.raises(RuntimeError, match="only files inside data"):
        guard.check_staged(root)


def test_move_out_of_data_is_rejected(guard, repository):
    root, git = repository
    git("mv", "data/state.json", "moved.json")
    with pytest.raises(RuntimeError):
        guard.check_staged(root)


def test_source_change_followed_by_revert_cannot_hide_in_net_diff(guard, repository):
    root, git = repository
    for text in ("unexpected change", "initial"):
        (root / "source.py").write_text(text)
        git("add", "source.py")
        git("commit", "-m", "Source change")
    assert not git("diff", "origin/main", "HEAD")
    with pytest.raises(RuntimeError):
        guard.check_unpushed(root)
