import hashlib
import json
from datetime import timedelta

import httpx
import pytest

from anthrion_signal.utils import read_json
from anthrion_signal.attachments import enrich_documents, extract_pages, hydrate_cached_documents
from anthrion_signal.award_history import export_awards
from anthrion_signal.models import Document
from anthrion_signal.record_reviews import RecordReview, apply_reviews, source_hash
from anthrion_signal.utils import atomic_json


DOCUMENT_URL = "https://ted.europa.eu/en/notice/123456-2026/pdf"
DOCUMENT_POLICY = {"hosts": ["ted.europa.eu"], "paths": [r"/en/notice/\d+-\d{4}/pdf"],
                   "reuse_basis": "Official TED notice reuse policy"}


def _review(signal, *, decision="guide", evidence=None):
    evidence = evidence or {"field": "description", "quote": signal.description[:100],
                            "source_url": signal.primary_source_url}
    value = {"id": signal.id, "source_hash": source_hash(signal), "decision": decision,
             "reviewed_at": "2026-09-09T12:00:00Z", "reviewed_by": "Independent reviewer",
             "reason": "Reviewed the complete retained source and document scope.", "evidence": [evidence]}
    if decision == "guide":
        value["guidance"] = {"source_hash": source_hash(signal), "approach": [
            {"text": "Configure Salesforce case workflows and integrate the existing systems.",
             "evidence": [evidence]}], "problems": [], "complexity": 5, "problem_level": 2}
    return RecordReview.model_validate(value)


def _cached_document(now, *, source_revision="source-v1", title="Previous source title", body="Source document text"):
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    return Document(title=title, url=DOCUMENT_URL, source_revision=source_revision,
                    status="cached", content_hash=content_hash, revision=content_hash[:16],
                    retrieved_at=now.isoformat(), reuse_basis=DOCUMENT_POLICY["reuse_basis"],
                    media_type="text/plain", pages=[{"page": 1, "text": body}])


def _write_cache(root, document, now):
    atomic_json(root / "data/documents/index.json", {document.url: {
        "document": document.model_dump(), "checked_at": now.isoformat(), "etag": "old-etag"}})


def test_new_notice_document_revision_reopens_excluded_record(signal, now):
    signal.documents[0].source_revision = "source-v1"
    review = _review(signal, decision="exclude")
    assert apply_reviews([signal], {signal.id: review}, now=now) == []
    signal.documents[0].source_revision = "source-v2"
    assert source_hash(signal) != review.source_hash
    assert apply_reviews([signal], {signal.id: review}, now=now) == [signal]


@pytest.mark.parametrize("changes", [{"kind": "invited_submission"}, {"date": "2026-10-05"},
                                    {"lot_id": "new-lot"}])
def test_typed_deadline_revisions_invalidate_guidance(signal, now, changes):
    review = _review(signal)
    assert apply_reviews([signal], {signal.id: review}, now=now)[0].reviewed_guidance
    signal.deadlines[0] = signal.deadlines[0].model_copy(update=changes)
    assert source_hash(signal) != review.source_hash
    assert apply_reviews([signal], {signal.id: review}, now=now)[0].reviewed_guidance is None


def test_hydration_keeps_fresh_notice_labels_and_rejects_incompatible_revision(tmp_path, signal, now):
    cached = _cached_document(now)
    _write_cache(tmp_path, cached, now)
    linked = Document(title="Revised scope and lots", url=DOCUMENT_URL,
                      kind="technicalSpecifications", source_revision="source-v2")
    signal.documents = [linked]
    hydrate_cached_documents(tmp_path, [signal])
    assert signal.documents[0] == linked
    assert signal.documents[0].content_hash is None
    assert signal.documents[0].pages == []

    # Even compatible extraction must not replace the current notice's title or kind.
    signal.documents = [linked.model_copy(update={"source_revision": "source-v1"})]
    hydrate_cached_documents(tmp_path, [signal])
    assert signal.documents[0].content_hash == cached.content_hash
    assert signal.documents[0].pages == cached.pages
    assert signal.documents[0].title == linked.title
    assert signal.documents[0].kind == linked.kind
    assert signal.documents[0].source_revision == "source-v1"
    assert linked.content_hash is None


