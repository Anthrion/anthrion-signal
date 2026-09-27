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

import httpx
import pytest
from pydantic import ValidationError

from anthrion_signal import cli, discovery_cache
from anthrion_signal.attachments import enrich_documents, extract_pages, hydrate_cached_documents
from anthrion_signal.collectors import RawRecord
from anthrion_signal.config import load_config, reviewed_inclusions
from anthrion_signal.discovery import discovery_signature, is_public_opportunity, prefilter
from anthrion_signal.discovery_retention import read_rejected, retain_rejected
from anthrion_signal.models import Dataset, Document, Signal
from anthrion_signal.normalise import normalise_ocds
from anthrion_signal.record_reviews import (INCLUSION_MARKER, RecordReview, apply_reviews, inclusion_hash,
                                            load_inclusions, load_reviews, source_hash)
from anthrion_signal.utils import atomic_json, jsonl_lines, read_json, read_retained_bytes

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ("Grounds maintenance works",
            "Grounds maintenance works for parks. Job records are held in the council's existing Salesforce system.",
            "45000000")
SPARSE = ("Resident engagement service",
          "The council seeks a supplier to run resident engagement sessions and record feedback from tenants.",
          "79000000")
TED_PDF = "https://ted.europa.eu/en/notice/123456-2026/pdf"
TED_POLICY = {"hosts": ["ted.europa.eu"], "paths": [r"/en/notice/\d+-\d{4}/pdf"], "reuse_basis": "Official TED reuse"}


