"""Reuse an exact, validated public export; never use cache existence as a test result."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from refresh_plan import code_digest, data_digest, is_ui_path, read_state

PREFIX = "signal-public-v1-"
MAX_BYTES = 900 * 1024 * 1024
# Already-compressed members no longer shrink much inside the tarball. Keep the
# cache bounded by the same actual-byte budget as its validated publication.
MAX_ARCHIVE = MAX_BYTES
MAX_FILES = 100_000
RECEIPT = "data/validated_data.json"
ARCHIVE = "tmp/public-data.tar.gz"
BOOKKEEPING = {RECEIPT, "data/publication_state.json", "data/published_release.json",
               "data/verification_state.json", "data/ui_verification_state.json", "data/translation_quota.json"}


def public_json_path(name):
    return PurePosixPath(name).suffix == ".json" or bool(re.fullmatch(
        r"(?:current|manifest)\.json\.gz|(?:current|awards)/[A-Z]+-[a-f0-9]{16}\.json\.gz|records/[A-Za-z0-9_-]{1,100}-[a-f0-9]{16}\.json\.gz|buyers/buyer_[a-f0-9]{20}-[a-f0-9]{16}\.json\.gz|history/[a-f0-9]{3,64}-[a-f0-9]{16}\.json\.gz", name))


def complete_roots(names):
    return "manifest.json" in names and len({"current.json", "current.json.gz"}.intersection(names)) == 1


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def input_digest(root):
    digest = hashlib.sha256()
    paths = []
    # Raw downloads/model caches are not export inputs; retained canonical facts are.
    ignored = {"data/raw", "data/ai_cache", "data/documents/blobs"}
    for directory, folders, files in os.walk(root / "data"):
        folders[:] = [name for name in folders if (Path(directory) / name).relative_to(root).as_posix() not in ignored]
        paths.extend(Path(directory) / name for name in files)
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        if relative not in BOOKKEEPING and not path.name.endswith(".lock"):
            digest.update(relative.encode() + b"\0" + digest_file(path).encode() + b"\0")
    return digest.hexdigest()


def compatible(receipt, fingerprint):
    return (isinstance(receipt, dict) and receipt.get("version") == 1
            and receipt.get("data_code") == fingerprint
            and isinstance(receipt.get("generation"), int) and receipt["generation"] > 0
            and bool(re.fullmatch(r"[a-f0-9]{64}", str(receipt.get("sha256", ""))))
            and bool(re.fullmatch(PREFIX + r"[a-f0-9]{64}-[0-9]+-[0-9]+", str(receipt.get("key", ""))))
            and receipt["key"].startswith(PREFIX + receipt["sha256"] + "-")
            and isinstance(receipt.get("signature"), dict)
            and set(receipt["signature"]) == {"code", "content", "translations", "health", "day"})


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def emit(**values):
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            for key, value in values.items():
                value = str(value).lower() if isinstance(value, bool) else value
                stream.write(f"{key}={value}\n")


def require_current_workflow(root):
    expected = os.getenv("EXECUTION_WORKFLOW_SHA")
    if expected:
        result = subprocess.run(["git", "diff", "--quiet", expected, "HEAD", "--", ".github/workflows/"], cwd=root)
        if result.returncode:
            raise ValueError("Workflow changed while this run was queued; the newer run must verify and publish it")


def select(root, base=None):
    receipt = read_state(root / RECEIPT)
    eligible = True
    if base:
        # PRs read the trusted base receipt; a proposed data/receipt edit is not proof.
        result = subprocess.run(["git", "show", f"{base}:{RECEIPT}"], cwd=root, capture_output=True, text=True)
        try:
            receipt = json.loads(result.stdout) if result.returncode == 0 else {}
        except ValueError:
            receipt = {}
        diff = subprocess.run(["git", "diff", "--name-only", "-z", base, "HEAD"], cwd=root,
                              capture_output=True, check=True).stdout
        eligible = all(is_ui_path(p.decode()) or p.endswith(b".md") or p.startswith(b"docs/")
                       for p in diff.split(b"\0") if p)
    eligible = eligible and compatible(receipt, data_digest(root))
    write_json(root / "tmp/selected-data.json", receipt if eligible else {})
    emit(eligible=eligible, key=receipt["key"] if eligible else "no-compatible-public-data")
    return eligible


def check_archive(root, receipt):
    archive = root / ARCHIVE
    if not compatible(receipt, data_digest(root)):
        raise ValueError("Public data receipt is incompatible with this code")
    if archive.stat().st_size > MAX_ARCHIVE or digest_file(archive) != receipt["sha256"]:
        raise ValueError("Public data archive failed integrity verification")


def restore(root, receipt):
    check_archive(root, receipt)
    archive = root / ARCHIVE
    staging = root / "tmp/verified-public-data"
    target = root / "app/public/data"
    # No tar.extractall: reject traversal, links, duplicate paths and archive bombs.
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        if len(members) > MAX_FILES or sum(m.size for m in members) > MAX_BYTES:
            raise ValueError("Public data archive exceeds the Pages budget")
        paths = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or ".." in path.parts
                    or "\\" in member.name or ":" in member.name or not public_json_path(member.name)
                    or member.name in paths or not path.parts or path.parts[0] == "."):
                raise ValueError("Unsafe public data archive member")
            paths.add(member.name)
        if not complete_roots(paths):
            raise ValueError("Public data archive is incomplete")
        # Resolve and check every deletion target before touching local directories.
        workspace = root.resolve()
        for directory in (staging, target):
            resolved = directory.resolve()
            if not resolved.is_relative_to(workspace) or resolved == workspace or directory.is_symlink():
                raise ValueError("Public data directory escapes the workspace")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for member in members:
            destination = staging / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging.rename(target)


def pack(root):
    from publication_state import signature_for

    require_current_workflow(root)
    fingerprint = data_digest(root)
    started = read_state(root / "tmp/refresh-plan.json").get("signature", {}).get("code")
    if started != fingerprint:
        raise ValueError("Pipeline changed during validation; a fresh validation is required")
    receipt = read_state(root / RECEIPT)
    archive = root / ARCHIVE
    archive.parent.mkdir(exist_ok=True)
    public = root / "app/public/data"
    names = json.loads((root / "tmp/public-data-files.json").read_text(encoding="utf-8"))
    if (not isinstance(names, list) or not complete_roots(names)
            or len(names) != len(set(names))):
        raise ValueError("A complete validated export inventory is required")
    files = []
    for name in names:
        path = public / name
        if (PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                or "\\" in name or ":" in name or not public_json_path(name)
                or not path.resolve().is_relative_to(public.resolve())
                or path.is_symlink() or not path.is_file()):
            raise ValueError("Only regular public JSON exports may be cached")
        files.append(path)
    if len(files) > MAX_FILES or sum(path.stat().st_size for path in files) > MAX_BYTES:
        raise ValueError("Public data exceeds the Pages budget")
    with tarfile.open(archive, "w:gz", compresslevel=3) as bundle:
        for path in files:
            bundle.add(path, arcname=path.relative_to(public).as_posix(), recursive=False)
    if archive.stat().st_size > MAX_ARCHIVE:
        raise ValueError("Public data cache exceeds its storage budget")
    sha = digest_file(archive)
    key = f"{PREFIX}{sha}-{os.getenv('GITHUB_RUN_ID', '0')}-{os.getenv('GITHUB_RUN_ATTEMPT', '0')}"
    candidate = {"version": 1, "generation": int(receipt.get("generation", 0)) + 1,
                 "data_code": fingerprint, "sha256": sha, "key": key,
                 "inputs": input_digest(root),
                 "validated_at": datetime.now(UTC).isoformat(), "signature": signature_for(root)}
    write_json(root / RECEIPT, candidate)
    emit(key=key)


def publication_plan(root, receipt, force=False):
    require_current_workflow(root)
    signature = {**receipt["signature"], "code": code_digest(root)}
    previous = read_state(root / "data/publication_state.json")
    published = read_state(root / "data/published_release.json")
    if receipt["generation"] < published.get("generation", 0):
        raise ValueError("An older data generation cannot replace the live release")
    verification = {"code": signature["code"], "day": datetime.now(UTC).date().isoformat()}
    full = force or read_state(root / "data/ui_verification_state.json") != verification
    return {"deploy": force or previous != signature, "full_ui": full,
            "signature": signature, "verification": verification,
            "generation": receipt["generation"], "key": receipt["key"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["select", "check", "unchanged", "restore", "pack", "publish-plan", "record"])
    parser.add_argument("--base")
    args = parser.parse_args()
    root = Path.cwd()
    if args.mode == "select":
        select(root, args.base)
    elif args.mode == "restore":
        restore(root, read_state(root / "tmp/selected-data.json"))
    elif args.mode == "check":
        check_archive(root, read_state(root / "tmp/selected-data.json"))
    elif args.mode == "unchanged":
        receipt = read_state(root / RECEIPT)
        emit(unchanged=compatible(receipt, data_digest(root)) and receipt.get("inputs") == input_digest(root))
    elif args.mode == "pack":
        pack(root)
    elif args.mode == "publish-plan":
        receipt = read_state(root / "tmp/selected-data.json")
        if not compatible(receipt, data_digest(root)):
            raise ValueError("Latest application requires a newly validated export")
        plan = publication_plan(root, receipt, os.getenv("FORCE_FULL_TESTS") == "true")
        write_json(root / "tmp/publication-plan.json", plan)
        emit(deploy=plan["deploy"], full_ui=plan["full_ui"])
    else:
        plan = read_state(root / "tmp/publication-plan.json")
        if not plan.get("deploy"):
            raise ValueError("Only a planned successful publication may be recorded")
        write_json(root / "data/publication_state.json", plan["signature"])
        write_json(root / "data/published_release.json", {k: plan[k] for k in ("generation", "key")})
        if plan["full_ui"]:
            write_json(root / "data/ui_verification_state.json", plan["verification"])


if __name__ == "__main__":
    main()
