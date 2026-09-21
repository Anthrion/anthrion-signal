import importlib
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 64


@pytest.fixture
def bundle(monkeypatch):
    # Temporary test folders have no production Git checkout. Tests exercising
    # workflow revision checks set their own revision explicitly below.
    monkeypatch.delenv("EXECUTION_WORKFLOW_SHA", raising=False)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = importlib.import_module("release_bundle")
    monkeypatch.setattr(module, "data_digest", lambda root: "data-code")
    monkeypatch.setattr(module, "code_digest", lambda root: "ui-code")
    return module


def receipt(**changes):
    return {"version": 1, "generation": 2, "data_code": "data-code", "sha256": SHA,
            "key": f"signal-public-v1-{SHA}-100-1", "signature": {
                "code": "old-ui", "content": "content", "translations": "translations",
                "health": [], "day": "2026-09-20"}, **changes}


@pytest.mark.parametrize("changes", [
    {"version": 2}, {"data_code": "changed-validator"}, {"sha256": ""}, {"generation": 0},
    {"key": f"signal-public-v1-{'b' * 64}-100-1"}, {"signature": {}},
])
def test_receipt_cannot_bypass_version_code_integrity_or_generation(bundle, changes):
    assert not bundle.compatible(receipt(**changes), "data-code")


def archive(bundle, root, entries=None):
    path = root / bundle.ARCHIVE
    path.parent.mkdir(parents=True)
    with tarfile.open(path, "w:gz") as output:
        for name, kind in (entries or [("current.json", "file"), ("manifest.json", "file"),
                                       ("records/notice-1.json", "file")]):
            entry = tarfile.TarInfo(name)
            entry.size = 2
            if kind == "link":
                entry.type = tarfile.SYMTYPE
                entry.linkname = "../../private.txt"
            output.addfile(entry, io.BytesIO(b"{}"))
    sha = bundle.digest_file(path)
    return receipt(sha256=sha, key=f"signal-public-v1-{sha}-100-1")


def test_validated_archive_restores_exactly_without_stale_output(bundle, tmp_path):
    historical = f"history/abc-{'a' * 16}.json.gz"
    proof = archive(bundle, tmp_path, [("current.json", "file"), ("manifest.json", "file"),
                                      ("records/notice-1.json", "file"), (historical, "file")])
    old = tmp_path / "app/public/data/old.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}")
    bundle.restore(tmp_path, proof)
    assert not old.exists()
    assert sorted(p.relative_to(old.parent).as_posix() for p in old.parent.rglob("*.json")) == [
        "current.json", "manifest.json", "records/notice-1.json"]
    assert (old.parent / historical).read_bytes() == b"{}"


@pytest.mark.parametrize("entries", [
    [("../escaped.json", "file")], [("/absolute.json", "file")],
    [("C:/windows.json", "file")], [("..\\escaped.json", "file")],
    [("current.json", "link")], [("current.json", "file"), ("current.json", "file")],
    [("private.pem", "file")], [("manifest.json", "file")],
    [("current.json", "file"), ("private.json.gz", "file")],
    [("current.json", "file"), ("history/unhashed.json.gz", "file")],
])
def test_unsafe_or_incomplete_archive_preserves_existing_output(bundle, tmp_path, entries):
    proof = archive(bundle, tmp_path, entries)
    old = tmp_path / "app/public/data/current.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"old":true}')
    with pytest.raises(ValueError):
        bundle.restore(tmp_path, proof)
    assert old.read_text() == '{"old":true}'
    assert not (tmp_path / "escaped.json").exists()


def test_corrupted_cache_and_oversized_archive_cannot_replace_live_data(bundle, tmp_path, monkeypatch):
    proof = archive(bundle, tmp_path)
    with (tmp_path / bundle.ARCHIVE).open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="integrity"):
        bundle.restore(tmp_path, proof)
    monkeypatch.setattr(bundle, "MAX_ARCHIVE", 1)
    with pytest.raises(ValueError):
        bundle.restore(tmp_path, proof)
    assert not (tmp_path / "app/public/data").exists()


