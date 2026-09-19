import json
import runpy
from pathlib import Path

import pytest

from anthrion_signal.cli import public_data
from anthrion_signal.discovery import prefilter
from anthrion_signal.models import Dataset, EnglishText
from anthrion_signal.public_context import attach_history
from anthrion_signal.public_feed import export_current
from anthrion_signal.utils import atomic_json, digest


def make_feed(tmp_path, signal, config):
    signal.title, signal.description = "CRM source title", "Full original description with a rare final phrase."
    prefilter([signal], config["company_profile"], config["search_terms"], config["capabilities"])
    translation = EnglishText(source_hash=digest([signal.title, signal.description]), version="test", title="English CRM title",
                              description="Complete translated text with an English rare phrase.")
    data = Dataset(generated_at="2026-09-18T10:00:00Z", data_updated_at="2026-09-18T10:00:00Z", profile_version="1",
                   scoring_version="none", run={}, sources=[], capabilities=[], markets={}, evidence_catalog={},
                   signals=[signal], translations={signal.id: translation})
    attach_history([signal], [signal])
    data.current_feed = export_current(tmp_path, data)
    body = public_data(data)
    atomic_json(tmp_path / "app/public/data/current.json", body)
    atomic_json(tmp_path / "app/public/data/manifest.json", {**body, "signals": [], "translations": {}})
    return data


def test_indexes_keep_original_english_search_and_lazy_full_evidence(tmp_path, signal, config):
    data = make_feed(tmp_path, signal, config)
    root = tmp_path / "app/public/data"
    summary = json.loads((root / data.current_feed["markets"]["GB"]["url"]).read_text(encoding="utf-8"))["signals"][0]
    assert summary["description"] == "" and summary["is_summary"]
    assert "rare final phrase" in summary["search_text"] and "English rare phrase" in summary["search_text"]
    detail = json.loads((root / data.current_feed["records"][signal.id]["url"]).read_text(encoding="utf-8"))
    assert detail["signal"]["description"] == signal.description
    assert not detail["signal"]["buyer_history"]
    buyer = json.loads((root / detail["signal"]["buyer_history_ref"]["url"]).read_text(encoding="utf-8"))
    assert buyer["records"][0]["signal_id"] == signal.id
    checker = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/check_public_output.py"))["check_public_output"]
    assert checker(root / "current.json")[0] == 1


def test_content_change_preserves_previous_manifest_dependencies(tmp_path, signal, config):
    data = make_feed(tmp_path, signal, config)
    old = data.current_feed["records"][signal.id]["url"]
    old_bytes = (tmp_path / "app/public/data" / old).read_bytes()
    signal.description += " Changed source requirement."
    data.translations = {}
    data.current_feed = export_current(tmp_path, data)
    assert old != data.current_feed["records"][signal.id]["url"]
    assert (tmp_path / "app/public/data" / old).read_bytes() == old_bytes


def test_corrupt_hashed_detail_fails_publication_validation(tmp_path, signal, config):
    data = make_feed(tmp_path, signal, config)
    root = tmp_path / "app/public/data"
    file = root / data.current_feed["records"][signal.id]["url"]
    page = json.loads(file.read_text(encoding="utf-8"))
    page["signal"]["description"] = "Tampered"
    atomic_json(file, page)
    checker = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/check_public_output.py"))["check_public_output"]
    with pytest.raises(ValueError, match="content hash"):
        checker(root / "current.json")


def test_every_expanded_market_has_consistent_official_ted_partition(config):
    from anthrion_signal.markets import MARKETS, TED_COUNTRIES
    source = next(s for s in config["sources"]["sources"] if s["id"] == "ted")
    assert {"BE", "NL", "FR", "CH", "AT", "IE", "PT", "PL", "EE", "LV", "LT", "CZ", "RO", "BG", "HR", "HU", "LU", "CY", "MT", "SI", "SK"} <= set(source["countries"])
    for market in source["countries"]:
        assert market in MARKETS and config["search_terms"]["markets"][market]["enabled"]
        assert config["search_terms"]["markets"][market]["ted_codes"][0] in TED_COUNTRIES
