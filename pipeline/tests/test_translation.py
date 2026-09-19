import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from anthrion_signal.translation import (
    DEFAULT_MODELS,
    GeminiTranslator,
    ModelBudget,
    QuotaLedger,
    RunFinished,
    TranslationError,
    TranslationQueue,
    VERSION,
    available_translations,
    field_key,
    http_error,
    next_reset,
    pacific_day,
    protect_literals,
    restore_literals,
    source_key,
    source_site_names,
    split_text,
    translation_lock,
    translation_text,
    untranslated_prose,
    validate_translation,
)
from anthrion_signal.utils import atomic_json, digest


class Clock:
    def __init__(self, now=None):
        self.now = now or datetime(2026, 9, 13, 12, tzinfo=UTC).timestamp()

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


MODELS = (ModelBudget("gemini-3.5-flash-lite", rpm=1000, tpm=1_000_000),
          ModelBudget("gemini-3.1-flash-lite", rpm=1000, tpm=1_000_000))


def test_translation_queue_interleaves_markets_without_losing_records_or_repeating_fields(tmp_path):
    records = [SimpleNamespace(id=str(i), title=f"Notice {i}", description=f"Description {i}",
        buyer_name="Shared buyer", countries=countries, last_material_update=f"2026-09-{20-i:02d}")
        for i, countries in enumerate([["DE"], ["DE"], ["DE"], ["FR"], ["BE", "NL"], ["AT"]])]
    queue = TranslationQueue(tmp_path / "cache.json")
    queue.prepare(records)
    content = [queue.state["fields"][key]["parts"][0]["source"] for key in queue.active]
    assert content[:8] == ["Notice 0", "Description 0", "Notice 3", "Description 3",
                          "Notice 4", "Description 4", "Notice 5", "Description 5"]
    assert content[8:12] == ["Notice 1", "Description 1", "Notice 2", "Description 2"]
    assert content[12:] == ["Shared buyer"]
    saved = list(queue.active)
    resumed = TranslationQueue(tmp_path / "cache.json")
    resumed.prepare(list(reversed(records)))
    assert resumed.active == saved


