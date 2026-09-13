"""Shared, bounded phrase matching for collection and capability evidence."""
import re
import unicodedata
from functools import lru_cache


@lru_cache(maxsize=8192)
def search_text(value):
    value = unicodedata.normalize("NFKD", value or "").casefold()
    return " " + re.sub(r"[^\w]+", " ", "".join(c for c in value if not unicodedata.combining(c))).strip() + " "


@lru_cache(maxsize=256)
def phrase_pattern(phrases):
    words = sorted({search_text(p).strip() for p in phrases if p.strip()}, key=lambda p: (-len(p), p))
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(p) for p in words) + r")(?!\w)") if words else None


def phrase_hits(text, phrases):
    pattern = phrase_pattern(tuple(phrases))
    return list(dict.fromkeys(match.group() for match in pattern.finditer(text))) if pattern else []


def collection_match(text, terms):
    text = re.sub(r"https?://\S+", " ", text, flags=re.IGNORECASE)
    return bool(phrase_hits(search_text(text), terms.get("discovery_phrases", [])))
