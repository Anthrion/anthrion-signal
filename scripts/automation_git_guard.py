"""Reject automation commits outside data/ before an authenticated push."""

import argparse
import subprocess
from pathlib import Path


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True,
    ).stdout


def check_paths(raw):
    paths = [path for path in raw.split(b"\0") if path]
    if any(not path.startswith(b"data/") or b".." in path.split(b"/") for path in paths):
        raise RuntimeError("Automation may commit and push only files inside data/")


def check_staged(root):
    # --no-renames checks both sides of a move across the permitted boundary.
    check_paths(git(root, "diff", "--cached", "--no-renames", "--name-only", "-z"))


def check_unpushed(root):
    commits = git(root, "rev-list", "origin/main..HEAD").decode().splitlines()
    for commit in commits:
        # Inspect each commit, not just the net diff (a change followed by a revert).
        check_paths(git(root, "diff-tree", "--root", "-m", "--no-commit-id", "--no-renames",
                        "--name-only", "-r", "-z", commit))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["staged", "unpushed"])
    args = parser.parse_args()
    (check_staged if args.mode == "staged" else check_unpushed)(Path.cwd())


if __name__ == "__main__":
    main()
