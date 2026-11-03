"""Rebase independent generated-data writes without overwriting another writer."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from refresh_plan import data_digest, read_state


class RepositoryStorageBlocked(RuntimeError):
    """A repository storage rejection cannot be repaired by rebasing."""


STORAGE_BLOCK = "tmp/repository-storage-block.json"
STORAGE_MESSAGE = (
    "GitHub rejected the write because the repository is above its size quota. "
    "Rebasing or retrying cannot free repository history. No force push or data deletion "
    "was attempted; the local commits remain unpublished. Repository storage recovery "
    "is required before collection checkpoints, translation reservations or releases can be saved."
)


def workflow_attempt():
    if (os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("GITHUB_RUN_ID")
            and os.getenv("GITHUB_RUN_ATTEMPT")):
        return f"{os.environ['GITHUB_RUN_ID']}:{os.environ['GITHUB_RUN_ATTEMPT']}"
    return None


def check_storage_block(root):
    # Only the same Actions attempt can stop later steps. A fresh run, rerun or
    # local recovery must be able to verify that GitHub has lifted the block.
    attempt = workflow_attempt()
    marker = read_state(root / STORAGE_BLOCK)
    if (attempt and marker.get("attempt") == attempt
            and marker.get("reason") == "repository_size_quota"):
        raise RepositoryStorageBlocked(STORAGE_MESSAGE)


def record_storage_block(root):
    attempt = workflow_attempt()
    if attempt:
        path = root / STORAGE_BLOCK
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"attempt": attempt, "reason": "repository_size_quota"}) + "\n",
                        encoding="utf-8")


def push(root, *, validated=False):
    check_storage_block(root)
    expected = read_state(root / "data/validated_data.json").get("data_code") if validated else None
    for _ in range(3):
        subprocess.run(["git", "fetch", "origin", "main"], cwd=root, check=True)
        subprocess.run(["git", "rebase", "--autostash", "origin/main"], cwd=root, check=True)
        conflicts = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=root,
                                   capture_output=True, check=True).stdout
        if conflicts:
            raise RuntimeError("Concurrent data edits conflict; refusing to discard either version")
        if validated and (not expected or data_digest(root) != expected):
            raise RuntimeError("Pipeline changed during validation; refusing to mark its data verified")
        subprocess.run([sys.executable, str(Path(__file__).with_name("automation_git_guard.py")),
                        "unpushed"], cwd=root, check=True)
        result = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=root,
                                capture_output=True, text=True, errors="replace")
        # Retain Git's diagnostics, including non-quota failures that can still
        # benefit from the existing bounded rebase/retry path.
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode == 0:
            return
        if "repository is above its size quota" in (result.stdout + result.stderr).casefold():
            record_storage_block(root)
            raise RepositoryStorageBlocked(STORAGE_MESSAGE)
    raise RuntimeError("Data push did not succeed after three normal, guarded rebases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--validated", action="store_true")
    mode.add_argument("--check-storage-block", action="store_true")
    args = parser.parse_args()
    try:
        if args.check_storage_block:
            check_storage_block(Path.cwd())
        else:
            push(Path.cwd(), validated=args.validated)
    except RepositoryStorageBlocked as exc:
        raise SystemExit(str(exc)) from None