def test_publication_uses_latest_ui_with_validated_data_and_cannot_roll_back(bundle, tmp_path):
    proof = receipt()
    plan = bundle.publication_plan(tmp_path, proof)
    assert plan["signature"] == {**proof["signature"], "code": "ui-code"}
    assert plan["deploy"] and plan["full_ui"]
    bundle.write_json(tmp_path / "data/publication_state.json", plan["signature"])
    bundle.write_json(tmp_path / "data/ui_verification_state.json", plan["verification"])
    assert not bundle.publication_plan(tmp_path, proof)["deploy"]
    assert not bundle.publication_plan(tmp_path, proof)["full_ui"]
    assert bundle.publication_plan(tmp_path, proof, force=True)["full_ui"]
    bundle.write_json(tmp_path / "data/published_release.json", {"generation": 3})
    with pytest.raises(ValueError, match="older data"):
        bundle.publication_plan(tmp_path, proof)


def test_queued_old_workflow_cannot_claim_a_new_publication_policy_passed(bundle, tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_WORKFLOW_SHA", "old-workflow")
    monkeypatch.setattr(bundle.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(ValueError, match="Workflow changed"):
        bundle.publication_plan(tmp_path, receipt())


def test_input_cache_ignores_quota_and_receipts_but_tracks_source_and_translation_changes(bundle, tmp_path):
    bundle.write_json(tmp_path / "data/current.json", {"title": "CRM"})
    before = bundle.input_digest(tmp_path)
    for name in bundle.BOOKKEEPING:
        bundle.write_json(tmp_path / name, {"updated": "today"})
    assert before == bundle.input_digest(tmp_path)
    bundle.write_json(tmp_path / "data/translation/cache.json", {"title": "CRM system"})
    assert before != bundle.input_digest(tmp_path)
    translated = bundle.input_digest(tmp_path)
    bundle.write_json(tmp_path / "data/current.json", {"title": "CRM", "deadline": "2026-10-01"})
    assert translated != bundle.input_digest(tmp_path)


def test_pack_includes_only_the_validated_dependency_graph_and_rejects_changed_pipeline(bundle, tmp_path, monkeypatch):
    state = importlib.import_module("publication_state")
    monkeypatch.setattr(state, "signature_for", lambda root: receipt()["signature"])
    bundle.write_json(tmp_path / "tmp/refresh-plan.json", {"signature": {"code": "data-code"}})
    bundle.write_json(tmp_path / "tmp/public-data-files.json", ["current.json", "manifest.json"])
    for name in ("current.json", "manifest.json", "obsolete.json"):
        bundle.write_json(tmp_path / "app/public/data" / name, {})
    bundle.pack(tmp_path)
    with tarfile.open(tmp_path / bundle.ARCHIVE) as archive_file:
        assert archive_file.getnames() == ["current.json", "manifest.json"]
    proof = bundle.read_state(tmp_path / bundle.RECEIPT)
    assert bundle.compatible(proof, "data-code")
    assert proof["generation"] == 1
    monkeypatch.setattr(bundle, "data_digest", lambda root: "changed-code")
    with pytest.raises(ValueError, match="Pipeline changed"):
        bundle.pack(tmp_path)


def test_pull_request_cannot_supply_its_own_receipt_or_use_ui_path_for_data_edits(bundle, tmp_path, monkeypatch):
    bundle.write_json(tmp_path / bundle.RECEIPT, receipt())
    outputs = []
    monkeypatch.setattr(bundle, "emit", lambda **kw: outputs.append(kw))
    changed = [b"app/src/styles.css\0"]
    trusted = [receipt()]
    def run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(trusted[0]) if command[1] == "show" else changed[0])
    monkeypatch.setattr(bundle.subprocess, "run", run)
    assert bundle.select(tmp_path, "trusted-base")
    changed[0] = b"app/src/styles.css\0data/current.json\0"
    assert not bundle.select(tmp_path, "trusted-base")
    changed[0] = b"app/src/styles.css\0"
    trusted[0] = {}
    assert not bundle.select(tmp_path, "trusted-base")


def test_cache_pruning_is_bounded_and_never_removes_other_workflows_or_active_receipts(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    prune = importlib.import_module("prune_public_cache")
    caches = [{"key": f"signal-public-v1-{i}", "id": i, "created_at": f"{i:02}", "size_in_bytes": 10}
              for i in range(12)]
    caches.append({"key": "pip-dependencies", "id": 50, "created_at": "20", "size_in_bytes": 100})
    deleted = prune.obsolete(caches, {"signal-public-v1-0", "signal-public-v1-1"}, budget=40)
    assert set(deleted) == set(range(2, 10))
    assert not {0, 1, 50}.intersection(deleted)


def test_release_workflows_keep_trusted_data_validation_and_tested_publication_separate():
    def workflow(name):
        return yaml.load((ROOT / f".github/workflows/{name}.yml").read_text(encoding="utf-8-sig"), Loader=yaml.BaseLoader)
    collect, publish, tests = [workflow(name) for name in ("ingest-and-deploy", "publish", "test")]
    assert "concurrency" not in collect
    assert collect["jobs"]["build"]["concurrency"]["group"] == "anthrion-signal-production"
    job = publish["jobs"]["publish"]
    assert job["concurrency"]["group"] == "anthrion-signal-publication"
    assert job["concurrency"]["cancel-in-progress"] == "false"
    steps = job["steps"]
    by_name = {s.get("name"): s for s in steps}
    for name in ["Verify and unpack public data", "UI desktop and mobile regression", "Published-data desktop and mobile integration"]:
        assert "continue-on-error" not in by_name[name]
        assert steps.index(by_name[name]) < steps.index(by_name["Upload tested Pages build"])
    assert steps.index(by_name["Upload tested Pages build"]) < steps.index(by_name["Deploy GitHub Pages"])
    assert by_name["Record successful publication"]["if"] == "steps.deployment.outcome == 'success'"
    assert steps.index(by_name["Deploy GitHub Pages"]) < steps.index(by_name["Record successful publication"])
    assert set(tests["on"]) == {"pull_request"}  # production gates replace the duplicate push job
    assert set(tests["jobs"]) == {"test"}  # retain the required status check
    assert tests["permissions"] == {"contents": "read"}
    pr_commands = "\n".join(step.get("run", "") for step in tests["jobs"]["test"]["steps"])
    assert "python -m pytest -q" in pr_commands and "npm test" in pr_commands
    assert "npm run test:e2e:pr" in pr_commands and "node build/preparePrData.mjs" in pr_commands
    assert "cli export" not in pr_commands and "release_bundle.py pack" not in pr_commands
    validation = next(s for s in collect["jobs"]["build"]["steps"] if s.get("name") == "Validate pipeline and public dataset")
    assert "check_public_output.py" in validation["run"] and "continue-on-error" not in validation
    assert tests["concurrency"] == {
        "group": "signal-pr-${{ github.event.pull_request.number }}", "cancel-in-progress": "true",
    }


def test_pr_routing_keeps_contracts_collectors_data_and_unknown_changes_on_pipeline_checks(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    checks = importlib.import_module("pr_checks")
    assert not checks.pipeline_required(["app/src/styles.css", "app/src/ResearchUI.tsx", "docs/plan.md"])
    for path in ("app/src/dataClient.ts", "pipeline/anthrion_signal/adapters/canada_buys.py",
                 "app/package-lock.json", ".github/workflows/publish.yml", "data/current.json.gz", "new-policy.json"):
        assert checks.pipeline_required(["app/src/styles.css", path])
