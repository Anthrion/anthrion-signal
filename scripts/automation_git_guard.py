"""Reject automation commits outside data/ before an authenticated push."""

import argparse
import re
import subprocess
from pathlib import Path

from storage_policy import CONTROL_FILES, CONTROL_LIMIT

MAX_BLOB_BYTES = CONTROL_LIMIT


def check_blob_sizes(root, objects):
    objects = sorted(set(objects) - {"0" * 40, "0" * 64})
    if not objects:
        return
    sizes = subprocess.run(["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        cwd=root, input=("\n".join(objects) + "\n").encode(), check=True, capture_output=True).stdout
    for line in sizes.decode().splitlines():
        _, kind, size = line.split()
        if kind == "blob" and int(size) >= MAX_BLOB_BYTES:
            raise RuntimeError("A Git control file exceeds its safety limit; large retained data belongs in Release snapshots")


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True,
    ).stdout


def check_paths(raw):
    paths = [path for path in raw.split(b"\0") if path]
    if any(not path.startswith(b"data/") or b".." in path.split(b"/") for path in paths):
        raise RuntimeError("Automation may commit and push only files inside data/")
    if any(path.decode("utf-8") not in CONTROL_FILES for path in paths):
        raise RuntimeError("Automation may commit only approved small control files; use Release snapshots for retained data")


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


def check_retained_tree(root, ref="HEAD"):
    """Human PRs may edit code, but cannot accidentally reintroduce bulk state."""
    entries = git(root, "ls-tree", "-r", "-z", ref, "--", "data/").split(b"\0")
    objects = []
    for entry in filter(None, entries):
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        check_paths(path + b"\0")
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise RuntimeError("Git control files must be regular files")
        objects.append(oid.decode())
    check_blob_sizes(root, objects)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["staged", "unpushed", "retained-tree"])
    parser.add_argument("--base")
    args = parser.parse_args()
    root = Path.cwd()
    if args.mode == "retained-tree":
        check_retained_tree(root)
        if args.base:
            for ref in git(root, "rev-list", f"{args.base}..HEAD").decode().splitlines():
                check_retained_tree(root, ref)
    else:
        (check_staged if args.mode == "staged" else check_unpushed)(root)


if __name__ == "__main__":
    main()
