import importlib
import io
import json
import subprocess
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("release_storage")


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def descriptor(storage, kind="records", digest="a" * 64, number=1, paths=()):
    return {"version": 1, "kind": kind, "digest": digest, "tag": f"{storage.PREFIX}{kind}-{digest}",
            "release_id": number, "assets": [{"name": path.name, "bytes": path.stat().st_size,
                                             "sha256": storage.sha256(path)} for path in paths] or [
                {"name": "public-data.tar.gz" if kind == "public" else f"{kind}-000.tar",
                 "bytes": 10, "sha256": "b" * 64}]}


def test_roundtrip_preserves_exact_files_and_never_rolls_back_control_state(storage, tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    expected = {"data/signals.jsonl.gz": b"compressed facts", "data/archive/uk.jsonl.gz": b"old facts"}
    for name, data in expected.items():
        put(source, name, data)
    put(source, "data/translation/cache.json.gz", b"translated")
    put(source, "data/translation_quota.json", b"old quota")
    put(source, "data/raw/response.json", b"not retained")
    entries, paths = storage.pack_state(source, "records", tmp_path / "packed")
    assert {entry["path"] for entry in entries} == set(expected)
    put(target, "data/stale.json", b"obsolete")
    put(target, "data/translation_quota.json", b"new quota reservation")
    put(target, "data/translation/cache.json.gz", b"new translation checkpoint")
    storage.unpack_state(target, "records", paths, storage.content_digest(entries))
    assert not (target / "data/stale.json").exists()
    for name, data in expected.items():
        assert (target / name).read_bytes() == data
    assert (target / "data/translation_quota.json").read_bytes() == b"new quota reservation"
    assert (target / "data/translation/cache.json.gz").read_bytes() == b"new translation checkpoint"


def test_snapshot_pack_is_deterministic_and_splits_before_attachment_limit(storage, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PART_BYTES", 12_000)
    for number in range(3):
        put(tmp_path, f"data/{number}.json", bytes([number]) * 8000)
    first, paths = storage.pack_state(tmp_path, "records", tmp_path / "pack1")
    second, again = storage.pack_state(tmp_path, "records", tmp_path / "pack2")
    assert len(paths) == 3
    assert first == second
    assert [storage.sha256(path) for path in paths] == [storage.sha256(path) for path in again]


@pytest.mark.parametrize("name,kind", [("../escape.json", "file"), ("data/../escape.json", "file"),
    ("data/translation_quota.json", "file"), ("data/translation/cache.json", "file"),
    ("data/raw/download.json", "file"), ("data/safe.json", "link")])
def test_untrusted_members_never_modify_existing_state(storage, tmp_path, name, kind):
    original = put(tmp_path, "data/signals.jsonl", b"accepted")
    archive = tmp_path / "bad.tar"
    with tarfile.open(archive, "w") as stream:
        entry = tarfile.TarInfo(name)
        entry.size = 2
        if kind == "link":
            entry.type = tarfile.SYMTYPE
            entry.linkname = "../escape.json"
        stream.addfile(entry, io.BytesIO(b"{}"))
    with pytest.raises(ValueError, match="Unsafe"):
        storage.unpack_state(tmp_path, "records", [archive], "a" * 64)
    assert original.read_bytes() == b"accepted"


def test_checksum_failure_does_not_replace_accepted_state(storage, tmp_path):
    put(tmp_path / "source", "data/current.json", b"new")
    old = put(tmp_path / "target", "data/current.json", b"old")
    _, paths = storage.pack_state(tmp_path / "source", "records", tmp_path / "parts")
    with pytest.raises(ValueError, match="verification"):
        storage.unpack_state(tmp_path / "target", "records", paths, "f" * 64)
    assert old.read_bytes() == b"old"


def test_symlink_destinations_cannot_redirect_a_restore(storage, tmp_path):
    source, target, external = tmp_path / "source", tmp_path / "target", tmp_path / "external"
    put(source, "data/nested/current.json", b"new")
    outside = put(external, "current.json", b"outside")
    (target / "data").mkdir(parents=True)
    try:
        (target / "data/nested").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links")
    entries, paths = storage.pack_state(source, "records", tmp_path / "parts")
    with pytest.raises(ValueError):
        storage.unpack_state(target, "records", paths, storage.content_digest(entries))
    assert outside.read_bytes() == b"outside"


def test_failed_upload_keeps_current_pointer_and_success_retains_recovery_point(storage, tmp_path):
    put(tmp_path, "data/translation/cache.json.gz", b"new translated fields")
    before = {"version": 1, "components": {"translations": descriptor(storage, "translations")}}
    pointer = put(tmp_path, storage.STATE_POINTER, json.dumps(before).encode())
    class Store:
        def upload(self, kind, digest, paths):
            raise RuntimeError("interrupted upload")
    with pytest.raises(RuntimeError):
        storage.save_component(tmp_path, Store(), "translations")
    assert json.loads(pointer.read_text()) == before
    assert not (tmp_path / "tmp/state-publish-base.json").exists()
    store = SimpleNamespace(upload=lambda kind, digest, paths: descriptor(storage, kind, digest, 2, paths))
    assert storage.save_component(tmp_path, store, "translations")
    after = json.loads(pointer.read_text())
    assert after["previous"]["translations"] == before["components"]["translations"]
    assert after["components"]["translations"]["release_id"] == 2
    assert json.loads((tmp_path / "tmp/state-publish-base.json").read_text()) == before
    assert not storage.save_component(tmp_path, Store(), "translations")


def test_compare_and_swap_rejects_another_writers_new_snapshot(storage, tmp_path, monkeypatch):
    put(tmp_path, "tmp/state-publish-base.json", b'{"old":1}')
    monkeypatch.setattr(storage.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout='{"new":2}'))
    with pytest.raises(RuntimeError, match="Another writer"):
        storage.check_state_base(tmp_path)


@pytest.mark.parametrize("change", [
    {"kind": "public"}, {"release_id": -1}, {"tag": "v1"},
    {"assets": [{"name": "../records-000.tar", "bytes": 1, "sha256": "a" * 64}]},
    {"assets": [{"name": "translations-000.tar", "bytes": 1, "sha256": "a" * 64}]},
])
def test_invalid_descriptors_are_rejected_before_network_access(storage, change):
    with pytest.raises(ValueError):
        storage.validate_descriptor({**descriptor(storage), **change})


def test_download_rejects_wrong_bytes(storage, tmp_path, monkeypatch):
    path = put(tmp_path, "source/records-000.tar", b"good")
    proof = descriptor(storage, paths=[path])
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    monkeypatch.setattr(store, "api", lambda *a, **k: {
        "id": 1, "body": storage.MARKER, "tag_name": proof["tag"],
        "assets": [{"name": path.name, "state": "uploaded", "size": 4}]})
    def download(args):
        Path(args[args.index("--output") + 1]).write_bytes(b"evil")
    monkeypatch.setattr(store, "command", download)
    with pytest.raises(ValueError, match="integrity"):
        store.download(proof, tmp_path / "out")


def test_upload_reuses_verified_attachment_and_never_overwrites_wrong_bytes(storage, tmp_path, monkeypatch):
    path = put(tmp_path, "parts/records-000.tar", b"verified snapshot")
    digest = "a" * 64
    existing = {"id": 10, "body": storage.MARKER, "tag_name": f"{storage.PREFIX}records-{digest}",
                "assets": [{"name": path.name, "state": "uploaded", "size": path.stat().st_size,
                            "digest": "sha256:" + storage.sha256(path)}]}
    monkeypatch.setattr(storage.subprocess, "check_output", lambda *a, **k: "source-sha")
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    monkeypatch.setattr(store, "release_by_tag", lambda tag: existing)
    def no_mutation(*args, **kwargs):
        raise AssertionError("Verified immutable attachment must not be overwritten")
    monkeypatch.setattr(store, "command", no_mutation)
    monkeypatch.setattr(store, "api", no_mutation)
    assert store.upload("records", digest, [path])["release_id"] == 10
    existing["assets"][0]["digest"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="checksum"):
        store.upload("records", digest, [path])


def test_upload_without_server_digest_requires_matching_readback(storage, tmp_path, monkeypatch):
    path = put(tmp_path, "parts/records-000.tar", b"verified snapshot")
    (tmp_path / "tmp").mkdir()
    existing = {"id": 10, "body": storage.MARKER, "tag_name": f"{storage.PREFIX}records-{'a' * 64}",
                "assets": [{"name": path.name, "state": "uploaded", "size": path.stat().st_size}]}
    monkeypatch.setattr(storage.subprocess, "check_output", lambda *a, **k: "source-sha")
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    monkeypatch.setattr(store, "release_by_tag", lambda tag: existing)
    monkeypatch.setattr(store, "command", lambda args: Path(args[args.index("--output") + 1]).write_bytes(b"wrong"))
    with pytest.raises(ValueError, match="read-back"):
        store.upload("records", "a" * 64, [path])


def test_retention_protects_current_previous_daily_weekly_and_recent_upload_on_old_commit(storage):
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    def release(number, hours, **extra):
        return {"id": number, "tag_name": f"{storage.PREFIX}records-{number:064x}", "body": storage.MARKER,
                "created_at": (now - timedelta(hours=hours)).isoformat(), **extra}
    items = [release(1, 1000), release(2, 1001), release(3, 1), release(4, 25), release(5, 26),
             release(6, 250), release(7, 251), release(8, 1000),
             release(9, 1000, published_at=(now - timedelta(hours=1)).isoformat()),
             release(10, 1000, tag_name="v1"), release(11, 1000, body="Human release")]
    assert {item["id"] for item in storage.retention_candidates(items, {1, 2}, now)} == {5, 7, 8}


@pytest.mark.parametrize("message", ["HTTP 503", "unexpected end of JSON input", "unexpected EOF"])
def test_safe_reads_retry_transient_errors_but_mutations_do_not(storage, tmp_path, monkeypatch, message):
    calls = []
    def request(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if len(calls) == 1 else 0, stderr=message, stdout="{}")
    monkeypatch.setattr(storage.subprocess, "run", request)
    monkeypatch.setattr(storage.time, "sleep", lambda seconds: None)
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    assert store.api("releases/1") == {}
    assert len(calls) == 2
    calls.clear()
    with pytest.raises(RuntimeError):
        store.api("releases", method="POST", body={})
    assert len(calls) == 1


@pytest.mark.parametrize("response", ["", '{"id":'])
def test_reads_retry_incomplete_success_responses(storage, tmp_path, monkeypatch, response):
    replies = iter([response, '{"id":10}'])
    calls = []
    def request(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=next(replies), stderr="")
    monkeypatch.setattr(storage.subprocess, "run", request)
    monkeypatch.setattr(storage.time, "sleep", lambda seconds: None)
    assert storage.ReleaseStore(tmp_path, "Anthrion/test").api("releases/10") == {"id": 10}
    assert len(calls) == 2


@pytest.mark.parametrize("applied", [False, True])
@pytest.mark.parametrize("failure", ["cli-json", "truncated-json", "empty-json", "timeout", "conflict"])
def test_uncertain_creation_is_reconciled_before_retry(storage, tmp_path, monkeypatch, applied, failure):
    path = put(tmp_path, "parts/records-000.tar", b"verified snapshot")
    digest = "a" * 64
    release = {"id": 10, "body": storage.MARKER, "tag_name": f"{storage.PREFIX}records-{digest}",
               "assets": [{"name": path.name, "state": "uploaded", "size": path.stat().st_size,
                           "digest": "sha256:" + storage.sha256(path)}]}
    events, created = [], False
    def request(args, **kwargs):
        nonlocal created
        method = args[args.index("--method") + 1]
        if method == "GET":
            events.append("inspect")
            return SimpleNamespace(returncode=0 if created else 1, stdout=json.dumps(release) if created else "",
                                   stderr="" if created else "HTTP 404")
        assert method == "POST"
        events.append("create")
        assert json.loads(kwargs["input"])["tag_name"] == release["tag_name"]
        if events.count("create") == 1:
            created = applied
            if failure == "timeout":
                raise subprocess.TimeoutExpired(args, 900)
            return SimpleNamespace(returncode=1 if failure in {"cli-json", "conflict"} else 0,
                                   stdout='{"id":' if failure == "truncated-json" else "",
                                   stderr="HTTP 422" if failure == "conflict" else "unexpected end of JSON input")
        created = True
        return SimpleNamespace(returncode=0, stdout=json.dumps(release), stderr="")
    monkeypatch.setattr(storage.subprocess, "check_output", lambda *a, **k: "source-sha")
    monkeypatch.setattr(storage.subprocess, "run", request)
    monkeypatch.setattr(storage.time, "sleep", lambda seconds: None)
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    if failure == "conflict" and not applied:
        with pytest.raises(storage.SnapshotRequestError, match="HTTP 422"):
            store.upload("records", digest, [path])
        assert events == ["inspect", "create", "inspect"]
    else:
        assert store.upload("records", digest, [path])["release_id"] == 10
        assert events == (["inspect", "create", "inspect"] if applied else
                          ["inspect", "create", "inspect", "inspect", "create"])


@pytest.mark.parametrize("failure", ["HTTP 403", "HTTP 503"])
def test_creation_never_retries_without_a_verified_absent_tag(storage, tmp_path, monkeypatch, failure):
    methods = []
    def request(args, **kwargs):
        method = args[args.index("--method") + 1]
        methods.append(method)
        # Initial 404 permits creation; subsequent failed reads must stop it.
        message = "HTTP 404" if len(methods) == 1 else (failure if method == "GET" else "HTTP 503")
        return SimpleNamespace(returncode=1, stdout="", stderr=message)
    monkeypatch.setattr(storage.subprocess, "run", request)
    monkeypatch.setattr(storage.time, "sleep", lambda seconds: None)
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    with pytest.raises(storage.SnapshotRequestError):
        store.ensure_release("records", "snapshot-tag", "source-sha")
    assert methods.count("POST") == 1


@pytest.mark.parametrize("response", ["null", "[]"])
@pytest.mark.parametrize("after_creation", [False, True])
def test_invalid_lookup_shapes_cannot_authorize_creation(storage, tmp_path, monkeypatch, response, after_creation):
    methods = []
    def request(args, **kwargs):
        method = args[args.index("--method") + 1]
        methods.append(method)
        if after_creation and len(methods) <= 2:
            return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 404" if method == "GET" else "HTTP 503")
        return SimpleNamespace(returncode=0, stdout=response, stderr="")
    monkeypatch.setattr(storage.subprocess, "run", request)
    monkeypatch.setattr(storage.time, "sleep", lambda seconds: None)
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    with pytest.raises(storage.SnapshotRequestError, match="Invalid JSON"):
        store.ensure_release("records", "snapshot-tag", "source-sha")
    assert methods == (["GET", "POST", "GET"] if after_creation else ["GET"])


def test_creation_retries_are_bounded_and_permission_failures_are_immediate(storage, tmp_path, monkeypatch):
    methods = []
    message = "HTTP 503"
    def request(args, **kwargs):
        method = args[args.index("--method") + 1]
        methods.append(method)
        return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 404" if method == "GET" else message)
    monkeypatch.setattr(storage.subprocess, "run", request)
    monkeypatch.setattr(storage.time, "sleep", lambda seconds: None)
    store = storage.ReleaseStore(tmp_path, "Anthrion/test")
    with pytest.raises(storage.SnapshotRequestError):
        store.ensure_release("records", "snapshot-tag", "source-sha")
    assert methods.count("POST") == 3
    methods.clear()
    message = "HTTP 403"
    with pytest.raises(storage.SnapshotRequestError, match="HTTP 403"):
        store.ensure_release("records", "snapshot-tag", "source-sha")
    assert methods == ["GET", "POST"]


def test_recent_pointer_history_protects_old_export_used_by_concurrent_publisher(storage, tmp_path, monkeypatch):
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    def git(*args):
        return subprocess.check_output(["git", "-c", "commit.gpgsign=false", *args], cwd=tmp_path, text=True)
    git("init", "--initial-branch=main")
    git("config", "user.name", "Snapshot test")
    git("config", "user.email", "snapshot@example.invalid")
    def commit(number, hours, published):
        stamp = (now - timedelta(hours=hours)).isoformat()
        monkeypatch.setenv("GIT_AUTHOR_DATE", stamp)
        monkeypatch.setenv("GIT_COMMITTER_DATE", stamp)
        for filename, identifier in (("validated_data", number), ("published_release", published)):
            put(tmp_path, f"data/{filename}.json", json.dumps({
                "storage": descriptor(storage, "public", f"{identifier:064x}", identifier),
            }).encode())
        git("add", "data")
        git("commit", "-m", f"Export {number}")
    commit(10, 250, 10)
    commit(11, 100, 11)
    commit(12, 8, 11)  # A publisher selected this old export just before export 13.
    commit(13, 1, 11)
    commit(14, 0, 11)  # More than one newer export can arrive during a slow publish.
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    assert storage.recent_public_releases(tmp_path, now) == {11, 12, 13, 14}
