"""Catalogue changes reuse decisions only after exact full-policy proof."""

import copy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from anthrion_signal import award_history, cli, discovery_cache
from anthrion_signal.discovery import discovery_signature
from anthrion_signal.models import Dataset
from anthrion_signal.utils import atomic_json, read_json


def policies(config):
    previous = copy.deepcopy(config)
    previous["search_terms"]["markets"] = {"GB": copy.deepcopy(config["search_terms"]["markets"]["GB"])}
    current = copy.deepcopy(previous)
    current["search_terms"]["markets"]["GP"] = {"name": "Guadeloupe", "enabled": True, "ted_codes": []}
    current["search_terms"]["markets"]["CARIBBEANREGIONAL"] = {"name": "Caribbean (regional)", "enabled": True}
    return previous, current


def legacy_cache(path):
    data = json.loads(gzip.decompress(path.read_bytes()))
    data.pop("markets", None)
    path.write_bytes(gzip.compress(json.dumps(data).encode()))


def no_misses(signals, *args):
    assert not signals, "Unchanged source decisions must not be recomputed"


@pytest.mark.parametrize("change", ["name", "enabled", "add"])
def test_exact_catalogue_change_reuses_legacy_decisions_and_saves_zero_miss_migration(
    tmp_path, signal, config, monkeypatch, change
):
    previous, current = policies(config)
    if change != "add":
        current = copy.deepcopy(previous)
        current["search_terms"]["markets"]["GB"][change] = "United Kingdom and Crown Dependencies" if change == "name" else False
    cache = discovery_cache.ClassificationCache(tmp_path, previous)
    cache.classify([signal])
    cache.save()
    legacy_cache(cache.path)
    assert discovery_signature(previous) != discovery_signature(current)
    migrated = discovery_cache.ClassificationCache(tmp_path, current, previous_markets=previous["search_terms"]["markets"])
    monkeypatch.setattr(discovery_cache, "prefilter", no_misses)
    assert migrated.classify([signal]) == 0
    assert migrated.dirty
    migrated.save()
    body = json.loads(gzip.decompress(cache.path.read_bytes()))
    assert body["signature"] == discovery_signature(current)
    assert body["markets"] == current["search_terms"]["markets"]
    assert discovery_cache.ClassificationCache(tmp_path, current).classify([signal]) == 0


