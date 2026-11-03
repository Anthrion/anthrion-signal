"""Reviewed restorations keep eligibility blockers, related lifecycle notices and honest reporting."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from anthrion_signal import cli
from anthrion_signal.discovery import discovery_signature, is_public_opportunity
from anthrion_signal.discovery_retention import retain_rejected
from anthrion_signal.models import Dataset
from anthrion_signal.utils import atomic_json

from test_record_inclusions import (PHYSICAL, canonical_rows, classified, configured, inclusion, notice,
                                    restored_by, write_ledger)

ROOT = Path(__file__).resolve().parents[2]
RESCORE = {"command": "rescore", "days": None, "max_pages": None, "max_ai": 0, "no_ai": True, "sources": None}
ALIAS = "ted-notice:6a1f0000-0000-4000-8000-000000000001"


@pytest.fixture
def command():
    spec = importlib.util.spec_from_file_location("review_records_fixes", ROOT / "scripts/review_records.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def threshold(config):
    return config["capabilities"]["discovery"]["minimum_candidate_score"]


@pytest.fixture
def public(release, source, now, config):
    return classified(notice(release, source, now, "Salesforce CRM implementation",
        "The council requires Salesforce implementation and systems integration for its contact centre.",
        "72200000", reference="001"), config)


def write_canonical(root, *signals):
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data/signals.jsonl").write_text("".join(s.model_dump_json() + "\n" for s in signals), encoding="utf-8")


def ted_copy(signal, ident, number, *, status="active", updated="2026-09-08T10:00:00+00:00"):
    url = f"https://ted.europa.eu/en/notice/-/detail/{number}"
    return signal.model_copy(deep=True, update={
        "id": ident, "source": "ted", "ocid": None, "status": status, "primary_source_url": url, "source_urls": [url],
        "external_ids": [f"ted:{number}", ALIAS], "updated_at": updated, "last_seen_at": updated})


def cancelled_pair(release, source, now, config):
    base = notice(release, source, now, *PHYSICAL)
    return (classified(ted_copy(base, "sig_ted_original", "111111-2026"), config),
            classified(ted_copy(base, "sig_ted_cancel", "222222-2026", status="cancelled",
                                updated="2026-09-09T10:00:00+00:00"), config))


def test_restoration_keeps_eligibility_blockers(tmp_path, release, source, config, now):
    restricted = notice(release, source, now, "Case management platform",
                        "The council will configure Salesforce case management for tenant referrals. "
                        "Only public institutions may apply.", "72200000")
    write_ledger(tmp_path, inclusion(restricted, evidence=[{"field": "description",
        "quote": "configure Salesforce case management", "source_url": restricted.primary_source_url}]))
    assert restored_by(tmp_path, config, restricted)[0]
    assert restricted.exclusion_reasons and not is_public_opportunity(restricted, now)


def test_replayed_restoration_receives_its_retained_cancellation(tmp_path, release, source, config, now, threshold,
                                                                 public, monkeypatch):
    original, cancellation = cancelled_pair(release, source, now, config)
    write_canonical(tmp_path, public)
    retain_rejected(tmp_path, [original, cancellation], now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    write_ledger(tmp_path, inclusion(original))
    result = cli.run(tmp_path, SimpleNamespace(**RESCORE, no_export=True))
    assert [s.id for s in result.signals] == [public.id]
    assert canonical_rows(tmp_path)[original.id].status == "cancelled"


def test_export_recovery_reconciles_a_restoration_with_its_cancellation(tmp_path, release, source, config, now,
                                                                         threshold, public, monkeypatch):
    original, cancellation = cancelled_pair(release, source, now, config)
    write_canonical(tmp_path, public)
    retain_rejected(tmp_path, [original, cancellation], now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    previous = Dataset(generated_at=now.isoformat(), data_updated_at=now.isoformat(), profile_version="1",
                       scoring_version="none", run={"discovery_signature": discovery_signature(configured(config)(tmp_path))},
                       sources=[], capabilities=[], markets={}, evidence_catalog={}, signals=[public])
    atomic_json(tmp_path / "data/current.json", previous.model_dump())
    write_ledger(tmp_path, inclusion(original))
    assert [s.id for s in cli.export(tmp_path).signals] == [public.id]


def test_restoration_merged_into_another_identity_is_reported_stale(tmp_path, release, source, config, now,
                                                                     threshold, public, monkeypatch):
    national = classified(notice(release, source, now, *PHYSICAL), config)
    national.external_ids = [*national.external_ids, ALIAS]
    ted = classified(ted_copy(national, "sig_ted_copy", "333333-2026", updated="2026-09-09T10:00:00+00:00"), config)
    write_canonical(tmp_path, public, national)
    retain_rejected(tmp_path, [ted], now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    write_ledger(tmp_path, inclusion(ted))
    result = cli.run(tmp_path, SimpleNamespace(**RESCORE, no_export=True))
    assert [s.id for s in result.signals] == [public.id]
    assert (result.run["reviewed_inclusions"], result.run["reviewed_inclusions_stale"]) == (0, 1)


def test_url_only_amendment_keeps_the_restoration_and_a_url_refresh_does_not_replay(
        tmp_path, release, source, config, now, threshold, public, monkeypatch, command):
    reviewed = classified(notice(release, source, now, *PHYSICAL), config)
    later, moved = "2026-09-10T10:00:00+00:00", "https://www.find-tender.service.gov.uk/Notice/777777-2026"
    amended = reviewed.model_copy(deep=True, update={"primary_source_url": moved, "source_urls": [moved],
                                                     "updated_at": later, "last_seen_at": later})
    write_canonical(tmp_path, public)
    retain_rejected(tmp_path, [reviewed], now, threshold)
    retain_rejected(tmp_path, [amended], now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    ingest = SimpleNamespace(**{**RESCORE, "command": "ingest", "sources": "usaspending"}, no_export=True)
    write_ledger(tmp_path, inclusion(reviewed))
    first = cli.run(tmp_path, ingest)
    assert {s.id for s in first.signals} == {public.id, reviewed.id}
    assert (first.run["reviewed_inclusions"], first.run["reviewed_inclusions_stale"]) == (1, 0)
    report = command.validate_ledgers(tmp_path)
    assert report["valid"] and report["record_reviews"]["warnings"] == 1
    # A URL refresh changes nothing collection decides, so it clears the warning without a replay.
    write_ledger(tmp_path, inclusion(reviewed, evidence=[{"field": "description", "quote": reviewed.description[:90],
                                                          "source_url": moved}]))
    report = command.validate_ledgers(tmp_path)
    assert report["valid"] and "warnings" not in report["record_reviews"]
    result = cli.run(tmp_path, ingest)
    assert result.run["rejected_records_replayed"] == 0
    assert {s.id for s in result.signals} == {public.id, reviewed.id}


def test_repaired_quote_replays_a_suspended_restoration(tmp_path, release, source, config, now, threshold, public,
                                                        monkeypatch, command):
    # An untraceable quote fails the PR check, but a bypassed push still needs its repair to replay.
    reviewed = classified(notice(release, source, now, *PHYSICAL), config)
    write_canonical(tmp_path, public)
    retain_rejected(tmp_path, [reviewed], now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    ingest = SimpleNamespace(**{**RESCORE, "command": "ingest", "sources": "usaspending"}, no_export=True)
    write_ledger(tmp_path, inclusion(reviewed, evidence=[{"field": "description", "quote": "An invented passage.",
                                                          "source_url": reviewed.primary_source_url}]))
    assert cli.run(tmp_path, ingest).run["reviewed_inclusions_stale"] == 1
    write_ledger(tmp_path, inclusion(reviewed))
    assert command.validate_ledgers(tmp_path)["valid"]
    result = cli.run(tmp_path, ingest)
    assert result.run["rejected_records_replayed"] == 1
    assert {s.id for s in result.signals} == {public.id, reviewed.id}


def test_export_keeps_the_collected_stale_count(tmp_path, release, source, config, now, threshold, public,
                                                monkeypatch):
    restored = classified(notice(release, source, now, *PHYSICAL), config)
    write_canonical(tmp_path, public)
    retain_rejected(tmp_path, [restored], now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    write_ledger(tmp_path, inclusion(restored, hash_value="1" * 64))
    assert cli.run(tmp_path, SimpleNamespace(**RESCORE, no_export=True)).run["reviewed_inclusions_stale"] == 1
    assert cli.export(tmp_path).run["reviewed_inclusions_stale"] == 1
