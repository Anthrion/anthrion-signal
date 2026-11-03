"""Record early storage warnings without publishing implementation details in the UI."""
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from automation_git_guard import check_retained_tree
from refresh_plan import read_state
from release_storage import ReleaseStore, inventory, write_json
from storage_policy import CONTROL_FILES


def measure(root):
    check_retained_tree(root)
    components = {kind: inventory(root, kind) for kind in ("records", "translations")}
    state = read_state(root / "data/retained_state.json")
    public = read_state(root / "data/validated_data.json")
    return {
        "retained_bytes": sum(entry["bytes"] for entries in components.values() for entry in entries),
        "retained_files": sum(len(entries) for entries in components.values()),
        "largest_retained_file": max(entry["bytes"] for entries in components.values() for entry in entries),
        "largest_snapshot_asset": max((asset["bytes"] for item in state.get("components", {}).values()
                                       for asset in item.get("assets", [])), default=0),
        "public_archive_bytes": sum(asset["bytes"] for asset in public.get("storage", {}).get("assets", [])),
        "public_bytes": public.get("public_bytes", 0),
        "public_files": public.get("public_files", 0),
        "control_bytes": sum((root / name).stat().st_size for name in CONTROL_FILES if (root / name).exists()),
        "runner_free_bytes": shutil.disk_usage(root).free,
    }


def warnings(metrics):
    limits = {"retained_bytes": 2 * 1024**3, "largest_retained_file": 800 * 1024**2,
              "public_archive_bytes": 750 * 1024**2, "repository_bytes": 500 * 1024**2,
              "release_storage_bytes": 40 * 1024**3, "retained_files": 7500,
              "public_bytes": 750 * 1024**2, "public_files": 85_000}
    messages = [f"{key}: {metrics[key]:,} exceeds the early warning threshold {limit:,}."
                for key, limit in limits.items() if metrics.get(key, 0) >= limit]
    if metrics.get("runner_free_bytes", 10 * 1024**3) < 3 * 1024**3:
        messages.append("Less than 3 GiB of runner disk space remains.")
    return messages


def main():
    root = Path.cwd()
    metrics = measure(root)
    store = ReleaseStore(root)
    repository = json.loads(store.command(["api", f"repos/{store.repo}"]))
    metrics["repository_bytes"] = repository["size"] * 1024
    pages = json.loads(store.command(["api", "--paginate", "--slurp", f"repos/{store.repo}/releases?per_page=100"]))
    releases = [item for page in pages for item in page]
    metrics["release_storage_bytes"] = sum(asset["size"] for item in releases for asset in item.get("assets", []))
    metrics["release_count"] = len(releases)
    report = {"measured_at": datetime.now(UTC).isoformat(), "metrics": metrics, "warnings": warnings(metrics)}
    write_json(root / "data/storage_health.json", report)
    for warning in report["warnings"]:
        print("::warning title=Signal storage headroom::" + warning)
    summary = "\n## Storage headroom\n\n| Measure | Value |\n|---|---:|\n"
    summary += "\n".join(f"| {key} | {value:,} |" for key, value in metrics.items()) + "\n"
    summary += "\n".join(report["warnings"]) or "\nAll monitored storage measures are below early warning thresholds.\n"
    print(summary)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(summary)


if __name__ == "__main__":
    main()
