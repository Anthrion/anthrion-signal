"""Timestamp accepted source and append evidence to the private company archive.

Uses only the standard library, Git, and OpenSSL. Never prints evidence or tokens.
Root trust comes from separately configured certificate bytes and a pinned digest,
never from certificates supplied by the timestamp response itself.
"""

import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SOURCE = "Anthrion/anthrion-signal"
ARCHIVE = "Anthrion/Timestamps"
FILES = ("manifest.json", "request.tsq", "token.tsr", "chain.txt", "trusted-root.crt", "receipt.txt")


class TimestampError(Exception):
    pass


class APIError(TimestampError):
    def __init__(self, status):
        super().__init__(f"GitHub returned HTTP {status}; check access and archive rules")
        self.status = status


class GitHub:
    def __init__(self, token):
        if not token:
            raise TimestampError("Required GitHub credential is not configured")
        self.token = token

    def call(self, method, path, payload=None):
        request = Request(
            f"https://api.github.com/repos/{path}", method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json", "User-Agent": "anthrion-signal-timestamp"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            # API response bodies can contain private archive metadata.
            raise APIError(exc.code) from None


def run(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True)
    if result.returncode:
        raise TimestampError(f"{Path(args[0]).name} validation failed; no evidence was accepted")
    return result.stdout


def openssl(*args):
    return run(os.getenv("OPENSSL", "openssl"), *map(str, args))


def validate_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise TimestampError("Specify a complete lowercase 40-character source commit SHA")
    return value


def source_manifest(root, sha, api):
    validate_sha(sha)
    # Manual backfills must refer to accepted main history, never arbitrary PR code.
    run("git", "merge-base", "--is-ancestor", sha, "origin/main", cwd=root)
    tree = run("git", "rev-parse", f"{sha}^{{tree}}", cwd=root).decode().strip()
    commit_time = run("git", "show", "-s", "--format=%cI", sha, cwd=root).decode().strip()
    prs = api.call("GET", f"{SOURCE}/commits/{sha}/pulls?per_page=100")
    merged = [pr for pr in prs if pr.get("merged_at") and pr.get("merge_commit_sha") == sha]
    pr = merged[0] if merged else None
    return {
        "schema_version": 1, "repo": SOURCE, "commit_sha": sha, "tree_sha": tree,
        "git_committer_timestamp": commit_time,
        "pull_request": None if pr is None else {
            "number": pr["number"], "author": pr["user"]["login"],
            "github_merged_at": pr["merged_at"],
        },
        "note": "The receipt supplies the trusted time. Git dates and PR metadata are informational.",
    }


def approved_root(folder, certificate, fingerprint):
    expected = fingerprint.replace(":", "").lower().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise TimestampError("Configure the independently approved root's SHA-256 fingerprint")
    if certificate.count("-----BEGIN CERTIFICATE-----") != 1:
        raise TimestampError("Configure exactly one independently approved TSA root certificate")
    path = folder / "approved-root.crt"
    path.write_text(certificate.strip() + "\n", encoding="ascii")
    der = openssl("x509", "-in", path, "-outform", "DER")
    if hashlib.sha256(der).hexdigest() != expected:
        raise TimestampError("TSA root certificate does not match the approved fingerprint")
    return path


def verify(folder, root):
    # Verify both the archived manifest bytes AND the nonce-bearing original request.
    # Supporting certificates remain untrusted; only the separately approved root anchors trust.
    empty_ca_directory = folder / "empty-ca-directory"
    empty_ca_directory.mkdir(exist_ok=True)
    common = ["ts", "-verify", "-in", folder / "token.tsr", "-CAfile", root,
              "-CApath", empty_ca_directory, "-untrusted", folder / "chain.txt"]
    openssl(*common, "-data", folder / "manifest.json")
    openssl(*common, "-queryfile", folder / "request.tsq")


def timestamp(folder, manifest, root, endpoint, supporting_chain=""):
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise TimestampError("The approved timestamp endpoint must be an HTTPS URL without credentials")
    (folder / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n",
    )
    openssl("ts", "-query", "-data", folder / "manifest.json", "-sha256", "-cert",
            "-out", folder / "request.tsq")
    request = Request(endpoint, data=(folder / "request.tsq").read_bytes(), headers={
        "Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply",
        "User-Agent": "anthrion-signal-timestamp",
    })
    try:
        with urlopen(request, timeout=45) as response:
            # Limit downloaded evidence; never follow a response with implicit trust.
            payload = response.read(2_000_001)
    except HTTPError as exc:
        raise TimestampError(f"Timestamp authority returned HTTP {exc.code}") from None
    if not payload or len(payload) > 2_000_000:
        raise TimestampError("Invalid timestamp response size")
    (folder / "token.tsr").write_bytes(payload)
    openssl("ts", "-reply", "-in", folder / "token.tsr", "-token_out", "-out", folder / "token.der")
    chain = openssl("pkcs7", "-inform", "DER", "-in", folder / "token.der", "-print_certs")
    (folder / "chain.txt").write_bytes(chain + b"\n" + supporting_chain.encode("ascii"))
    verify(folder, root)
    (folder / "trusted-root.crt").write_bytes(root.read_bytes())
    receipt = openssl("ts", "-reply", "-in", folder / "token.tsr", "-text")
    (folder / "receipt.txt").write_bytes(receipt)


def record_path(manifest):
    return f"records/Anthrion_anthrion-signal/{validate_sha(manifest['commit_sha'])}"


def existing_record(api, head, manifest, root, scratch):
    dest = record_path(manifest)
    try:
        api.call("GET", f"{ARCHIVE}/contents/{dest}?ref={head}")
    except APIError as exc:
        if exc.status == 404:
            return False
        raise
    # A pre-existing record must verify. Missing/corrupt evidence is not overwritten.
    folder = scratch / "existing"
    folder.mkdir(exist_ok=True)
    for name in FILES:
        item = api.call("GET", f"{ARCHIVE}/contents/{dest}/{name}?ref={head}")
        if item.get("encoding") != "base64":
            raise TimestampError("Unsupported existing archive file encoding")
        (folder / name).write_bytes(base64.b64decode(item["content"]))
    saved = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for key in ("repo", "commit_sha", "tree_sha"):
        if saved.get(key) != manifest[key]:
            raise TimestampError("Existing evidence refers to a different source; refusing to overwrite")
    verify(folder, root)
    return True


def archive_head(api):
    ref = api.call("GET", f"{ARCHIVE}/git/ref/heads/main")
    return ref["object"]["sha"]


def append_record(api, folder, manifest, root, scratch):
    # Git's non-force ref update is atomic. A race rebuilds on the newest archive head.
    blobs = None
    for attempt in range(4):
        head = archive_head(api)
        if existing_record(api, head, manifest, root, scratch):
            return "already archived and verified"
        parent = api.call("GET", f"{ARCHIVE}/git/commits/{head}")
        if blobs is None:
            blobs = []
            for name in FILES:
                blob = api.call("POST", f"{ARCHIVE}/git/blobs", {
                    "encoding": "base64", "content": base64.b64encode((folder / name).read_bytes()).decode(),
                })
                blobs.append({"path": f"{record_path(manifest)}/{name}", "mode": "100644",
                              "type": "blob", "sha": blob["sha"]})
        tree = api.call("POST", f"{ARCHIVE}/git/trees", {"base_tree": parent["tree"]["sha"], "tree": blobs})
        commit = api.call("POST", f"{ARCHIVE}/git/commits", {
            "message": f"Timestamp {SOURCE}@{manifest['commit_sha']}",
            "tree": tree["sha"], "parents": [head],
        })
        try:
            api.call("PATCH", f"{ARCHIVE}/git/refs/heads/main", {"sha": commit["sha"], "force": False})
            return "archived and verified"
        except APIError as exc:
            if exc.status not in (409, 422) or archive_head(api) == head or attempt == 3:
                raise
            time.sleep(2)
    raise TimestampError("Archive could not be updated")


def main():
    if os.getenv("GITHUB_REPOSITORY") != SOURCE or os.getenv("GITHUB_REF") != "refs/heads/main":
        raise TimestampError("Timestamping is restricted to Anthrion Signal's main-branch workflow")
    sha = validate_sha(os.getenv("TIMESTAMP_COMMIT_SHA") or os.environ["GITHUB_SHA"])
    source_api = GitHub(os.getenv("GH_TOKEN"))
    archive_api = GitHub(os.getenv("TIMESTAMPS_WRITE_TOKEN"))
    metadata = archive_api.call("GET", ARCHIVE)
    if metadata.get("private") is not True:
        raise TimestampError("Timestamp archive must be private")
    manifest = source_manifest(Path.cwd(), sha, source_api)
    with tempfile.TemporaryDirectory(prefix="anthrion-timestamp-") as temp:
        scratch = Path(temp)
        root = approved_root(scratch, os.getenv("TIMESTAMP_TSA_ROOT_PEM", ""),
                             os.getenv("TIMESTAMP_TSA_ROOT_SHA256", ""))
        if existing_record(archive_api, archive_head(archive_api), manifest, root, scratch):
            print("Source timestamp already archived privately and verified.")
            return
        folder = scratch / "evidence"
        folder.mkdir()
        # Respect the provider's minimum interval within this repository's serial queue.
        # Other company repositories need their own coordinated request limits.
        time.sleep(15)
        timestamp(folder, manifest, root, os.getenv("TIMESTAMP_TSA_URL", "https://timestamp.sectigo.com/qualified"),
                  os.getenv("TIMESTAMP_TSA_CHAIN_PEM", ""))
        result = append_record(archive_api, folder, manifest, root, scratch)
        print(f"Source timestamp {result} privately.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never let a library traceback expose private API response bodies or receipt bytes.
        message = str(exc) if isinstance(exc, TimestampError) else "Timestamp failed; evidence was not accepted"
        raise SystemExit(message) from None
