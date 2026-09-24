"""Valid source strings must survive JSONL round trips across all durable stores."""
import gzip
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from anthrion_signal import cli
from anthrion_signal.award_history import retained_history
from anthrion_signal.collectors import RawRecord
from anthrion_signal.discovery_retention import read_rejected, retain_rejected
from anthrion_signal.models import Signal, SourceHealth
from anthrion_signal.normalise import normalise_ocds
from anthrion_signal.retention import read_archive
from anthrion_signal.utils import jsonl_lines


def load_script(name):
    path = Path(__file__).resolve().parents[2] / 'scripts' / f'{name}.py'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('separator', ['\u0085', '\u2028', '\u2029'])
@pytest.mark.parametrize('ending', ['\n', '\r\n'])
def test_valid_json_strings_survive_archive_rejection_and_history_readers(tmp_path, signal, now, separator, ending):
    signal.incumbent_supplier = f'Consulting Services Limited.{separator}Partner'
    signal.prefilter_score = 0
    serialized = signal.model_dump_json()
    body = serialized + ending + ending
    assert Signal.model_validate_json(serialized).incumbent_supplier == signal.incumbent_supplier
    assert len(body.splitlines()) > len(list(jsonl_lines(body)))  # Reproduces the old split inside a string.
    assert [Signal.model_validate_json(line) for line in jsonl_lines(body)] == [signal]
    archive = tmp_path / 'data/archive/2026-09.jsonl.gz'
    archive.parent.mkdir(parents=True)
    archive.write_bytes(gzip.compress(body.encode('utf-8')))
    assert read_archive(tmp_path, '2026-09')[signal.id] == signal
    assert retained_history(tmp_path, []) == [signal]
    reconcile = load_script('reconcile_release_data')
    assert reconcile.records(body.encode('utf-8'))[signal.id] == signal.model_dump(mode='json')
    assert reconcile.records(archive.read_bytes(), compressed=True)[signal.id] == signal.model_dump(mode='json')
    audit = load_script('audit_relevance')
    assert audit.retained_records(tmp_path)[0] == [signal]
    retain_rejected(tmp_path, [signal], now, 12)
    retain_rejected(tmp_path, [signal], now, 12)  # Also reads the existing compressed partition.
    assert read_rejected(tmp_path) == [signal]


@pytest.mark.parametrize('separator', ['\u0085', '\u2028', '\u2029'])
def test_ingest_then_export_and_rescore_preserve_supplier_name(tmp_path, signal, release, source, now, config, monkeypatch, separator):
    release['id'], release['ocid'], release['tag'] = 'unicode-award', 'unicode-award', ['award']
    release['awards'] = [{'suppliers': [{'name': f'Consulting Services Limited.{separator}Partner'}]}]
    award = normalise_ocds(RawRecord(release, source, now.isoformat()))
    health = SourceHealth(id=source['id'], name=source['name'], website=source['website'], enabled=True, status='healthy')
    monkeypatch.setattr(cli, 'load_config', lambda root: config)
    monkeypatch.setattr(cli, '_collect', lambda *args: (source['id'], [signal, award], {}, health, 2))
    args = SimpleNamespace(command='ingest', days=None, max_pages=None, max_ai=0, no_ai=True, sources=source['id'])
    cli.run(tmp_path, args)  # Exercises the exact failing write-then-export path.
    args.command = 'rescore'
    cli.run(tmp_path, args)  # Reads canonical data again without any collection.
    saved = [Signal.model_validate_json(line) for line in jsonl_lines((tmp_path / 'data/signals.jsonl').read_text(encoding='utf-8'))]
    assert any(s.incumbent_supplier == award.incumbent_supplier for s in saved)
    assert (tmp_path / 'app/public/data/current.json.gz').exists()


def test_genuinely_truncated_json_is_not_silently_discarded(tmp_path):
    archive = tmp_path / 'data/archive/2026-09.jsonl.gz'
    archive.parent.mkdir(parents=True)
    archive.write_bytes(gzip.compress(b'{"id":"unfinished\n'))
    with pytest.raises(ValueError, match='Invalid JSON'):
        read_archive(tmp_path, '2026-09')
