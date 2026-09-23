import hashlib
import gzip
import json
import os
import re
import tempfile
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

BRUSSELS = ZoneInfo("Europe/Brussels")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_date(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[+-]\d{2}:\d{2}", value):
        value = value[:10] + "T00:00:00" + value[10:]
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    except ValueError:
        for fmt in ("%d/%m/%Y", "%d %B %Y", "%d %b %Y", "%Y%m%d"):
            try:
                return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def iso(value) -> str | None:
    dt = parse_date(value)
    return dt.isoformat(timespec="seconds") if dt else None


def calendar_day(value) -> str | None:
    """Keep a published calendar day as YYYY-MM-DD; a clock time keeps its instant.

    A zone designator on a date, as in TED's "2026-07-02+02:00" or "2023-10-30Z",
    names where that day applies, not a time. Stored as local midnight in UTC, it
    became the previous date for every reader west of the offset.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if match := re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:Z|[+-]\d{2}:\d{2})", text):
        text = match[1]
    if re.search(r"\d:\d{2}", text):
        return iso(text)
    parsed = parse_date(text)
    return parsed.date().isoformat() if parsed else None


def utc_midnight_day(value) -> str | None:
    """The date of an exact UTC-midnight instant, as earlier releases stored "YYYY-MM-DDZ"."""
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00\+00:00", value):
        return value[:10]
    return None


def brussels_midnight_day(value) -> str | None:
    """The Brussels date of an exact UTC instant at Brussels midnight, or None.

    This is how earlier releases stored a TED day published with +01:00/+02:00.
    """
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T2[23]:00:00\+00:00", value):
        return None
    local = datetime.fromisoformat(value).astimezone(BRUSSELS)
    return local.date().isoformat() if local.hour == 0 else None


def clean(value, limit=24000) -> str:
    if value is None:
        return ""
    text = str(value)
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()[:limit]


def normal_text(value) -> str:
    return re.sub(r"[^\w]+", " ", clean(value).casefold()).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    return f" {normal_text(phrase)} " in f" {normal_text(text)} "


def canonical_url(url: str) -> str:
    p = urlparse(str(url))
    if p.scheme not in ("https", "http") or not p.netloc or p.username or p.password:
        return ""
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_") and k not in ("gclid", "fbclid")]
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", urlencode(sorted(query)), ""))


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def official_notice_url(url: str) -> str:
    """CCS/GCA related notices must actually belong to Find a Tender, not mention it."""
    try:
        link = canonical_url(url)
        parsed = urlparse(link)
        if (parsed.hostname == "www.find-tender.service.gov.uk"
                and parsed.port in (None, 80 if parsed.scheme == "http" else 443)
                and re.fullmatch(r"/Notice/\d+-\d{4}", parsed.path)):
            return link
    except ValueError:
        pass
    return ""


def read_json(path: Path, default):
    if not retained_path(path).exists():
        return default
    return json.loads(read_retained_bytes(path))


def retained_path(path: Path) -> Path:
    """Read old plain snapshots and their lossless compressed successors."""
    compressed = path.with_name(path.name + ".gz")
    return path if path.exists() or not compressed.exists() else compressed


def read_retained_bytes(path: Path) -> bytes:
    actual = retained_path(path)
    body = actual.read_bytes()
    return gzip.decompress(body) if actual.suffix == ".gz" else body


def atomic_retained_bytes(path: Path, body: bytes, *, threshold=32 * 1024 * 1024) -> bool:
    """Compress growing Git snapshots atomically; public web assets stay ordinary JSON.

    Write and fsync the replacement before removing the old representation. Gzip's
    fixed timestamp makes unchanged records byte-stable across collection runs.
    Small legacy fixtures and files remain readable without a migration step.
    """
    if path.suffix == ".gz":
        path = path.with_suffix("")
    compressed = path.with_name(path.name + ".gz")
    if len(body) < threshold and not compressed.exists():
        return atomic_bytes(path, body)
    packed = gzip.compress(body, compresslevel=6, mtime=0)
    if len(packed) >= 95 * 1024 * 1024:
        raise ValueError("Compressed retained snapshot needs partitioning before Git publication")
    changed = atomic_bytes(compressed, packed)
    legacy = path.exists()
    path.unlink(missing_ok=True)
    return changed or legacy


def atomic_retained_json(path: Path, value) -> bool:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    return atomic_retained_bytes(path, body.encode("utf-8"))


def jsonl_lines(body: str):
    """JSON Lines uses LF, not Unicode separators that may occur inside strings.

    CRLF also works: the JSON parser accepts the trailing CR as whitespace.
    Leave each record untouched and let malformed JSON fail validation.
    """
    return (line for line in body.split("\n") if line.strip())


def atomic_bytes(path: Path, body: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == body:
        return False
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        # Windows readers and virus scanners can briefly hold an otherwise writable file.
        for attempt in range(8):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(.05 * 2 ** attempt, 1))
    finally:
        temp.unlink(missing_ok=True)
    return True


def atomic_json(path: Path, value) -> bool:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    return atomic_bytes(path, body.encode("utf-8"))


def unique(values):
    return list(dict.fromkeys(x for x in values if x))
