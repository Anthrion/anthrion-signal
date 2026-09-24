"""Lossless public JSON transport, with explicit decoded-size limits."""
import gzip
import io

DETAIL_LIMIT = 16 * 1024 * 1024
INDEX_LIMIT = 256 * 1024 * 1024


def decoded_limit(name):
    # Indexes and the complete fallback already exceed the detail-bucket limit.
    # They were previously unbounded plain JSON; history keeps its existing bound.
    return INDEX_LIMIT if name in {"current.json", "current.json.gz", "manifest.json"} or name.startswith(("current/", "awards/")) else DETAIL_LIMIT


def decode_public_bytes(body, name):
    if name.endswith(".gz"):
        limit = decoded_limit(name)
        if len(body) > limit:
            raise ValueError("Public JSON exceeds its download size limit")
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
            body = stream.read(limit + 1)
        if len(body) > limit:
            raise ValueError("Public JSON exceeds its decoded size limit")
    return body