@pytest.mark.parametrize("change", ["cpv", "capability", "profile", "inclusion", "engine"])
def test_catalogue_bridge_never_accepts_changed_policy_or_engine(config, monkeypatch, change):
    previous, current = policies(config)
    old_signature = discovery_signature(previous)
    bridge = [{"signature": old_signature, "markets": previous["search_terms"]["markets"]}]
    if change == "cpv":
        current["search_terms"]["cpv_prefixes"].append("99")
    elif change == "capability":
        current["capabilities"]["capabilities"][0]["needs"].append("changed capability requirement")
    elif change == "profile":
        current["company_profile"]["version"] += "-changed"
    elif change == "inclusion":
        current["reviewed_inclusions"].append(["sig_restored", "source-hash", "platform", [["description", "new evidence"]]])
    else:
        original = Path.read_text
        def changed_engine(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            return text + "\n# changed classifier engine\n" if path.name == "capability_matching.py" else text
        monkeypatch.setattr(Path, "read_text", changed_engine)
    proof = discovery_cache.DiscoverySignatures(current, previous["search_terms"]["markets"], bridge)
    assert not proof.accepts(old_signature)
    assert proof.transitions() == []


@pytest.mark.parametrize("catalogue", [None, [], {"GB": None}, {"GB": {"name": "UK", "enabled": "yes"}}])
def test_missing_or_malformed_prior_catalogue_cannot_bypass_signature(config, catalogue):
    previous, current = policies(config)
    proof = discovery_cache.DiscoverySignatures(current, catalogue, [{"markets": catalogue, "signature": "not-proved"}])
    assert not proof.accepts(discovery_signature(previous))
    assert proof.transitions() == []


def test_catalogue_reuse_keeps_record_translation_and_schema_validation(tmp_path, signal, config):
    previous, current = policies(config)
    cache = discovery_cache.ClassificationCache(tmp_path, previous)
    cache.classify([signal])
    cache.save()
    unchanged = signal.model_copy(deep=True)
    changed = signal.model_copy(deep=True, update={"id": "changed", "description": "CRM implementation with a new integration requirement."})
    translated = signal.model_copy(deep=True, update={"id": "translated"})
    overlay = {"translated": {"title": "CRM implementation", "description": "Implement CRM and a customer portal."}}
    migrated = discovery_cache.ClassificationCache(tmp_path, current)
    assert migrated.classify([unchanged, changed, translated], overlay) == 2
    body = json.loads(gzip.decompress(cache.path.read_bytes()))
    next(iter(body["records"].values()))["delivery_priority"] = "invalid"
    cache.path.write_bytes(gzip.compress(json.dumps(body).encode()))
    assert discovery_cache.ClassificationCache(tmp_path, current).classify([signal]) == 1


def seed_snapshot(root, signal, config, now):
    current = signal.model_copy(deep=True, update={"countries": ["GP"]})
    award = signal.model_copy(deep=True, update={"id": "award", "countries": ["GP"], "signal_type": "AWARD", "status": "complete"})
    cache = discovery_cache.ClassificationCache(root, config)
    cache.classify([current, award])
    cache.save()
    legacy_cache(cache.path)
    dataset = Dataset(generated_at=now.isoformat(), data_updated_at=now.isoformat(), profile_version="1",
                      scoring_version="none", sources=[], capabilities=[], markets=config["search_terms"]["markets"],
                      evidence_catalog={}, signals=[current], run={"discovery_signature": discovery_signature(config)})
    atomic_json(root / "data/current.json", dataset.model_dump())
    (root / "data/signals.jsonl").write_text(current.model_dump_json() + "\n" + award.model_dump_json() + "\n", encoding="utf-8")
    atomic_json(root / "data/discovery/state.json", {"signature": discovery_signature(config)})
    award_history.prepare_awards(root, [current, award], config, now)
    legacy_cache(root / "data/discovery/award_classification.json.gz")
    return current, award


def test_catalogue_only_export_skips_rejected_replay_and_publishes_new_shards(
    tmp_path, signal, config, now, monkeypatch
):
    previous, current = policies(config)
    seed_snapshot(tmp_path, signal, previous, now)
    monkeypatch.setattr(cli, "load_config", lambda root: current)
    monkeypatch.setattr(cli, "read_rejected", lambda root: pytest.fail("Catalogue changes must not replay rejected notices"))
    monkeypatch.setattr(discovery_cache, "prefilter", no_misses)
    monkeypatch.setattr(award_history, "prefilter", no_misses)
    original = cli.read_json
    current_reads = []
    def tracked(path, default):
        if path.name == "current.json":
            current_reads.append(path)
        return original(path, default)
    monkeypatch.setattr(cli, "read_json", tracked)
    monkeypatch.setattr(award_history, "read_json", tracked)
    exported = cli.export(tmp_path)
    assert len(current_reads) == 1
    assert exported.markets == current["search_terms"]["markets"]
    assert exported.current_feed["markets"]["CARIBBEAN"]["count"] == 1
    assert exported.award_history["CARIBBEAN"]["count"] == 1
    assert exported.run["discovery_signature"] == discovery_signature(current)


def test_ingest_without_export_preserves_proof_for_later_legacy_award_cache(
    tmp_path, signal, config, now, monkeypatch
):
    previous, current = policies(config)
    seed_snapshot(tmp_path, signal, previous, now)
    current["sources"]["sources"] = []
    monkeypatch.setattr(cli, "load_config", lambda root: current)
    monkeypatch.setattr(cli, "read_rejected", lambda root: pytest.fail("Catalogue changes must not replay rejected notices"))
    monkeypatch.setattr(discovery_cache, "prefilter", no_misses)
    monkeypatch.setattr(award_history, "prefilter", no_misses)
    args = SimpleNamespace(command="ingest", days=None, max_pages=None, max_ai=0, no_ai=True, sources=None, no_export=True)
    ingested = cli.run(tmp_path, args)
    assert ingested.run["rejected_records_replayed"] == 0
    assert read_json(tmp_path / "data/current.json", {})["markets"] == current["search_terms"]["markets"]
    state = read_json(tmp_path / "data/discovery/state.json", {})
    assert state["market_catalogues"] == [{"signature": discovery_signature(previous), "markets": previous["search_terms"]["markets"]}]
    exported = cli.export(tmp_path)
    assert exported.award_history["CARIBBEAN"]["count"] == 1
    migrated = json.loads(gzip.decompress((tmp_path / "data/discovery/award_classification.json.gz").read_bytes()))
    assert migrated["signature"] == discovery_signature(current)
    assert migrated["markets"] == current["search_terms"]["markets"]


@pytest.mark.parametrize("operation", ["policy_change", "rescore"])
def test_real_policy_change_and_explicit_rescore_still_replay_rejected(
    tmp_path, signal, config, now, monkeypatch, operation
):
    previous, current = policies(config)
    seed_snapshot(tmp_path, signal, previous, now)
    if operation == "policy_change":
        current["search_terms"]["cpv_prefixes"].append("99")
    current["sources"]["sources"] = []
    monkeypatch.setattr(cli, "load_config", lambda root: current)
    replays = []
    monkeypatch.setattr(cli, "read_rejected", lambda root: replays.append(root) or [])
    args = SimpleNamespace(command="rescore" if operation == "rescore" else "ingest", days=None,
                           max_pages=None, max_ai=0, no_ai=True, sources=None, no_export=True)
    cli.run(tmp_path, args)
    assert replays == [tmp_path]


def test_corrupt_optional_transition_and_prior_dataset_recompute_without_crashing(tmp_path, signal, config, now):
    previous, current = policies(config)
    _, award = seed_snapshot(tmp_path, signal, previous, now)
    (tmp_path / "data/discovery/state.json").write_text("{bad", encoding="utf-8")
    (tmp_path / "data/current.json").write_text("{bad", encoding="utf-8")
    assert discovery_cache.ClassificationCache(tmp_path, current).classify([signal]) == 1
    awards, _, _ = award_history.prepare_awards(tmp_path, [award], current, now)
    assert [item.id for item in awards] == [award.id]
