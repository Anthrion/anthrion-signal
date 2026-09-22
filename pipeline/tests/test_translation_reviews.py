from anthrion_signal.translation import VERSION, TranslationQueue, available_translations, field_key
from anthrion_signal.translation_reviews import reviewed_translations, prioritize_unreviewed_translations
from anthrion_signal.utils import atomic_json, digest

import pytest


def translated(tmp_path, signal):
    signal.title = "Système de gestion des dossiers"
    signal.description = "La commune recherche une solution de gestion des dossiers avec un portail pour les citoyens."
    entry = {"id": signal.id, "source_hash": digest([signal.title, signal.description]), "version": VERSION,
             "title": "Case management system", "description": "The municipality is seeking a case management solution with a portal for citizens.",
             "source_language": "fr", "reviewed_by": "Independent reviewer", "reviewed_at": "2026-09-22T10:00:00Z"}
    atomic_json(tmp_path / "config/reviewed_translations.json", {"version": 1, "records": [entry]})
    return entry


def test_reviewed_translation_preserves_source_and_cannot_follow_changed_text(tmp_path, signal):
    entry = translated(tmp_path, signal)
    original = signal.description
    assert available_translations(tmp_path, [signal])[signal.id]["title"] == entry["title"]
    assert signal.description == original
    signal.description += " Une nouvelle exigence."
    assert not available_translations(tmp_path, [signal])


def test_reviewed_translation_still_passes_literal_and_language_checks(tmp_path, signal):
    entry = translated(tmp_path, signal)
    entry["description"] += " For 999 users."
    atomic_json(tmp_path / "config/reviewed_translations.json", {"version": 1, "records": [entry]})
    with pytest.raises(ValueError, match="quality checks"):
        reviewed_translations(tmp_path, [signal])
    entry["description"] = signal.description
    atomic_json(tmp_path / "config/reviewed_translations.json", {"version": 1, "records": [entry]})
    with pytest.raises(ValueError, match="quality checks"):
        reviewed_translations(tmp_path, [signal])


def test_reviewed_translation_correction_and_withdrawal_leave_no_cache_copy(tmp_path, signal):
    entry = translated(tmp_path, signal)
    path = tmp_path / "data/translation/cache.json"
    queue = TranslationQueue(path)
    queue.prepare([signal])
    assert prioritize_unreviewed_translations(tmp_path, [signal], queue)
    assert field_key(signal.description) not in queue.active
    assert field_key(signal.title) not in queue.active
    assert field_key(signal.buyer_name, "organisation") in queue.active
    assert not queue.overlay([signal])["signals"]
    entry["description"] = "The municipality wants a case management solution including a citizen portal."
    atomic_json(tmp_path / "config/reviewed_translations.json", {"version": 1, "records": [entry]})
    assert available_translations(tmp_path, [signal])[signal.id]["description"] == entry["description"]
    atomic_json(tmp_path / "config/reviewed_translations.json", {"version": 1, "records": []})
    restored = TranslationQueue(path)
    restored.prepare([signal])
    assert not prioritize_unreviewed_translations(tmp_path, [signal], restored)
    assert field_key(signal.description) in restored.active
    assert restored.completed(field_key(signal.description)) is None
    assert not available_translations(tmp_path, [signal])


def test_reviewed_notice_does_not_suppress_shared_fields_needed_elsewhere(tmp_path, signal):
    translated(tmp_path, signal)
    other = signal.model_copy(update={"id": "unreviewed-notice"})
    queue = TranslationQueue(tmp_path / "cache.json")
    queue.prepare([signal, other])
    before = set(queue.active)
    prioritize_unreviewed_translations(tmp_path, [signal, other], queue)
    assert set(queue.active) == before
