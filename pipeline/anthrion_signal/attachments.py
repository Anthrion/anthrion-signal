"""Small, opt-in official document cache. Document text is never executable input.

Only reviewed source/path reuse rules authorize retrieval. Unknown attachments
remain linked. No login, OCR, model calls or cross-host redirects are supported.
"""
import hashlib
import io
import json
import re
import subprocess
import sys
from datetime import timedelta
from urllib.parse import urljoin, urlsplit

import httpx

from .models import Document
from .utils import atomic_bytes, atomic_json, parse_date, read_json

MAX_BYTES = 4_000_000
MAX_CACHE_BYTES = 40_000_000
MAX_PAGES = 80
MAX_TEXT = 160_000


def permitted(url, policy):
    try:
        parsed = urlsplit(url)
        return bool(policy.get("reuse_basis") and parsed.scheme == "https" and not parsed.username
                    and not parsed.password and parsed.port in (None, 443) and not parsed.query
                    and parsed.hostname in policy.get("hosts", [])
                    and any(re.fullmatch(pattern, parsed.path) for pattern in policy.get("paths", [])))
    except ValueError:
        return False


def extract_pages(body, media_type):
    if media_type == "text/plain":
        text = body.decode("utf-8", errors="replace")[:MAX_TEXT]
        return {"status": "cached", "page_count": None, "pages": [{"page": 1, "text": text}]}
    if media_type != "application/pdf" or not body.startswith(b"%PDF-"):
        return {"status": "unsupported", "page_count": None, "pages": []}
    from pypdf import apply_configuration
    with apply_configuration(maximum_declared_stream_length=MAX_BYTES,
            array_based_stream_maximum_output_length=8_000_000, zlib_maximum_output_length=8_000_000,
            lzw_maximum_output_length=8_000_000, run_length_maximum_output_length=8_000_000,
            jbig2_maximum_output_length=MAX_BYTES, jbig2dec_binary=None,
            page_tree_maximum_entries=2_000, page_tree_maximum_depth=20,
            xform_maximum_invocations_per_extraction=200, image_maximum_buffer_size=MAX_BYTES):
        return _pdf_pages(body)


def _pdf_pages(body):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(body), strict=True, root_object_recovery_limit=1_000)
    if reader.is_encrypted:
        return {"status": "inaccessible", "page_count": None, "pages": []}
    count = len(reader.pages)
    if count > MAX_PAGES:
        return {"status": "too_large", "page_count": count, "pages": []}
    pages, remaining = [], MAX_TEXT
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "")[:remaining]
        pages.append({"page": number, "text": text})
        remaining -= len(text)
        if not remaining:
            break
    return {"status": "cached" if any(p["text"].strip() for p in pages) else "needs_ocr",
            "page_count": count, "pages": pages}


def _extract_file(path, media_type):
    # The parser is confined to a child process with a wall-clock limit. Its output
    # is plain JSON only, and file bytes/text never become commands or prompts.
    try:
        result = subprocess.run([sys.executable, "-m", "anthrion_signal.attachments", str(path), media_type],
                                capture_output=True, text=True, encoding="utf-8", timeout=20, check=True)
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, ValueError):
        return {"status": "unsupported", "page_count": None, "pages": []}


def fetch_document(client, url, policy, headers=None):
    for _ in range(3):
        if not permitted(url, policy):
            return "permission_required", None, None
        with client.stream("GET", url, headers={"Accept-Encoding": "identity", **(headers or {})}, follow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.headers.get("location", ""))
                continue
            if response.status_code == 304:
                return "unchanged", None, None
            if response.status_code in {404, 410}:
                return "missing", None, None
            if response.status_code != 200:
                return "inaccessible", None, None
            if response.headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
                return "unsupported", None, None
            if int(response.headers.get("content-length", "0")) > MAX_BYTES:
                return "too_large", None, None
            media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type not in {"application/pdf", "text/plain"}:
                return "unsupported", None, None
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    return "too_large", None, None
                chunks.append(chunk)
            return "downloaded", b"".join(chunks), {"media_type": media_type,
                "etag": response.headers.get("etag"), "last_modified": response.headers.get("last-modified")}
    return "inaccessible", None, None


