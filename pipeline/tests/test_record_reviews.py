import json

import pytest

from anthrion_signal.canonical import canonical_signal_json
from anthrion_signal.models import Dataset, Lot
from anthrion_signal.public_feed import export_current
from anthrion_signal.record_reviews import (
    RecordReview, apply_reviews, load_reviews, source_hash, validate_guidance,
)
from anthrion_signal.utils import atomic_json


def review(signal, *, decision="guide"):
    evidence = {"field": "description", "quote": signal.description[:100],
                "source_url": signal.primary_source_url}
    value = {"id": signal.id, "source_hash": source_hash(signal), "decision": decision,
             "reviewed_at": "2026-09-09T12:00:00Z", "reviewed_by": "Independent reviewer",
             "reason": "Reviewed complete source scope and lots.", "evidence": [evidence]}
    if decision == "guide":
        value["guidance"] = {"source_hash": source_hash(signal), "approach": [
            {"text": "Configure the council's Salesforce workflows and integrate its existing systems.",
             "evidence": [evidence]}], "problems": [], "complexity": 5, "problem_level": 2}
    return RecordReview.model_validate(value)


def test_exclusion_is_reversible_and_bound_to_the_complete_scope(signal, now):
    decision = review(signal, decision="exclude")
    ledger = {signal.id: decision}
    assert not apply_reviews([signal], ledger, now=now)
    assert apply_reviews([signal], {}, now=now) == [signal]
    signal.last_seen_at = "2026-09-10T10:00:00Z"
    signal.matched_capabilities = ["data"]
    assert not apply_reviews([signal], ledger, now=now)
    # A newly separable digital lot must escape the old whole-record judgment.
    signal.lots.append(Lot(id="2", title="CRM implementation", description="A separately awarded software lot.",
                          source_url=signal.primary_source_url))
    assert apply_reviews([signal], ledger, now=now) == [signal]
    assert signal.reviewed_guidance is None


def test_guidance_needs_exact_evidence_and_published_lots(signal):
    value = review(signal).guidance.model_dump()
    validate_guidance(signal, value)
    value["approach"][0]["evidence"][0]["quote"] = "This sentence was never published."
    with pytest.raises(ValueError, match="cannot be traced"):
        validate_guidance(signal, value)
    value = review(signal).guidance.model_dump()
    value["approach"][0]["lot_id"] = "made-up-lot"
    with pytest.raises(ValueError, match="unpublished lot"):
        validate_guidance(signal, value)
    value = review(signal).guidance.model_dump()
    value["approach"][0]["evidence"][0]["source_url"] = "https://unrelated.example/notice"
    with pytest.raises(ValueError, match="provenance"):
        validate_guidance(signal, value)


def test_guidance_is_fresh_uk_only_and_cannot_survive_an_award(signal, now):
    ledger = {signal.id: review(signal)}
    assert apply_reviews([signal], ledger, now=now)[0].reviewed_guidance
    assert "reviewed_guidance" not in json.loads(canonical_signal_json(signal))
    signal.description += " A revised scope."
    assert apply_reviews([signal], ledger, now=now)[0].reviewed_guidance is None
    for update in [{"signal_type": "AWARD", "status": "complete"}, {"countries": ["DE"]}]:
        changed = signal.model_copy(update=update)
        assert apply_reviews([changed], {changed.id: review(changed)}, now=now)[0].reviewed_guidance is None


def test_invalid_ledgers_stop_publication_and_do_not_silently_hide_records(tmp_path, signal):
    row = review(signal).model_dump(mode="json")
    path = tmp_path / "config/record_reviews.json"
    atomic_json(path, {"version": 1, "records": [row, row]})
    with pytest.raises(ValueError, match="Duplicate"):
        load_reviews(tmp_path)
    row["guidance"]["problem_level"] = 11
    atomic_json(path, {"version": 1, "records": [row]})
    with pytest.raises(ValueError):
        load_reviews(tmp_path)


def test_excluded_records_do_not_leak_into_related_or_buyer_history(tmp_path, signal, config, now):
    from anthrion_signal.award_history import export_awards
    from anthrion_signal.discovery import prefilter

    hidden = signal.model_copy(deep=True, update={"id": "hidden-notice", "title": "Physical catering supply"})
    # Both deliberately pass the old lexical classifier; only one exact notice is hidden.
    for row in [signal, hidden]:
        prefilter([row], config["company_profile"], config["search_terms"], config["capabilities"])
    decision = review(hidden, decision="exclude")
    atomic_json(tmp_path / "config/record_reviews.json", {"version": 1, "records": [decision.model_dump(mode="json")]})
    visible = apply_reviews([signal, hidden], load_reviews(tmp_path), now=now)
    records = {}
    export_awards(tmp_path, [signal, hidden], config, now, records, visible)
    assert hidden.id not in records
    assert hidden.id not in {entry["signal_id"] for entry in signal.buyer_history}
    assert hidden.id not in {entry["signal_id"] for entry in signal.procedure_history}
    assert hidden.description  # The caller's original source still exists.


def test_guidance_lives_in_details_without_growing_search_indexes(tmp_path, signal, now):
    apply_reviews([signal], {signal.id: review(signal)}, now=now)
    data = Dataset(generated_at=now.isoformat(), data_updated_at=now.isoformat(), profile_version="1",
                   scoring_version="none", run={}, sources=[], capabilities=[], markets={},
                   evidence_catalog={}, signals=[signal])
    manifest = export_current(tmp_path, data)
    root = tmp_path / "app/public/data"
    detail = json.loads((root / manifest["records"][signal.id]["url"]).read_text(encoding="utf-8"))
    index = json.loads((root / manifest["markets"]["GB"]["url"]).read_text(encoding="utf-8"))
    assert detail["signal"]["reviewed_guidance"]["complexity"] == 5
    assert "reviewed_guidance" not in index["signals"][0]
