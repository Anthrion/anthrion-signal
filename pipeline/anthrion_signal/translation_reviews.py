"""Approved, exact-source translations supplement the persistent provider cache."""
from typing import Literal

from pydantic import Field

from .models import StrictModel
from .utils import digest, read_json


class ReviewedTranslation(StrictModel):
    id: str
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    version: str
    title: str
    description: str
    source_language: str = Field(pattern=r"^[a-z]{2,3}$")
    reviewed_by: str = Field(min_length=3)
    reviewed_at: str


class TranslationLedger(StrictModel):
    version: Literal[1]
    records: list[ReviewedTranslation]


def reviewed_translations(root, sources):
    from .translation import VERSION, translation_text, validate_translation

    path = root / "config/reviewed_translations.json"
    if not path.exists():
        return {}
    ledger = TranslationLedger.model_validate(read_json(path, {}))
    reviews = {entry.id: entry for entry in ledger.records}
    if len(reviews) != len(ledger.records):
        raise ValueError("Duplicate reviewed translation identifier")
    result = {}
    for source in sources:
        source = source if isinstance(source, dict) else source.model_dump()
        entry = reviews.get(source["id"])
        if (entry is None or entry.version != VERSION
                or entry.source_hash != digest([source["title"], source.get("description", "")])):
            continue
        names = [source["buyer_name"]] if source.get("buyer_name") else []
        for field in ("title", "description"):
            original, translated = source.get(field, ""), getattr(entry, field)
            if not original and not translated:
                continue
            if not validate_translation(original, {"text": translated, "language": entry.source_language}, names):
                raise ValueError(f"Reviewed translation failed the existing quality checks: {entry.id}/{field}")
            for name in names:
                if (translation_text(name).casefold() in translation_text(original).casefold()
                        and translation_text(name).casefold() not in translated.casefold()):
                    raise ValueError("Reviewed translation changed a protected buyer name")
        result[entry.id] = entry.model_dump(include={"source_hash", "version", "title", "description"})
    return result


def prioritize_unreviewed_translations(root, sources, queue):
    """Skip already reviewed passages for this run without altering the cache.

    The versioned ledger is the only store for reviewed wording: corrections and
    withdrawals must not leave untraceable copies in field caches or sidecars.
    Shared fields still run when another, unreviewed notice needs them. The next
    queue.prepare restores work automatically if its approval has been removed.
    """
    from .translation import field_key

    sources = list(sources)
    accepted = reviewed_translations(root, sources)
    covered, needed = set(), set()
    for source in sources:
        keys = {field_key(text) for text in (source.title, source.description) if text.strip()}
        (covered if source.id in accepted else needed).update(keys)
    skipped = covered - needed
    queue.active = [key for key in queue.active if key not in skipped]
    queue.active_keys.difference_update(skipped)
    return accepted
