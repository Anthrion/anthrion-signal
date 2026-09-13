import json
from datetime import UTC, datetime

import httpx
import pytest

from anthrion_signal.translation import (
    GeminiTranslator,
    ModelBudget,
    QuotaLedger,
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
    split_text,
    translation_lock,
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


def test_both_daily_budgets_exhausted_leave_work_queued(tmp_path, service):
    create, clock, requests = service
    translator = create()
    for model in MODELS:
        translator.ledger.model_state(model)["days"][pacific_day(clock())] = model.rpd
    translator.ledger.save()
    queue = TranslationQueue(tmp_path / "cache.json", clock)
    queue.add("A lead must not disappear when translation is unavailable.")
    result = queue.run(translator, MODELS)
    assert result["pending_fields"] == 1
    assert not requests


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
