import gzip
import importlib.util
import json
from pathlib import Path

import pytest

from anthrion_signal.models import Document
from anthrion_signal.record_reviews import source_hash
from anthrion_signal.translation import VERSION, source_key
from anthrion_signal.utils import atomic_json


@pytest.fixture
def command():
    path = Path(__file__).resolve().parents[2] / "scripts/review_records.py"
    spec = importlib.util.spec_from_file_location("review_records_command", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(record.model_dump_json() for record in records).encode()
    path.write_bytes(gzip.compress(body, mtime=0) if path.suffix == ".gz" else body)


def review(signal):
    return {"id": signal.id, "source_hash": source_hash(signal), "decision": "guide",
            "reviewed_at": "2026-09-22T10:00:00Z", "reviewed_by": "Independent reviewer",
            "reason": "Reviewed complete retained notice and its requirements.",
            "guidance": {"source_hash": source_hash(signal), "approach": [{
                "text": "Implement the stated Salesforce workflows and systems integration.",
                "evidence": [{"field": "description", "quote": signal.description[:80],
                              "source_url": signal.primary_source_url}]}],
                "problems": [], "complexity": 5, "problem_level": 2}}


def translation(signal):
    return {"id": signal.id, "source_hash": source_key(signal), "version": VERSION,
            "title": signal.title, "description": signal.description, "source_language": "en",
            "reviewed_by": "Independent reviewer", "reviewed_at": "2026-09-22T10:00:00Z"}


def test_packets_preserve_retained_precedence_and_only_hydrate_selected_sources(command, tmp_path, signal, monkeypatch):
    archive_only = signal.model_copy(deep=True, update={"id": "archive-only", "title": "Latest archived scope",
        "updated_at": "2026-09-21T10:00:00Z", "description": "Full source scope including an embedded\u2028separator."})
    stale = archive_only.model_copy(update={"title": "Older rejected scope", "updated_at": "2026-09-01T10:00:00Z"})
    canonical = signal.model_copy(deep=True)
    canonical.documents = [Document(title="Specification", url="https://example.org/spec.pdf", source_revision="r1")]
    write_records(tmp_path / "data/discovery/rejected/day.jsonl.gz", [stale])
    write_records(tmp_path / "data/archive/month.jsonl.gz", [archive_only,
        canonical.model_copy(update={"title": "Superseded archive", "updated_at": "2099-01-01T00:00:00Z"})])
    write_records(tmp_path / "data/signals.jsonl.gz", [canonical])
    # Unselected data does not need to instantiate thousands of full Signal models.
    with gzip.open(tmp_path / "data/signals.jsonl.gz", "at", encoding="utf-8") as stream:
        stream.write('\n{"id":"unselected","not_a_signal":true}\n')
    cached = canonical.documents[0].model_copy(update={"status": "cached", "content_hash": "a" * 64,
        "revision": "cached-revision", "pages": [{"page": 1, "text": "Complete extracted specification text."}]})
    atomic_json(tmp_path / "data/documents/index.json", {cached.url: {"document": cached.model_dump()}})
    fallback = signal.model_copy(update={"id": "generated-renewal"})
    atomic_json(tmp_path / "data/current.json", {"signals": [fallback.model_dump()]})
    original = {path: path.read_bytes() for path in (tmp_path / "data").rglob("*") if path.is_file()}
    hydrated = []
    hydrate = command.hydrate_cached_documents

    def track(root, records):
        hydrated.extend(record.id for record in records)
        return hydrate(root, records)

    monkeypatch.setattr(command, "hydrate_cached_documents", track)
    packet = command.export_packets(tmp_path, [canonical.id, archive_only.id, fallback.id, "missing"])
    records = {row["id"]: row for row in packet["records"]}
    assert records[canonical.id]["title"] == canonical.title  # Canonical overrides later archive timestamps.
    assert records[archive_only.id]["title"] == archive_only.title
    assert records[archive_only.id]["description"] == archive_only.description
    assert records[canonical.id]["documents"][0]["pages"] == cached.pages
    assert records[canonical.id]["translation_source_hash"] == source_key(canonical)
    assert set(hydrated) == {canonical.id, archive_only.id, fallback.id}
    assert packet["missing_ids"] == ["missing"]
    assert {path: path.read_bytes() for path in original} == original


def test_export_requires_explicit_ids_reports_missing_and_cannot_overwrite_ledgers(command, tmp_path, signal, capsys):
    write_records(tmp_path / "data/signals.jsonl", [signal])
    ids = tmp_path / "ids.txt"
    ids.write_text(signal.id + "\nmissing\n" + signal.id + "\n", encoding="utf-8")
    output = tmp_path / "artifacts/packet.json"
    assert command.main(["--root", str(tmp_path), "export", "--ids-file", str(ids), "--output", str(output)]) == 1
    value = json.loads(output.read_text(encoding="utf-8"))
    assert [row["id"] for row in value["records"]] == [signal.id]
    assert value["missing_ids"] == ["missing"]
    ledger = tmp_path / "config/record_reviews.json"
    atomic_json(ledger, {"version": 1, "records": []})
    previous = ledger.read_bytes()
    assert command.main(["--root", str(tmp_path), "export", "--id", signal.id, "--output", str(ledger)]) == 1
    assert ledger.read_bytes() == previous
    assert "read-only" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        command.main(["--root", str(tmp_path), "export"])


def test_validation_distinguishes_active_stale_and_missing_without_refreshing_hashes(command, tmp_path, signal):
    stale = signal.model_copy(deep=True, update={"id": "stale"})
    write_records(tmp_path / "data/signals.jsonl", [signal, stale])
    sources = command.load_selected(tmp_path, {signal.id, stale.id})
    current = review(sources[signal.id])
    old = review(sources[stale.id])
    old["source_hash"] = old["guidance"]["source_hash"] = "0" * 64
    # Old evidence need not match changed source, but must never be silently refreshed.
    old["guidance"]["approach"][0]["evidence"][0]["quote"] = "Previous source text that has since changed."
    missing = {**current, "id": "missing"}
    atomic_json(tmp_path / "config/record_reviews.json", {"version": 1, "records": [current, old, missing]})
    translated = translation(sources[signal.id])
    atomic_json(tmp_path / "config/reviewed_translations.json", {"version": 1, "records": [translated,
        {**translation(sources[stale.id]), "version": "retired-translation-version"}, {**translated, "id": "missing"}]})
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    report = command.validate_ledgers(tmp_path)
    assert report["valid"]
    for name in ("record_reviews", "translations"):
        assert {key: report[name][key] for key in ("active", "stale", "missing", "invalid")} == {
            "active": 1, "stale": 1, "missing": 1, "invalid": 0}
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize(("language", "status"), [("fra", "stale"), ("ger-DE", "active")])
def test_language_metadata_drift_is_reported_without_rewriting_review(command, tmp_path, signal, language, status):
    signal.source_language = "und"
    write_records(tmp_path / "data/signals.jsonl", [signal])
    source = command.load_selected(tmp_path, {signal.id})[signal.id]
    row = review(source)
    row["guidance"]["original_language"] = "de"
    row["guidance"]["localized"] = {"de": {"approach": [{
        "text": "Die vorhandenen Abläufe konfigurieren und freigegebene Systeme über APIs anbinden."
    }], "problems": []}}
    atomic_json(tmp_path / "config/record_reviews.json", {"version": 1, "records": [row]})
    source.source_language = language
    assert source_hash(source) == row["source_hash"]
    write_records(tmp_path / "data/signals.jsonl", [source])
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    result = command.validate_ledgers(tmp_path)
    assert result["valid"]
    assert result["record_reviews"][status] == 1
    assert result["record_reviews"]["invalid"] == 0
    assert result["record_reviews"]["records"] == [{"id": signal.id, "status": status}]
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("failure", ["evidence", "rating", "duplicate-review", "duplicate-translation", "translation"])
def test_invalid_proposed_reviews_and_translations_fail_without_mutating_sources(command, tmp_path, signal, failure, capsys):
    write_records(tmp_path / "data/signals.jsonl", [signal])
    source = command.load_selected(tmp_path, {signal.id})[signal.id]
    row, translated = review(source), translation(source)
    if failure == "evidence":
        row["guidance"]["approach"][0]["evidence"][0]["quote"] = "A made-up requirement absent from the source."
    elif failure == "rating":
        row["guidance"]["complexity"] = 11
    elif failure == "translation":
        translated["description"] += " This adds an unsupported claim."
    atomic_json(tmp_path / "config/record_reviews.json", {"version": 1,
        "records": [row, row] if failure == "duplicate-review" else [row]})
    atomic_json(tmp_path / "config/reviewed_translations.json", {"version": 1,
        "records": [translated, translated] if failure == "duplicate-translation" else [translated]})
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert command.main(["--root", str(tmp_path), "validate"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["valid"]
    section = "translations" if failure in {"translation", "duplicate-translation"} else "record_reviews"
    assert result[section]["invalid"] == 1
    assert {path: path.read_bytes() for path in before} == before
