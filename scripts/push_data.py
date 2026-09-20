"""Rebase independent generated-data writes without overwriting another writer."""
import argparse
import subprocess
import sys
from pathlib import Path

from refresh_plan import data_digest, read_state


def push(root, *, validated=False):
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
        result = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=root)
        if result.returncode == 0:
            return
    raise RuntimeError("Data push did not succeed after three normal, guarded rebases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validated", action="store_true")
    push(Path.cwd(), validated=parser.parse_args().validated)
