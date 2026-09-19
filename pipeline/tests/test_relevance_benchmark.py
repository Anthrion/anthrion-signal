import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("relevance_benchmark", Path(__file__).resolve().parents[2] / "scripts/relevance_benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def case(id, buyer, ocid=None, date="2026-08-01", used=False):
    return {"signal": {"id": id, "source": "ted", "buyer_name": buyer, "countries": ["DE"],
                       "ocid": ocid, "published_at": date}, "used_for_policy": used}


def test_related_and_same_buyer_cases_cannot_leak_into_holdout():
    rows = benchmark.assign_splits([case("a", "City", "one", used=True),
                                   case("b", "City", "two", "2026-09-19"),
                                   case("c", "Alias", "two"), case("d", "Independent", "three", "2026-09-19")], "2026-09-18")
    assert len({r["group"] for r in rows[:3]}) == 1
    assert [r["split"] for r in rows] == ["regression", "regression", "regression", "holdout"]


def test_splits_stable_when_input_is_reordered():
    rows = [case("a", "City", "one"), case("b", "City", "two"), case("c", "Other", "three")]
    first = {r["signal"]["id"]: (r["group"], r["split"]) for r in benchmark.assign_splits(rows)}
    assert first == {r["signal"]["id"]: (r["group"], r["split"]) for r in benchmark.assign_splits(rows[::-1])}


def test_authoritative_cross_source_notice_and_registry_aliases_share_a_split():
    first, second, third = case("a", "Alpha", used=True), case("b", "Beta"), case("c", "Gamma")
    first["signal"].update(external_ids=["ted:123456-2026"], buyer_identifiers=["DE-RG:888"])
    second["signal"].update(source="germany", external_ids=["ted:123456-2026"])
    third["signal"].update(source="another-source", buyer_identifiers=["DE-RG:888"])
    rows = benchmark.assign_splits([first, second, third])
    assert len({r["group"] for r in rows}) == 1
    assert all(r["split"] == "regression" for r in rows)


def test_precision_and_recall_have_different_denominators():
    rows = [{"expected": e, "predicted": p} for e, p in [
        ("retain", "retain"), ("retain", "exclude"), ("retain", "exclude"),
        ("exclude", "retain"), ("exclude", "exclude"), (None, "retain")]]
    result = benchmark.metrics(rows)
    assert result["precision"] == .5
    assert result["recall"] == pytest.approx(1 / 3)
    assert result["unlabelled_or_uncertain"] == 1
    assert result["recall_wilson_95"][0] < result["recall"] < result["recall_wilson_95"][1]
    assert benchmark.metrics([])["recall"] is None


def test_blind_sample_hides_current_classification_and_known_buyers(signal):
    known = case("known", signal.buyer_name, used=True)
    other = signal.model_copy(deep=True)
    other.id, other.buyer_name = "fresh", "Unseen organisation"
    other.prefilter_score, other.exclusion_reasons = 0, ["Don't show reviewer"]
    queue = benchmark.sample_queue([signal, other], set(), [known], size=5)
    assert [r["signal"]["id"] for r in queue] == ["fresh"]
    assert queue[0]["expected"] is None
    assert "exclusion_reasons" not in queue[0]["signal"]
    assert "prefilter_score" not in queue[0]["signal"]


def test_collection_matches_padded_references_and_explicit_amendments_not_titles(signal):
    signal.primary_source_url = "https://ted.europa.eu/en/notice/-/detail/00577910-2026"
    controls = [{"notice": "577910-2026"}, {"notice": "other", "aliases": ["577910-2026"]},
                {"notice": "missing", "title": signal.title}]
    result = benchmark.collection_controls([signal], controls)
    assert result["matched"] == 2
    assert result["records"][-1]["collected"] is False
