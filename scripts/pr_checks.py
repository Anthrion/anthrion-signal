"""Select fast PR code checks; real-data validation remains a publication gate."""
import os
import re
import subprocess

from refresh_plan import is_ui_path


def pipeline_required(paths):
    return any(not (is_ui_path(path) or path.endswith(".md") or path.startswith("docs/")) for path in paths)


def main():
    base = os.environ["BASE_SHA"]
    if not re.fullmatch(r"[a-f0-9]{40,64}", base):
        raise ValueError("Invalid pull-request base revision")
    changed = subprocess.run(["git", "diff", "--name-only", "-z", base, "HEAD"],
                             check=True, capture_output=True).stdout.decode().split("\0")
    required = pipeline_required([path for path in changed if path])
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"pipeline={str(required).lower()}\n")
    print("Pipeline code tests required." if required else "UI-only PR: frontend checks required.")


if __name__ == "__main__":
    main()
