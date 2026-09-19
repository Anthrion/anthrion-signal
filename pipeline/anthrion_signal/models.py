from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MatchLevel = Literal["DIRECT", "STRONG_ADJACENT", "WEAK_ADJACENT", "NONE", "UNKNOWN"]
SignalType = Literal[
    "LIVE_TENDER", "EARLY_MARKET_ENGAGEMENT", "PIPELINE", "FUTURE_OPPORTUNITY", "FRAMEWORK",
    "RFI", "RFP", "RENEWAL_SIGNAL", "AWARD", "STRATEGIC_INTENT", "FUNDING", "PARTNERSHIP",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Evidence(StrictModel):
    quote: str = Field(min_length=3, max_length=1500)
    source_url: str


class Requirement(StrictModel):
    text: str = Field(min_length=3, max_length=800)
    importance: int = Field(ge=1, le=5)
    category: str
    evidence: Evidence
    capability_id: str | None
    match_level: MatchLevel
    company_evidence_ids: list[str]
    explanation: str = Field(max_length=1200)

    @model_validator(mode="after")
    def require_grounding(self):
        if self.match_level not in ("NONE", "UNKNOWN") and (
            not self.capability_id or not self.company_evidence_ids or not self.explanation.strip()
        ):
            raise ValueError("Non-zero capability matches require profile evidence and an explanation")
        return self


class DimensionAssessment(StrictModel):
    level: MatchLevel
    opportunity_evidence: list[Evidence]
    company_evidence_ids: list[str]
    explanation: str = Field(max_length=1500)

    @model_validator(mode="after")
    def grounded(self):
        if self.level != "UNKNOWN" and not self.opportunity_evidence:
            raise ValueError("Known dimensions require opportunity evidence")
        if self.level not in ("NONE", "UNKNOWN") and not self.company_evidence_ids:
            raise ValueError("Positive dimensions require company evidence")
        return self


class ReferenceAssessment(StrictModel):
    level: Literal["MULTIPLE_DIRECT", "DIRECT_PLUS_ADJACENT", "ONE_DIRECT", "GENERIC", "NONE", "UNKNOWN"]
    reference_ids: list[str]
    opportunity_evidence: list[Evidence]
    explanation: str = Field(max_length=1500)


class Risk(StrictModel):
    text: str = Field(max_length=700)
    evidence: Evidence
    kind: Literal["eligibility", "delivery", "commercial", "scope", "timing", "information_gap"]


class Blocker(StrictModel):
    text: str = Field(max_length=700)
    evidence: Evidence
    company_evidence_id: str


class LegacyAnalysis(StrictModel):
    summary: str = Field(min_length=10, max_length=1800)
    requirements: list[Requirement] = Field(max_length=16)
    references: ReferenceAssessment
    delivery: DimensionAssessment
    sector: DimensionAssessment
    geography: DimensionAssessment
    feasibility: DimensionAssessment
    risks: list[Risk] = Field(max_length=12)
    hard_blockers: list[Blocker] = Field(max_length=8)
    information_gaps: list[str] = Field(max_length=12)
    recommendation_evidence: list[Evidence]


class RequirementMapping(StrictModel):
    text: str = Field(min_length=3, max_length=800)
    importance: int = Field(ge=1, le=5)
    category: str
    evidence: Evidence
    capability_id: str | None
    match_level: Literal["DIRECT", "STRONG", "PLAUSIBLE", "WEAK", "NONE"]
    possible_products: list[str] = Field(max_length=5)
    explanation: str = Field(min_length=5, max_length=1200)

    @model_validator(mode="after")
    def grounded_mapping(self):
        if self.match_level != "NONE" and not self.capability_id:
            raise ValueError("A positive mapping needs a capability identifier")
        return self


class SolutionRoute(StrictModel):
    level: Literal["EXPLICIT_ECOSYSTEM", "VENDOR_NEUTRAL_DIRECT", "FUNCTIONAL_ARCHITECTURE", "ADJACENT", "INDIRECT", "NONE"]
    explanation: str = Field(min_length=5, max_length=1500)
    opportunity_evidence: list[Evidence] = Field(min_length=1, max_length=5)


class DeliveryAssessment(StrictModel):
    level: Literal["BUILD", "IMPLEMENT_AND_ADVISE", "MANAGED_SUPPORT", "DISCOVERY", "CONTRACT_STAFF", "LICENCES", "NONE"]
    explanation: str = Field(min_length=5, max_length=1500)
    opportunity_evidence: list[Evidence] = Field(min_length=1, max_length=5)


class EligibilityCheck(StrictModel):
    text: str = Field(min_length=5, max_length=700)
    status: Literal["CHECK_REQUIRED", "CONFIRMED_BLOCKER", "PARTNER_REQUIRED"]
    evidence: Evidence
    company_evidence_id: str | None


class Analysis(StrictModel):
    version: Literal["2.0"]
    summary: str = Field(min_length=10, max_length=1800)
    assessed_scope: str = Field(min_length=5, max_length=800)
    scope_basis: Literal["WHOLE_REQUIREMENT", "SEPARATELY_ADDRESSABLE_LOT", "PARTIAL_OR_UNCERTAIN"]
    scope_evidence: list[Evidence] = Field(min_length=1, max_length=3)
    requirements: list[RequirementMapping] = Field(min_length=1, max_length=30)
    solution_route: SolutionRoute
    delivery: DeliveryAssessment
    solution_suggestion: str = Field(min_length=10, max_length=1200)
    solution_evidence: list[Evidence] = Field(min_length=1, max_length=5)
    requirements_completeness: Literal["DETAILED", "SUMMARY", "SPARSE"]
    eligibility_checks: list[EligibilityCheck] = Field(max_length=12)
    risks: list[Risk] = Field(max_length=12)
    information_gaps: list[str] = Field(max_length=12)


Lifecycle = Literal["OPEN", "EARLY_ENGAGEMENT", "FUTURE", "AWARDED", "CLOSED", "EXPIRED", "CANCELLED", "WITHDRAWN", "UNKNOWN"]


class ScoreComponent(StrictModel):
    id: str
    label: str
    points: float | None
    max_points: float
    known_weight: float
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    company_evidence_ids: list[str] = Field(default_factory=list)


class Document(StrictModel):
    title: str
    url: str
    kind: str = "document"
    status: Literal["linked", "cached", "missing", "inaccessible", "unsupported", "needs_ocr", "too_large", "permission_required"] = "linked"
    content_hash: str | None = None
    revision: str | None = None
    retrieved_at: str | None = None
    page_count: int | None = None
    pages: list[dict[str, Any]] = Field(default_factory=list)
    previous_revisions: list[dict[str, str]] = Field(default_factory=list)
    source_revision: str | None = None
    media_type: str | None = None
    reuse_basis: str | None = None


class Amount(StrictModel):
    kind: Literal["estimated_contract", "framework_ceiling", "grant_range", "programme_funding", "award", "annual_spend", "unknown"] = "unknown"
    minimum: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)
    currency: str | None = None
    source_label: str
    source_url: str