@pytest.fixture
def command():
    spec = importlib.util.spec_from_file_location("review_records_inclusions", ROOT / "scripts/review_records.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def threshold(config):
    return config["capabilities"]["discovery"]["minimum_candidate_score"]


def notice(release, source, now, title, description, cpv, reference="002", lots=()):
    """A separate procurement with an open response window, unlike the fixture's fixed date."""
    value = copy.deepcopy(release)
    value.update(ocid=f"ocds-test-{reference}", id=f"{reference}-2026")
    value["tender"].update(id=f"PARKS-2026-{reference}", title=title, description=description,
                           tenderPeriod={"endDate": "2099-10-01T12:00:00Z"}, lots=list(lots))
    value["tender"]["items"][0]["classification"]["id"] = cpv
    value["tender"]["documents"][0]["url"] = f"https://www.find-tender.service.gov.uk/Notice/{reference}-2026"
    return normalise_ocds(RawRecord(value, source, now.isoformat()))


def inclusion(signal, *, priority="ai", hash_value=None, evidence=None):
    return {"id": signal.id, "source_hash": hash_value or inclusion_hash(signal), "decision": "include",
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


def restored_by(root, config, signal):
    cache = discovery_cache.ClassificationCache(root, config)
    cache.classify([signal])
    return INCLUSION_MARKER in signal.prefilter_matches, cache.stale_inclusions


def canonical_rows(root):
    return {s.id: s for s in (Signal.model_validate_json(line) for line in
            jsonl_lines(read_retained_bytes(root / "data/signals.jsonl").decode("utf-8")))}


def test_restorations_need_scope_evidence_and_priority_and_cannot_recommend_delivery(release, source, now):
    restored = notice(release, source, now, *PHYSICAL, lots=[{"id": "1", "title": "Parks", "description": "Parks work."}])
    row = inclusion(restored)
    assert RecordReview.model_validate(row).priority == "ai"
    lot = {"field": "lot:1:description", "quote": "Parks work.", "source_url": restored.primary_source_url}
    assert RecordReview.model_validate({**row, "evidence": [lot]}).evidence[0].field == "lot:1:description"
    guidance = {"source_hash": row["source_hash"], "approach": [{
        "text": "Integrate the parks job records with the council's Salesforce case management.",
        "evidence": row["evidence"]}], "problems": [], "complexity": 3, "problem_level": 1}
    for change in ({"evidence": []}, {"priority": None}, {"priority": "crm"}, {"guidance": guidance}):
        with pytest.raises(ValidationError):
            RecordReview.model_validate({**row, **change})
    # Only scope text bound by the inclusion hash can support a restoration.
    for field in ("eligibility_text", f"document:{'a' * 64}:1", "lot:1:status"):
        with pytest.raises(ValidationError, match="Restoration evidence must quote"):
            RecordReview.model_validate({**row, "evidence": [{**row["evidence"][0], "field": field}]})
    for other in ({"decision": "exclude"}, {"decision": "guide", "guidance": guidance}):
        assert RecordReview.model_validate({**row, **other, "priority": None}).priority is None
        with pytest.raises(ValidationError, match="Only a restoration"):
            RecordReview.model_validate({**row, **other})
    # A restoration is not an exclusion and publishes no recommendation.
    assert apply_reviews([restored], {restored.id: RecordReview.model_validate(row)}, now=now) == [restored]
    assert restored.reviewed_guidance is None


def test_existing_ledger_validates_without_restorations(config):
    reviews = load_reviews(ROOT)
    assert reviews and all(review.priority is None for review in reviews.values() if review.decision != "include")
    assert load_inclusions(ROOT) == {r.id: r for r in reviews.values() if r.decision == "include"}
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
    cache = discovery_cache.ClassificationCache(tmp_path, config)
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
    assert is_public_opportunity(restored, now) and not cache.stale_inclusions
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


def test_restoration_survives_changes_the_availability_rules_judge(tmp_path, release, source, config, now, threshold):
    restored = notice(release, source, now, *PHYSICAL)
    write_ledger(tmp_path, inclusion(restored))
    amended = restored.model_copy(deep=True, update={
        "deadline_at": "2099-11-15T12:00:00Z", "response_deadlines": ["2099-11-15T12:00:00Z"], "deadlines": [],
        "value_max": 900000.0, "status": "open", "buyer_name": "Example Council Parks Service",
        "documents": [*restored.documents, Document(title="Specification", url=TED_PDF, status="cached",
                                                    content_hash="b" * 64, revision="b" * 16)]})
    assert source_hash(amended) != source_hash(restored) and inclusion_hash(amended) == inclusion_hash(restored)
    assert restored_by(tmp_path, config, amended) == (True, set())
    assert amended.prefilter_score == threshold and is_public_opportunity(amended, now)


def test_restored_ted_notice_stays_restored_after_its_document_is_retrieved(tmp_path, release, source, config, now):
    restored = notice(release, source, now, *SPARSE).model_copy(update={
        "source": "ted", "documents": [Document(title="Notice PDF", url=TED_PDF, source_revision="v1")]})
    write_ledger(tmp_path, inclusion(restored))
    assert restored_by(tmp_path, config, restored)[0]
    before = source_hash(restored)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"Content-Type": "text/plain"}, content=b"Configure Salesforce case management."))) as client:
        assert enrich_documents(tmp_path, [restored], [{"id": "ted", "documents": TED_POLICY}], now, client=client,
                                extractor=lambda path, media: extract_pages(path.read_bytes(), media)) == 1
    assert restored.documents[0].content_hash and source_hash(restored) != before
    assert restored_by(tmp_path, config, restored) == (True, set())
    # A later raw release hydrated from the document cache matches the same restoration.
    replay = restored.model_copy(deep=True, update={"documents": [Document(title="Notice PDF", url=TED_PDF,
                                                                           source_revision="v1")]})
    hydrate_cached_documents(tmp_path, [replay])
    assert replay.documents[0].content_hash == restored.documents[0].content_hash
    assert restored_by(tmp_path, config, replay)[0]


