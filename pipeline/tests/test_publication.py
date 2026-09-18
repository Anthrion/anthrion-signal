import json
import os
import subprocess
import sys
from pathlib import Path

from anthrion_signal.translation import VERSION
from anthrion_signal.utils import atomic_json, digest


def test_successful_signature_describes_built_data_not_later_checkout(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/publication_state.py"
    data = tmp_path / "data"
    data.mkdir()
    current = data / "current.json"
    current.write_text(json.dumps({"run": {"content_digest": "built-version"}, "sources": []}), encoding="utf-8")
    output = tmp_path / "outputs"
    env = {**os.environ, "GITHUB_OUTPUT": str(output), "BUILD_CODE_DIGEST": "built-code"}
    subprocess.run([sys.executable, str(script), "before"], cwd=tmp_path, env=env, check=True)
    subprocess.run([sys.executable, str(script), "after"], cwd=tmp_path, env=env, check=True)
    values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    assert values["deploy"] == "true"
    current.write_text(json.dumps({"run": {"content_digest": "newer-unbuilt-version"}, "sources": []}), encoding="utf-8")
    subprocess.run([sys.executable, str(script), "deployed"], cwd=tmp_path,
                   env={**env, "BUILD_CODE_DIGEST": "newer-code",
                        "DEPLOYED_SIGNATURE": values["signature"]}, check=True)
    deployed = json.loads((data / "publication_state.json").read_text(encoding="utf-8"))
    assert deployed["content"] == digest(["built-version", {}])
    assert deployed["code"] == "built-code"


def test_code_only_changes_and_failed_deployments_remain_due(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/publication_state.py"
    (tmp_path / "data").mkdir()
    (tmp_path / "data/current.json").write_text(
        json.dumps({"run": {"content_digest": "same-data"}, "sources": []}), encoding="utf-8")
    output = tmp_path / "outputs"
    env = {**os.environ, "GITHUB_OUTPUT": str(output), "BUILD_CODE_DIGEST": "code-v1",
           "FORCE_DEPLOY": "false"}

    def step(command, **overrides):
        output.write_text("", encoding="utf-8")
        subprocess.run([sys.executable, str(script), command], cwd=tmp_path,
                       env={**env, **overrides}, check=True)
        return dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())

    step("before")
    built = step("after")
    step("deployed", DEPLOYED_SIGNATURE=built["signature"])
    step("before")
    assert step("after")["deploy"] == "false"
    assert step("after", BUILD_CODE_DIGEST="code-v2")["deploy"] == "true"
    # A failed deployment never updates the successful publication marker.
    step("before")
    assert step("after", BUILD_CODE_DIGEST="code-v2")["deploy"] == "true"


def test_translation_changes_publish_but_quota_and_unused_entries_do_not(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/publication_state.py"
    signal = {"id": "record", "title": "Titel", "description": "Text"}
    atomic_json(tmp_path / "data/current.json", {
        "run": {"content_digest": "same"}, "sources": [], "signals": [signal],
    })
    output = tmp_path / "outputs"
    env = {**os.environ, "GITHUB_OUTPUT": str(output), "BUILD_CODE_DIGEST": "same", "FORCE_DEPLOY": "false"}

    def step(command, **overrides):
        output.write_text("", encoding="utf-8")
        subprocess.run([sys.executable, str(script), command], cwd=tmp_path, env={**env, **overrides}, check=True)
        return dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())

    step("before")
    step("deployed", DEPLOYED_SIGNATURE=step("after")["signature"])
    step("before")
    entry = {"source_hash": digest([signal["title"], signal["description"]]),
             "version": VERSION, "title": "Title", "description": "Text"}
    path = tmp_path / "data/translation/translations.en.json"
    atomic_json(path, {"version": 1, "target": "en", "signals": {"removed": entry}})
    atomic_json(tmp_path / "data/translation_quota.json", {"usage": 60})
    assert step("after")["deploy"] == "false"
    atomic_json(path, {"version": 1, "target": "en", "signals": {"record": entry}})
    assert step("after")["deploy"] == "true"


def test_historical_award_changes_publish_when_live_content_is_unchanged(tmp_path):
    script = Path(__file__).resolve().parents[2] / 'scripts/publication_state.py'
    atomic_json(tmp_path / 'data/current.json', {'run': {'content_digest': 'same-live'}, 'sources': []})
    public = tmp_path / 'app/public/data/current.json'
    atomic_json(public, {'award_history': {'GB': {'url': 'awards/GB-before.json', 'count': 1}}})
    output = tmp_path / 'outputs'
    env = {**os.environ, 'GITHUB_OUTPUT': str(output), 'BUILD_CODE_DIGEST': 'same-code', 'FORCE_DEPLOY': 'false'}
    def step(command, **overrides):
        output.write_text('', encoding='utf-8')
        subprocess.run([sys.executable, str(script), command], cwd=tmp_path, env={**env, **overrides}, check=True)
        return dict(line.split('=', 1) for line in output.read_text(encoding='utf-8').splitlines())
    step('before')
    step('deployed', DEPLOYED_SIGNATURE=step('after')['signature'])
    step('before')
    assert step('after')['deploy'] == 'false'
    atomic_json(public, {'award_history': {'GB': {'url': 'awards/GB-after.json', 'count': 2}}})
    assert step('after')['deploy'] == 'true'
