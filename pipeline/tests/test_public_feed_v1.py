import gzip
import json
import runpy
from pathlib import Path

import pytest

from anthrion_signal.cli import public_data
from anthrion_signal.discovery import prefilter
from anthrion_signal.models import Dataset, EnglishText
from anthrion_signal.public_context import attach_history
from anthrion_signal.public_feed import export_current, atomic_public_json
from anthrion_signal.utils import atomic_json, digest, read_json


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
    summary = read_json(root / data.current_feed["markets"]["GB"]["url"], {})["signals"][0]
    assert summary["description"] == "" and summary["is_summary"]
    assert "rare final phrase" in summary["search_text"] and "English rare phrase" in summary["search_text"]
    detail = read_json(root / data.current_feed["records"][signal.id]["url"], {})
    assert detail["signal"]["description"] == signal.description
    assert not detail["signal"]["buyer_history"]
    buyer = read_json(root / detail["signal"]["buyer_history_ref"]["url"], {})
    assert buyer["records"][0]["signal_id"] == signal.id
    checker = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/check_public_output.py"))["check_public_output"]
    atomic_json(root / "obsolete.json", {"old": "unreferenced export"})
    inventory = tmp_path / "tmp/public-data-files.json"
    assert checker(root / "current.json", inventory)[0] == 1
    assert set(json.loads(inventory.read_text())) == {
        "current.json", "manifest.json", detail["signal"]["buyer_history_ref"]["url"],
        *[p["url"] for p in data.current_feed["markets"].values()],
        *[p["url"] for p in data.current_feed["records"].values()],
    }


def test_content_change_preserves_previous_manifest_dependencies(tmp_path, signal, config):
    data = make_feed(tmp_path, signal, config)
    old = data.current_feed["records"][signal.id]["url"]
    old_bytes = (tmp_path / "app/public/data" / old).read_bytes()
    signal.description += " Changed source requirement."
    data.translations = {}
    data.current_feed = export_current(tmp_path, data)
    assert old != data.current_feed["records"][signal.id]["url"]
    assert (tmp_path / "app/public/data" / old).read_bytes() == old_bytes


def test_linked_history_gets_full_details_without_becoming_a_live_lead(tmp_path, signal, config, now):
    from anthrion_signal.award_history import export_awards
    from anthrion_signal.public_feed import record_file
    signal.buyer_name = "Council history fixture"
    earlier = signal.model_copy(deep=True, update={"id": "history-old", "title": "Park grounds maintenance", "description": "Complete grounds maintenance specification.", "status": "complete"})
    unrelated = earlier.model_copy(deep=True, update={"id": "unlinked-old", "buyer_name": "Separate authority", "buyer_id": None, "buyer_identifiers": [], "ocid": "separate", "procedure_id": None, "procedure_identifiers": []})
    data = make_feed(tmp_path, signal, config)
    records = {}
    data.award_history = export_awards(tmp_path, [signal, earlier, unrelated], config, now, records, [signal])
    assert records[earlier.id]["view"] == "history"
    assert unrelated.id not in records
    data.current_feed = export_current(tmp_path, data, records)
    root = tmp_path / "app/public/data"
    detail = json.loads(gzip.decompress((root / records[earlier.id]["url"]).read_bytes()))["records"][earlier.id]
    assert detail["signal"]["description"] == earlier.description
    current = read_json(root / data.current_feed["markets"]["GB"]["url"], {})
    assert [s["id"] for s in current["signals"]] == [signal.id]
    checker = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/check_public_output.py"))["check_public_output"]
    def roots():
        body = public_data(data)
        atomic_json(root / "current.json", body)
        atomic_json(root / "manifest.json", {**body, "signals": [], "translations": {}})
    roots()
    checker(root / "current.json")
    # A shared, correctly hashed bucket must not carry additional unpublished records.
    history_url = records[earlier.id]["url"]
    bucket = json.loads(gzip.decompress((root / history_url).read_bytes()))
    bucket["records"][unrelated.id] = {"signal": {**detail["signal"], "id": unrelated.id}}
    extra_url = f"history/abc-{digest(bucket)[:16]}.json.gz"
    (root / extra_url).write_bytes(gzip.compress(json.dumps(bucket).encode()))
    data.current_feed["records"][earlier.id]["url"] = extra_url
    roots()
    with pytest.raises(ValueError, match="outside its manifest"):
        checker(root / "current.json")
    data.current_feed["records"][earlier.id]["url"] = history_url
    # A retained record cannot publish itself by referring to its own buyer page.
    attach_history([unrelated], [unrelated])
    _, pointer = record_file(tmp_path, unrelated, view="history")
    data.current_feed["records"][unrelated.id] = pointer
    roots()
    with pytest.raises(ValueError, match="unlinked history"):
        checker(root / "current.json")


def test_history_titles_only_reuse_translations_for_the_same_original_source(signal):
    translation = EnglishText(source_hash=digest([signal.title, signal.description]), version="test", title="English timeline title", description="English scope")
    attach_history([signal], [signal], {signal.id: translation})
    assert signal.buyer_history[0]["title_en"] == "English timeline title"
    signal.title += " Revised"
    attach_history([signal], [signal], {signal.id: translation})
    assert "title_en" not in signal.buyer_history[0]


def test_history_buckets_preserve_full_records_and_split_without_overwriting_old_versions(tmp_path, signal):
    from anthrion_signal.public_feed import history_files
    prefixes = {}
    for number in range(4097):
        ident = f"history-{number}"
        prefix = digest(ident)[:3]
        if prefix in prefixes:
            identifiers = [prefixes[prefix], ident]
            break
        prefixes[prefix] = ident
    signals = [signal.model_copy(deep=True, update={"id": ident, "description": "Portail français — complete source. " * 30}) for ident in identifiers]
    manifest = history_files(tmp_path, signals, {}, {})
    assert len({ref["url"] for ref in manifest.values()}) == 1
    path = tmp_path / "app/public/data" / manifest[identifiers[0]]["url"]
    original = path.read_bytes()
    decoded = gzip.decompress(original)
    payload = json.loads(decoded)
    assert set(payload["records"]) == set(identifiers)
    assert all(payload["records"][item.id]["signal"]["description"] == item.description for item in signals)
    assert history_files(tmp_path, list(reversed(signals)), {}, {}) == manifest
    assert path.read_bytes() == original
    split = history_files(tmp_path, signals, {}, {}, max_bytes=len(decoded) - 1)
    assert len({ref["url"] for ref in split.values()}) == 2
    assert path.read_bytes() == original
    signals[0].description += " Published amendment."
    assert history_files(tmp_path, signals, {}, {})[identifiers[0]]["url"] != manifest[identifiers[0]]["url"]
    assert path.read_bytes() == original


def test_corrupt_hashed_detail_fails_publication_validation(tmp_path, signal, config):
    data = make_feed(tmp_path, signal, config)
    root = tmp_path / "app/public/data"
    file = root / data.current_feed["records"][signal.id]["url"]
    page = read_json(file, {})
    page["signal"]["description"] = "Tampered"
    atomic_public_json(file, page)
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