@pytest.mark.parametrize("change", ["title", "description", "lot title", "lot description", "new lot"])
def test_changed_scope_text_makes_a_restoration_stale(tmp_path, release, source, config, now, change):
    lots = [{"id": "1", "title": "Parks", "description": "Maintain the parks."}]
    restored = notice(release, source, now, *PHYSICAL, lots=lots)
    write_ledger(tmp_path, inclusion(restored))
    changed = restored.model_copy(deep=True)
    if change in ("title", "description"):
        setattr(changed, change, getattr(changed, change) + " Revised.")
    elif change == "new lot":
        changed.lots.append(changed.lots[0].model_copy(update={"id": "2"}))
    else:
        setattr(changed.lots[0], change.split()[1], "Revised lot scope.")
    assert restored_by(tmp_path, config, changed) == (False, {restored.id})
    assert changed.prefilter_score == 0 and changed.exclusion_reasons
    # A later classification of the reviewed text supersedes the stale outcome.
    cache = discovery_cache.ClassificationCache(tmp_path, config)
    cache.classify([changed])
    cache.classify([restored.model_copy(deep=True)])
    assert cache.stale_inclusions == set()


@pytest.mark.parametrize("problem", ["quote", "url", "lot url"])
def test_unverifiable_evidence_suspends_collection_but_fails_validation(
        tmp_path, release, source, config, now, threshold, command, problem):
    # OCDS also appends lot text to the description, so keep it unrelated to the rules.
    lots = [{"id": "1", "title": "Parks", "description": "Maintain the parks and record job requests."}]
    restored = classified(notice(release, source, now, *PHYSICAL, lots=lots), config)
    assert restored.exclusion_reasons
    url = restored.primary_source_url
    evidence = {"quote": {"field": "description", "quote": "Implement a Salesforce customer portal.", "source_url": url},
                "url": {"field": "description", "quote": restored.description[:60],
                        "source_url": "https://www.find-tender.service.gov.uk/Notice/999-2026"},
                # An amendment gives each lot its new release URL; exclusions check this exactly too.
                "lot url": {"field": "lot:1:description", "quote": "record job requests",
                            "source_url": "https://www.find-tender.service.gov.uk/Notice/998-2026"}}[problem]
    retain_rejected(tmp_path, [restored], now, threshold)
    write_ledger(tmp_path, inclusion(restored, evidence=[evidence]))
    candidate = restored.model_copy(deep=True)
    assert restored_by(tmp_path, config, candidate) == (False, {restored.id})
    assert apply_reviews([candidate], load_reviews(tmp_path), now=now) == [candidate]
    report = command.validate_ledgers(tmp_path)
    assert not report["valid"] and report["record_reviews"]["decisions"]["include"]["invalid"] == 1
    assert report["record_reviews"]["records"][0]["error"]


def test_restoration_never_overrides_availability(tmp_path, release, source, config, now):
    restored = notice(release, source, now, *PHYSICAL)
    write_ledger(tmp_path, inclusion(restored))
    for update in [{"deadline_at": "2026-09-01T12:00:00Z", "response_deadlines": [], "deadlines": []},
                   {"signal_type": "AWARD", "status": "awarded"}, {"status": "cancelled"}, {"status": "withdrawn"},
                   {"status": "closed"}, {"status": "restricted"}, {"status": "postponed"}, {"status": "unverified"},
                   {"signal_type": "RENEWAL_SIGNAL", "related_signal_id": "sig_award", "status": "inferred"}]:
        unavailable = restored.model_copy(deep=True, update=update)
        assert restored_by(tmp_path, config, unavailable) == (True, set())
        assert not is_public_opportunity(unavailable, now), update


def test_collection_reads_only_restorations_but_export_validates_the_ledger(tmp_path, release, source, config, now):
    restored, other = notice(release, source, now, *PHYSICAL), notice(release, source, now, *SPARSE, reference="003")
    broken = {"id": other.id, "decision": "exclude", "source_hash": "not-a-hash", "reason": "short"}
    write_ledger(tmp_path, broken, {"id": "sig_guide", "decision": "guide"}, inclusion(restored))
    assert restored_by(tmp_path, config, restored)[0]
    with pytest.raises(ValidationError):
        load_reviews(tmp_path)
    write_ledger(tmp_path, {**broken, "id": restored.id}, inclusion(restored))
    with pytest.raises(ValueError, match="Duplicate"):
        discovery_cache.ClassificationCache(tmp_path, config)
    write_ledger(tmp_path, {**inclusion(restored), "priority": None})
    with pytest.raises(ValidationError):
        discovery_cache.ClassificationCache(tmp_path, config)


