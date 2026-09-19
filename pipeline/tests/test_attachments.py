import hashlib
import io
from datetime import timedelta

import httpx

from anthrion_signal.attachments import MAX_BYTES, enrich_documents, extract_pages, fetch_document
from anthrion_signal.models import Document

POLICY = {"hosts": ["ted.europa.eu"], "paths": [r"/en/notice/\d+-\d{4}/pdf"],
          "reuse_basis": "Official TED notice reuse policy"}
URL = "https://ted.europa.eu/en/notice/123456-2026/pdf"


def test_pdf_text_and_page_attribution_without_ocr():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    text = DecodedStreamObject()
    text.set_data(b"BT /F1 12 Tf 10 200 Td (Published participation requirement) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(text)
    body = io.BytesIO()
    writer.write(body)
    result = extract_pages(body.getvalue(), "application/pdf")
    assert result["status"] == "cached" and result["page_count"] == 1
    assert result["pages"][0] == {"page": 1, "text": "Published participation requirement"}


def test_scan_is_explicitly_needs_ocr():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=400)
    body = io.BytesIO()
    writer.write(body)
    assert extract_pages(body.getvalue(), "application/pdf")["status"] == "needs_ocr"


def test_redirect_is_checked_before_private_or_external_contact():
    requests = []
    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_document(client, URL, POLICY)[0] == "permission_required"
    assert requests == [URL]


def test_stream_size_and_content_type_are_bounded():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            headers={"Content-Type": "application/pdf"}, content=b"x" * (MAX_BYTES + 1)))) as client:
        assert fetch_document(client, URL, POLICY)[0] == "too_large"
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            headers={"Content-Type": "text/html"}, text="Login"))) as client:
        assert fetch_document(client, URL, POLICY)[0] == "unsupported"


def test_http_compression_cannot_bypass_stream_limits():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200,
            headers={"Content-Type": "application/pdf", "Content-Encoding": "gzip"}, content=b""))) as client:
        assert fetch_document(client, URL, POLICY)[0] == "unsupported"


def test_hash_revisions_cache_hit_and_request_budget(tmp_path, signal, now):
    calls, body = [], [b"Revision one"]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, headers={"Content-Type": "text/plain"}, content=body[0])
    signal.source = "ted"
    signal.documents = [Document(title="Notice", url=URL)]
    source = [{"id": "ted", "documents": POLICY}]
    def extractor(path, media):
        return extract_pages(path.read_bytes(), media)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert enrich_documents(tmp_path, [signal], source, now, client=client, extractor=extractor) == 1
        first_hash = signal.documents[0].content_hash
        assert first_hash == hashlib.sha256(body[0]).hexdigest()
        assert enrich_documents(tmp_path, [signal], source, now, client=client, extractor=extractor) == 0
        body[0] = b"Revision two"
        assert enrich_documents(tmp_path, [signal], source, now + timedelta(days=8), client=client, extractor=extractor) == 1
    latest = signal.documents[0]
    assert latest.content_hash != first_hash and latest.previous_revisions[0]["content_hash"] == first_hash
    assert latest.previous_revisions[0]["status"] == "superseded" and len(calls) == 2
    assert len(list((tmp_path / "data/documents/blobs").iterdir())) == 2


def test_unknown_reuse_policy_never_downloads(tmp_path, signal, now):
    signal.documents = [Document(title="Private portal attachment", url="https://example.com/file.pdf")]
    with httpx.Client(transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(AssertionError("request not permitted")))) as client:
        assert enrich_documents(tmp_path, [signal], [], now, client=client) == 0
    assert signal.documents[0].status == "linked"