def _compatible_cached_document(document, value):
    cached = Document.model_validate(value)
    # A stable URL can point to revised procurement documents. Never attach an
    # earlier extraction to a new source revision or replace fresh source labels.
    if cached.url != document.url or cached.source_revision != document.source_revision:
        return None
    current_time, cached_time = parse_date(document.retrieved_at), parse_date(cached.retrieved_at)
    if document.content_hash and (not cached.content_hash or current_time and
                                  (not cached_time or current_time > cached_time)):
        return None
    return cached.model_copy(update={"title": document.title, "kind": document.kind,
                                     "source_revision": document.source_revision})


def hydrate_cached_documents(root, signals):
    cache = read_json(root / "data/documents/index.json", {})
    for signal in signals:
        signal.documents = [(_compatible_cached_document(d, cache[d.url]["document"]) or d)
                            if d.url in cache else d for d in signal.documents]


def enrich_documents(root, signals, sources, now, *, limit=2, client=None, extractor=_extract_file):
    limit = min(max(limit, 0), 2)
    policies = {s["id"]: s.get("documents", {}) for s in sources}
    path = root / "data/documents/index.json"
    cache = read_json(path, {})
    used = sum(p.stat().st_size for p in (root / "data/documents/blobs").glob("*"))
    owned_client = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=False, headers={"User-Agent": "AnthrionSignal/1.0"})
    attempted = 0
    try:
        for signal in signals:
            policy = policies.get(signal.source, {})
            for index, document in enumerate(signal.documents):
                previous = cache.get(document.url, {})
                checked = parse_date(previous.get("checked_at"))
                retained_revision = None
                if previous:
                    cached = _compatible_cached_document(document, previous["document"])
                    if cached is not None:
                        document = cached
                        signal.documents[index] = document
                    else:
                        # The weekly check and conditional request belong to the
                        # cached revision, not this newly published source scope.
                        # Keep its history separately: rejecting its extraction
                        # must not orphan the retained source-document revisions.
                        retained_revision = Document.model_validate(previous["document"])
                        previous, checked = {}, None
                if not permitted(document.url, policy) or attempted >= limit:
                    continue
                if checked and checked > now - timedelta(days=7):
                    continue
                attempted += 1
                headers = {"If-None-Match": previous["etag"]} if previous.get("etag") else {}
                try:
                    status, body, metadata = fetch_document(client, document.url, policy, headers)
                except (httpx.HTTPError, ValueError):
                    status, body, metadata = "inaccessible", None, None
                if status == "unchanged":
                    previous["checked_at"] = now.isoformat()
                    continue
                if body is not None:
                    content_hash = hashlib.sha256(body).hexdigest()
                    blob = root / "data/documents/blobs" / content_hash
                    if not blob.exists() and used + len(body) > MAX_CACHE_BYTES:
                        document.status = "too_large"
                    else:
                        if not blob.exists():
                            atomic_bytes(blob, body)
                            used += len(body)
                        if document.content_hash and document.content_hash != content_hash:
                            document.previous_revisions.append({"content_hash": document.content_hash,
                                "revision": document.revision or document.content_hash[:16],
                                "retrieved_at": document.retrieved_at or "", "status": "superseded"})
                        extracted = extractor(blob, metadata["media_type"])
                        document = document.model_copy(update={**extracted, "content_hash": content_hash,
                            "revision": content_hash[:16], "retrieved_at": now.isoformat(),
                            "media_type": metadata["media_type"], "reuse_basis": policy["reuse_basis"]})
                else:
                    document.status = status
                if retained_revision is not None:
                    revisions = list(retained_revision.previous_revisions)
                    if retained_revision.content_hash:
                        revisions.append({"content_hash": retained_revision.content_hash,
                            "revision": retained_revision.revision or retained_revision.content_hash[:16],
                            "retrieved_at": retained_revision.retrieved_at or "", "status": "superseded"})
                    revisions.extend(document.previous_revisions)
                    document = document.model_copy(update={"previous_revisions": list({
                        revision["content_hash"]: revision for revision in revisions
                        if revision.get("content_hash") and revision["content_hash"] != document.content_hash
                    }.values())})
                signal.documents[index] = document
                cache[document.url] = {"document": document.model_dump(), "checked_at": now.isoformat(),
                                       **(metadata or {})}
    finally:
        if owned_client:
            client.close()
    if attempted:
        atomic_json(path, cache)
    return attempted


if __name__ == "__main__":
    from pathlib import Path
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512_000_000, 512_000_000))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    body = Path(sys.argv[1]).read_bytes()
    if len(body) > MAX_BYTES:
        raise SystemExit(1)
    print(json.dumps(extract_pages(body, sys.argv[2]), ensure_ascii=True))
