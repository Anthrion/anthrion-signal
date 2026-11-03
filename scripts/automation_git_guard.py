"""Reject automation commits outside data/ before an authenticated push."""

import argparse
import re
import subprocess
from pathlib import Path

MAX_BLOB_BYTES = 95 * 1024 * 1024


def check_blob_sizes(root, objects):
    objects = sorted(set(objects) - {"0" * 40, "0" * 64})
    if not objects:
        return
    sizes = subprocess.run(["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        cwd=root, input=("\n".join(objects) + "\n").encode(), check=True, capture_output=True).stdout
    for line in sizes.decode().splitlines():
        _, kind, size = line.split()
        if kind == "blob" and int(size) >= MAX_BLOB_BYTES:
            raise RuntimeError("A generated file exceeds the 95 MiB safety limit; compress or partition it before pushing")


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
    entries = git(root, "diff", "--cached", "--raw", "--no-abbrev", "--no-renames", "-z").split(b"\0")
    objects = [entry.split()[3].decode() for entry in entries
               if re.match(rb"^:[0-7]{6} [0-7]{6} [0-9a-f]+ [0-9a-f]+ [A-Z]", entry)]
    check_blob_sizes(root, objects)


def check_unpushed(root):
    commits = git(root, "rev-list", "origin/main..HEAD").decode().splitlines()
    for commit in commits:
        # Inspect each commit, not just the net diff (a change followed by a revert).
        check_paths(git(root, "diff-tree", "--root", "-m", "--no-commit-id", "--no-renames",
                        "--name-only", "-r", "-z", commit))
    objects = git(root, "rev-list", "--objects", "origin/main..HEAD").decode().splitlines()
    check_blob_sizes(root, [line.split(" ", 1)[0] for line in objects])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["staged", "unpushed"])
    args = parser.parse_args()
    (check_staged if args.mode == "staged" else check_unpushed)(Path.cwd())


if __name__ == "__main__":
    main()
