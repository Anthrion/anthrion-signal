from datetime import UTC, datetime, timedelta

import pytest

from anthrion_signal.dedupe import merge, merge_provenance


def test_replayed_release_keeps_distinct_content_and_source_links(signal):
    old = signal.model_copy(deep=True)
    proof = old.provenance[0]
    alternate = proof.model_copy(update={"url": "https://example.gov/notices/mirror"})
    old.provenance.append(alternate)
    incoming = signal.model_copy(deep=True)
    incoming.provenance = [proof.model_copy(update={"raw_hash": "revised-content",
        "retrieved_at": "2026-09-10T12:00:00Z"})]
    incoming.raw_source_hash = "revised-content"

    merged, _ = merge(old, incoming)

    assert {(p.url, p.raw_hash) for p in merged.provenance} == {
        (proof.url, proof.raw_hash), (alternate.url, proof.raw_hash), (proof.url, "revised-content")}
    assert merged.title == old.title
    assert merged.description == old.description
    assert merged.raw_source_hash == "revised-content"
    assert merge(merged, incoming)[0].provenance == merged.provenance


@pytest.mark.parametrize("older_replayed_last", [True, False])
def test_duplicate_content_keeps_latest_retrieval_in_either_order(signal, older_replayed_last):
    proof = signal.provenance[0]
    earlier = proof.model_copy(update={"retrieved_at": "2026-09-19T12:00:00+02:00"})
    later = proof.model_copy(update={"retrieved_at": "2026-09-19T10:30:00Z"})
    previous, incoming = ([later], [earlier]) if older_replayed_last else ([earlier], [later])

    assert merge_provenance(previous, incoming) == [later]


def test_source_version_history_retains_existing_bound_and_newest_evidence(signal):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    versions = [signal.provenance[0].model_copy(update={"raw_hash": f"revision-{i}",
        "retrieved_at": (start + timedelta(days=i)).isoformat()}) for i in range(70)]

    result = merge_provenance(versions[35:], versions[:35])

    assert len(result) == 60
    assert [p.raw_hash for p in result] == [f"revision-{i}" for i in range(10, 70)]
