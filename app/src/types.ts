export interface Evidence {
  quote: string
  source_url: string
}
export interface CapabilityEvidence extends Evidence {
  capability: string
  phrase: string
  strength: string
  basis: string
  field: string
  language: string
  context: 'delivery' | 'existing_system' | 'uncertain'
  source_hash: string
  original_quote?: string
  translated_quote?: string
  original_language?: string
  original_field?: string
}
export interface PublishedAmount {
  kind:
    | 'estimated_contract'
    | 'framework_ceiling'
    | 'grant_range'
    | 'programme_funding'
    | 'award'
    | 'annual_spend'
    | 'unknown'
  minimum?: number | null
  maximum?: number | null
  currency?: string | null
  source_label: string
  source_url: string
}
export interface DeadlineEvent {
  kind:
    | 'questions'
    | 'expression_of_interest'
    | 'application'
    | 'invited_submission'
    | 'tender'
    | 'unknown'
  date: string
  time?: string | null
  timezone?: string | null
  precision: 'date' | 'local_time' | 'instant'
  instant?: string | null
  source_text: string
  source_url: string
  lot_id?: string | null
  status: 'current' | 'superseded' | 'conflicting'
}
export interface ParticipationRequirement {
  id: string
  requirement: string
  status: 'needs_checking'
  source_quote: string
  source_url: string
  translated_quote?: string
  source_hash?: string
  company_evidence: null
}
export interface HistoryRecord {
  signal_id: string
  source?: string
  countries?: string[]
  buyer_name?: string | null
  buyer_id?: string | null
  procedure_id?: string | null
  title: string
  signal_type?: string
  notice_type?: string | null
  published_at?: string | null
  award_date?: string | null
  award_statuses?: string[]
  supplier?: string | null
  status: string
  source_url: string
  lot_ids: string[]
  amount?: PublishedAmount | null
  contract_start?: string | null
  contract_end?: string | null
  extension_end?: string | null
  winners?: Signal['winners']
  lots?: Signal['lots']
}
export interface PublishedDocument {
  title: string
  url: string
  kind: string
  status?: string
  content_hash?: string | null
  revision?: string | null
  retrieved_at?: string | null
  page_count?: number | null
  pages?: { page: number; text: string }[]
  previous_revisions?: {
    content_hash: string
    revision?: string | null
    retrieved_at?: string | null
  }[]
  source_revision?: string | null
  media_type?: string | null
  reuse_basis?: string | null
}
export interface Requirement {
  text: string
  importance: number
  category: string
  evidence: Evidence
  capability_id: string | null
  match_level: string
  company_evidence_ids?: string[]
  possible_products?: string[]
  explanation: string
}
export interface ScoreComponent {
  id: string
  label: string
  points: number | null
  max_points: number
  known_weight: number
  explanation: string
  evidence: Evidence[]
  company_evidence_ids: string[]
}
export interface Signal {
  id: string
  title: string
  description: string
  buyer_name: string | null
  buyer_id?: string | null
  buyer_identifiers?: string[]
  buyer_identity_basis?: 'identifier' | 'source_name' | 'unknown'
  agency_name?: string | null
  department_name?: string | null
  buyer_name_conflicts?: string[]
  source_language?: string
  procedure_identifiers?: string[]
  contacts?: {
    name?: string | null
    role?: string | null
    email?: string | null
    source_url: string
  }[]
  procedure_id?: string | null
  procedure_history?: HistoryRecord[]
  buyer_history?: HistoryRecord[]
  buyer_history_ref?: { url: string; count: number; identity_basis: string } | null
  award_date?: string | null
  winners?: { name: string; identifiers: string[]; lot_ids: string[]; source_url: string }[]
  capability_evidence?: CapabilityEvidence[]
  delivery_role?: {
    kind: 'direct_supplier' | 'advertised_component' | 'funded_project' | 'unknown'
    evidence: CapabilityEvidence[]
  }
  participation_requirements?: ParticipationRequirement[]
  eligibility_text?: string | null
  amount?: PublishedAmount | null
  deadlines?: DeadlineEvent[]
  lots?: {
    id: string
    title: string
    description: string
    status: string
    source_url: string
    deadline_at?: string | null
    value_min?: number | null
    value_max?: number | null
    currency?: string | null
  }[]
  /** Complete source and translated search text supplied by a market summary shard. */
  search_text?: string
  is_summary?: boolean
  source: string
  source_type: string
  primary_source_url: string
  source_urls: string[]
  ocid: string | null
  external_ids: string[]
  signal_type: string
  procurement_stage: string
  status: string
  lifecycle_state?: string
  lifecycle_reason?: string
  discovery_families?: string[]
  delivery_priority?: 'platform' | 'ai' | 'other'
  exclusion_reasons?: string[]
  notice_type: string | null
  published_at: string | null
  updated_at: string | null
  deadline_at: string | null
  response_deadlines?: string[]
  contract_start: string | null
  contract_end: string | null
  extension_end: string | null
  value_min: number | null
  value_max: number | null
  currency: string | null
  regions: string[]
  countries: string[]
  categories: string[]
  cpv_codes: string[]
  framework: string | null
  lot_ids: string[]
  incumbent_supplier: string | null
  award_statuses?: string[]
  first_seen_at: string
  last_seen_at: string
  last_material_update: string
  // Optional legacy fields are accepted from older cached datasets only.
  fit_score?: number | null
  confidence_score?: number
  known_weight?: number
  score_components?: ScoreComponent[]
  prefilter_score?: number
  prefilter_matches: string[]
  matched_capabilities: string[]
  recommendation?: string
  score_explanation?: string
  ai_status?: string
  ai_model?: string | null
  ai_scored_at?: string | null
  analysis?: {
    version?: string
    summary: string
    assessed_scope?: string
    scope_basis?: string
    scope_evidence?: Evidence[]
    solution_suggestion?: string
    solution_evidence?: Evidence[]
    solution_route?: { level: string; explanation: string; opportunity_evidence: Evidence[] }
    requirements_completeness?: string
    eligibility_checks?: {
      text: string
      status: string
      evidence: Evidence
      company_evidence_id: string | null
    }[]
    requirements: Requirement[]
    risks: { text: string; kind: string; evidence: Evidence }[]
    hard_blockers?: { text: string; evidence: Evidence; company_evidence_id: string }[]
    information_gaps: string[]
  } | null
  documents: PublishedDocument[]
  provenance: {
    source: string
    source_name: string
    url: string
    release_id: string
    retrieved_at: string
    published_at: string | null
  }[]
  changes: { at: string; kind: string; fields: string[]; source_url: string }[]
  related_signal_id: string | null
  renewal_basis: string | null
}
export interface Source {
  id: string
  name: string
  website: string
  enabled: boolean
  status: string
  last_attempt: string | null
  last_success: string | null
  records: number
  message: string | null
  countries?: string[]
  coverage?: string | null
}
export type DisplayLanguage = 'en' | 'original'
export interface EnglishText {
  source_hash: string
  version: string
  title: string
  description: string
  buyer_name?: string | null
  buyer_original?: string | null
}
export interface Dataset {
  schema_version: string
  generated_at: string
  data_updated_at: string
  profile_version: string
  scoring_version: string
  sources: Source[]
  capabilities: { id: string; label: string; family: string; search_terms?: string[] }[]
  evidence_catalog: Record<
    string,
    { label: string; quote: string; page?: number; section?: string; document: string }
  >
  markets: Record<string, { name: string; enabled: boolean; coverage?: string }>
  signals: Signal[]
  translations?: Record<string, EnglishText>
  award_history?: Record<string, { url: string; count: number }>
  current_feed?: CurrentFeedManifest
  run: {
    sources_attempted: number
    sources_succeeded: number
    raw_records: number
    new_signals: number
    material_updates: number
    gemini_calls?: number
    cache_hits?: number
    ai_failures?: number
    [key: string]: unknown
  }
}
export interface CurrentFeedManifest {
  version: string
  markets: Record<string, { url: string; count: number }>
  records: Record<string, { url: string; markets: string[]; view?: 'opportunities' | 'awards' }>
}
export interface Filters {
  q: string
  searchMode: string
  match: string
  view: string
  sort: string
  market: string
  score: string
  confidence: string
  source: string
  type: string
  recommendation: string
  capability: string
  sector: string
  buyer: string
  supplier: string
  awardFrom: string
  awardTo: string
  amountType: string
  region: string
  cpv: string
  minValue: string
  maxValue: string
  currency: string
  deadline: string
  change: string
}
