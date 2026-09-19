import gzip
import json
from types import SimpleNamespace

import pytest

from anthrion_signal import cli, utils
from anthrion_signal.models import Signal, SourceHealth
from anthrion_signal.public_context import public_signal


def test_lossless_migration_is_deterministic_and_keeps_unicode_lines(tmp_path, signal):
    path = tmp_path / "signals.jsonl"
    signal.description += " original\u2028text café"
    body = (signal.model_dump_json() + "\n").encode("utf-8")
    path.write_bytes(body)
    assert utils.atomic_retained_bytes(path, body, threshold=1)
    packed = path.with_suffix(".jsonl.gz")
    assert not path.exists() and packed.exists()
    assert gzip.decompress(packed.read_bytes()) == body
    assert utils.read_retained_bytes(path) == body
    assert not utils.atomic_retained_bytes(path, body, threshold=1)
    restored = Signal.model_validate_json(next(utils.jsonl_lines(utils.read_retained_bytes(path).decode("utf-8"))))
    assert restored.model_dump() == signal.model_dump()
    utils.atomic_retained_bytes(path, b'{}\n')
    assert packed.exists() and not path.exists() and utils.read_json(path, {}) == {}


def test_failed_replacement_preserves_plain_source_and_corrupt_gzip_is_not_empty(tmp_path, monkeypatch):
    path = tmp_path / "current.json"
    path.write_text('{"retained":true}', encoding="utf-8")
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(utils, "atomic_bytes", fail)
    with pytest.raises(OSError):
        utils.atomic_retained_bytes(path, b'{"new":true}', threshold=1)
    assert utils.read_json(path, {}) == {"retained": True}
    path.unlink()
    path.with_suffix(".json.gz").write_bytes(b"corrupt")
    with pytest.raises(gzip.BadGzipFile):
        utils.read_json(path, {})


def test_ingest_rescore_export_and_validation_preserve_compressed_source_facts(tmp_path, signal, source, config, monkeypatch):
    health = SourceHealth(id=source["id"], name=source["name"], website=source["website"], enabled=True, status="healthy")
    monkeypatch.setattr(cli, "load_config", lambda root: config)
    monkeypatch.setattr(cli, "_collect", lambda *args: (source["id"], [signal], {}, health, 1))
    monkeypatch.setattr(cli, "enrich_documents", lambda *args, **kwargs: None)
    write = utils.atomic_retained_bytes
    monkeypatch.setattr(cli, "atomic_retained_bytes", lambda path, body: write(path, body, threshold=1))
    monkeypatch.setattr(cli, "atomic_retained_json", lambda path, value: write(path, json.dumps(value).encode(), threshold=1))
    args = SimpleNamespace(command="ingest", days=None, max_pages=None, max_ai=0, no_ai=True, sources=source["id"])
    initial = cli.run(tmp_path, args)
    assert not (tmp_path / "data/signals.jsonl").exists()
    assert (tmp_path / "data/signals.jsonl.gz").exists()
    assert (tmp_path / "data/current.json.gz").exists()
    args.command = "rescore"
    repeated = cli.run(tmp_path, args)
    assert [public_signal(s) for s in repeated.signals] == [public_signal(s) for s in initial.signals]
    assert cli.export(tmp_path).signals
    assert utils.read_json(tmp_path / "app/public/data/current.json", {})["signals"]
    assert not (tmp_path / "app/public/data/current.json.gz").exists()


def test_deferred_export_and_translation_preparation_do_not_build_assets(tmp_path, signal, source, config, monkeypatch):
    health = SourceHealth(id=source["id"], name=source["name"], website=source["website"], enabled=True, status="healthy")
    monkeypatch.setattr(cli, "load_config", lambda root: config)
    monkeypatch.setattr(cli, "_collect", lambda *args: (source["id"], [signal], {}, health, 1))
    monkeypatch.setattr(cli, "enrich_documents", lambda *args, **kwargs: None)
    args = SimpleNamespace(command="ingest", days=None, max_pages=None, max_ai=0, no_ai=True, sources=source["id"], no_export=True)
    cli.run(tmp_path, args)
    before = {p: p.read_bytes() for p in (tmp_path / "data").rglob("*") if p.is_file()}
    candidates, _, _ = cli.prepare_current(tmp_path)
    assert candidates.signals
    assert not (tmp_path / "app/public/data").exists()
    assert before == {p: p.read_bytes() for p in (tmp_path / "data").rglob("*") if p.is_file()}
    def translation_inputs(signals):
        return [(s.id, s.title, s.description, s.buyer_name, s.prefilter_score, s.matched_capabilities) for s in signals]
    assert translation_inputs(candidates.signals) == translation_inputs(cli.export(tmp_path).signals)
