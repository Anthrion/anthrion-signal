import gzip
import json
import runpy
from pathlib import Path

import pytest

from anthrion_signal.collectors import RawRecord
from anthrion_signal.models import Amount, Signal
from anthrion_signal.normalise import normalise_ted
from anthrion_signal.utils import digest

prepare_repair = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/repair_retained_amount.py"))["prepare_repair"]


def test_offline_amount_repair_preserves_other_rows_source_facts_and_raw_hash(config, now):
    source = next(s for s in config["sources"]["sources"] if s["id"] == "ted")
    raw = {"data": {"publication-number": "111111-2026", "title-proc": {"eng": "CRM services"},
                    "form-type": "competition", "estimated-value-proc": "8264463", "estimated-value-cur-proc": "EUR"},
           "source": source, "retrieved_at": now.isoformat(), "kind": "ted"}
    original = normalise_ted(RawRecord(**raw))
    sparse = original.model_copy(deep=True)
    sparse.primary_source_url = "https://ted.europa.eu/en/notice/-/detail/222222-2026"
    sparse.source_urls.append(sparse.primary_source_url)
    sparse.amount = Amount(kind="estimated_contract", source_label="estimated-value-proc", source_url=sparse.primary_source_url)
    sparse.provenance = []
    sparse.raw_source_hash = digest("replacement source")
    other = original.model_copy(update={"id": "other"}).model_dump_json().encode() + b"\n"
    canonical = other + sparse.model_dump_json().encode() + b"\n"
    retained = gzip.compress(json.dumps([raw]).encode())
    body, receipt = prepare_repair(canonical, retained, sparse.id, "111111-2026")
    assert body.startswith(other)
    result = Signal.model_validate_json(body.splitlines()[1])
    assert result.amount == original.amount
    assert result.raw_source_hash == sparse.raw_source_hash and result.fingerprint == sparse.fingerprint
    assert result.primary_source_url == sparse.primary_source_url
    assert result.provenance[0].raw_hash == digest(raw["data"])
    assert result.provenance[0].release_id == "111111-2026"
    assert set(receipt["changed_fields"]) <= {"amount", "provenance", "content_hash", "material_change_hash"}
    with pytest.raises(ValueError, match="surviving numeric"):
        wrong = sparse.model_copy(update={"value_max": 999}).model_dump_json().encode()
        prepare_repair(wrong, retained, sparse.id, "111111-2026")
    with pytest.raises(ValueError, match="exactly once"):
        prepare_repair(canonical, retained, sparse.id, "222222-2026")
