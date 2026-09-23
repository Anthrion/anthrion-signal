"""Source-bound editorial decisions; never delete or reclassify source records.

The versioned ledger is reviewed code/config, not a model's runtime output. A
changed scope invalidates its decision and restores normal discovery behaviour.
"""
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .discovery import is_public_opportunity
from .models import StrictModel
from .utils import digest, read_json


GUIDANCE_COUNTRIES = frozenset({"GB", "US", "CA", "DE", "AT", "CH"})
LANGUAGE_CODES = frozenset((
    "aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy "
    "da de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz "
    "ia id ie ig ii ik io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv "
    "mg mh mi mk ml mn mr ms mt my na nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu "
    "rm rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty "
    "ug uk ur uz ve vi vo wa wo xh yi yo za zh zu"
).split())
# ISO 639-2 source codes used by TED and other official notices, including the
# bibliographic aliases. Reviewed metadata always uses the canonical two letters.
LANGUAGE_ALIASES = {
    "eng": "en", "deu": "de", "ger": "de", "fra": "fr", "fre": "fr", "ita": "it",
    "spa": "es", "por": "pt", "nld": "nl", "dut": "nl", "dan": "da", "swe": "sv",
    "nor": "no", "nob": "nb", "nno": "nn", "fin": "fi", "isl": "is", "ice": "is",
    "ell": "el", "gre": "el", "pol": "pl", "ces": "cs", "cze": "cs", "slk": "sk",
    "slo": "sk", "slv": "sl", "hrv": "hr", "hun": "hu", "ron": "ro", "rum": "ro",
    "bul": "bg", "est": "et", "lav": "lv", "lit": "lt", "gle": "ga", "cym": "cy",
    "wel": "cy", "gla": "gd", "mlt": "mt", "ltz": "lb", "roh": "rm", "cat": "ca",
    "eus": "eu", "baq": "eu", "sqi": "sq", "alb": "sq", "mkd": "mk", "mac": "mk",
    "bos": "bs", "srp": "sr", "ukr": "uk", "rus": "ru", "tur": "tr", "ara": "ar",
    "zho": "zh", "chi": "zh", "jpn": "ja", "kor": "ko", "hin": "hi", "heb": "he",
}


def source_language_code(value):
    language = (value or "").strip().lower().replace("_", "-").split("-", 1)[0]
    return language if language in LANGUAGE_CODES else LANGUAGE_ALIASES.get(language)


class ReviewEvidence(StrictModel):
    field: str
    quote: str = Field(min_length=8, max_length=4000)
    source_url: str


class GuidancePoint(StrictModel):
    text: str = Field(min_length=12, max_length=1200)
    lot_id: str | None = None
    evidence: list[ReviewEvidence] = Field(min_length=1, max_length=8)


class LocalizedGuidancePoint(StrictModel):
    text: str = Field(min_length=12, max_length=1200)
    lot_id: str | None = None

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value):
        if not value.strip():
            raise ValueError("Localized guidance text cannot be blank")
        return value


class LocalizedGuidance(StrictModel):
    approach: list[LocalizedGuidancePoint] = Field(min_length=1, max_length=12)
    problems: list[LocalizedGuidancePoint] = Field(default_factory=list, max_length=6)


class Guidance(StrictModel):
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    approach: list[GuidancePoint] = Field(min_length=1, max_length=12)
    problems: list[GuidancePoint] = Field(default_factory=list, max_length=6)
    complexity: int = Field(ge=1, le=10)
    problem_level: int = Field(ge=1, le=10)
    original_language: str | None = None
    localized: dict[str, LocalizedGuidance] = Field(default_factory=dict)

    @field_validator("original_language")
    @classmethod
    def canonical_language(cls, value):
        if value is not None and value not in LANGUAGE_CODES:
            raise ValueError("Original guidance language must be a canonical ISO 639-1 code")
        return value

    @model_validator(mode="after")
    def aligned_localizations(self):
        for language, localized in self.localized.items():
            if language not in LANGUAGE_CODES or language == "en":
                raise ValueError("Localized guidance needs a canonical non-English language code")
            if self.original_language and language != self.original_language:
                raise ValueError("Localized guidance does not match its reviewed original language")
            for field in ("approach", "problems"):
                original_points, localized_points = getattr(self, field), getattr(localized, field)
                if len(original_points) != len(localized_points):
                    raise ValueError("Localized guidance must preserve the English point counts")
                if any(left.lot_id != right.lot_id for left, right in zip(original_points, localized_points, strict=True)):
                    raise ValueError("Localized guidance must preserve the English lot alignment")
        return self


