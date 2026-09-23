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


def test_guidance_is_fresh_and_cannot_survive_an_award_or_unsupported_country(signal, now):
    ledger = {signal.id: review(signal)}
    assert apply_reviews([signal], ledger, now=now)[0].reviewed_guidance
    assert "reviewed_guidance" not in json.loads(canonical_signal_json(signal))
    signal.description += " A revised scope."
    assert apply_reviews([signal], ledger, now=now)[0].reviewed_guidance is None
    for update in [{"signal_type": "AWARD", "status": "complete"}, {"countries": ["FR"]}]:
        changed = signal.model_copy(update=update)
        assert apply_reviews([changed], {changed.id: review(changed)}, now=now)[0].reviewed_guidance is None


@pytest.mark.parametrize("country", ["GB", "US", "CA", "DE", "AT", "CH"])
def test_current_guidance_is_supported_in_each_rollout_country(signal, now, country):
    signal.countries = [country]
    decision = review(signal)
    current = apply_reviews([signal], {signal.id: decision}, now=now)[0]
    assert current.reviewed_guidance["approach"][0]["text"] == decision.guidance.approach[0].text
    # Exporting this same object as historical context cannot erase its current guidance.
    history = apply_reviews([current], {signal.id: decision}, now=now, guidance=False)[0]
    assert history.reviewed_guidance is None
    assert current.reviewed_guidance


@pytest.mark.parametrize("update", [
    {"status": "cancelled"},
    {"deadline_at": "2026-09-01T12:00:00Z", "response_deadlines": ["2026-09-01T12:00:00Z"], "deadlines": []},
    {"signal_type": "AWARD", "status": "complete"},
    {"exclusion_reasons": ["Reviewed unrelated scope"]},
])
def test_rollout_does_not_recommend_unavailable_or_excluded_records(signal, now, update):
    changed = signal.model_copy(update={"countries": ["CA"], **update})
    assert apply_reviews([changed], {changed.id: review(changed)}, now=now)[0].reviewed_guidance is None


def localized_guidance(signal, language="de"):
    value = review(signal).guidance.model_dump()
    value["original_language"] = language
    value["localized"] = {language: {
        "approach": [{"text": "Salesforce-Prozesse konfigurieren und die vorhandenen Systeme über APIs anbinden."}],
        "problems": [],
    }}
    return value


@pytest.mark.parametrize("source_language", ["de", "deu", "ger", "de-DE", "DE_at", "und"])
def test_reviewed_original_language_supports_aliases_and_unknown_source_metadata(signal, source_language):
    signal.source_language = source_language
    value = localized_guidance(signal)
    validated = validate_guidance(signal, value)
    assert validated.original_language == "de"
    assert validated.localized["de"].approach[0].text == value["localized"]["de"]["approach"][0]["text"]
    assert validated.approach[0].evidence[0].quote == signal.description[:100]
    assert "evidence" not in validated.localized["de"].approach[0].model_dump()
    assert signal.source_language == source_language


@pytest.mark.parametrize(("source_language", "canonical"), [("fra", "fr"), ("fre-CA", "fr"), ("ita", "it"), ("roh", "rm")])
def test_original_language_binding_accepts_other_rollout_source_languages(signal, source_language, canonical):
    signal.source_language = source_language
    assert validate_guidance(signal, localized_guidance(signal, canonical)).original_language == canonical


@pytest.mark.parametrize("language", ["deu", "de-DE", "DE", "und", "zz", ""])
def test_reviewed_original_language_requires_canonical_iso_codes(signal, language):
    value = review(signal).guidance.model_dump()
    value["original_language"] = language
    with pytest.raises(ValueError, match="canonical ISO"):
        validate_guidance(signal, value)


@pytest.mark.parametrize("language", ["en", "deu", "de-DE", "DE", "und", "zz"])
def test_localized_keys_cannot_duplicate_english_or_use_unsupported_codes(signal, language):
    value = localized_guidance(signal)
    value["original_language"] = None
    value["localized"] = {language: value["localized"]["de"]}
    with pytest.raises(ValueError, match="canonical non-English"):
        validate_guidance(signal, value)


def test_localization_needs_a_bound_language_and_cannot_override_known_source_metadata(signal):
    signal.source_language = "und"
    value = localized_guidance(signal)
    value["original_language"] = None
    with pytest.raises(ValueError, match="no matching reviewed or source language"):
        validate_guidance(signal, value)
    signal.source_language = "deu"
    assert validate_guidance(signal, value).localized["de"]
    value["original_language"] = "fr"
    value["localized"] = {}
    with pytest.raises(ValueError, match="conflicts with the source language"):
        validate_guidance(signal, value)
    value = localized_guidance(signal)
    value["localized"]["fr"] = value["localized"]["de"]
    with pytest.raises(ValueError, match="reviewed original language"):
        validate_guidance(signal, value)