class Deadline(StrictModel):
    kind: Literal["questions", "expression_of_interest", "application", "invited_submission", "tender", "unknown"] = "unknown"
    date: str
    time: str | None = None
    timezone: str | None = None
    precision: Literal["date", "local_time", "instant"]
    instant: str | None = None
    source_text: str
    source_url: str
    lot_id: str | None = None
    status: Literal["current", "superseded", "conflicting"] = "current"


class Lot(StrictModel):
    id: str
    title: str = ""
    description: str = ""
    status: str = "unknown"
    source_url: str
    deadline_at: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    currency: str | None = None


class Provenance(StrictModel):
    source: str
    source_name: str
    url: str
    release_id: str
    ocid: str | None = None
    retrieved_at: str
    published_at: str | None = None
    raw_hash: str


class Change(StrictModel):
    at: str
    kind: str
    fields: list[str]
    source_url: str


class Signal(StrictModel):
    @model_validator(mode="before")
    @classmethod
    def migrate_incomplete_assessment(cls, data):
        if isinstance(data, dict) and isinstance(data.get("analysis"), dict):
            analysis = data["analysis"]
            if analysis.get("version") == "2.0" and "scope_basis" not in analysis:
                return {**data, "analysis": None, "fit_score": None, "known_weight": 0,
                        "score_components": [], "analysis_cache_key": None, "ai_status": "pending"}
        return data

    id: str
    fingerprint: str = ""
    ocid: str | None = None
    lot_id: str | None = None
    lot_ids: list[str] = Field(default_factory=list)
    external_ids: list[str] = Field(default_factory=list)
    source: str
    source_type: str
    source_urls: list[str] = Field(default_factory=list)
    primary_source_url: str
    title: str
    description: str
    buyer_name: str | None = None
    buyer_identifiers: list[str] = Field(default_factory=list)
    buyer_id: str | None = None
    buyer_identity_basis: Literal["identifier", "source_name", "unknown"] = "unknown"
    agency_name: str | None = None
    department_name: str | None = None
    contacts: list[dict[str, str]] = Field(default_factory=list)
    buyer_name_conflicts: list[str] = Field(default_factory=list)
    source_language: str = "und"
    procedure_id: str | None = None
    procedure_identifiers: list[str] = Field(default_factory=list)
    lots: list[Lot] = Field(default_factory=list)
    lot_award_baseline: dict[str, str] = Field(default_factory=dict)
    procedure_history: list[dict[str, Any]] = Field(default_factory=list)
    buyer_history: list[dict[str, Any]] = Field(default_factory=list)
    buyer_history_ref: dict[str, Any] | None = None
    award_date: str | None = None
    winners: list[dict[str, Any]] = Field(default_factory=list)
    amount: Amount | None = None
    deadlines: list[Deadline] = Field(default_factory=list)
    delivery_role: dict[str, Any] = Field(default_factory=dict)
    participation_requirements: list[dict[str, Any]] = Field(default_factory=list)
    signal_type: SignalType
    procurement_stage: str
    notice_type: str | None = None
    status: str = "unknown"
    lifecycle_state: Lifecycle = "UNKNOWN"
    lifecycle_reason: str = "Source status requires verification."
    discovery_version: str | None = None
    discovery_families: list[str] = Field(default_factory=list)
    delivery_priority: Literal["platform", "ai", "other"] = "other"
    exclusion_reasons: list[str] = Field(default_factory=list)
    published_at: str | None = None
    updated_at: str | None = None
    deadline_at: str | None = None
    response_deadlines: list[str] = Field(default_factory=list)
    contract_start: str | None = None
    contract_end: str | None = None
    extension_end: str | None = None
    value_min: float | None = Field(default=None, ge=0)
    value_max: float | None = Field(default=None, ge=0)
    currency: str | None = None
    cpv_codes: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    framework: str | None = None
    incumbent_supplier: str | None = None
    award_statuses: list[str] = Field(default_factory=list)
    eligibility_text: str | None = None
    documents: list[Document] = Field(default_factory=list)
    first_seen_at: str
    last_seen_at: str
    last_material_update: str
    raw_source_hash: str
    content_hash: str = ""
    material_change_hash: str = ""
    prefilter_score: float = 0
    prefilter_matches: list[str] = Field(default_factory=list)
    matched_capabilities: list[str] = Field(default_factory=list)
    capability_evidence: list[dict[str, str]] = Field(default_factory=list)
    scope_evidence: list[dict[str, str]] = Field(default_factory=list)
    fit_score: float | None = Field(default=None, ge=0, le=100)
    confidence_score: float = Field(default=0, ge=0, le=100)
    known_weight: float = 0
    score_components: list[ScoreComponent] = Field(default_factory=list)
    score_explanation: str = "Awaiting evidence analysis."
    recommendation: str = "REVIEW"
    analysis: Analysis | LegacyAnalysis | None = None
    ai_status: str = "pending"
    ai_model: str | None = None
    ai_scored_at: str | None = None
    analysis_cache_key: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)
    changes: list[Change] = Field(default_factory=list)
    related_signal_id: str | None = None
    renewal_basis: str | None = None


class SourceHealth(StrictModel):
    id: str
    name: str
    website: str
    enabled: bool
    status: Literal["healthy", "partial", "failed", "disabled", "not_checked"]
    last_attempt: str | None = None
    last_success: str | None = None
    records: int = 0
    message: str | None = None
    countries: list[str] = Field(default_factory=list)
    coverage: str | None = None


class EnglishText(StrictModel):
    source_hash: str
    version: str
    title: str
    description: str
    buyer_name: str | None = None
    buyer_original: str | None = None


class Dataset(StrictModel):
    schema_version: str = "1.0"
    generated_at: str
    data_updated_at: str
    company_name: str = "Anthrion"
    profile_version: str
    scoring_version: str
    run: dict[str, Any]
    sources: list[SourceHealth]
    capabilities: list[dict[str, Any]]
    markets: dict[str, Any]
    evidence_catalog: dict[str, Any]
    signals: list[Signal]
    translations: dict[str, EnglishText] = Field(default_factory=dict)
    award_history: dict[str, dict[str, Any]] = Field(default_factory=dict)
    current_feed: dict[str, Any] = Field(default_factory=dict)
