"""Bound this workflow's disposable public-data cache, leaving other caches alone."""
import json
import os
import urllib.request
from pathlib import Path

from refresh_plan import read_state
from release_bundle import PREFIX


def obsolete(caches, protected, budget=1024 * 1024 * 1024):
    own = sorted((c for c in caches if c["key"].startswith(PREFIX)), key=lambda c: c["created_at"], reverse=True)
    retained = sum(c["size_in_bytes"] for c in own if c["key"] in protected)
    count = sum(c["key"] in protected for c in own)
    remove = []
    for cache in own:
        if cache["key"] in protected:
            continue
        if count < 8 and retained + cache["size_in_bytes"] <= budget:
            count += 1
            retained += cache["size_in_bytes"]
        else:
            remove.append(cache["id"])
    return remove


def main():
    endpoint = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/caches"
    headers = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"}
    caches = []
    page = 1
    while True:
        request = urllib.request.Request(f"{endpoint}?key={PREFIX}&per_page=100&page={page}", headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)["actions_caches"]
        caches.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    protected = {read_state(Path(name)).get("key") for name in
                 ("data/validated_data.json", "data/published_release.json")}
    for identifier in obsolete(caches, protected):
        request = urllib.request.Request(f"{endpoint}/{identifier}", headers=headers, method="DELETE")
        with urllib.request.urlopen(request, timeout=30):
            pass


if __name__ == "__main__":
    main()