@pytest.mark.parametrize("field", ["approach", "problems"])
def test_localization_cannot_add_or_drop_english_points(signal, field):
    value = localized_guidance(signal)
    value[field].append(value["approach"][0].copy())
    with pytest.raises(ValueError, match="point counts"):
        validate_guidance(signal, value)


def test_localization_preserves_lot_order_and_cannot_add_evidence(signal):
    signal.lot_ids = ["1", "2"]
    value = localized_guidance(signal)
    value["approach"] = [{**value["approach"][0], "lot_id": lot} for lot in signal.lot_ids]
    localized = value["localized"]["de"]
    localized["approach"] = [{**localized["approach"][0], "lot_id": lot} for lot in reversed(signal.lot_ids)]
    with pytest.raises(ValueError, match="lot alignment"):
        validate_guidance(signal, value)
    localized["approach"].reverse()
    assert len(validate_guidance(signal, value).localized["de"].approach) == 2
    localized["approach"][0]["evidence"] = value["approach"][0]["evidence"]
    with pytest.raises(ValueError, match="Extra inputs"):
        validate_guidance(signal, value)


def test_localizations_keep_source_hash_and_original_evidence_enforcement(signal):
    value = localized_guidance(signal)
    value["approach"][0]["evidence"][0]["quote"] = "This localized proposal has no source support."
    with pytest.raises(ValueError, match="cannot be traced"):
        validate_guidance(signal, value)
    value = localized_guidance(signal)
    signal.description += " The source scope was revised."
    with pytest.raises(ValueError, match="earlier source scope"):
        validate_guidance(signal, value)


def test_legacy_and_missing_localizations_remain_compatible(signal):
    signal.source_language = "und"
    legacy = review(signal).guidance.model_dump(exclude={"localized", "original_language"})
    assert validate_guidance(signal, legacy).localized == {}
    legacy["original_language"] = "de"
    assert validate_guidance(signal, legacy).original_language == "de"


@pytest.mark.parametrize("reviewed_language", ["de", None])
def test_metadata_only_language_drift_suspends_guidance_but_keeps_notice(signal, now, reviewed_language):
    signal.source_language = "und" if reviewed_language else "deu"
    value = localized_guidance(signal)
    value["original_language"] = reviewed_language
    validate_guidance(signal, value)
    row = review(signal).model_dump()
    row["guidance"] = value
    ledger = {signal.id: RecordReview.model_validate(row)}
    assert apply_reviews([signal], ledger, now=now)[0].reviewed_guidance
    before = source_hash(signal)
    signal.source_language = "fra"
    assert source_hash(signal) == before
    with pytest.raises(ValueError, match="language"):
        validate_guidance(signal, value)
    assert apply_reviews([signal], ledger, now=now) == [signal]
    assert signal.reviewed_guidance is None


def test_equivalent_language_metadata_keeps_reviewed_guidance(signal, now):
    signal.source_language = "deu"
    value = localized_guidance(signal)
    row = review(signal).model_dump()
    row["guidance"] = value
    ledger = {signal.id: RecordReview.model_validate(row)}
    before = source_hash(signal)
    signal.source_language = "ger-DE"
    assert source_hash(signal) == before
    assert apply_reviews([signal], ledger, now=now)[0].reviewed_guidance == ledger[signal.id].guidance.model_dump()


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
    signal.countries = ["DE"]
    signal.source_language = "und"
    decision = review(signal).model_dump(mode="json")
    decision["guidance"] = localized_guidance(signal)
    apply_reviews([signal], {signal.id: RecordReview.model_validate(decision)}, now=now)
    data = Dataset(generated_at=now.isoformat(), data_updated_at=now.isoformat(), profile_version="1",
                   scoring_version="none", run={}, sources=[], capabilities=[], markets={},
                   evidence_catalog={}, signals=[signal])
    manifest = export_current(tmp_path, data)
    root = tmp_path / "app/public/data"
    detail = json.loads((root / manifest["records"][signal.id]["url"]).read_text(encoding="utf-8"))
    index = json.loads((root / manifest["markets"]["DE"]["url"]).read_text(encoding="utf-8"))
    assert detail["signal"]["reviewed_guidance"]["complexity"] == 5
    assert detail["signal"]["reviewed_guidance"]["original_language"] == "de"
    assert detail["signal"]["reviewed_guidance"]["localized"]["de"]["approach"][0]["text"].startswith("Salesforce-Prozesse")
    assert "evidence" not in detail["signal"]["reviewed_guidance"]["localized"]["de"]["approach"][0]
    assert "reviewed_guidance" not in index["signals"][0]
