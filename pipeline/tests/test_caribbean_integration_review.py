"""Cross-review regressions for shared Caribbean collection integration."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from anthrion_signal import cli
from anthrion_signal.boamp_caribbean import normalise_boamp_caribbean
from anthrion_signal.collectors import Collection, RawRecord
from anthrion_signal.dedupe import reconcile


def test_boamp_correction_chain_keeps_scope_when_later_notice_references_original(monkeypatch):
    """A -> B -> C -> A references still describe one cumulative procedure."""
    fixtures = {row["idweb"]: row for row in json.loads(
        (Path(__file__).parent / "fixtures/boamp_caribbean.json").read_text(encoding="utf-8"))}
    source = {"id": "boamp_caribbean", "name": "BOAMP Caribbean", "website": "https://www.boamp.fr",
              "source_type": "official_notice", "collector": "boamp_caribbean", "enabled": True}
    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    original = copy.deepcopy(fixtures["26-101686"])
    original.update(id=original["idweb"], date=original["dateparution"])
    rows = [original]
    for ident, parent, day, detail in [
        ("26-104001", original["idweb"], "2026-10-24", "Module de gestion des dossiers requis."),
        ("26-104002", "26-104001", "2026-10-25", "Connecteur de synchronisation Salesforce requis."),
        ("26-104003", original["idweb"], "2026-10-26", "Portail usager multilingue requis."),
    ]:
        amendment = copy.deepcopy(fixtures["26-103594"])
        amendment.update(idweb=ident, id=ident, annonce_lie=[parent], date=day, dateparution=day)
        amendment["donnees"]["FNSimple"]["rectificatif"]["infosRectif"] = detail
        rows.append(amendment)
    result = Collection(records=[RawRecord(row, source, now.isoformat(), "boamp_caribbean") for row in rows])
    monkeypatch.setattr(cli, "collect_with_backfill", lambda *args: result)
    monkeypatch.setattr(cli, "hydrate_sparse", lambda *args: None)
    _, incoming, _, health, count = cli._collect(
        source, {}, now, {"runtime": {}, "search_terms": {}, "capabilities": {}})
    assert health.status == "healthy" and count == 4
    current, _, _ = reconcile([], incoming)
    assert len(current) == 1
    assert "Module de gestion des dossiers requis." in current[0].description
    assert "Connecteur de synchronisation Salesforce requis." in current[0].description
    assert "Portail usager multilingue requis." in current[0].description


@pytest.mark.parametrize("with_later_correction", [False, True])
def test_boamp_same_day_original_replay_cannot_replace_saved_correction_scope(monkeypatch, with_later_correction):
    fixtures = {row["idweb"]: row for row in json.loads(
        (Path(__file__).parent / "fixtures/boamp_caribbean.json").read_text(encoding="utf-8"))}
    source = {"id": "boamp_caribbean", "name": "BOAMP Caribbean", "website": "https://www.boamp.fr",
              "source_type": "official_notice", "collector": "boamp_caribbean", "enabled": True}
    now = datetime(2026, 10, 28, 12, tzinfo=UTC)
    original = copy.deepcopy(fixtures["26-101686"])
    original.update(id=original["idweb"], date="2026-10-24", dateparution="2026-10-24")
    amendment = copy.deepcopy(fixtures["26-103594"])
    amendment.update(id="26-104001", idweb="26-104001", annonce_lie=[original["idweb"]],
                     date="2026-10-24", dateparution="2026-10-24")
    amendment["donnees"]["FNSimple"]["rectificatif"]["infosRectif"] = "Connecteur de synchronisation Salesforce requis."
    first = normalise_boamp_caribbean(RawRecord(original, source, now.isoformat(), "boamp_caribbean"))
    second = normalise_boamp_caribbean(RawRecord(amendment, source, now.isoformat(), "boamp_caribbean"), first)
    previous, _, _ = reconcile([], [first, second])
    latest = copy.deepcopy(amendment)
    latest.update(id="26-104002", idweb="26-104002", date="2026-10-25", dateparution="2026-10-25")
    latest["donnees"]["FNSimple"]["rectificatif"]["infosRectif"] = "Portail usager multilingue requis."
    rows = [original, latest] if with_later_correction else [original]
    result = Collection(records=[RawRecord(row, source, now.isoformat(), "boamp_caribbean") for row in rows])
    monkeypatch.setattr(cli, "collect_with_backfill", lambda *args: result)
    monkeypatch.setattr(cli, "hydrate_sparse", lambda *args: None)
    _, incoming, _, health, count = cli._collect(
        source, {}, now, {"runtime": {}, "search_terms": {}, "capabilities": {}}, previous)
    assert health.status == "healthy" and count == len(rows)
    current, _, _ = reconcile(previous, incoming)
    assert len(current) == 1
    assert "Connecteur de synchronisation Salesforce requis." in current[0].description
    if with_later_correction:
        assert "Portail usager multilingue requis." in current[0].description
