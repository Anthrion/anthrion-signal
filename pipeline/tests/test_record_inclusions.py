"""Reviewed restorations admit exact notices; availability, caches and benchmarks keep their own rules."""
import copy
import gzip
import hashlib
import importlib.util
import json
import runpy
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from anthrion_signal import cli, discovery_cache
from anthrion_signal.attachments import hydrate_cached_documents
from anthrion_signal.collectors import RawRecord
from anthrion_signal.config import load_config, reviewed_inclusions
from anthrion_signal.discovery import discovery_signature, is_public_opportunity, prefilter
from anthrion_signal.discovery_retention import read_rejected, retain_rejected
from anthrion_signal.models import Dataset, Document, Signal
from anthrion_signal.normalise import normalise_grants, normalise_ocds, set_hashes
from anthrion_signal.public_context import backfill_retained_facts
from anthrion_signal.record_reviews import INCLUSION_MARKER, RecordReview, apply_reviews, load_reviews, source_hash
from anthrion_signal.utils import atomic_json, jsonl_lines, read_json, read_retained_bytes

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ("Grounds maintenance works",
            "Grounds maintenance works for parks. Job records are held in the council's existing Salesforce system.",
            "45000000")
SPARSE = ("Resident engagement service",
          "The council seeks a supplier to run resident engagement sessions and record feedback from tenants.",
          "79000000")
DOCUMENT_URL = "https://www.find-tender.service.gov.uk/Notice/002-2026/specification"