def test_export_packet_inclusion_hash_matches_the_classified_notice(tmp_path, release, source, config, now, threshold,
                                                                   command):
    restored = notice(release, source, now, *SPARSE)
    restored.documents = [Document(title="Specification", url=TED_PDF, source_revision="r1")]
    body = "The supplier will configure Salesforce case management for resident feedback and referrals."
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    cached = restored.documents[0].model_copy(update={
        "status": "cached", "content_hash": content_hash, "revision": content_hash[:16], "media_type": "text/plain",
        "retrieved_at": now.isoformat(), "reuse_basis": "Official TED reuse", "pages": [{"page": 1, "text": body}]})
    atomic_json(tmp_path / "data/documents/index.json", {TED_PDF: {"document": cached.model_dump()}})
    retain_rejected(tmp_path, [classified(restored, config)], now, threshold)
    packet = command.export_packets(tmp_path, [restored.id])["records"][0]
    # Hydration changes the full source hash, never the scope a restoration binds.
    assert packet["documents"][0]["content_hash"] == content_hash and packet["source_hash"] != source_hash(restored)
    assert packet["inclusion_hash"] == inclusion_hash(restored)
    write_ledger(tmp_path, inclusion(restored, hash_value=packet["inclusion_hash"]))
    replayed = read_rejected(tmp_path)
    assert restored_by(tmp_path, config, replayed[0]) == (True, set())
    assert replayed[0].prefilter_score == threshold and replayed[0].documents[0].content_hash is None


def test_only_restoration_identity_changes_the_discovery_signature(tmp_path, release, source, now):
    (tmp_path / "config").mkdir()
    for path in (ROOT / "config").glob("*.yaml"):
        shutil.copy(path, tmp_path / "config" / path.name)
    restored, other = notice(release, source, now, *PHYSICAL), notice(release, source, now, *SPARSE, reference="003")
    exclude = {**inclusion(other), "decision": "exclude", "priority": None, "source_hash": source_hash(other)}
    guide = {**inclusion(restored), "id": "sig_guided", "decision": "guide", "priority": None,
             "source_hash": source_hash(restored), "guidance": {
                 "source_hash": source_hash(restored), "problems": [], "complexity": 3, "problem_level": 1,
                 "approach": [{"text": "Integrate the parks job records with Salesforce.",
                               "evidence": inclusion(restored)["evidence"]}]}}
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
    assert load_config(tmp_path)["reviewed_inclusions"] == [[restored.id, inclusion_hash(restored), "ai"]]
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
    write_ledger(tmp_path, inclusion(restored, hash_value=packet["inclusion_hash"]))
    result = cli.export(tmp_path)
    assert {s.id for s in result.signals} == {public.id, restored.id}
    assert (result.run["reviewed_inclusions"], result.run["reviewed_inclusions_stale"]) == (1, 0)
    assert result.run["reviewed_exclusions"] == 0
    assert result.run["discovery_signature"] != previous.run["discovery_signature"]
    published = {s["id"]: s for s in read_json(tmp_path / "app/public/data/current.json", {})["signals"]}
    assert published[restored.id]["delivery_priority"] == "ai" and published[restored.id]["exclusion_reasons"] == []
    assert published[restored.id]["prefilter_matches"][0] == INCLUSION_MARKER
    check = runpy.run_path(str(ROOT / "scripts/check_public_output.py"))["check_public_output"]
    assert check(tmp_path / "app/public/data/current.json")[0] == 2
    assert {path: path.read_bytes() for path in retained} == retained
    # A stale restoration is reported; removing it restores the rules' decision on export.
    write_ledger(tmp_path, inclusion(restored, hash_value="1" * 64))
    result = cli.export(tmp_path)
    assert [s.id for s in result.signals] == [public.id] and result.run["reviewed_inclusions_stale"] == 1
    write_ledger(tmp_path)
    result = cli.export(tmp_path)
    assert [s.id for s in result.signals] == [public.id] and result.run["reviewed_inclusions_stale"] == 0