def test_verified_limits_use_full_project_capacity_without_resetting_previous_usage(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    day = pacific_day(clock())
    for model in DEFAULT_MODELS:
        assert (model.rpm, model.tpm, model.rpd) == (15, 250_000, 500)
        ledger.model_state(model)["days"][day] = 350
        assert ledger.daily_remaining(model) == 150
        assert not ledger.daily_exhausted(model)
    ledger.allocate("new-limits", DEFAULT_MODELS, 300, minimum_calls=2)
    ledger.activate("new-limits")
    for model in DEFAULT_MODELS:
        assert ledger.model_state(model)["days"][day] == 500
        assert ledger.daily_remaining(model) == 150
        assert not ledger.daily_exhausted(model)
        ledger.reserve(model, 100)
    ledger.finish_allowance()
    for model in DEFAULT_MODELS:
        assert ledger.model_state(model)["days"][day] == 351


def test_no_ci_reservation_when_no_model_can_complete_count_and_generation(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    for model in DEFAULT_MODELS:
        ledger.model_state(model)["days"][pacific_day(clock())] = model.rpd - 1
    with pytest.raises(RunFinished) as error:
        ledger.allocate("unusable", DEFAULT_MODELS, 150, minimum_calls=2)
    assert error.value.reason == "daily_budget"
    assert "unusable" not in ledger.state["allocations"]
    assert not ledger.path.exists()


def test_ci_reserves_only_usable_model_capacity_without_crossing_daily_limit(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    day = pacific_day(clock())
    ledger.model_state(DEFAULT_MODELS[0])["days"][day] = 499
    ledger.model_state(DEFAULT_MODELS[1])["days"][day] = 498
    ledger.allocate("last-batch", DEFAULT_MODELS, 150, minimum_calls=2)
    ledger.activate("last-batch")
    limits = ledger.state["allocations"]["last-batch"]["limits"]
    assert list(limits.values()) == [0, 2]
    ledger.reserve(DEFAULT_MODELS[1], 100)
    ledger.reserve(DEFAULT_MODELS[1], 100)
    with pytest.raises(TranslationError, match="local_quota"):
        ledger.reserve(DEFAULT_MODELS[1], 100)
    ledger.finish_allowance()
    assert ledger.model_state(DEFAULT_MODELS[0])["days"][day] == 499
    assert ledger.model_state(DEFAULT_MODELS[1])["days"][day] == 500


def test_minute_preflight_reserves_room_for_both_requests(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    model = DEFAULT_MODELS[0]
    for _ in range(14):
        ledger.reserve(model, 100)
    assert ledger.delay(model, 100, calls=1) == 0
    assert ledger.delay(model, 100, calls=2) == 61
    ledger.reserve(model, 100)
    with pytest.raises(TranslationError, match="local_quota"):
        ledger.reserve(model, 100)
    clock.sleep(61)
    assert ledger.delay(model, 100, calls=2) == 0


@pytest.mark.parametrize("source", [
    "Gesucht wird die Implementierung einer Kundenplattform.",
    "Implementazione della piattaforma per la gestione dei clienti.",
    "Servicios de desarrollo y mantenimiento de aplicaciones informaticas.",
    "Fourniture et maintenance du logiciel de gestion des clients.",
    "Hankinnan kohteena on asiakkuudenhallinnan tietojarjestelman toteuttaminen.",
    "Upphandlingen avser ett system for hantering av kundservicearenden.",
    "Kommunen onsker at anskaffe et system til digital sagsbehandling.",
    "\u03a8\u03b7\u03c6\u03b9\u03b1\u03ba\u03cc\u03c2 \u039c\u03b5\u03c4\u03b1\u03c3\u03c7\u03b7\u03bc\u03b1\u03c4\u03b9\u03c3\u03bc\u03cc\u03c2 \u0394\u03b9\u03b1\u03b4\u03b9\u03ba\u03b1\u03c3\u03b9\u03ce\u03bd \u039a\u03c4\u03ae\u03c3\u03b7\u03c2 \u0399\u03b8\u03b1\u03b3\u03ad\u03bd\u03b5\u03b9\u03b1\u03c2",
])
def test_foreign_prose_cannot_pass_by_claiming_to_be_english(source):
    assert untranslated_prose(source)
    assert not validate_translation(source, {"text": source, "language": "en"})
    assert not validate_translation(source, {"text": source, "language": "mul"})
    assert not validate_translation(source, {"text": source, "language": "und"})
    assert untranslated_prose("We invite suppliers to submit proposals.\n\n" + source)


@pytest.mark.parametrize("text", [
    "Analysis, optimisation, and redesign of organisational structures and business processes, particularly in the context of digital transformation.",
    "The contracting authority is AB Botkyrkabyggen.",
    "Bergstrasse District, Heppenheim - Huawei maintenance contract extension.",
    "Security-enhancing technology - Ankaret and Lovsangargarden residential care homes",
    "Services for the Deutsche Bundesbank and Bundesministerium der Finanzen.",
    "We require a CRM implementation for 25 users.",
    "The municipalities of Elves, Aurland, Austrheim, Austevoll, Etne, Fedje, Gulen, Masfjorden, Modalen, Osteroy, Samnanger, Sveio, Tysnes, Vaksdal and Vindafjord have established a joint ICT operations company.",
    "Helse Nord-Trondelag HF, St. Olavs Hospital HF and Helse More og Romsdal HF have, by their clinics for mental health care, drug treatment, rehabilitation and habilitation need to use digital, standardised and normed review and mapping tools.",
    "\u0394\u0391\u03a0\u0395\u0395\u03a0 02/2026",
])
def test_english_with_official_names_and_short_identifiers_is_preserved(text):
    assert validate_translation(text, {"text": text, "language": "en"})


def test_protected_foreign_buyer_does_not_invalidate_english_passage():
    name = "\u039a\u039f\u0399\u039d\u03a9\u039d\u0399\u0391 \u03a4\u0397\u03a3 \u03a0\u039b\u0397\u03a1\u039f\u03a6\u039f\u03a1\u0399\u0391\u03a3"
    source = f"{name}: CRM procurement."
    assert validate_translation(source, {"text": source, "language": "en"}, [name])


def test_encoded_italian_characters_are_not_protected_as_procurement_numbers():
    source = "L&#8217;appalto avr&#224; durata di 60 mesi, per &#8364; 280.000 ai sensi dell'art. 71 del 36/2023."
    masked, literals = protect_literals(source)
    assert "L’appalto avrà" in masked
    assert set(literals.values()) == {"60", "280.000", "71", "36/2023"}
    assert restore_literals(masked, literals) == translation_text(source)
    english = "The contract will last 60 months, for € 280.000 under art. 71 of 36/2023."
    assert validate_translation(source, {"text": english, "language": "it"})
    assert not validate_translation(source, {"text": english.replace("60", "50"), "language": "it"})
    assert not validate_translation(source, {"text": english.replace("36/2023", "36/2024"), "language": "it"})


def test_character_decoding_preserves_url_parameters_and_rejects_encoded_foreign_output():
    url = "https://example.org/?notice=71&notices=36&copy=1"
    assert translation_text(url) == url
    assert translation_text("&#x2019; &amp; &unknown;") == "’ & &unknown;"
    source = "L&#8217;affidamento dei servizi di sviluppo e manutenzione delle applicazioni."
    assert not validate_translation(source, {"text": source, "language": "en"})
    assert untranslated_prose(source)


def test_english_entity_decoding_survives_cache_resume_without_changing_source(tmp_path, service):
    create, clock, requests = service
    source = "The authority&#8217;s contract covers 60 months &amp; 280.000 users."
    signal = SimpleNamespace(id="encoded", title=source, description="", buyer_name=None,
                             last_material_update="2026-09-14")
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.prepare([signal])
    queue.run(create(), MODELS)
    assert queue.overlay([signal])["signals"][signal.id]["title"] == translation_text(source)
    resumed = TranslationQueue(queue.path, clock)
    resumed.prepare([signal])
    assert resumed.run(create(), MODELS)["api_calls"] == 0
    assert len(requests) == 2
    assert signal.title == source
    assert resumed.state["fields"][field_key(source)]["parts"][0]["source"] == source
    assert resumed.overlay([signal])["signals"][signal.id]["source_hash"] == source_key(signal)


def test_named_site_lists_do_not_hide_untranslated_requirements_or_changed_figures(tmp_path):
    sites = ("Lot LOT-0001: Lot 1 DE-5213-401 Neunkhausener Plateau. 370 ha "
             "Lot LOT-0002: Lot 2 DE-5507-401 Ahrgebirge. 3.803 ha "
             "Lot LOT-0003: Lot 3 DE-6715-401 Offenbacher Wald, Bellheimer Wald und Queichwiesen. 2.259 ha")
    source = "Erfassung der Vogelarten. " + sites.replace(": Lot ", ": Los ")
    english = "Survey of bird species. " + sites
    assert "Offenbacher Wald, Bellheimer Wald und Queichwiesen" in source_site_names(source)
    assert validate_translation(source, {"text": english, "language": "de"})
    assert not validate_translation(source, {"text": source, "language": "de"})
    assert not validate_translation(source, {"text": english.replace("370", "371"), "language": "de"})
    untranslated = "\nDie Erfassung muss durch qualifizierte Fachleute erfolgen."
    assert not validate_translation(source + untranslated, {"text": english + untranslated, "language": "de"})
    ordinary_lot = "Lot LOT-0001: Entwicklung und Wartung der Anwendung."
    assert source_site_names(ordinary_lot) == []
    assert untranslated_prose(ordinary_lot, source=ordinary_lot)
    signal = SimpleNamespace(id="sites", title="Bird survey", description=source, buyer_name=None,
                             last_material_update="2026-09-14")
    queue = TranslationQueue(tmp_path / "cache.json")
    queue.prepare([signal])
    queue.state["fields"][field_key(signal.title)]["parts"][0]["result"] = {
        "text": signal.title, "language": "en"}
    queue.state["fields"][field_key(source)]["parts"][0]["result"] = {"text": english, "language": "de"}
    atomic_json(tmp_path / "data/translation/translations.en.json", queue.overlay([signal]))
    assert available_translations(tmp_path, [vars(signal)])["sites"]["description"] == english


def test_site_names_remain_protected_when_splitting_before_their_area(tmp_path):
    source = "Lot LOT-0001: Los 1 DE-6715-401 Offenbacher Wald und Queichwiesen. 2.259 ha"
    queue = TranslationQueue(tmp_path / "cache.json")
    key = queue.add(source)
    names = queue.state["fields"][key]["protected_names"]
    first = source.split("2.259")[0]
    masked, literals = protect_literals(first, names)
    assert "Offenbacher" not in masked
    assert "Offenbacher Wald und Queichwiesen" in literals.values()


@pytest.mark.parametrize("broken", [
    "Lot LOT-0001: Lot 41OF-6914-401 Bienwald und Viehstrichwiesen. 3.127 ha",
    "Lot LOT-0001: Lot 41DE-6914-401 Bienwald und Viehstrichwiesen. 3.127 has",
    "Lot LOT-0001: The 41DE-6914-401 Bienwald und Viehstrichwiesen. 3.127 ha",
])
def test_site_identifiers_area_units_and_lot_labels_cannot_be_mistranslated(broken):
    source = "Lot LOT-0001: Los 41DE-6914-401 Bienwald und Viehstrichwiesen. 3.127 ha"
    assert not validate_translation(source, {"text": broken, "language": "de"})
    masked, literals = protect_literals(source)
    assert "DE-6914-401" in literals.values()
    assert "3.127 ha" in literals.values()
    assert "LOT-0001" in literals.values()
    assert restore_literals(masked, literals) == source


def test_fragments_receive_language_hint_from_complete_unmasked_source(tmp_path, service):
    create, clock, requests = service
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    source = "Die Erfassung muss durch qualifizierte Fachleute erfolgen.\nLos 19"
    key = queue.add(source)
    field = queue.state["fields"][key]
    first, last = source.split("\n")
    field["parts"] = [queue.part(first + "\n"), queue.part(last)]
    field["parts"][0]["result"] = {"text": "The survey must be performed by qualified professionals.", "language": "de"}
    queue.run(create(max_calls=2), MODELS)
    assert requests[0][1][0]["source_language_hint"] == "de"
    assert "Fachleute" not in requests[0][1][0]["text"]


def test_source_site_labels_with_attached_numbers_pass_without_ignoring_foreign_prose(tmp_path):
    source = ("44 ha Lot LOT-0029: Los29 DE-5809-401 Mittel- und Untermosel. 3.421 ha "
              "Lot LOT-0041: Los 41DE-6914-401 Bienwald und Viehstrichwiesen. 3.127 ha")
    english = source.replace("Los", "Lot")
    names = source_site_names(source)
    assert "Bienwald und Viehstrichwiesen" in names
    assert not untranslated_prose(english, source=source)
    assert validate_translation(source, {"text": english, "language": "de"})
    assert not validate_translation(source, {"text": source, "language": "de"})
    requirement = "\nDie Erfassung muss durch qualifizierte Fachleute erfolgen."
    assert not validate_translation(source + requirement, {"text": english + requirement, "language": "de"})
    queue = TranslationQueue(tmp_path / "cache.json")
    key = queue.add(source)
    field = queue.state["fields"][key]
    field["protected_names"].remove("Bienwald und Viehstrichwiesen")
    field["parts"][0]["failures"] = {model.name: 2 for model in MODELS}
    field["parts"][0]["blocked"] = True
    queue.add(source)
    assert field["parts"][0]["blocked"]
    assert not list(queue.pending(MODELS[0]))


def test_existing_encoded_english_cache_is_decoded_and_reused_without_provider_calls(tmp_path, service):
    create, clock, requests = service
    source = "Research &amp; development for the buyer&rsquo;s platform, covering 60 users."
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    key = queue.add(source)
    queue.state["fields"][key]["parts"][0]["result"] = {"text": source, "language": "en"}
    queue.save()
    resumed = TranslationQueue(queue.path, clock)
    resumed.add(source)
    assert resumed.completed(key) == "Research & development for the buyer’s platform, covering 60 users."
    assert resumed.run(create(), MODELS)["api_calls"] == 0
    assert not requests


def test_decoding_cached_output_does_not_accept_a_changed_contract_value(tmp_path):
    source = "Research &amp; development for 60 users."
    queue = TranslationQueue(tmp_path / "cache.json")
    key = queue.add(source)
    queue.state["fields"][key]["parts"][0]["result"] = {"text": source.replace("60", "50"), "language": "en"}
    queue.add(source)
    assert queue.completed(key) is None


def test_previously_copied_foreign_cache_is_requeued_but_good_cache_is_reused(tmp_path):
    queue = TranslationQueue(tmp_path / "cache.json")
    bad = "Gesucht wird die Implementierung einer Kundenplattform."
    good = "We require a customer platform."
    for source in (bad, good):
        key = queue.add(source)
        queue.state["fields"][key]["parts"][0]["result"] = {"text": source, "language": "en"}
    queue.save()
    resumed = TranslationQueue(queue.path)
    for source in (bad, good):
        resumed.add(source)
    assert resumed.completed(field_key(bad)) is None
    assert resumed.completed(field_key(good)) == good
    assert len(list(resumed.pending(MODELS[0]))) == 1


def test_validator_correction_recovers_good_rejected_result_without_retrying_or_unblocking(tmp_path):
    queue = TranslationQueue(tmp_path / "cache.json")
    source = "10052652 - Adobe Creative Cloud Lot LOT-0000: 10052652 - Adobe Creative Cloud. 10052652 - Adobe Creative Cloud"
    key = queue.add(source)
    part = queue.state["fields"][key]["parts"][0]
    part["rejected"] = {"text": source, "language": "de"}
    part["blocked"] = True
    queue.add(source)
    assert queue.completed(key) is None
    part["blocked"] = False
    queue.add(source)
    assert queue.completed(key) == source


def test_english_prose_can_include_a_list_of_place_names_without_retranslating_it():
    text = "The following broadcasters may participate.\nMDR - Saxony-Anhalt, Saxony, Thuringia;\nThe agreement runs for two years."
    assert validate_translation(text, {"text": text, "language": "en"})


def test_names_have_separate_reusable_cache_and_never_replace_official_name(tmp_path):
    queue = TranslationQueue(tmp_path / "cache.json")
    buyer = "Stadtverwaltung Berlin"
    signal = SimpleNamespace(id="one", title="A customer platform", description="", buyer_name=buyer,
                             last_material_update="2026-09-13")
    queue.prepare([signal, SimpleNamespace(**{**vars(signal), "id": "two"})])
    assert len(queue.active) == 2
    assert field_key(buyer) != field_key(buyer, "organisation")
    for key in queue.active:
        field = queue.state["fields"][key]
        name = field["purpose"] == "organisation"
        assert field["protected_names"] == []
        field["parts"][0]["result"] = {"text": "Berlin City Administration" if name else signal.title,
                                       "language": "de" if name else "en"}
    overlay = queue.overlay([signal])
    assert overlay["signals"]["one"]["buyer_name"] == "Berlin City Administration"
    assert signal.buyer_name == buyer
    atomic_json(tmp_path / "data/translation/translations.en.json", overlay)
    public = available_translations(tmp_path, [vars(signal)])["one"]
    assert public["buyer_original"] == buyer
    changed = {**vars(signal), "buyer_name": "Another buyer"}
    public = available_translations(tmp_path, [changed])["one"]
    assert "buyer_name" not in public
    assert public["title"] == signal.title


def test_notice_prose_is_queued_before_supplementary_names(tmp_path):
    queue = TranslationQueue(tmp_path / "cache.json")
    records = [SimpleNamespace(id=str(n), title=f"Notice {n}", description=f"Description {n}",
                               buyer_name=f"Buyer {n}", last_material_update=str(n)) for n in range(3)]
    queue.prepare(records)
    assert [queue.state["fields"][key]["purpose"] for key in queue.active] == ["passage"] * 6 + ["organisation"] * 3


def test_quality_retry_is_bounded_and_safety_blocks_never_reset(tmp_path):
    clock = Clock()
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    key = queue.add("We require a new customer platform.")
    part = queue.state["fields"][key]["parts"][0]
    exhausted = {model.name: 2 for model in MODELS}
    part["failures"] = exhausted.copy()
    queue.retry_quality(part)
    clock.now += 3599
    queue.retry_quality(part)
    assert part["failures"] == exhausted
    clock.now += 1
    queue.retry_quality(part)
    assert part["failures"] == {}
    part["failures"] = exhausted.copy()
    queue.retry_quality(part)
    clock.now += 3601
    queue.retry_quality(part)
    assert part["failures"] == exhausted
    clock.now = next_reset(clock()) + 1
    queue.retry_quality(part)
    assert part["failures"] == {}
    part.update(blocked=True, failures=exhausted.copy())
    clock.now = next_reset(clock()) + 1
    queue.retry_quality(part)
    assert part["blocked"] and part["failures"] == exhausted


def test_ci_crash_retains_prepaid_quota_and_new_attempt_cannot_reuse_it(tmp_path):
    clock = Clock()
    path = tmp_path / "quota.json"
    ledger = QuotaLedger(path, clock)
    ledger.allocate("run-1", MODELS, 60)
    checkpoint = path.read_bytes()
    ledger.activate("run-1")
    ledger.reserve(MODELS[0], 100)
    assert ledger.state["models"][MODELS[0].name]["days"][pacific_day(clock())] == 30
    # The only remotely committed state survives a lost runner, not its actual-use count.
    path.write_bytes(checkpoint)
    restarted = QuotaLedger(path, clock)
    with pytest.raises(ValueError):
        restarted.allocate("run-1", MODELS, 60)
    restarted.allocate("run-2", MODELS, 60)
    assert sum(m["days"][pacific_day(clock())] for m in restarted.state["models"].values()) == 120


def test_ci_completion_refunds_only_unused_allowance(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    ledger.reserve(MODELS[0], 100)
    ledger.allocate("run", MODELS, 10)
    ledger.activate("run")
    ledger.reserve(MODELS[0], 100)
    ledger.reserve(MODELS[1], 100)
    ledger.finish_allowance()
    ledger.finish_allowance()
    assert ledger.state["models"][MODELS[0].name]["days"][pacific_day(clock())] == 2
    assert ledger.state["models"][MODELS[1].name]["days"][pacific_day(clock())] == 1
    with pytest.raises(ValueError):
        ledger.activate("run")


def test_ci_allowance_respects_each_model_remaining_quota_and_day(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    ledger.model_state(MODELS[0])["days"][pacific_day(clock())] = MODELS[0].rpd
    ledger.allocate("run", MODELS, 4)
    ledger.activate("run")
    assert ledger.delay(MODELS[0], 0) > 0
    assert ledger.delay(MODELS[1], 0) == 0
    for _ in range(4):
        ledger.reserve(MODELS[1], 100)
    with pytest.raises(TranslationError):
        ledger.reserve(MODELS[1], 100)
    clock.now = next_reset(clock()) + 1
    assert ledger.delay(MODELS[1], 0) > 0
    ledger.finish_allowance()
    assert ledger.delay(MODELS[1], 0) == 0


def test_export_only_exact_complete_translations_and_tolerates_bad_cache(tmp_path):
    signal = {"id": "record", "title": "Titel", "description": "Beschreibung"}
    path = tmp_path / "data/translation/translations.en.json"
    entry = {"source_hash": digest([signal["title"], signal["description"]]),
             "version": VERSION, "title": "Title", "description": "Description"}
    overlay = {"version": 1, "target": "en", "signals": {"record": entry, "removed": entry}}
    atomic_json(path, overlay)
    assert available_translations(tmp_path, [signal]) == {"record": entry}
    assert available_translations(tmp_path, [{**signal, "description": "Updated description"}]) == {}
    for broken in ({**entry, "description": ""}, {**entry, "version": "old"}, {**entry, "title": []}):
        atomic_json(path, {**overlay, "signals": {"record": broken}})
        assert available_translations(tmp_path, [signal]) == {}
    path.write_text("invalid", encoding="utf-8")
    assert available_translations(tmp_path, [signal]) == {}


def test_prompt_clarification_retries_rejected_fields_once_but_never_safety_blocks(tmp_path):
    path = tmp_path / "cache.json"
    queue = TranslationQueue(path)
    key = queue.add("An already-English source must remain unchanged.")
    field = queue.state["fields"][key]
    field.pop("retry_profile")
    field["parts"][0]["failures"] = {model.name: 2 for model in MODELS}
    field["parts"][0]["blocked"] = True
    queue.save()
    resumed = TranslationQueue(path)
    resumed.add("An already-English source must remain unchanged.")
    part = resumed.state["fields"][key]["parts"][0]
    assert part["failures"] == {}
    assert part["blocked"]
    assert not list(resumed.pending(MODELS[0]))
    part["failures"] = {MODELS[0].name: 2}
    resumed.save()
    resumed = TranslationQueue(path)
    resumed.add("An already-English source must remain unchanged.")
    assert resumed.state["fields"][key]["parts"][0]["failures"][MODELS[0].name] == 2


def response(items, finish="STOP"):
    return httpx.Response(200, json={
        "candidates": [{"finishReason": finish, "content": {"parts": [{"text": json.dumps({
            "items": [{"id": item["id"], "text": item["text"], "language": "en"} for item in items],
        })}]}}],
        "usageMetadata": {"promptTokenCount": 110, "candidatesTokenCount": 120},
    })


@pytest.fixture
def service(tmp_path):
    clock, requests, clients = Clock(), [], []

    def create(handler=None, **kwargs):
        ledger = QuotaLedger(tmp_path / "quota.json", clock)

        def transport(request):
            body = json.loads(request.content)
            counting = request.url.path.endswith(":countTokens")
            actual = body["generateContentRequest"] if counting else body
            items = json.loads(actual["contents"][0]["parts"][0]["text"])["items"]
            # The reservation has reached durable storage before the transport executes.
            persisted = json.loads((tmp_path / "quota.json").read_text())
            assert sum(sum(m["days"].values()) for m in persisted["models"].values()) >= len(requests) + 1
            requests.append((request, items))
            override = handler(request, items, counting) if handler else None
            return override if override is not None else httpx.Response(200, json={"totalTokens": 100}) if counting else response(items)

        client = httpx.Client(base_url="https://generativelanguage.googleapis.com/v1beta/",
                              transport=httpx.MockTransport(transport), headers={"x-goog-api-key": "test-private-key"})
        translator = GeminiTranslator("test-private-key", ledger, clock=clock, sleep=clock.sleep,
                                      client=client, **kwargs)
        clients.append(translator)
        return translator

    yield create, clock, requests
    for client in clients:
        client.close()


def test_complete_and_resume_without_calls(tmp_path, service):
    create, clock, requests = service
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    key = queue.add("We require CRM implementation for 25 users.")
    summary = queue.run(create(), MODELS)
    assert summary["completed_fields"] == 1
    assert len(requests) == 2
    assert queue.completed(key) == "We require CRM implementation for 25 users."
    assert b"test-private-key" not in requests[0][0].content
    assert "key=" not in str(requests[0][0].url)
    resumed = TranslationQueue(tmp_path / "cache.json", clock)
    resumed.add("We require CRM implementation for 25 users.")
    assert resumed.run(create(), MODELS)["api_calls"] == 0


def test_run_budget_preserves_pending_work(tmp_path, service):
    create, clock, _ = service
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    key = queue.add("An implementation opportunity.")
    result = queue.run(create(max_calls=1), MODELS)
    assert result["stop_reason"] == "run_budget"
    assert queue.completed(key) is None
    queue.save()
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("An implementation opportunity.")
    assert queue.run(create(), MODELS)["completed_fields"] == 1


def test_rate_limited_primary_uses_backup_without_resetting_ledger(tmp_path, service):
    create, clock, requests = service

    def handler(request, items, counting):
        if "3.5" in request.url.path and not counting:
            return httpx.Response(429, json={"error": {"details": [
                {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                    {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"},
                ]},
            ]}})

    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("A Salesforce implementation opportunity.")
    translator = create(handler)
    assert queue.run(translator, MODELS)["completed_fields"] == 1
    assert ["3.5" in r.url.path for r, _ in requests] == [True, True, False, False]
    persisted = QuotaLedger(tmp_path / "quota.json", clock)
    assert persisted.model_state(MODELS[0])["blocked_until"] > clock() + 3600
    assert persisted.model_state(MODELS[0])["days"][pacific_day(clock())] == 2


def test_large_batch_hands_off_to_backup_when_split_consumes_primary_daily_allowance(tmp_path, service):
    create, clock, requests = service

    def handler(request, items, counting):
        if counting and len(items) > 1:
            return httpx.Response(200, json={"totalTokens": 7000})

    models = (ModelBudget(MODELS[0].name, rpm=1000, tpm=1_000_000, rpd=3), MODELS[1])
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("We need a customer platform.")
    queue.add("We need a reporting platform.")
    summary = queue.run(create(handler), models)
    assert summary["pending_fields"] == 0
    assert summary["stop_reason"] == "complete"
    assert ["3.5" in request.url.path for request, _ in requests] == [True, True, True, False, False]


def test_both_daily_budgets_exhausted_leave_work_queued(tmp_path, service):
    create, clock, requests = service
    translator = create()
    for model in MODELS:
        translator.ledger.model_state(model)["days"][pacific_day(clock())] = model.rpd
    translator.ledger.save()
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("A lead must not disappear when translation is unavailable.")
    result = queue.run(translator, MODELS)
    assert result["stop_reason"] == "daily_budget"
    assert result["pending_fields"] == 1
    assert not requests


def test_token_busy_primary_uses_ready_backup_without_sleeping(tmp_path, service):
    create, clock, requests = service
    models = (ModelBudget(MODELS[0].name, tpm=20_000), MODELS[1])
    translator = create()
    translator.ledger.reserve(models[0], 18_000)
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("We need Salesforce implementation.")
    started = clock()
    result = queue.run(translator, models)
    assert result["pending_fields"] == 0
    assert clock() == started
    assert len(requests) == 2
    assert all(models[1].name in request.url.path for request, _ in requests)


def test_provider_daily_limit_pauses_queue_until_reset(tmp_path, service):
    create, clock, requests = service
    translator = create()
    for model in MODELS:
        translator.ledger.block(model, TranslationError("daily_quota"))
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("A public procurement opportunity.")
    result = queue.run(translator, MODELS)
    assert result["stop_reason"] == "daily_budget"
    assert result["pending_fields"] == 1
    assert not requests
    clock.now = next_reset(clock()) + 2
    assert queue.run(translator, MODELS)["stop_reason"] == "run_budget"
    assert queue.run(create(), MODELS)["pending_fields"] == 0


def test_input_token_limit_splits_batches(tmp_path, service):
    create, clock, _ = service

    def handler(request, items, counting):
        if counting:
            return httpx.Response(200, json={"totalTokens": 7000 if len(items) > 1 else 100})

    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("First notice.")
    queue.add("Second notice.")
    result = queue.run(create(handler), MODELS)
    assert result["split_events"] == 1
    assert result["completed_fields"] == 2


def test_output_truncation_splits_single_passage_without_losing_source(tmp_path, service):
    create, clock, _ = service

    def handler(request, items, counting):
        if not counting:
            return response(items, "MAX_TOKENS" if len(items[0]["text"]) > 160 else "STOP")

    queue = TranslationQueue(tmp_path / "cache.json", clock)
    text = "Complete requirement with a period. " * 20
    key = queue.add(text)
    result = queue.run(create(handler), MODELS)
    assert result["split_events"] > 0
    assert queue.completed(key) == text
    assert "".join(p["source"] for p in queue.state["fields"][key]["parts"]) == text


def test_splitting_two_parts_of_same_field_uses_current_indices(tmp_path, service):
    create, clock, _ = service

    def handler(request, items, counting):
        if not counting and any(len(item["text"]) > 2000 for item in items):
            return response(items, "MAX_TOKENS")

    queue = TranslationQueue(tmp_path / "cache.json", clock)
    text = "Keep all of this numbered requirement 123. " * 250
    key = queue.add(text)
    result = queue.run(create(handler, max_calls=200), MODELS)
    assert result["pending_fields"] == 0
    assert queue.completed(key) == text


def test_safety_block_is_not_retried_on_another_model(tmp_path, service):
    create, clock, requests = service

    def handler(request, items, counting):
        if not counting:
            return response(items, "SAFETY")

    queue = TranslationQueue(tmp_path / "cache.json", clock)
    key = queue.add("Source content requiring review.")
    result = queue.run(create(handler), MODELS)
    assert result["stop_reason"] == "needs_review"
    assert queue.state["fields"][key]["parts"][0]["blocked"]
    assert all("3.5" in r.url.path for r, _ in requests)


def test_auth_failure_stops_all_models(tmp_path, service):
    create, clock, requests = service
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("Keep this record.")
    result = queue.run(create(lambda *args: httpx.Response(403)), MODELS)
    assert result["stop_reason"] == "credentials"
    assert len(requests) == 1


def test_duplicate_result_ids_never_publish(tmp_path, service):
    create, clock, _ = service

    def handler(request, items, counting):
        if not counting:
            return response([items[0], items[0]])

    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("First notice.")
    queue.add("Second notice.")
    result = queue.run(create(handler), MODELS)
    assert result["completed_fields"] == 0
    assert result["stop_reason"] == "needs_review"
    assert result["api_calls"] == 8


def test_invalid_translation_only_retries_failed_field(tmp_path, service):
    create, clock, requests = service

    def handler(request, items, counting):
        if not counting and "3.5" in request.url.path:
            changed = [{**item, "text": item["text"].replace("__KEEP_", "__BROKEN_")} for item in items]
            return response(changed)

    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("Good notice.")
    queue.add("Contract value is 123.")
    assert queue.run(create(handler), MODELS)["completed_fields"] == 2
    subsequent = [items for r, items in requests[2:] if r.url.path.endswith(":generateContent")]
    assert all(len(items) == 1 for items in subsequent)


def test_static_sidecar_does_not_modify_source_or_ids(tmp_path, service, signal):
    create, clock, _ = service
    before = signal.model_dump()
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.prepare([signal])
    queue.run(create(), MODELS)
    overlay = queue.overlay([signal])
    assert overlay["signals"][signal.id]["source_hash"] == source_key(signal)
    assert signal.model_dump() == before
    changed = signal.model_copy(update={"description": "A materially revised requirement."})
    assert changed.id not in queue.overlay([changed])["signals"]
    metadata = signal.model_copy(update={"deadline_at": "2027-01-01T00:00:00Z"})
    assert metadata.id in queue.overlay([metadata])["signals"]


def test_partial_record_is_not_published_as_fully_translated(tmp_path, signal):
    queue = TranslationQueue(tmp_path / "cache.json")
    queue.prepare([signal])
    key = field_key(signal.title)
    queue.state["fields"][key]["parts"][0]["result"] = {"text": signal.title, "language": "en"}
    assert not queue.overlay([signal])["signals"]


@pytest.mark.parametrize("source,text,valid", [
    ("CRM 25", "CRM 25", True),
    ("CRM 25", "CRM 20", False),
    ("CRM 25", "CRM", False),
    ("CRM 25", "customer management 25", False),
    ("Salesforce CRM", "Salesforce CRM", True),
    ("URL https://example.org/notice", "URL https://wrong.org/notice", False),
    ("Contract 1.161.102,50 EUR", "Contract 1,161,102.50 EUR", False),
    ("A notice", "<script>alert('x')</script>", False),
])
def test_mechanical_quality_guards(source, text, valid):
    assert validate_translation(source, {"text": text, "language": "de"}) == valid


def test_english_text_is_not_paraphrased():
    assert not validate_translation("A procurement notice.", {"text": "A lead.", "language": "en"})


def test_source_split_is_lossless_and_does_not_split_identifiers():
    original = "First sentence.\n\nSecond sentence. Another sentence. " * 300
    pieces = split_text(original)
    assert "".join(pieces) == original
    assert all(len(piece) <= 6000 for piece in pieces)
    assert split_text("x" * 7000) == ["x" * 7000]


def test_quota_reloads_and_waits_for_sliding_window(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    model = ModelBudget("gemini-3.5-flash-lite", rpm=2, tpm=3000, rpd=5)
    ledger.reserve(model, 1200)
    clock.sleep(10)
    ledger.reserve(model, 1200)
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    assert ledger.delay(model, 1200) == 51
    clock.sleep(51)
    ledger.reserve(model, 1200)
    assert ledger.model_state(model)["days"][pacific_day(clock())] == 3


@pytest.mark.parametrize("utc,day,reset", [
    ("2026-09-13T06:59:00+00:00", "2026-09-12", "2026-09-13T07:00:00+00:00"),
    ("2026-12-13T07:59:00+00:00", "2026-12-12", "2026-12-13T08:00:00+00:00"),
    ("2026-11-01T07:30:00+00:00", "2026-11-01", "2026-11-02T08:00:00+00:00"),
])
def test_pacific_reset_handles_dst(utc, day, reset):
    timestamp = datetime.fromisoformat(utc).timestamp()
    assert pacific_day(timestamp) == day
    assert next_reset(timestamp) == datetime.fromisoformat(reset).timestamp()


def test_retry_info_is_respected_without_logging_provider_body():
    error = http_error(httpx.Response(429, headers={"Retry-After": "80"}, json={"error": {
        "message": "Private provider diagnostic", "details": [
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "95s"},
        ],
    }}), 0)
    assert error.kind == "rate_limit"
    assert error.retry_after == 95
    assert str(error) == "rate_limit"


def test_rate_limit_never_misclassified_as_oversized_input():
    response = httpx.Response(429, json={"error": {"message": "Input tokens per minute limit exceeded"}})
    assert http_error(response, 0).kind == "rate_limit"


def test_corrupt_ledger_fails_closed(tmp_path):
    path = tmp_path / "quota.json"
    path.write_text('{"version":2}')
    with pytest.raises(ValueError, match="refusing to reset"):
        QuotaLedger(path)


def test_two_workers_cannot_use_same_project_ledger(tmp_path):
    with translation_lock(tmp_path):
        with pytest.raises(ValueError, match="locked"):
            with translation_lock(tmp_path):
                pass
    assert not (tmp_path / ".translation.lock").exists()


def test_token_reservation_cannot_exceed_local_budget(tmp_path):
    ledger = QuotaLedger(tmp_path / "quota.json")
    with pytest.raises(TranslationError, match="too_large"):
        ledger.delay(ModelBudget("gemini-3.5-flash-lite", tpm=100), 101)


def test_names_numbers_and_links_are_restored_exactly():
    source = "Example Authority needs Salesforce CRM for 1.161.102,50 EUR, see https://example.org/2026."
    masked, mapping = protect_literals(source, ["Example Authority"])
    assert "Example Authority" not in masked
    assert "1.161.102,50" not in masked
    assert "https://" not in masked
    assert restore_literals(masked, mapping) == source
    token = next(iter(mapping))
    with pytest.raises(TranslationError):
        restore_literals(masked.replace(token, ""), mapping)
    with pytest.raises(TranslationError):
        restore_literals(masked + token, mapping)


def test_repeated_provider_failures_back_off_and_success_resets(tmp_path):
    clock = Clock()
    ledger = QuotaLedger(tmp_path / "quota.json", clock)
    model = MODELS[0]
    ledger.block(model, TranslationError("transient"))
    assert ledger.delay(model, 0) == 61
    clock.sleep(61)
    ledger.block(model, TranslationError("transient"))
    assert ledger.delay(model, 0) == 122
    clock.sleep(122)
    ledger.usage(model, {"promptTokenCount": 100})
    ledger.block(model, TranslationError("transient"))
    assert ledger.delay(model, 0) == 61