def test_old_cache_cannot_replace_newer_retained_extraction(tmp_path, signal, now):
    old = _cached_document(now - timedelta(days=8), body="Old extracted specification")
    current = _cached_document(now, title="Current title", body="Newly extracted specification")
    _write_cache(tmp_path, old, now)
    signal.documents = [current]
    hydrate_cached_documents(tmp_path, [signal])
    assert signal.documents == [current]


def test_new_source_revision_bypasses_old_cache_cooldown_and_conditional_headers(tmp_path, signal, now):
    old = _cached_document(now)
    earlier = {"content_hash": "a" * 64, "revision": "earlier-revision",
               "retrieved_at": (now - timedelta(days=10)).isoformat(), "status": "superseded"}
    old.previous_revisions = [earlier]
    _write_cache(tmp_path, old, now)
    signal.source = "ted"
    signal.documents = [Document(title="New specification", url=DOCUMENT_URL, source_revision="source-v2")]
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"Content-Type": "text/plain"}, content=b"Revised source text")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert enrich_documents(tmp_path, [signal], [{"id": "ted", "documents": DOCUMENT_POLICY}], now,
            client=client, extractor=lambda path, media: extract_pages(path.read_bytes(), media)) == 1
    assert len(calls) == 1
    assert "if-none-match" not in calls[0].headers
    assert signal.documents[0].source_revision == "source-v2"
    assert signal.documents[0].title == "New specification"
    assert signal.documents[0].pages[0]["text"] == "Revised source text"
    assert signal.documents[0].previous_revisions == [earlier, {
        "content_hash": old.content_hash, "revision": old.revision,
        "retrieved_at": old.retrieved_at, "status": "superseded"}]
    saved = json.loads((tmp_path / "data/documents/index.json").read_text(encoding="utf-8"))
    assert saved[DOCUMENT_URL]["document"]["previous_revisions"] == signal.documents[0].previous_revisions


def test_source_revision_with_unchanged_bytes_retains_history_without_duplicate_current_hash(tmp_path, signal, now):
    old = _cached_document(now)
    earlier = {"content_hash": "a" * 64, "revision": "earlier-revision", "status": "superseded"}
    old.previous_revisions = [earlier]
    _write_cache(tmp_path, old, now)
    signal.source = "ted"
    signal.documents = [Document(title="Revised notice label", url=DOCUMENT_URL, source_revision="source-v2",
                                 previous_revisions=[earlier.copy()])]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            headers={"Content-Type": "text/plain"}, content=b"Source document text"))) as client:
        enrich_documents(tmp_path, [signal], [{"id": "ted", "documents": DOCUMENT_POLICY}], now,
                         client=client, extractor=lambda path, media: extract_pages(path.read_bytes(), media))
    assert signal.documents[0].content_hash == old.content_hash
    assert signal.documents[0].source_revision == "source-v2"
    assert signal.documents[0].previous_revisions == [earlier]


def test_failed_new_revision_fetch_preserves_history_without_old_extraction(tmp_path, signal, now):
    old = _cached_document(now)
    earlier = {"content_hash": "a" * 64, "revision": "earlier-revision", "status": "superseded"}
    old.previous_revisions = [earlier]
    _write_cache(tmp_path, old, now)
    signal.source = "ted"
    signal.documents = [Document(title="New inaccessible specification", url=DOCUMENT_URL, source_revision="source-v2")]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        enrich_documents(tmp_path, [signal], [{"id": "ted", "documents": DOCUMENT_POLICY}], now, client=client)
    current = signal.documents[0]
    assert current.status == "inaccessible"
    assert current.source_revision == "source-v2"
    assert current.content_hash is None and current.pages == []
    assert current.previous_revisions == [earlier, {"content_hash": old.content_hash, "revision": old.revision,
        "retrieved_at": old.retrieved_at, "status": "superseded"}]
    # The replacement index keeps the earlier hashes even without a new blob.
    signal.documents = [Document(title=current.title, url=DOCUMENT_URL, source_revision="source-v2")]
    hydrate_cached_documents(tmp_path, [signal])
    assert signal.documents[0].previous_revisions == current.previous_revisions
    assert signal.documents[0].content_hash is None and signal.documents[0].pages == []


