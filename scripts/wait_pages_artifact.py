"""Wait until the workflow artifact listing includes the tested Pages upload."""
import json
import os
import re
import subprocess
from time import sleep


def wait_for_artifact(repository, run_id, name, artifact_id):
    if not re.fullmatch(r"[1-9][0-9]*", artifact_id):
        raise ValueError("Pages upload did not return a valid artifact ID")

    command = ["gh", "api", "--method", "GET", f"repos/{repository}/actions/runs/{run_id}/artifacts",
               "-f", f"name={name}"]
    # The upload response can arrive before the artifact is listed.
    for delay in (1, 1, 2, 4, 8, 16):
        sleep(delay)
        try:
            response = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)
            result = json.loads(response.stdout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
            continue
        artifacts = result.get("artifacts") if isinstance(result, dict) else None
        if not isinstance(artifacts, list) or len(artifacts) != 1:
            continue
        artifact = artifacts[0]
        if (isinstance(artifact, dict) and artifact.get("id") == int(artifact_id)
                and artifact.get("name") == name and artifact.get("expired") is False):
            print(f"Pages artifact {artifact_id} is visible for workflow run {run_id}.", flush=True)
            return
    raise ValueError(f"Pages artifact {artifact_id} did not become visible for workflow run {run_id}")


if __name__ == "__main__":
    try:
        wait_for_artifact(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_RUN_ID"],
                          os.environ["PAGES_ARTIFACT_NAME"], os.environ["PAGES_ARTIFACT_ID"])
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