def test_rescore_moves_a_restored_notice_into_canonical_and_reports_it_stale(
        tmp_path, release, source, config, now, threshold, monkeypatch, command):
    public, restored = fixture_root(tmp_path, release, source, config, now, threshold)
    monkeypatch.setattr(cli, "load_config", configured(config))
    packet = command.export_packets(tmp_path, [restored.id])["records"][0]
    write_ledger(tmp_path, inclusion(restored, hash_value=packet["inclusion_hash"]))
    args = SimpleNamespace(command="rescore", days=None, max_pages=None, max_ai=0, no_ai=True, sources=None)
    result = cli.run(tmp_path, args)
    assert result.run["rejected_records_replayed"] == 1 and result.run["rejected_records_retained"] == 0
    assert (result.run["reviewed_inclusions"], result.run["reviewed_inclusions_stale"]) == (1, 0)
    assert {s.id for s in result.signals} == {public.id, restored.id}
    stored = canonical_rows(tmp_path)[restored.id]
    assert stored.description == restored.description and stored.exclusion_reasons == []
    exported = read_json(tmp_path / "app/public/data/current.json", {})
    assert restored.id in {s["id"] for s in exported["signals"]} and exported["run"]["reviewed_inclusions"] == 1
    write_ledger(tmp_path, inclusion(restored, hash_value="1" * 64))
    result = cli.run(tmp_path, SimpleNamespace(**vars(args), no_export=True))
    assert [s.id for s in result.signals] == [public.id]
    assert (result.run["reviewed_inclusions"], result.run["reviewed_inclusions_stale"]) == (0, 1)
    assert read_json(tmp_path / "data/run_metadata.json", {})["reviewed_inclusions_stale"] == 1
    stored = canonical_rows(tmp_path)[restored.id]  # Source evidence remains retained.
    assert stored.exclusion_reasons and INCLUSION_MARKER not in stored.prefilter_matches


def test_validation_judges_restorations_by_their_inclusion_hash(tmp_path, release, source, config, now, threshold,
                                                                command):
    active, stale, invalid = (notice(release, source, now, *PHYSICAL, reference=reference)
                              for reference in ("002", "003", "004"))
    retain_rejected(tmp_path, [classified(s, config) for s in (active, stale, invalid)], now, threshold)
    sources = command.load_selected(tmp_path, {active.id, stale.id, invalid.id})
    assert inclusion_hash(sources[active.id]) == inclusion_hash(active) != source_hash(sources[active.id])
    write_ledger(tmp_path, inclusion(active),
                 inclusion(stale, hash_value="0" * 64, evidence=[{"field": "description", "quote": "Earlier published wording.",
                                                                "source_url": stale.primary_source_url}]),
                 inclusion(invalid, evidence=[{"field": "description", "quote": "An invented Salesforce requirement.",
                                               "source_url": invalid.primary_source_url}]),
                 {**inclusion(active), "id": "sig_missing"},
                 {**inclusion(active), "id": "sig_excluded_elsewhere", "decision": "exclude", "priority": None})
    report = command.validate_ledgers(tmp_path)
    assert not report["valid"]
    assert report["record_reviews"]["decisions"] == {
        "include": {"active": 1, "stale": 1, "missing": 1, "invalid": 1},
        "exclude": {"active": 0, "stale": 0, "missing": 1, "invalid": 0}}
    rows = {row["id"]: row for row in report["record_reviews"]["records"]}
    assert rows[active.id] == {"id": active.id, "decision": "include", "status": "active"}
    assert "cannot be traced" in rows[invalid.id]["error"]
