import base64
import importlib.util
import io
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def timestamp_module(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/timestamp_source.py"
    spec = importlib.util.spec_from_file_location("timestamp_source", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "urlopen", lambda *a, **k: pytest.fail("Live timestamp/API calls are forbidden"))
    return module


@pytest.fixture
def evidence(timestamp_module, tmp_path, monkeypatch):
    executable = shutil.which("openssl")
    if not executable and Path("C:/Program Files/Git/usr/bin/openssl.exe").is_file():
        executable = "C:/Program Files/Git/usr/bin/openssl.exe"
    if not executable:
        pytest.fail("OpenSSL is required for the timestamp verification regression tests")
    monkeypatch.setenv("OPENSSL", executable)
    module = timestamp_module
    authority = tmp_path / "local-test-authority"
    authority.mkdir()

    def ssl(*args):
        result = subprocess.run([executable, *map(str, args)], cwd=authority, capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        return result.stdout

    (authority / "root.cnf").write_text(
        "[req]\ndistinguished_name = dn\nx509_extensions = v3_ca\nprompt = no\n"
        "[dn]\nCN = Offline test root\n[v3_ca]\nbasicConstraints=critical,CA:TRUE\n"
        "keyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n",
    )
    ssl("req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "root.key",
        "-out", "root.crt", "-days", "2", "-config", "root.cnf")
    ssl("req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", "tsa.key",
        "-out", "tsa.csr", "-subj", "/CN=Offline test timestamp authority")
    (authority / "extensions.cnf").write_text(
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n"
        "extendedKeyUsage=critical,timeStamping\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n",
    )
    ssl("x509", "-req", "-in", "tsa.csr", "-CA", "root.crt", "-CAkey", "root.key", "-set_serial", "2",
        "-out", "tsa.crt", "-days", "1", "-extfile", "extensions.cnf")
    (authority / "serial").write_text("01\n")
    (authority / "tsa.cnf").write_text(
        "[tsa]\ndefault_tsa = local\n[local]\nserial = serial\ncrypto_device = builtin\n"
        "signer_cert = tsa.crt\ncerts = root.crt\nsigner_key = tsa.key\nsigner_digest = sha256\n"
        "default_policy = 1.2.3.4.1\nother_policies = 1.2.3.4.2\ndigests = sha256\n"
        "accuracy = secs:1\nordering = yes\ntsa_name = yes\ness_cert_id_chain = no\ness_cert_id_alg = sha256\n",
    )
    certificate = (authority / "root.crt").read_text()
    fingerprint = module.hashlib.sha256(ssl("x509", "-in", "root.crt", "-outform", "DER")).hexdigest()
    root = module.approved_root(tmp_path, certificate, fingerprint)
    manifest = {"repo": module.SOURCE, "commit_sha": "a" * 40, "tree_sha": "b" * 40, "pull_request": None}
    folder = tmp_path / "evidence"
    folder.mkdir()

    def local_reply(request, **kwargs):
        assert request.full_url == "https://offline.invalid/tsa"
        (authority / "request.tsq").write_bytes(request.data)
        ssl("ts", "-reply", "-config", "tsa.cnf", "-queryfile", "request.tsq", "-out", "reply.tsr")
        return io.BytesIO((authority / "reply.tsr").read_bytes())

    monkeypatch.setattr(module, "urlopen", local_reply)
    module.timestamp(folder, manifest, root, "https://offline.invalid/tsa")
    return module, folder, manifest, root, certificate, fingerprint


def test_receipt_verifies_and_evidence_is_not_printed(evidence, capsys):
    module, folder, _, root, _, _ = evidence
    module.verify(folder, root)
    assert all((folder / name).is_file() for name in module.FILES)
    assert "Time stamp:" in (folder / "receipt.txt").read_text()
    assert not capsys.readouterr().out


def test_modified_manifest_rejected(evidence):
    module, folder, _, root, _, _ = evidence
    (folder / "manifest.json").write_text('{"tampered": true}')
    with pytest.raises(module.TimestampError):
        module.verify(folder, root)


def test_wrong_root_fingerprint_rejected(evidence, tmp_path):
    module, _, _, _, certificate, _ = evidence
    with pytest.raises(module.TimestampError, match="fingerprint"):
        module.approved_root(tmp_path, certificate, "0" * 64)


def test_different_request_nonce_rejected(evidence):
    module, folder, _, root, _, _ = evidence
    module.openssl("ts", "-query", "-data", folder / "manifest.json", "-sha256", "-cert",
                   "-out", folder / "request.tsq")
    with pytest.raises(module.TimestampError):
        module.verify(folder, root)


def test_existing_record_is_verified_and_not_overwritten(evidence, tmp_path):
    module, folder, manifest, root, _, _ = evidence

    class ExistingArchive:
        def call(self, method, path, payload=None):
            assert method == "GET", "Idempotent retries must not write another record"
            name = path.split("?", 1)[0].rsplit("/", 1)[1]
            if name == manifest["commit_sha"]:
                return []
            return {"encoding": "base64", "content": base64.b64encode((folder / name).read_bytes()).decode()}

    assert module.existing_record(ExistingArchive(), "head", manifest, root, tmp_path)
    changed = {**manifest, "tree_sha": "c" * 40}
    with pytest.raises(module.TimestampError, match="different source"):
        module.existing_record(ExistingArchive(), "head", changed, root, tmp_path)


def test_archive_race_retries_without_force_or_overwriting(evidence, tmp_path, monkeypatch):
    module, folder, manifest, root, _, _ = evidence
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)

    class RacingArchive:
        head = "head-0"
        trees = []
        patches = 0

        def call(self, method, path, payload=None):
            if "/contents/" in path:
                raise module.APIError(404)
            if method == "GET" and path.endswith("git/ref/heads/main"):
                return {"object": {"sha": self.head}}
            if method == "GET" and "/git/commits/" in path:
                return {"tree": {"sha": f"tree-{self.head}"}}
            if path.endswith("/git/blobs"):
                return {"sha": module.hashlib.sha256(payload["content"].encode()).hexdigest()}
            if path.endswith("/git/trees"):
                self.trees.append(payload)
                return {"sha": f"new-tree-{self.head}"}
            if path.endswith("/git/commits"):
                assert payload["parents"] == [self.head]
                return {"sha": f"commit-{self.head}"}
            if method == "PATCH":
                assert payload["force"] is False
                self.patches += 1
                if self.patches == 1:
                    self.head = "head-1"
                    raise module.APIError(422)
                return {}
            pytest.fail(f"Unexpected archive call {method} {path}")

    archive = RacingArchive()
    assert module.append_record(archive, folder, manifest, root, tmp_path) == "archived and verified"
    assert [tree["base_tree"] for tree in archive.trees] == ["tree-head-0", "tree-head-1"]
    assert all(item["path"].startswith(module.record_path(manifest) + "/")
               for tree in archive.trees for item in tree["tree"])


def test_direct_push_manifest_needs_no_pr(timestamp_module, monkeypatch, tmp_path):
    module = timestamp_module

    class SourceAPI:
        def call(self, *args):
            return []

    def git(*args, **kwargs):
        return b"b" * 40 if "rev-parse" in args else b"2026-09-17T12:00:00+00:00"

    monkeypatch.setattr(module, "run", git)
    manifest = module.source_manifest(tmp_path, "a" * 40, SourceAPI())
    assert manifest["pull_request"] is None
    assert manifest["tree_sha"] == "b" * 40
    assert "github_merge_timestamp" not in manifest


def test_public_archive_is_rejected_before_any_tsa_request(timestamp_module, monkeypatch):
    module = timestamp_module
    monkeypatch.setenv("GITHUB_REPOSITORY", module.SOURCE)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)

    class PublicArchive:
        def __init__(self, token):
            pass

        def call(self, *args):
            return {"private": False}

    monkeypatch.setattr(module, "GitHub", PublicArchive)
    with pytest.raises(module.TimestampError, match="must be private"):
        module.main()


def test_manual_input_cannot_be_a_git_option(timestamp_module):
    with pytest.raises(timestamp_module.TimestampError):
        timestamp_module.validate_sha("--upload-pack=unexpected")
