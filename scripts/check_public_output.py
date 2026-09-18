"""Fail closed if credential-shaped values or unsafe URLs enter public JSON."""
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from anthrion_signal.models import Dataset, Signal
from anthrion_signal.discovery import is_public_award

path = Path("app/public/data/current.json")
raw = json.loads(path.read_text(encoding="utf-8"))
data = Dataset.model_validate(raw)
retired = {"analysis", "fit_score", "confidence_score", "ai_status", "score_components", "recommendation"}
records = list(raw["signals"])
pages = []
for manifest in data.award_history.values():
    if not re.fullmatch(r"awards/[A-Z]+-[a-f0-9]{16}\.json", manifest["url"]):
        raise SystemExit("Unsafe award history path")
    page = json.loads((path.parent / manifest["url"]).read_text(encoding="utf-8"))
    if page.get("schema_version") != "1.0" or len(page["signals"]) != manifest["count"]:
        raise SystemExit("Award history manifest mismatch")
    if any(not is_public_award(Signal.model_validate(s), datetime.now(UTC)) for s in page["signals"]):
        raise SystemExit("Non-awarded record detected in award history")
    records.extend(page["signals"])
    pages.append(page)
if any(retired.intersection(signal) for signal in records):
    raise SystemExit("Retired model analysis detected in public output")
serialized = json.dumps([raw, *pages])
patterns = [r"AIza[0-9A-Za-z_-]{30,}", r"gh[pousr]_[A-Za-z0-9_]{20,}", r"-----BEGIN .*PRIVATE KEY-----"]
if any(re.search(pattern, serialized) for pattern in patterns):
    raise SystemExit("Credential-shaped material detected in public output")
for item in records:
    signal = Signal.model_validate(item)
    for url in signal.source_urls + [signal.primary_source_url] + [d.url for d in signal.documents]:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.username or parsed.password:
            raise SystemExit("Unsafe link detected in public output")
print(f"Public output checked: {len(data.signals)} live-feed records and {sum(p['count'] for p in data.award_history.values())} market award entries, no credential-shaped values or unsafe links.")
