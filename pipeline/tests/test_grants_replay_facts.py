"""Retained source corrections survive legacy replay before availability checks."""
import gzip
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from anthrion_signal import cli
from anthrion_signal.collectors import RawRecord
from anthrion_signal.discovery import lifecycle
from anthrion_signal.models import Dataset, Signal
from anthrion_signal.normalise import material_payload, normalise_grants, set_hashes
from anthrion_signal.utils import atomic_json, digest, jsonl_lines


@pytest.mark.parametrize("operation", ["rescore", "export"])
def test_same_day_grant_remains_public_after_equal_timestamp_legacy_replay(tmp_path, config, now, monkeypatch, operation):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "grants")
    raw = {"id": "123456", "title": "Salesforce CRM implementation and systems integration", "status": "posted",
        "agencyDetails": {"agencyCode": "DOE-SC", "agencyName": "Office of Science"},
        "facts": {"agencyName": "Public contact", "agencyContactName": "Public contact", "agencyContactDesc": "Grant specialist",
                  "createTimeStampStr": "2026-09-08-00-00-00", "postingDateStr": "2026-09-08-00-00-00",
                  "responseDateStr": now.strftime("%Y-%m-%d-00-00-00"),
                  "synopsisDesc": "Implement Salesforce CRM and systems integration for a new customer service portal."}}
    corrected = normalise_grants(RawRecord(raw, source, now.isoformat(), "grants"))
    legacy = corrected.model_copy(deep=True)
    legacy.buyer_name, legacy.deadline_at = "Public contact", now.strftime("%Y-%m-%dT00:00:00+00:00")
    set_hashes(legacy)
    assert legacy.updated_at == corrected.updated_at
    assert legacy.raw_source_hash == corrected.raw_source_hash == digest(raw)
    assert lifecycle(legacy, now)[0] == "EXPIRED" and lifecycle(corrected, now)[0] == "OPEN"

    (tmp_path / "data/discovery/rejected").mkdir(parents=True)
    (tmp_path / "data/signals.jsonl").write_text(legacy.model_dump_json() + "\n", encoding="utf-8")
    rejected = [legacy]
    if operation == "export":
        # A same-day midnight alias would already fail export's availability
        # gate. A stale next-day cutoff reaches reconciliation, where the cache
        # must restore the actual closing day and agency after the merge.
        alias = legacy.model_copy(update={"id": "sig_retained_alias",
            "deadline_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+00:00")}, deep=True)
        set_hashes(alias)
        rejected.append(alias)
        previous = Dataset(generated_at=now.isoformat(), data_updated_at=now.isoformat(),
            profile_version=config["company_profile"]["version"], scoring_version="none",
            run={"discovery_signature": "previous-policy"}, sources=[], capabilities=[],
            markets=config["search_terms"]["markets"], evidence_catalog={}, signals=[legacy])
        atomic_json(tmp_path / "data/current.json", previous.model_dump())
    (tmp_path / "data/discovery/rejected/2026-09-08.jsonl.gz").write_bytes(
        gzip.compress(("\n".join(s.model_dump_json() for s in rejected) + "\n").encode("utf-8")))
    atomic_json(tmp_path / "data/source_state.json", {"grants": {"detail_cache": {"123456": {"record": raw}}}})

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(cli, "datetime", FrozenDateTime)
    monkeypatch.setattr(cli, "load_config", lambda root: config)
    if operation == "rescore":
        args = SimpleNamespace(command="rescore", days=None, max_pages=None, max_ai=0, no_ai=True, sources=None)
        result = cli.run(tmp_path, args)
        assert result.run["rejected_records_replayed"] == 1
        stored = Signal.model_validate_json(next(jsonl_lines((tmp_path / "data/signals.jsonl").read_text(encoding="utf-8"))))
    else:
        reconciled_aliases = []
        actual_reconcile = cli.reconcile

        def observed_reconcile(previous, incoming):
            reconciled_aliases.extend(s.id for s in incoming)
            records, index, stats = actual_reconcile(previous, incoming)
            # Demonstrate that the conditional path really replayed stale facts.
            assert records[0].buyer_name == "Public contact"
            assert records[0].deadline_at == alias.deadline_at
            return records, index, stats

        monkeypatch.setattr(cli, "reconcile", observed_reconcile)
        canonical_before = (tmp_path / "data/signals.jsonl").read_bytes()
        result = cli.export(tmp_path)
        assert reconciled_aliases == [alias.id]
        assert result.run["discovery_signature"] != "previous-policy"
        assert (tmp_path / "data/signals.jsonl").read_bytes() == canonical_before
        stored = result.signals[0]
    assert [s.id for s in result.signals] == [corrected.id]
    assert stored.buyer_name == "Office of Science" and stored.contacts[0]["name"] == "Public contact"
    assert stored.deadline_at == corrected.deadline_at and stored.deadlines[0].precision == "date"
    assert stored.lifecycle_state == "OPEN"
    assert (stored.title, stored.description, stored.raw_source_hash, stored.updated_at) == (
        legacy.title, legacy.description, legacy.raw_source_hash, legacy.updated_at)
    assert stored.content_hash == stored.material_change_hash == digest(material_payload(stored))
    published = json.loads((tmp_path / "app/public/data/current.json").read_text(encoding="utf-8"))["signals"]
    assert [s["id"] for s in published] == [corrected.id]
    assert published[0]["buyer_name"] == "Office of Science" and published[0]["deadline_at"] == now.date().isoformat()
