"""Calendar presentation must never promote a TED revision past a cancellation."""
from datetime import timedelta

import pytest

from anthrion_signal.collectors import RawRecord
from anthrion_signal.dedupe import merge
from anthrion_signal.models import Signal
from anthrion_signal.normalise import normalise_ted
from anthrion_signal.record_reviews import source_hash
from anthrion_signal.translation import source_key
from anthrion_signal.utils import calendar_day, iso


def collected(config, now, published="2026-07-02+02:00"):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "ted")
    notice = {
        "publication-number": "453517-2026",
        "title-proc": {"fra": "Maintenance applicative de la plateforme"},
        "description-proc": {"fra": "Développement et maintenance de la plateforme CRM"},
        "buyer-name": {"fra": ["Example Ministry"]}, "buyer-country": ["FRA"],
        "form-type": "competition", "notice-type": "cn-standard", "publication-date": published,
        "deadline-receipt-tender-date-lot": ["2026-09-23+02:00"],
        "deadline-receipt-tender-time-lot": ["16:00:00+02:00"], "classification-cpv": ["72000000"],
    }
    return normalise_ted(RawRecord(notice, source, now.isoformat(), "ted"))


@pytest.mark.parametrize("value,day", [
    ("2026-07-02+02:00", "2026-07-02"),
    ("2026-01-15+01:00", "2026-01-15"),
    ("2023-10-30Z", "2023-10-30"),
    ("2026-07-02", "2026-07-02"),
])
def test_calendar_fact_and_revision_instant_are_separate(config, now, value, day):
    signal = collected(config, now, value)
    assert signal.published_at == day
    assert signal.provenance[0].published_at == day
    assert signal.updated_at == signal.last_material_update == iso(value)
    assert signal.deadline_at == "2026-09-23T14:00:00+00:00"


def test_newer_national_cancellation_still_wins(config, now):
    ted = collected(config, now)
    revision = ted.model_copy(deep=True, update={
        "source": "germany", "updated_at": "2026-07-01T23:30:00+00:00",
        "status": "cancelled", "last_seen_at": (now + timedelta(hours=1)).isoformat(),
    })
    merged, changed = merge(ted, revision)
    assert changed and merged.status == "cancelled"
    assert merged.updated_at == revision.updated_at


def test_explicit_clock_precision_and_mixed_source_times_are_preserved(config, now):
    clock = "2026-07-02T00:00:00+02:00"
    ted = collected(config, now, clock)
    assert ted.published_at == ted.updated_at == iso(clock)
    row = ted.model_dump()
    row.update(source="germany", published_at="2026-06-30T10:15:00+00:00",
               updated_at="2026-07-05T22:00:00+00:00", last_material_update="2026-07-05T22:00:00+00:00")
    restored = Signal.model_validate(row)
    assert restored.published_at == row["published_at"]
    assert restored.updated_at == restored.last_material_update == row["updated_at"]


def test_recollection_keeps_review_and_translation_keys_and_is_not_an_update(config, now):
    current = collected(config, now)
    old = current.model_copy(deep=True, update={"published_at": current.updated_at})
    old.provenance[0].published_at = current.updated_at
    assert old.content_hash == current.content_hash
    assert source_hash(old) == source_hash(current)
    assert source_key(old) == source_key(current)
    merged, changed = merge(old, current)
    assert not changed
    assert merged.changes == old.changes
    assert merged.last_material_update == old.last_material_update


@pytest.mark.parametrize("value", [None, "", "not a date", "2026-02-30+02:00"])
def test_invalid_calendar_dates_are_not_invented(value):
    assert calendar_day(value) is None
