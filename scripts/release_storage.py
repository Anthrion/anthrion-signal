"""Store bounded, checksummed snapshots outside Git; credentials stay in gh's environment."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from refresh_plan import read_state
from storage_policy import CONTROL_FILES, MAX_STATE_BYTES, MAX_STATE_FILES, PART_BYTES, PREFIX, STATE_POINTER

IGNORED = ("data/raw/", "data/ai_cache/", "data/documents/blobs/")
KINDS = {"records", "translations", "public"}
MARKER = "Anthrion Signal managed data snapshot v1."


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(path.suffix + ".tmp")
    staging.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    staging.replace(path)


def retained_name(name, kind):
    path = PurePosixPath(name)
    return (kind in {"records", "translations"} and name.startswith("data/")
            and name == path.as_posix() and len(path.parts) > 1
            and all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part) for part in path.parts)
            and name.endswith((".json", ".json.gz", ".jsonl", ".jsonl.gz"))
            and name not in CONTROL_FILES and not name.startswith(IGNORED)
            and name.startswith("data/translation/") == (kind == "translations"))


def inventory(root, kind):
    if (root / "data").is_symlink():
        raise ValueError("Retained data cannot use a linked root")
    entries = []
    for folder, dirs, names in os.walk(root / "data", followlinks=False):
        for directory in dirs:
            if (Path(folder) / directory).is_symlink():
                raise ValueError("Retained data cannot contain directory links")
        dirs[:] = [name for name in dirs
                   if not ((Path(folder) / name).relative_to(root).as_posix() + "/").startswith(IGNORED)]
        for name in names:
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            if retained_name(relative, kind):
                if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Retained data must be regular workspace files")
                entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    entries.sort(key=lambda entry: entry["path"])
    if not entries:
        raise ValueError("Refusing an empty retained snapshot")
    if len(entries) > MAX_STATE_FILES or sum(entry["bytes"] for entry in entries) > MAX_STATE_BYTES:
        raise ValueError("Retained snapshot exceeds the monitored processing budget")
    return entries


def content_digest(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def pack_state(root, kind, output):
    entries = inventory(root, kind)
    output.mkdir(parents=True, exist_ok=True)
    parts, group, total = [], [], 0

    def finish():
        path = output / f"{kind}-{len(parts):03d}.tar"
        with tarfile.open(path, "w", format=tarfile.PAX_FORMAT) as archive:
            for entry in group:
                source = root / entry["path"]
                info = tarfile.TarInfo(entry["path"])
                info.size, info.mode, info.mtime = entry["bytes"], 0o644, 0
                with source.open("rb") as stream:
                    archive.addfile(info, stream)
                if sha256(source) != entry["sha256"]:
                    raise ValueError("Retained data changed during snapshot creation")
        if path.stat().st_size >= 2 * PART_BYTES:
            raise ValueError("Snapshot attachment exceeds GitHub's per-file limit")
        parts.append(path)

    for entry in entries:
        if entry["bytes"] > PART_BYTES:
            raise ValueError("A retained file exceeds the monitored 1 GiB processing limit")
        if group and total + entry["bytes"] > PART_BYTES:
            finish()
            group, total = [], 0
        group.append(entry)
        total += entry["bytes"]
    if group:
        finish()
    return entries, parts


class ReleaseStore:
    def __init__(self, root, repo=None):
        self.root = root
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repo):
            raise ValueError("An explicit GitHub repository is required")

    def command(self, args, *, payload=None, timeout=900):
        # Retry reads only: a timed-out mutation may already have succeeded.
        retryable = args[:2] == ["release", "download"] or (args[0] == "api" and
                    ("--method" not in args or args[args.index("--method") + 1] == "GET"))
        for attempt in range(3 if retryable else 1):
            try:
                result = subprocess.run(["gh", *args], cwd=self.root, input=payload, capture_output=True,
                                        text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                if not retryable or attempt == 2:
                    raise
            else:
                if result.returncode == 0:
                    return result.stdout
                transient = re.search(r"HTTP (429|500|502|503|504)|connection reset|TLS handshake|timeout|unexpected EOF",
                                      result.stderr, re.IGNORECASE)
                if not retryable or not transient or attempt == 2:
                    raise RuntimeError(f"GitHub snapshot operation failed: {result.stderr.strip()[:1000]}")
            time.sleep(5 * (attempt + 1))

    def api(self, path, *, method="GET", body=None):
        args = ["api", "--method", method, f"repos/{self.repo}/{path}"]
        if body is not None:
            args += ["--input", "-"]
        result = self.command(args, payload=json.dumps(body) if body is not None else None)
        return json.loads(result) if result.strip() else None

    def upload(self, kind, digest, paths):
        if kind not in KINDS or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid snapshot identity")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        tag = f"{PREFIX}{kind}-{digest}"
        # The tag is content-addressed: an interrupted upload can resume without
        # creating another release or overwriting an already accepted attachment.
        query = subprocess.run(["gh", "api", f"repos/{self.repo}/releases/tags/{tag}"], cwd=self.root,
                               capture_output=True, text=True, timeout=120)
        if query.returncode == 0:
            release = json.loads(query.stdout)
        elif "HTTP 404" in query.stderr:
            release = self.api("releases", method="POST", body={
                "tag_name": tag, "target_commitish": head, "name": f"Signal {kind} snapshot",
                "body": MARKER, "prerelease": True, "make_latest": "false",
            })
        else:
            raise RuntimeError("Cannot inspect the snapshot release; refusing an ambiguous upload")
        if release.get("body") != MARKER or release.get("draft") or release.get("tag_name") != tag:
            raise ValueError("Snapshot tag is already used by an unmanaged release")
        assets = []
        for path in paths:
            size, digest_bytes = path.stat().st_size, sha256(path)
            if size >= 2 * PART_BYTES:
                raise ValueError("Release attachment must remain below 2 GiB")
            existing = next((a for a in release["assets"] if a["name"] == path.name), None)
            if existing and existing.get("state") == "starter":
                self.api(f"releases/assets/{existing['id']}", method="DELETE")
                existing = None
            if not existing:
                self.command(["release", "upload", tag, str(path), "--repo", self.repo])
                release = self.api(f"releases/{release['id']}")
                existing = next((a for a in release["assets"] if a["name"] == path.name), None)
            if not existing or existing.get("state") != "uploaded" or existing.get("size") != size:
                raise ValueError("Release attachment was not fully uploaded")
            if existing.get("digest"):
                if existing["digest"] != "sha256:" + digest_bytes:
                    raise ValueError("GitHub's uploaded attachment checksum does not match")
            else:
                with tempfile.TemporaryDirectory(dir=self.root / "tmp") as scratch:
                    copy = Path(scratch) / path.name
                    self.command(["release", "download", tag, "--repo", self.repo,
                                  "--pattern", path.name, "--output", str(copy)])
                    if sha256(copy) != digest_bytes:
                        raise ValueError("Uploaded attachment failed read-back verification")
            assets.append({"name": path.name, "bytes": size, "sha256": digest_bytes})
        return {"version": 1, "kind": kind, "digest": digest, "tag": tag,
                "release_id": release["id"], "assets": assets}

    def download(self, descriptor, output):
        validate_descriptor(descriptor)
        output.mkdir(parents=True, exist_ok=True)
        release = self.api(f"releases/{descriptor['release_id']}")
        if (release.get("body") != MARKER or release.get("tag_name") != descriptor["tag"]
                or release.get("id") != descriptor["release_id"] or release.get("draft")):
            raise ValueError("Snapshot release identity does not match trusted metadata")
        paths = []
        for asset in descriptor["assets"]:
            actual = next((a for a in release["assets"] if a["name"] == asset["name"]), None)
            if not actual or actual.get("state") != "uploaded" or actual.get("size") != asset["bytes"]:
                raise ValueError("Required snapshot attachment is missing or incomplete")
            path = output / asset["name"]
            if not path.exists() or path.stat().st_size != asset["bytes"] or sha256(path) != asset["sha256"]:
                self.command(["release", "download", descriptor["tag"], "--repo", self.repo,
                              "--pattern", asset["name"], "--output", str(path), "--clobber"])
            if path.stat().st_size != asset["bytes"] or sha256(path) != asset["sha256"]:
                raise ValueError("Snapshot download failed integrity verification")
            paths.append(path)
        return paths


def validate_descriptor(value):
    if (not isinstance(value, dict) or value.get("version") != 1 or value.get("kind") not in KINDS
            or not re.fullmatch(r"[a-f0-9]{64}", str(value.get("digest", "")))
            or value.get("tag") != f"{PREFIX}{value['kind']}-{value['digest']}"
            or type(value.get("release_id")) is not int or value["release_id"] <= 0
            or not isinstance(value.get("assets"), list) or not 1 <= len(value["assets"]) <= 16):
        raise ValueError("Invalid trusted snapshot descriptor")
    names = set()
    total = 0
    pattern = r"public-data\.tar\.gz" if value["kind"] == "public" else value["kind"] + r"-[0-9]{3}\.tar"
    for asset in value["assets"]:
        if (not isinstance(asset, dict) or not re.fullmatch(pattern, str(asset.get("name", "")))
                or asset["name"] in names or type(asset.get("bytes")) is not int
                or not 0 < asset["bytes"] < 2 * PART_BYTES
                or not re.fullmatch(r"[a-f0-9]{64}", str(asset.get("sha256", "")))):
            raise ValueError("Invalid snapshot attachment descriptor")
        names.add(asset["name"])
        total += asset["bytes"]
    if total > MAX_STATE_BYTES + 20 * 1024 * 1024:
        raise ValueError("Snapshot exceeds the monitored processing budget")


def unpack_state(root, kind, paths, expected_digest):
    """Validate every byte and path in staging before replacing retained state."""
    if (root / "tmp").is_symlink() or (root / "data").is_symlink():
        raise ValueError("Snapshot directories cannot be links")
    (root / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verified-state-", dir=root / "tmp") as temporary:
        staging = Path(temporary)
        entries, seen, total = [], set(), 0
        for path in paths:
            with tarfile.open(path, "r:") as archive:
                for member in archive:
                    total += member.size
                    if (not member.isfile() or not retained_name(member.name, kind)
                            or member.name in seen or member.size < 0 or member.size > PART_BYTES
                            or total > MAX_STATE_BYTES or len(seen) >= MAX_STATE_FILES):
                        raise ValueError("Unsafe or oversized retained snapshot member")
                    seen.add(member.name)
                    target = staging / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    entries.append({"path": member.name, "bytes": target.stat().st_size, "sha256": sha256(target)})
        entries.sort(key=lambda entry: entry["path"])
        if not entries or content_digest(entries) != expected_digest:
            raise ValueError("Retained snapshot content failed verification")
        # Validate all existing destinations, including parent links, before the
        # first replacement. Control files and quota ledgers are never restored.
        existing = inventory(root, kind) if any(
            retained_name(p.relative_to(root).as_posix(), kind) for p in (root / "data").rglob("*")) else []
        for name in seen | {entry["path"] for entry in existing}:
            target = root / name
            if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
                raise ValueError("Retained snapshot destination escapes the workspace")
        for entry in existing:
            if entry["path"] not in seen:
                (root / entry["path"]).unlink()
        for name in sorted(seen):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            (staging / name).replace(target)


def save_component(root, store, kind):
    state = read_state(root / STATE_POINTER)
    current = state.get("components", {}).get(kind)
    entries = inventory(root, kind)
    digest = content_digest(entries)
    if current and current.get("digest") == digest:
        print(f"Retained {kind} unchanged; existing snapshot reused.")
        return False
    (root / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="state-upload-", dir=root / "tmp") as directory:
        entries, paths = pack_state(root, kind, Path(directory))
        if content_digest(entries) != digest:
            raise ValueError("Retained state changed before upload")
        descriptor = store.upload(kind, digest, paths)
    marker = root / "tmp/state-publish-base.json"
    if not marker.exists():
        write_json(marker, state)
    state.setdefault("previous", {})[kind] = current
    state.setdefault("components", {})[kind] = descriptor
    state["version"] = 1
    write_json(root / STATE_POINTER, state)
    print(f"Verified retained {kind}: {len(entries)} files, {sum(e['bytes'] for e in entries):,} bytes.")
    return True


def restore_state(root, store, state):
    if state.get("version") != 1 or set(state.get("components", {})) != {"records", "translations"}:
        raise ValueError("A complete retained-state snapshot is required")
    (root / "data").mkdir(exist_ok=True)
    (root / "tmp").mkdir(exist_ok=True)
    for kind, descriptor in state["components"].items():
        if descriptor.get("kind") != kind:
            raise ValueError("Snapshot component identity does not match")
        with tempfile.TemporaryDirectory(prefix="state-download-", dir=root / "tmp") as directory:
            paths = store.download(descriptor, Path(directory))
            unpack_state(root, kind, paths, descriptor["digest"])
    # Remember the state from which these local bytes were restored, even if a
    # quota-only push subsequently rebases independent publication bookkeeping.
    write_json(root / "tmp/state-publish-base.json", state)
    print("Verified retained records and translations restored; current quota controls preserved.")


def check_state_base(root):
    marker = root / "tmp/state-publish-base.json"
    if marker.exists():
        result = subprocess.run(["git", "show", f"origin/main:{STATE_POINTER}"], cwd=root,
                                capture_output=True, text=True, check=False)
        remote = json.loads(result.stdout) if result.returncode == 0 else {}
        if remote != read_state(marker):
            raise RuntimeError("Another writer changed the retained snapshot; refusing to overwrite its progress")


def protected_releases(root):
    state = read_state(root / STATE_POINTER)
    descriptors = [item for key in ("components", "previous") for item in state.get(key, {}).values() if item]
    for file in ("data/validated_data.json", "data/published_release.json"):
        descriptor = read_state(root / file).get("storage")
        if descriptor:
            descriptors.append(descriptor)
    for descriptor in descriptors:
        validate_descriptor(descriptor)
    return {entry["release_id"] for entry in descriptors}


def retention_candidates(releases, protected, now):
    """Preserve in-flight work, accepted states, seven daily and four weekly recovery points."""
    keep, managed = set(protected), []
    for release in releases:
        tag = release.get("tag_name", "")
        match = re.fullmatch(re.escape(PREFIX) + r"(records|translations|public)-[a-f0-9]{64}", tag)
        if release.get("body") != MARKER or release.get("draft") or not match:
            continue
        # created_at can be the target commit's age, not the upload's age.
        stamps = [release.get("published_at") or release["created_at"]]
        stamps += [asset["created_at"] for asset in release.get("assets", []) if asset.get("created_at")]
        date = max(datetime.fromisoformat(stamp.replace("Z", "+00:00")) for stamp in stamps)
        if now - date < timedelta(hours=6):
            keep.add(release["id"])
        managed.append((date, match[1], release))
    daily, weekly = set(), set()
    for date, kind, release in sorted(managed, key=lambda item: item[0], reverse=True):
        day, week = (kind, date.date()), (kind, date.isocalendar()[:2])
        if now - date < timedelta(days=7) and day not in daily:
            keep.add(release["id"])
            daily.add(day)
        if now - date < timedelta(days=28) and week not in weekly:
            keep.add(release["id"])
            weekly.add(week)
    return [entry for _, _, entry in managed if entry["id"] not in keep]


def prune(root, store):
    # Fetch small accepted pointers immediately before pruning. The writer's own
    # pending snapshot is included too, including translation-only checkpoints.
    subprocess.run(["git", "fetch", "origin", "main"], cwd=root, check=True)
    protected = protected_releases(root)
    for name in (STATE_POINTER, "data/validated_data.json", "data/published_release.json"):
        result = subprocess.run(["git", "show", f"origin/main:{name}"], cwd=root, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("Cannot inspect accepted snapshot references; retention stopped")
        value = json.loads(result.stdout)
        if name == STATE_POINTER:
            items = [item for key in ("components", "previous") for item in value.get(key, {}).values() if item]
        else:
            items = [value["storage"]] if value.get("storage") else []
        for item in items:
            validate_descriptor(item)
            protected.add(item["release_id"])
    pages = json.loads(store.command(["api", "--paginate", "--slurp", f"repos/{store.repo}/releases?per_page=100"]))
    releases = [release for page in pages for release in page]
    candidates = retention_candidates(releases, protected, datetime.now(UTC))
    for release in candidates:
        store.api(f"releases/{release['id']}", method="DELETE")
        # These generated tags have no source-history role. Human v* release tags
        # and all unmanaged releases are outside this retention namespace.
        store.api(f"git/refs/tags/{release['tag_name']}", method="DELETE")
    print(f"Snapshot retention: removed {len(candidates)} superseded backups; accepted states and recovery points retained.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["restore", "save-records", "save-translations", "upload-public", "download-public", "ensure-public", "prune"])
    parser.add_argument("--repo")
    parser.add_argument("--base")
    args = parser.parse_args()
    root = Path.cwd()
    store = ReleaseStore(root, args.repo)
    if args.mode == "restore":
        if args.base:
            # PR jobs restore the accepted base snapshot, never a proposed pointer.
            state = json.loads(subprocess.check_output(["git", "show", f"{args.base}:{STATE_POINTER}"], text=True))
        else:
            state = read_state(root / STATE_POINTER)
        restore_state(root, store, state)
    elif args.mode.startswith("save-"):
        save_component(root, store, args.mode.removeprefix("save-"))
    elif args.mode == "upload-public":
        from release_bundle import ARCHIVE, RECEIPT, check_archive
        receipt = read_state(root / RECEIPT)
        check_archive(root, receipt)
        receipt["storage"] = store.upload("public", receipt["sha256"], [root / ARCHIVE])
        write_json(root / RECEIPT, receipt)
    elif args.mode in {"download-public", "ensure-public"}:
        from release_bundle import ARCHIVE, check_archive
        receipt = read_state(root / "tmp/selected-data.json")
        if args.mode == "ensure-public":
            try:
                check_archive(root, receipt)
            except (OSError, ValueError):
                pass
            else:
                print("Verified cached public export reused.")
                return
        descriptor = receipt.get("storage", {})
        if descriptor.get("kind") != "public" or descriptor.get("digest") != receipt.get("sha256"):
            raise ValueError("A trusted durable public export is required")
        store.download(descriptor, (root / ARCHIVE).parent)
        check_archive(root, receipt)
    else:
        prune(root, store)


if __name__ == "__main__":
    main()