class RecordReview(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["exclude", "guide"]
    reviewed_at: datetime
    reviewed_by: str = Field(min_length=3)
    reason: str = Field(min_length=12, max_length=1600)
    evidence: list[ReviewEvidence] = Field(default_factory=list, max_length=12)
    guidance: Guidance | None = None

    @model_validator(mode="after")
    def valid_decision(self):
        if self.reviewed_at.tzinfo is None:
            raise ValueError("Review timestamp needs a timezone")
        if self.decision == "exclude" and (not self.evidence or self.guidance is not None):
            raise ValueError("An exclusion needs source evidence and cannot recommend delivery")
        if self.decision == "guide" and (not self.guidance or self.guidance.source_hash != self.source_hash):
            raise ValueError("Guidance must refer to the reviewed scope")
        return self


class ReviewLedger(StrictModel):
    version: Literal[1]
    records: list[RecordReview]


def source_hash(signal):
    """Only source facts: collection time and derived classifications may change.

    New lots, document revisions, eligibility, dates, platforms or buyers require
    a new review. Cached extraction status and generated timelines do not.
    """
    fields = ("id", "title", "description", "buyer_name", "countries", "cpv_codes",
              "source", "primary_source_url", "source_urls", "signal_type", "notice_type",
              "eligibility_text", "framework", "lot_id", "lot_ids", "lots", "deadline_at",
              "response_deadlines", "deadlines", "value_min", "value_max", "currency", "status")
    values = signal.model_dump(include=set(fields))
    values["documents"] = sorted(
        ({"url": d.url, "title": d.title, "source_revision": d.source_revision,
          "content_hash": d.content_hash, "revision": d.revision}
         for d in signal.documents), key=lambda d: (d["url"], d["title"]))
    return digest(["reviewed-scope-1", values])


def load_reviews(root):
    path = root / "config/record_reviews.json"
    if not path.exists():
        return {}
    ledger = ReviewLedger.model_validate(read_json(path, {}))
    result = {review.id: review for review in ledger.records}
    if len(result) != len(ledger.records):
        raise ValueError("Duplicate reviewed record identifier")
    return result


def evidence_text(signal, evidence):
    if evidence.field in {"title", "description", "eligibility_text"}:
        if evidence.source_url not in [signal.primary_source_url, *signal.source_urls]:
            raise ValueError("Review evidence URL is outside the notice provenance")
        return getattr(signal, evidence.field) or ""
    if evidence.field.startswith("lot:"):
        _, lot_id, field = evidence.field.split(":", 2)
        if field not in {"title", "description"}:
            raise ValueError("Unsupported lot evidence field")
        lot = next((lot for lot in signal.lots if lot.id == lot_id), None)
        if lot is None or evidence.source_url != lot.source_url:
            raise ValueError("Review evidence has no matching source lot")
        return getattr(lot, field)
    if evidence.field.startswith("document:"):
        _, content_hash, page_number = evidence.field.split(":", 2)
        document = next((d for d in signal.documents if d.url == evidence.source_url
                         and d.content_hash == content_hash), None)
        if document:
            return next((p.get("text", "") for p in document.pages
                         if str(p.get("page")) == page_number), "")
    raise ValueError("Unsupported review evidence field")


def validate_evidence(signal, evidence):
    # Exact retained text, never a keyword, translated paraphrase or model citation.
    if evidence.quote not in evidence_text(signal, evidence):
        raise ValueError(f"Review passage cannot be traced to {signal.id}")


def validate_guidance(signal, value):
    guidance = Guidance.model_validate(value)
    if guidance.source_hash != source_hash(signal):
        raise ValueError("Guidance refers to an earlier source scope")
    source_language = source_language_code(signal.source_language)
    if guidance.original_language and source_language and guidance.original_language != source_language:
        raise ValueError("Reviewed original language conflicts with the source language")
    original_language = guidance.original_language or source_language
    if any(language != original_language for language in guidance.localized):
        raise ValueError("Localized guidance has no matching reviewed or source language")
    lots = set(signal.lot_ids) | {lot.id for lot in signal.lots}
    if signal.lot_id:
        lots.add(signal.lot_id)
    for point in guidance.approach + guidance.problems:
        if point.lot_id and point.lot_id not in lots:
            raise ValueError("Guidance refers to an unpublished lot")
        for evidence in point.evidence:
            validate_evidence(signal, evidence)
    return guidance


def matching_review(signal, reviews):
    review = reviews.get(signal.id)
    if review is None or review.source_hash != source_hash(signal):
        return None
    for evidence in review.evidence:
        validate_evidence(signal, evidence)
    if review.guidance:
        # Language metadata may change without changing the reviewed source text.
        # Suspend that recommendation; authoring validation remains strict.
        language = source_language_code(signal.source_language)
        original = review.guidance.original_language or language
        if ((language and review.guidance.original_language and language != original)
                or any(localized != original for localized in review.guidance.localized)):
            return None
        validate_guidance(signal, review.guidance)
    return review


def apply_reviews(signals, reviews, *, now=None, guidance=True):
    now = now or datetime.now(UTC)
    selected = []
    for signal in signals:
        # Never trust a retained/generated assessment instead of today's ledger.
        # History and current exports may share objects. Suppressing guidance in
        # history must not erase the caller's reviewed current-record guidance.
        if not guidance and (signal.id in reviews or signal.reviewed_guidance is not None):
            signal = signal.model_copy()
        signal.reviewed_guidance = None
        review = matching_review(signal, reviews)
        if review and review.decision == "exclude":
            continue
        if (guidance and review and review.guidance and GUIDANCE_COUNTRIES.intersection(signal.countries)
                and is_public_opportunity(signal, now)):
            signal.reviewed_guidance = review.guidance.model_dump()
        selected.append(signal)
    return selected
