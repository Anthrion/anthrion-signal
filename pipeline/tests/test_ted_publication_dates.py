"""TED publication days stay calendar days for every reader and every retained store."""
import json
from datetime import timedelta

import pytest
from pydantic import ValidationError

from anthrion_signal.collectors import RawRecord
from anthrion_signal.dedupe import earliest_publication, merge, reconcile
from anthrion_signal.models import Signal
from anthrion_signal.normalise import material_payload, normalise_ted
from anthrion_signal.record_reviews import source_hash
from anthrion_signal.translation import source_key
from anthrion_signal.utils import calendar_day, digest, iso

DAY_FIELDS = ("published_at", "updated_at", "last_material_update")


def ted_source(config):
    return next(s for s in config["sources"]["sources"] if s["id"] == "ted")


def notice(**changes):
    # The shape of TED notice 453517-2026 (France), which TED dates 2 July 2026.
    return {"publication-number": "453517-2026", "notice-identifier": "6d571f43-c045-4339-aebb-3ab08880a94c",
            "title-proc": {"fra": "Développements informatiques et tierce maintenance applicative"},
            "description-proc": {"fra": "Maintenance applicative de la plateforme et prestations associées"},
            "buyer-name": {"fra": ["Ministère de l'enseignement supérieur"]}, "buyer-country": ["FRA"],
            "form-type": "competition", "notice-type": "cn-standard", "publication-date": "2026-07-02+02:00",
            "deadline-receipt-tender-date-lot": ["2026-09-23+02:00"],
            "deadline-receipt-tender-time-lot": ["16:00:00+02:00"], "classification-cpv": ["72000000"], **changes}


def collected(config, at, **changes):
    return normalise_ted(RawRecord(notice(**changes), ted_source(config), at.isoformat(), "ted"))


def retained(signal, **fields):
    """A stored JSON row, as earlier releases wrote it, read back through the model."""
    row = json.loads(signal.model_dump_json())
    for name, value in fields.items():
        row[name] = value
    return row


def legacy_row(signal, instant):
    row = retained(signal, **dict.fromkeys(DAY_FIELDS, instant))
    for item in row["provenance"]:
        item["published_at"] = instant
    return row


@pytest.mark.parametrize("published,day", [
    ("2026-07-02+02:00", "2026-07-02"),  # Brussels summer time: notice 453517-2026
    ("2026-01-15+01:00", "2026-01-15"),  # Brussels winter time
    ("2023-10-30Z", "2023-10-30"),       # older notices use a UTC designator
])
def test_ted_publication_day_is_stored_as_its_calendar_date(config, now, published, day):
    signal = collected(config, now, **{"publication-date": published})
    assert (signal.published_at, signal.updated_at, signal.last_material_update) == (day, day, day)
    assert [p.published_at for p in signal.provenance] == [day]
    # Deadlines already keep their published clock time and offset.
    assert signal.deadline_at == "2026-09-23T14:00:00+00:00"
    assert signal.deadlines[0].source_text == "2026-09-23T16:00:00+02:00"


def test_ted_publication_timestamp_remains_an_instant(config, now):
    signal = collected(config, now, **{"publication-date": "2026-07-02T10:15:00+02:00"})
    assert signal.published_at == signal.updated_at == "2026-07-02T08:15:00+00:00"


def test_calendar_day_accepts_published_day_forms_only():
    assert calendar_day(" 2026-07-02-05:00 ") == "2026-07-02"
    assert calendar_day("20260909") == "2026-09-09"
    assert calendar_day("2026-07-02T00:00:00Z") == "2026-07-02T00:00:00+00:00"
    assert calendar_day("2026-02-30+01:00") is None
    assert calendar_day("") is None and calendar_day(None) is None


@pytest.mark.parametrize("published,day", [
    ("2026-07-02+02:00", "2026-07-02"),
    ("2026-01-15+01:00", "2026-01-15"),
    ("2023-10-30Z", "2023-10-30"),
])
def test_retained_utc_instants_are_restored_without_changing_any_hash(config, now, published, day):
    fresh = collected(config, now, **{"publication-date": published})
    before = iso(published)  # how earlier releases stored the day, e.g. 2026-07-01T22:00:00+00:00
    assert before != day
    restored = Signal.model_validate_json(json.dumps(legacy_row(fresh, before)))
    assert all(getattr(restored, name) == day for name in DAY_FIELDS)
    assert [p.published_at for p in restored.provenance] == [day]
    assert restored.model_dump() == fresh.model_dump()
    assert Signal.model_validate_json(restored.model_dump_json()) == restored
    # Material changes, reviewed scope and translations are keyed without these dates.
    legacy = restored.model_copy(update=dict.fromkeys(DAY_FIELDS, before))
    assert digest(material_payload(legacy)) == legacy.content_hash == restored.content_hash
    assert source_hash(legacy) == source_hash(restored)
    assert source_key(legacy) == source_key(restored)


