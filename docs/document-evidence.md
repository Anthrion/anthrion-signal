# Document evidence

Policy checked on 18 September 2026. The implementation is in
`pipeline/anthrion_signal/attachments.py`; reviewed source permissions live in
`config/sources.yaml`.

## Permitted source

Automatic retrieval currently permits only official TED notice PDFs matching
`https://ted.europa.eu/en/notice/<publication-number>/pdf`, where the publication
number consists of digits, a hyphen and a four-digit year. The configuration
requires the exact host `ted.europa.eu` and path expression
`/en/notice/\d+-\d{4}/pdf`.

TED documents this [direct notice download format](https://docs.ted.europa.eu/ODS/latest/reuse/download-direct.html).
Its [legal notice](https://ted.europa.eu/en/legal-notice) permits reuse of official
procurement notices unless otherwise indicated and distinguishes third-party
rights. The source URL and that reuse basis accompany extracted evidence. This
permission does not extend automatically to linked buyer portals or attachments
owned by other organisations. Those documents remain links until their access
and reuse rules receive a separate review. Authenticated portals, paid downloads
and national Swiss services are not connected by this policy.

Notice discovery uses the [TED Search API](https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html),
which documents pagination and iteration, with a maximum of 250 notices and
10,000 returned fields per page. The configured collector requests at most 200
notices per page. Document downloads have their own small limit below and do not
increase the model or translation budget.

## Retrieval and extraction limits

| Limit | Current setting |
| --- | --- |
| Documents attempted per ingestion run | At most 2 |
| Refresh interval for an attempted URL | 7 days |
| File size | 4,000,000 bytes |
| Retained local binary cache | 40,000,000 bytes |
| HTTP timeout | 20 seconds per HTTP operation |
| Redirect chain | At most 3 requests, each checked against the same source policy |
| PDF parser wall time | 20 seconds in a child process |
| PDF pages | At most 80; larger documents are marked `too_large` |
| Extracted text | At most 160,000 characters per document |

Only HTTPS on the default TLS port is accepted. Credentials in URLs, query
strings and unapproved hosts or paths are rejected. Redirects never bypass that
check. Compressed HTTP responses are rejected; response bytes are counted while
streaming. Supported media types are PDF and plain UTF-8 text, although the only
enabled source path is presently the TED PDF route.

PDF processing uses pinned `pypdf` with bounded declared and decoded streams,
page-tree traversal and form invocation counts. The child also has CPU and
address-space limits on Unix. Windows uses the parser bounds and child timeout.
No OCR service, model invocation, macro execution or external decoder is used.
An image-only PDF is marked `needs_ocr`, not treated as an empty specification.
The text cap can stop extraction before the final page; `page_count` records the
document's total page count and `pages` contains only the extracted page evidence.

## Evidence and revisions

Each retrieved document retains its official URL, SHA-256 content hash, a short
revision derived from that hash, retrieval time, media type and reuse basis.
Extracted text is stored with one-based page numbers. A source-provided revision
or modification identifier is kept separately as `source_revision` when present.
The hash proves which bytes were processed; it is not a claim of an authenticated
digital signature.

A changed byte hash records the preceding hash, revision and retrieval time in
`previous_revisions` with status `superseded`. The current version carries the
current page text; earlier revision metadata remains available. An HTTP 304
updates the private check time while preserving the original retrieval time and
evidence. A later retrieval failure does not erase previously extracted text;
its retrieval time and updated availability status remain visible.

Documents may be `linked`, `cached`, `missing`, `inaccessible`, `unsupported`,
`needs_ocr`, `too_large` or `permission_required`. A link alone does not imply that
Signal downloaded or reviewed its contents. New notices and less frequently
visited records can remain linked while the bounded queue advances.

The cache index and extracted evidence are retained in `data/documents/index.json`.
Binary files are held under `data/documents/blobs/`, which is ignored by Git and
is not a public download directory. The public record contains the official
source link and permitted text evidence, never a local filesystem path. Offline
exports hydrate existing evidence and perform no document requests.

Offline tests cover policy restrictions, redirect checks, file limits,
compression rejection, actual PDF text extraction, image-only PDF status,
content hashes, revisions and cached retrieval. Public-output validation checks
that extracted pages carry retrieval and reuse metadata.
