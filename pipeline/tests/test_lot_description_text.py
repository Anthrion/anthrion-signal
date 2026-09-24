"""OCDS lot text in notice descriptions: null or empty lot parts are never printed."""

import copy

import pytest

from anthrion_signal.collectors import RawRecord
from anthrion_signal.normalise import normalise_ocds
from anthrion_signal.public_feed import search_text
from anthrion_signal.utils import clean


def with_lots(release, *lots):
    data = copy.deepcopy(release)
    data["tender"]["lots"] = copy.deepcopy(list(lots))
    return data


def normalised(release, source, now, *lots, prior=None):
    return normalise_ocds(RawRecord(with_lots(release, *lots), source, now.isoformat()), prior=prior)


def previous_lot_text(lots):
    # The wording used before this fix, kept to prove text-bearing lots are unchanged.
    return " ".join(
        f"Lot {lot.get('id')}: {lot.get('title', '')}. {lot.get('description', '')}" for lot in lots
    )


@pytest.mark.parametrize(
    ("lot", "expected"),
    [
        (
            {"id": "1", "title": None, "description": "Case management platform."},
            "Lot 1: Case management platform.",
        ),
        ({"id": "1", "title": "CRM platform", "description": None}, "Lot 1: CRM platform."),
        (
            {"id": "1", "title": "", "description": "Case management platform."},
            "Lot 1: Case management platform.",
        ),
        ({"id": "1", "title": "CRM platform", "description": "  "}, "Lot 1: CRM platform."),
    ],
    ids=["null-title", "null-description", "empty-title", "blank-description"],
)
def test_null_or_empty_lot_parts_are_omitted(release, source, now, lot, expected):
    signal = normalised(release, source, now, lot)
    assert signal.description == release["tender"]["description"] + " " + expected
    assert "None" not in signal.description
    assert ": ." not in signal.description


@pytest.mark.parametrize(
    "lot",
    [
        {"id": "LOT-0000", "title": None, "description": None},
        {"id": "LOT-0000", "title": "", "description": ""},
        {"id": "LOT-0000"},
        {"id": "LOT-0000", "title": "<p> </p>", "description": None},
    ],
    ids=["both-null", "both-empty", "both-absent", "markup-only"],
)
def test_lot_without_text_adds_nothing_and_its_identifier_stays_searchable(release, source, now, lot):
    signal = normalised(release, source, now, lot)
    assert signal.description == release["tender"]["description"]
    assert signal.lot_ids == ["LOT-0000"]
    assert [(item.id, item.title, item.description) for item in signal.lots] == [("LOT-0000", "", "")]
    assert "Lot LOT-0000" in search_text(signal, None).split("\n")


def test_real_lot_text_keeps_the_established_wording(release, source, now):
    lots = [
        {"id": "1", "title": "CRM platform", "description": "Salesforce configuration and support."},
        {"id": "2", "title": "Integration", "description": "MuleSoft integration with finance systems."},
        {"id": "3", "title": "Training"},
    ]
    signal = normalised(release, source, now, *lots)
    main = release["tender"]["description"]
    assert signal.description == (
        main + " Lot 1: CRM platform. Salesforce configuration and support."
        " Lot 2: Integration. MuleSoft integration with finance systems."
        " Lot 3: Training."
    )
    # Byte-identical to the previous wording: these descriptions keep their source-text
    # hashes, cached English translations and reviewed decisions.
    assert signal.description == clean(main + " " + previous_lot_text(lots))


def test_mixed_lots_keep_order_and_every_identifier(release, source, now):
    lots = [
        {"id": "1", "title": "CRM platform", "description": None},
        {"id": "2", "title": None, "description": None},
        {"id": "3", "title": None, "description": "Data migration."},
    ]
    signal = normalised(release, source, now, *lots)
    assert (
        signal.description
        == release["tender"]["description"] + " Lot 1: CRM platform. Lot 3: Data migration."
    )
    assert signal.lot_ids == ["1", "2", "3"]
    assert {"Lot 1", "Lot 2", "Lot 3"} <= set(search_text(signal, None).split("\n"))


def test_textless_lots_do_not_stand_in_for_a_missing_description(release, source, now):
    data = with_lots(release, {"id": "1", "title": None, "description": None})
    data["tender"]["description"] = None
    assert normalise_ocds(RawRecord(data, source, now.isoformat())).description == ""
    # The existing fallback to the procedure's earlier release now applies as intended.
    prior = normalise_ocds(RawRecord(release, source, now.isoformat()))
    assert (
        normalise_ocds(RawRecord(data, source, now.isoformat()), prior=prior).description == prior.description
    )
