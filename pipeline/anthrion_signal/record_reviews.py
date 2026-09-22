"""Source-bound editorial decisions; never delete or reclassify source records.

The versioned ledger is reviewed code/config, not a model's runtime output. A
changed scope invalidates its decision and restores normal discovery behaviour.
"""
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, model_validator

from .discovery import is_public_opportunity
from .models import StrictModel
from .utils import digest, read_json


class ReviewEvidence(StrictModel):
    field: str
    quote: str = Field(min_length=8, max_length=4000)
    source_url: str


class GuidancePoint(StrictModel):
    text: str = Field(min_length=12, max_length=1200)
    lot_id: str | None = None
    evidence: list[ReviewEvidence] = Field(min_length=1, max_length=8)


class Guidance(StrictModel):
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    approach: list[GuidancePoint] = Field(min_length=1, max_length=12)
    problems: list[GuidancePoint] = Field(default_factory=list, max_length=6)
    complexity: int = Field(ge=1, le=10)
    problem_level: int = Field(ge=1, le=10)


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
        if (guidance and review and review.guidance and "GB" in signal.countries
                and is_public_opportunity(signal, now)):
            signal.reviewed_guidance = review.guidance.model_dump()
        selected.append(signal)
    return selected