@pytest.fixture
def command():
    spec = importlib.util.spec_from_file_location("review_records_inclusions", ROOT / "scripts/review_records.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def threshold(config):
    return config["capabilities"]["discovery"]["minimum_candidate_score"]


def notice(release, source, now, title, description, cpv, reference="002"):
    """A separate procurement with an open response window, unlike the fixture's fixed date."""
    value = copy.deepcopy(release)
    value.update(ocid=f"ocds-test-{reference}", id=f"{reference}-2026")
    value["tender"].update(id=f"PARKS-2026-{reference}", title=title, description=description,
                           tenderPeriod={"endDate": "2099-10-01T12:00:00Z"})
    value["tender"]["items"][0]["classification"]["id"] = cpv
    value["tender"]["documents"][0]["url"] = f"https://www.find-tender.service.gov.uk/Notice/{reference}-2026"
    return normalise_ocds(RawRecord(value, source, now.isoformat()))


def packet_hash(root, signal, state=None):
    """The hash review_records.py export reports for this retained version."""
    view = signal.model_copy(deep=True)
    backfill_retained_facts([view], state or {})
    hydrate_cached_documents(root, [view])
    return source_hash(view)


def inclusion(signal, *, priority="ai", hash_value=None, evidence=None):
    return {"id": signal.id, "source_hash": hash_value or source_hash(signal), "decision": "include",
            "priority": priority, "reviewed_at": "2026-09-26T10:00:00Z", "reviewed_by": "Independent reviewer",
            "reason": "The complete retained notice keeps its case records in the council's Salesforce system.",
            "evidence": evidence or [{"field": "description", "quote": signal.description[:90],
                                      "source_url": signal.primary_source_url}]}


def write_ledger(root, *rows):
    atomic_json(root / "config/record_reviews.json", {"version": 1, "records": list(rows)})


def classified(signal, config):
    result = signal.model_copy(deep=True)
    prefilter([result], config["company_profile"], config["search_terms"], config["capabilities"])
    return result


def canonical_rows(root):
    return {s.id: s for s in (Signal.model_validate_json(line) for line in
            jsonl_lines(read_retained_bytes(root / "data/signals.jsonl").decode("utf-8")))}


def test_restorations_need_evidence_and_priority_and_cannot_recommend_delivery(release, source, now):
    restored = notice(release, source, now, *PHYSICAL)
    row = inclusion(restored)
    assert RecordReview.model_validate(row).priority == "ai"
    guidance = {"source_hash": row["source_hash"], "approach": [{
        "text": "Integrate the parks job records with the council's Salesforce case management.",
        "evidence": row["evidence"]}], "problems": [], "complexity": 3, "problem_level": 1}
    for change in ({"evidence": []}, {"priority": None}, {"priority": "crm"}, {"guidance": guidance}):
        with pytest.raises(ValidationError):
            RecordReview.model_validate({**row, **change})
    for other in ({"decision": "exclude"}, {"decision": "guide", "guidance": guidance}):
        assert RecordReview.model_validate({**row, **other, "priority": None}).priority is None
        with pytest.raises(ValidationError, match="Only a restoration"):
            RecordReview.model_validate({**row, **other})
    # A restoration is not an exclusion and publishes no recommendation.
    review = RecordReview.model_validate(row)
    assert apply_reviews([restored], {restored.id: review}, now=now) == [restored]
    assert restored.reviewed_guidance is None


def test_existing_ledger_validates_without_a_priority(config):
    reviews = load_reviews(ROOT)
    assert reviews and all(review.priority is None for review in reviews.values() if review.decision != "include")
    assert config["reviewed_inclusions"] == reviewed_inclusions(ROOT)


@pytest.mark.parametrize("case", [PHYSICAL, SPARSE])
def test_matching_restoration_admits_the_notice_and_the_cache_keeps_the_classifier_output(
        tmp_path, release, source, config, now, threshold, monkeypatch, case):
    restored = notice(release, source, now, *case)
    # Identical wording shares one cache entry, but the review binds only its own notice.
    twin = notice(release, source, now, *case, reference="005")
    expected = classified(restored, config)
    assert expected.prefilter_score < threshold
    assert bool(expected.exclusion_reasons) == (case is PHYSICAL)
    write_ledger(tmp_path, inclusion(restored))
    cache = discovery_cache.ClassificationCache(tmp_path, config, {})
    assert cache.classify([restored, twin]) == 1
    for field in discovery_cache.FIELDS:
        assert getattr(twin, field) == getattr(expected, field)
    assert restored.prefilter_score == threshold
    assert restored.exclusion_reasons == [] and restored.scope_evidence == []
    assert restored.delivery_priority == "ai"
    assert restored.prefilter_matches == [INCLUSION_MARKER, *expected.prefilter_matches]
    # Capability tags are never invented; they remain the classifier's evidenced output.
    for field in ("matched_capabilities", "discovery_families", "capability_evidence", "categories"):
        assert getattr(restored, field) == getattr(expected, field)
    assert is_public_opportunity(restored, now)
    cache.save()
    stored = json.loads(gzip.decompress(cache.path.read_bytes()))["records"]
    assert list(stored.values()) == [json.loads(json.dumps({f: getattr(expected, f) for f in discovery_cache.FIELDS}))]
    # Removing the review restores the cached classifier decision without recomputation.
    (tmp_path / "config/record_reviews.json").unlink()

    def no_misses(signals, *args):
        assert not signals

    monkeypatch.setattr(discovery_cache, "prefilter", no_misses)
    assert discovery_cache.ClassificationCache(tmp_path, config).classify([restored]) == 0
    for field in discovery_cache.FIELDS:
        assert getattr(restored, field) == getattr(expected, field)


def test_changed_notice_makes_restoration_stale_without_checking_old_evidence(tmp_path, release, source, config, now):
    restored = notice(release, source, now, *PHYSICAL)
    old = inclusion(restored, hash_value="0" * 64, evidence=[{"field": "description", "source_url": restored.primary_source_url,
                                                            "quote": "Earlier wording that is no longer published."}])
    write_ledger(tmp_path, old)
    discovery_cache.ClassificationCache(tmp_path, config, {}).classify([restored])
    assert restored.prefilter_score == 0 and restored.exclusion_reasons
    assert INCLUSION_MARKER not in restored.prefilter_matches
    write_ledger(tmp_path, inclusion(restored))
    restored.description += " The contractor also supplies road salt."
    discovery_cache.ClassificationCache(tmp_path, config, {}).classify([restored])
    assert restored.prefilter_score == 0 and INCLUSION_MARKER not in restored.prefilter_matches


def test_invalid_evidence_for_a_matching_restoration_fails_loudly(tmp_path, release, source, config, now):
    restored = notice(release, source, now, *PHYSICAL)
    write_ledger(tmp_path, inclusion(restored, evidence=[{"field": "description", "source_url": restored.primary_source_url,
                                                        "quote": "Implement a Salesforce customer portal."}]))
    with pytest.raises(ValueError, match="cannot be traced"):
        discovery_cache.ClassificationCache(tmp_path, config, {}).classify([restored])


@pytest.mark.parametrize("update", [
    {"deadline_at": "2026-09-01T12:00:00Z", "response_deadlines": [], "deadlines": []},
    {"signal_type": "AWARD", "status": "awarded"},
    {"status": "cancelled"}, {"status": "withdrawn"}, {"status": "closed"}, {"status": "restricted"},
    {"status": "postponed"}, {"status": "unverified"}, {"title": "CANCELLED Grounds maintenance works"},
    {"signal_type": "RENEWAL_SIGNAL", "related_signal_id": "sig_award", "status": "inferred"},
])
def test_restoration_never_overrides_availability(tmp_path, release, source, config, now, threshold, update):
    restored = notice(release, source, now, *PHYSICAL).model_copy(update=update)
    write_ledger(tmp_path, inclusion(restored, hash_value=packet_hash(tmp_path, restored)))
    discovery_cache.ClassificationCache(tmp_path, config, {}).classify([restored])
    assert INCLUSION_MARKER in restored.prefilter_matches and restored.prefilter_score >= threshold
    assert not is_public_opportunity(restored, now)


def test_restoration_matches_the_exported_document_view_without_hydrating_the_record(
        tmp_path, release, source, config, now, threshold, command):
    restored = notice(release, source, now, *SPARSE)
    restored.documents = [Document(title="Specification", url=DOCUMENT_URL, source_revision="r1")]
    body = "The supplier will configure Salesforce case management for resident feedback and referrals."
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    cached = restored.documents[0].model_copy(update={
        "status": "cached", "content_hash": content_hash, "revision": content_hash[:16], "media_type": "text/plain",
        "retrieved_at": now.isoformat(), "reuse_basis": "Official notice reuse terms", "pages": [{"page": 1, "text": body}]})
    atomic_json(tmp_path / "data/documents/index.json", {DOCUMENT_URL: {"document": cached.model_dump()}})
    retain_rejected(tmp_path, [classified(restored, config)], now, threshold)
    packet = command.export_packets(tmp_path, [restored.id])["records"][0]
    assert packet["documents"][0]["content_hash"] == content_hash
    assert packet["source_hash"] != source_hash(restored)
    evidence = [{"field": f"document:{content_hash}:1", "quote": body, "source_url": DOCUMENT_URL}]
    # A hash of the raw, unhydrated record is not what reviewers export or collection compares.
    write_ledger(tmp_path, inclusion(restored, evidence=evidence))
    replayed = read_rejected(tmp_path)
    discovery_cache.ClassificationCache(tmp_path, config, {}).classify(replayed)
    assert INCLUSION_MARKER not in replayed[0].prefilter_matches
    write_ledger(tmp_path, inclusion(restored, hash_value=packet["source_hash"], evidence=evidence))
    discovery_cache.ClassificationCache(tmp_path, config, {}).classify(replayed)
    assert INCLUSION_MARKER in replayed[0].prefilter_matches and replayed[0].prefilter_score == threshold
    assert replayed[0].documents[0].content_hash is None and not replayed[0].documents[0].pages


def test_restoration_backfills_retained_facts_from_the_callers_state(
        tmp_path, release, source, config, now, threshold, command, monkeypatch):
    grants = next(s for s in config["sources"]["sources"] if s["id"] == "grants")
    raw = {"id": "123456", "title": "Community archive programme", "status": "posted",
           "agencyDetails": {"agencyCode": "DOE-SC", "agencyName": "Office of Science"},
           "facts": {"agencyName": "Public contact", "agencyContactName": "Public contact",
                     "createTimeStampStr": "2026-09-08-00-00-00", "postingDateStr": "2026-09-08-00-00-00",
                     "responseDateStr": "2099-10-01-00-00-00",
                     "synopsisDesc": "Digitise community archive records and publish a searchable catalogue."}}
    legacy = normalise_grants(RawRecord(raw, grants, now.isoformat(), "grants"))
    legacy.buyer_name = "Public contact"  # Repaired only by the retained API cache.
    set_hashes(legacy)
    state = {"grants": {"detail_cache": {"123456": {"record": raw}}}}
    atomic_json(tmp_path / "data/source_state.json", state)
    retain_rejected(tmp_path, [legacy], now, threshold)
    packet = command.export_packets(tmp_path, [legacy.id])["records"][0]
    assert packet["buyer_name"] == "Office of Science" and packet["source_hash"] != source_hash(legacy)
    write_ledger(tmp_path, inclusion(legacy, hash_value=packet["source_hash"]))
    reads, ledgers = [], []
    read = discovery_cache.read_json
    monkeypatch.setattr(discovery_cache, "read_json", lambda path, default: reads.append(path.name) or read(path, default))
    monkeypatch.setattr(discovery_cache, "load_reviews", lambda root: ledgers.append(root) or load_reviews(root))
    unrelated = notice(release, source, now, *SPARSE, reference="003")
    # In-memory state is authoritative when supplied; otherwise the retained file is read once, lazily.
    for given, included, loaded in ((state, True, []), (None, True, ["source_state.json"]), ({}, False, [])):
        reads.clear()
        cache = discovery_cache.ClassificationCache(tmp_path, config, given)
        cache.classify([unrelated])
        assert reads == []
        candidate = legacy.model_copy(deep=True)
        cache.classify([candidate])
        cache.classify([candidate])
        assert (INCLUSION_MARKER in candidate.prefilter_matches) is included
        assert candidate.buyer_name == "Public contact"  # Matching never repairs the caller's record.
        assert reads == loaded
    assert len(ledgers) == 3


def test_only_restoration_identity_changes_the_discovery_signature(tmp_path, release, source, now):
    (tmp_path / "config").mkdir()
    for path in (ROOT / "config").glob("*.yaml"):
        shutil.copy(path, tmp_path / "config" / path.name)
    restored, other = notice(release, source, now, *PHYSICAL), notice(release, source, now, *SPARSE, reference="003")
    exclude = {**inclusion(other), "decision": "exclude", "priority": None}
    guide = {**inclusion(restored), "id": "sig_guided", "decision": "guide", "priority": None, "guidance": {
        "source_hash": source_hash(restored), "approach": [{"text": "Integrate the parks job records with Salesforce.",
                                                             "evidence": inclusion(restored)["evidence"]}],
        "problems": [], "complexity": 3, "problem_level": 1}}
    write_ledger(tmp_path, exclude, guide)
    base = load_config(tmp_path)
    assert base["reviewed_inclusions"] == []
    signature = discovery_signature(base)

    def signed(*rows):
        write_ledger(tmp_path, *rows)
        return discovery_signature({**base, "reviewed_inclusions": reviewed_inclusions(tmp_path)})

    # Exclusions and guidance apply at export; editing them must not force a full replay.
    assert signed({**exclude, "reason": "A revised, independently checked exclusion reason."},
                  {**guide, "guidance": {**guide["guidance"], "complexity": 7}}) == signature
    included = inclusion(restored)
    added = signed(exclude, guide, included)
    assert added != signature
    assert load_config(tmp_path)["reviewed_inclusions"] == [[restored.id, included["source_hash"], "ai"]]
    assert discovery_signature(load_config(tmp_path)) == added
    assert signed(included, guide, exclude) == added
    # Evidence and wording are checked when applied; only identity, hash and priority replay.
    assert signed(exclude, guide, {**included, "reason": "A different, still accurate reviewed reason."}) == added
    changed = {signed(exclude, guide, {**included, "priority": "platform"}),
               signed(exclude, guide, {**included, "source_hash": "1" * 64})}
    assert len(changed) == 2 and not changed & {signature, added}
    assert signed(exclude, guide) == signature
    (tmp_path / "config/record_reviews.json").unlink()
    assert reviewed_inclusions(tmp_path) == []


def configured(config):
    # load_config's restoration summary, read from each fixture root's own ledger.
    return lambda root: {**config, "reviewed_inclusions": reviewed_inclusions(root)}


def fixture_root(tmp_path, release, source, config, now, threshold):
    public = classified(notice(release, source, now, "Salesforce CRM implementation",
        "The council requires Salesforce implementation and systems integration for its contact centre.",
        "72200000", reference="001"), config)
    restored = classified(notice(release, source, now, *PHYSICAL), config)
    assert public.prefilter_score >= threshold and restored.exclusion_reasons
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/signals.jsonl").write_text(public.model_dump_json() + "\n", encoding="utf-8")
    retain_rejected(tmp_path, [restored], now, threshold)
    return public, restored


def test_export_recovers_a_restored_notice_once_the_ledger_changes_the_signature(
        tmp_path, release, source, config, now, threshold, monkeypatch, command):
    public, restored = fixture_root(tmp_path, release, source, config, now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    # The last collection ran before the restoration was approved.
    previous = Dataset(generated_at=now.isoformat(), data_updated_at=now.isoformat(), profile_version="1",
                       scoring_version="none", run={"discovery_signature": discovery_signature(configured(config)(tmp_path))},
                       sources=[], capabilities=[], markets={}, evidence_catalog={}, signals=[public])
    atomic_json(tmp_path / "data/current.json", previous.model_dump())
    retained = {path: path.read_bytes() for path in [tmp_path / "data/signals.jsonl",
                                                     *(tmp_path / "data/discovery/rejected").rglob("*.gz")]}
    assert [s.id for s in cli.prepare_current(tmp_path)[0].signals] == [public.id]
    packet = command.export_packets(tmp_path, [restored.id])["records"][0]
    write_ledger(tmp_path, inclusion(restored, hash_value=packet["source_hash"]))
    result = cli.export(tmp_path)
    assert {s.id for s in result.signals} == {public.id, restored.id}
    assert result.run["reviewed_inclusions"] == 1 and result.run["reviewed_exclusions"] == 0
    assert result.run["discovery_signature"] != previous.run["discovery_signature"]
    published = {s["id"]: s for s in read_json(tmp_path / "app/public/data/current.json", {})["signals"]}
    assert published[restored.id]["delivery_priority"] == "ai" and published[restored.id]["exclusion_reasons"] == []
    assert published[restored.id]["prefilter_matches"][0] == INCLUSION_MARKER
    check = runpy.run_path(str(ROOT / "scripts/check_public_output.py"))["check_public_output"]
    assert check(tmp_path / "app/public/data/current.json")[0] == 2
    assert {path: path.read_bytes() for path in retained} == retained
    # Removing the review restores the rules' decision on the next export.
    write_ledger(tmp_path)
    assert [s.id for s in cli.export(tmp_path).signals] == [public.id]


def test_rescore_moves_a_restored_notice_into_canonical_and_removal_restores_the_rules(
        tmp_path, release, source, config, now, threshold, monkeypatch, command):
    public, restored = fixture_root(tmp_path, release, source, config, now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    packet = command.export_packets(tmp_path, [restored.id])["records"][0]
    write_ledger(tmp_path, inclusion(restored, hash_value=packet["source_hash"]))
    args = SimpleNamespace(command="rescore", days=None, max_pages=None, max_ai=0, no_ai=True, sources=None)
    result = cli.run(tmp_path, args)
    assert result.run["rejected_records_replayed"] == 1 and result.run["rejected_records_retained"] == 0
    assert result.run["reviewed_inclusions"] == 1
    assert {s.id for s in result.signals} == {public.id, restored.id}
    stored = canonical_rows(tmp_path)[restored.id]
    assert stored.description == restored.description and stored.exclusion_reasons == []
    # The canonical version, re-hashed at export, still matches the reviewed packet.
    exported = read_json(tmp_path / "app/public/data/current.json", {})
    assert restored.id in {s["id"] for s in exported["signals"]} and exported["run"]["reviewed_inclusions"] == 1
    write_ledger(tmp_path)
    result = cli.run(tmp_path, SimpleNamespace(**vars(args), no_export=True))
    assert [s.id for s in result.signals] == [public.id] and result.run["reviewed_inclusions"] == 0
    stored = canonical_rows(tmp_path)[restored.id]  # Source evidence remains retained.
    assert stored.exclusion_reasons and INCLUSION_MARKER not in stored.prefilter_matches


def test_validation_reports_restorations_by_status(tmp_path, release, source, config, now, threshold, command):
    active, stale, invalid = (notice(release, source, now, *PHYSICAL, reference=reference)
                              for reference in ("002", "003", "004"))
    retain_rejected(tmp_path, [classified(s, config) for s in (active, stale, invalid)], now, threshold)
    sources = command.load_selected(tmp_path, {active.id, stale.id, invalid.id})
    write_ledger(tmp_path, inclusion(active, hash_value=source_hash(sources[active.id])),
                 inclusion(stale, hash_value="0" * 64, evidence=[{"field": "description", "quote": "Earlier published wording.",
                                                                "source_url": stale.primary_source_url}]),
                 inclusion(invalid, hash_value=source_hash(sources[invalid.id]), evidence=[{
                     "field": "description", "quote": "An invented Salesforce requirement.",
                     "source_url": invalid.primary_source_url}]),
                 {**inclusion(active), "id": "sig_missing"},
                 {**inclusion(active, hash_value=source_hash(sources[active.id])), "id": "sig_excluded_elsewhere",
                  "decision": "exclude", "priority": None})
    report = command.validate_ledgers(tmp_path)
    assert not report["valid"]
    assert report["record_reviews"]["decisions"] == {
        "include": {"active": 1, "stale": 1, "missing": 1, "invalid": 1},
        "exclude": {"active": 0, "stale": 0, "missing": 1, "invalid": 0}}
    rows = {row["id"]: row for row in report["record_reviews"]["records"]}
    assert rows[active.id] == {"id": active.id, "decision": "include", "status": "active"}
    assert "cannot be traced" in rows[invalid.id]["error"]
