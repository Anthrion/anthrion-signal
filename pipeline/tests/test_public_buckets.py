import gzip
import json

import pytest

from anthrion_signal.public_feed import bucket_files
from anthrion_signal.utils import digest


def test_bundles_preserve_every_payload_and_stable_immutable_bytes(tmp_path):
    values = [(f"notice_{number}", {"signal": {"id": f"notice_{number}", "description": "Portail français — €100.00"},
                                   "translation": {"description": "Complete English source"}}) for number in range(500)]
    references = bucket_files(tmp_path, "records", values, target_bytes=600)
    assert len(set(references.values())) < len(values)
    expected = dict(values)
    original = {}
    for relative in set(references.values()):
        body = (tmp_path / "app/public/data" / relative).read_bytes()
        original[relative] = body
        page = json.loads(gzip.decompress(body))
        assert relative.endswith(digest(page)[:16] + ".json.gz")
        for ident, detail in page["records"].items():
            assert detail == expected.pop(ident)
            assert references[ident] == relative
    assert not expected
    assert bucket_files(tmp_path, "records", values, target_bytes=600) == references
    assert all((tmp_path / "app/public/data" / name).read_bytes() == body for name, body in original.items())
    amended = [(ident, {**value, "amendment": "Published correction"}) for ident, value in values]
    bucket_files(tmp_path, "records", amended, target_bytes=600)
    assert all((tmp_path / "app/public/data" / name).read_bytes() == body for name, body in original.items())


def test_small_download_target_splits_records_sharing_a_partition(tmp_path):
    values = []
    for number in range(1000):
        ident = f"notice_{number}"
        if digest(ident)[:2] == "ab":
            values.append((ident, {"signal": {"id": ident, "description": "x" * 300}}))
    assert len(values) > 1
    references = bucket_files(tmp_path, "records", values, target_bytes=500)
    assert len(set(references.values())) == len(values)
    for path in set(references.values()):
        assert len(gzip.decompress((tmp_path / "app/public/data" / path).read_bytes())) < 500


@pytest.mark.parametrize("values", [[("../unsafe", {})], [("same", {}), ("same", {})]])
def test_invalid_or_duplicate_identities_cannot_be_published(tmp_path, values):
    with pytest.raises(ValueError, match="identity"):
        bucket_files(tmp_path, "records", values)


def test_compressed_bootstrap_uses_the_index_limit_and_details_stay_bounded(tmp_path, monkeypatch):
    from anthrion_signal import public_compression
    from anthrion_signal.public_feed import atomic_public_json
    monkeypatch.setattr(public_compression, "DETAIL_LIMIT", 128)
    monkeypatch.setattr(public_compression, "INDEX_LIMIT", 1024)
    payload = {"source": "Original source text " * 20}
    root = tmp_path / "app/public/data"
    atomic_public_json(root / "manifest.json.gz", payload)
    assert json.loads(gzip.decompress((root / "manifest.json.gz").read_bytes())) == payload
    with pytest.raises(ValueError, match="decoded size"):
        atomic_public_json(root / "records/notice.json.gz", payload)