def test_restored_record_merges_with_later_collections_without_an_update(config, now):
    discovered, _, _ = reconcile([], [collected(config, now)])
    stored = Signal.model_validate_json(json.dumps(legacy_row(discovered[0], "2026-07-01T22:00:00+00:00")))
    assert stored.last_material_update == "2026-07-02"
    later = collected(config, now + timedelta(hours=1))
    # An unrepaired replayed row would otherwise win an earliest-date comparison.
    replayed = Signal.model_validate_json(json.dumps(legacy_row(later, "2026-07-01T22:00:00+00:00")))
    assert min(["2026-07-02", "2026-07-01T22:00:00+00:00"]) == "2026-07-01T22:00:00+00:00"
    records, _, stats = reconcile([stored], [replayed, later])
    assert stats == {"new_signals": 0, "material_updates": 0, "duplicates_merged": 2}
    merged = records[0]
    assert [change.kind for change in merged.changes] == ["discovered"]
    assert all(getattr(merged, name) == "2026-07-02" for name in DAY_FIELDS)
    assert merged.content_hash == stored.content_hash
    assert merged.last_seen_at == later.last_seen_at
    _, changed = merge(stored, later)
    assert not changed


def test_restoration_is_limited_to_ted_days(config, now, signal):
    ted = collected(config, now)
    ted_entry = json.loads(ted.model_dump_json())["provenance"][0]

    # Another source's instant at Brussels midnight is not a TED day.
    other = Signal.model_validate_json(json.dumps(retained(
        signal, published_at="2026-07-01T22:00:00+00:00", updated_at="2026-07-01T22:00:00+00:00")))
    assert other.published_at == other.updated_at == "2026-07-01T22:00:00+00:00"

    # A collection time stays an instant even when it falls on Brussels midnight.
    row = legacy_row(ted, "2026-07-01T22:00:00+00:00")
    row["last_seen_at"] = row["last_material_update"] = "2026-09-20T22:00:00+00:00"
    seen = Signal.model_validate_json(json.dumps(row))
    assert seen.published_at == "2026-07-02" and seen.last_material_update == "2026-09-20T22:00:00+00:00"

    # Linked Spanish and German facts keep their own values; only TED provenance changes.
    spain_entry = {**ted_entry, "source": "spain", "source_name": "Spanish Public Procurement",
                   "published_at": "2026-09-06T00:00:00+00:00", "release_id": "20377057"}
    german_entry = {**ted_entry, "source": "germany", "source_name": "German Public Procurement",
                    "published_at": "2026-08-30T22:00:00+00:00", "release_id": "81059491-01"}
    for entry, value in ((spain_entry, "2026-09-06T00:00:00+00:00"), (german_entry, "2026-08-30T22:00:00+00:00"),
                         ({**german_entry, "published_at": "2026-06-29T10:00:00+00:00"}, "2026-06-29T10:00:00+00:00")):
        row = retained(ted, source=entry["source"], published_at=value, updated_at=value,
                       provenance=[entry, {**ted_entry, "published_at": "2026-09-06T22:00:00+00:00"}])
        linked = Signal.model_validate_json(json.dumps(row))
        assert linked.published_at == linked.updated_at == value
        assert [p.published_at for p in linked.provenance] == [value, "2026-09-07"]

    # TED-only lineage keeps an earlier notice's day even when its provenance was not retained.
    row = retained(ted, published_at="2026-03-10T23:00:00+00:00", updated_at="2026-03-31T22:00:00+00:00",
                   last_material_update="2026-03-10T23:00:00+00:00",
                   provenance=[{**ted_entry, "published_at": "2026-03-31T22:00:00+00:00"}])
    lineage = Signal.model_validate_json(json.dumps(row))
    assert (lineage.published_at, lineage.updated_at, lineage.last_material_update) == (
        "2026-03-11", "2026-04-01", "2026-03-11")

    # Direct construction with provenance objects follows the same rule.
    built = Signal(**{**ted.model_dump(exclude={"provenance"}), "published_at": "2026-07-01T22:00:00+00:00",
                      "provenance": [ted.provenance[0].model_copy(update={"published_at": "2026-07-01T22:00:00+00:00"})]})
    assert built.published_at == built.provenance[0].published_at == "2026-07-02"


def test_malformed_retained_dates_still_fail_schema_validation(config, now):
    ted = collected(config, now)
    entry = json.loads(ted.model_dump_json())["provenance"][0]
    row = retained(ted, published_at={"not": "a date"}, first_seen_at=["unhashable"],
                   provenance=[{**entry, "published_at": "2026-07-01T22:00:00+00:00"},
                               {**entry, "published_at": {"not": "a date"}}])
    with pytest.raises(ValidationError):
        Signal.model_validate(row)


def test_earliest_publication_compares_instants_and_calendar_days():
    assert earliest_publication(["2026-07-02T08:00:00+00:00", "2026-07-02"]) == "2026-07-02"
    assert earliest_publication(["2026-07-02", "2026-07-01T23:30:00+00:00"]) == "2026-07-01T23:30:00+00:00"
    # Text order would choose 23:30 UTC; the other value is 23:00 UTC.
    assert earliest_publication(["2026-07-01T23:30:00+00:00", "2026-07-02T01:00:00+02:00"]) == "2026-07-02T01:00:00+02:00"
    assert earliest_publication(["not a date", "2026-07-02"]) == "2026-07-02"