def test_no_download_budget_preserves_new_source_revision_without_old_pages(tmp_path, signal, now):
    _write_cache(tmp_path, _cached_document(now), now)
    current = Document(title="New specification", url=DOCUMENT_URL, source_revision="source-v2")
    signal.source = "ted"
    signal.documents = [current]
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: pytest.fail("No request is allowed when the document budget is exhausted"))) as client:
        assert enrich_documents(tmp_path, [signal], [{"id": "ted", "documents": DOCUMENT_POLICY}], now,
                                limit=0, client=client) == 0
    assert signal.documents == [current]
    assert not signal.documents[0].pages


def test_historical_exclusion_uses_same_document_evidence_without_mutating_canonical(
        tmp_path, signal, config, now, monkeypatch):
    from anthrion_signal import award_history

    hidden = signal.model_copy(deep=True, update={"id": "hidden-document-notice"})
    hidden.documents = [Document(title="Procurement specification", url=DOCUMENT_URL,
                                 source_revision="source-v1")]
    cached = _cached_document(now, body="The complete contract is for physical catering services.")
    _write_cache(tmp_path, cached, now)
    reviewed = hidden.model_copy(deep=True)
    hydrate_cached_documents(tmp_path, [reviewed])
    review = _review(reviewed, decision="exclude", evidence={
        "field": f"document:{cached.content_hash}:1", "quote": cached.pages[0]["text"],
        "source_url": DOCUMENT_URL})
    atomic_json(tmp_path / "config/record_reviews.json", {"version": 1, "records": [review.model_dump(mode="json")]})
    assert apply_reviews([reviewed], {hidden.id: review}, now=now) == []
    hydrated_ids = []

    def track_hydration(root, signals):
        hydrated_ids.extend(row.id for row in signals)
        hydrate_cached_documents(root, signals)

    monkeypatch.setattr(award_history, "hydrate_cached_documents", track_hydration)
    manifest = {}
    export_awards(tmp_path, [signal, hidden], config, now, manifest, [signal])
    assert hydrated_ids == [hidden.id]
    assert hidden.id not in manifest
    assert hidden.id not in {row["signal_id"] for row in signal.buyer_history}
    assert hidden.id not in {row["signal_id"] for row in signal.procedure_history}
    assert hidden.documents[0].content_hash is None
    assert hidden.documents[0].source_revision == "source-v1"


def test_award_export_does_not_clear_shared_current_guidance(tmp_path, signal, config, now):
    review = _review(signal)
    atomic_json(tmp_path / "config/record_reviews.json", {"version": 1, "records": [review.model_dump(mode="json")]})
    apply_reviews([signal], {signal.id: review}, now=now)
    original_guidance = signal.reviewed_guidance
    manifest = {}
    export_awards(tmp_path, [signal], config, now, manifest, [signal])
    assert signal.reviewed_guidance == original_guidance
    assert original_guidance
    detail = read_json(tmp_path / "app/public/data" / manifest[signal.id]["url"], {})
    assert detail["signal"]["reviewed_guidance"] == original_guidance


def test_history_clears_retained_guidance_without_modifying_unlisted_caller(signal, now):
    apply_reviews([signal], {signal.id: _review(signal)}, now=now)
    original_guidance = signal.reviewed_guidance
    historical = apply_reviews([signal], {}, now=now, guidance=False)
    assert historical[0] is not signal
    assert historical[0].reviewed_guidance is None
    assert signal.reviewed_guidance == original_guidance
