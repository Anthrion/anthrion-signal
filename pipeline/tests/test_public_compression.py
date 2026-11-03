import gzip
import json

import pytest

from anthrion_signal import public_compression as codec
from anthrion_signal.public_feed import atomic_public_json


def test_public_compression_is_deterministic_and_lossless(tmp_path):
    value = {"schema_version": "1.0", "source": "Bürgerportal — Québec\u2028suite", "amount": 123456.125,
             "translation": {"title": "English title"}, "lots": [None, {"id": "LOT-0001"}]}
    path = tmp_path / "records/notice.json.gz"
    atomic_public_json(path, value)
    first = path.read_bytes()
    assert json.loads(codec.decode_public_bytes(first, "records/notice.json.gz")) == value
    assert gzip.decompress(first) == json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    atomic_public_json(path, value)
    assert path.read_bytes() == first


def test_compression_bounds_distinguish_indexes_from_details_and_reject_corruption(monkeypatch):
    monkeypatch.setattr(codec, "DETAIL_LIMIT", 128)
    monkeypatch.setattr(codec, "INDEX_LIMIT", 1024)
    body = b"x" * 129
    packed = gzip.compress(body)
    assert codec.decode_public_bytes(packed, "awards/GB-example.json.gz") == body
    assert codec.decode_public_bytes(packed, "current.json.gz") == body
    with pytest.raises(ValueError, match="decoded size limit"):
        codec.decode_public_bytes(packed, "history/abc-example.json.gz")
    with pytest.raises((OSError, EOFError)):
        codec.decode_public_bytes(gzip.compress(b"x" * 64)[:-4], "records/example.json.gz")
