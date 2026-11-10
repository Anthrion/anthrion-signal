"""Read the public snapshot from its bootstrap and immutable record files."""
import json
import re
from collections import defaultdict

from .public_compression import decode_public_bytes
from .utils import digest, retained_path

PATHS = re.compile(
    r"(?:(?:awards|current)/[A-Z]+-[a-f0-9]{16}|records/[A-Za-z0-9_-]{1,100}-[a-f0-9]{16}|"
    r"buyers/(?:buyer_[a-f0-9]{20}|bucket-[a-f0-9]{2}-[0-9]+)-[a-f0-9]{16})\.json(?:\.gz)?|"
    r"history/[a-f0-9]{3,64}-[a-f0-9]{16}\.json\.gz"
)


def read_public_shard(root, relative):
    if not PATHS.fullmatch(relative):
        raise ValueError("Unsafe public data path")
    page = json.loads(decode_public_bytes((root / relative).read_bytes(), relative))
    suffix = ".json.gz" if relative.endswith(".gz") else ".json"
    if page.get("schema_version") != "1.0" or not relative.endswith(digest(page)[:16] + suffix):
        raise ValueError("Public content hash/schema mismatch")
    return page


def read_public_snapshot(path):
    """Reconstruct complete current notices for offline audits, never for deployment."""
    path = retained_path(path)
    data = json.loads(decode_public_bytes(path.read_bytes(), path.name))
    if path.name not in {"manifest.json", "manifest.json.gz"}:
        return data
    paths = defaultdict(list)
    for ident, pointer in data["current_feed"]["records"].items():
        if pointer.get("view") == "opportunities":
            if not pointer["url"].startswith("records/"):
                raise ValueError("Current record points outside its detail files")
            paths[pointer["url"]].append(ident)
    signals, translations = [], {}
    for relative, identifiers in paths.items():
        page = read_public_shard(path.parent, relative)
        for ident in identifiers:
            detail = page["records"][ident] if "records" in page else page
            if detail["signal"]["id"] != ident:
                raise ValueError("Record detail identity mismatch")
            signals.append(detail["signal"])
            if "translation" in detail:
                translations[ident] = detail["translation"]
    if len(signals) != data["run"]["public_signals"]:
        raise ValueError("Current record count does not match the public manifest")
    return {**data, "signals": signals, "translations": translations}
