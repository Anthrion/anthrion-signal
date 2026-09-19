"""Compact canonical rows without changing the public serialization contract."""

from .models import Signal


_ENRICHMENT_FIELDS = frozenset({
    "buyer_id", "buyer_identity_basis", "agency_name", "department_name", "contacts",
    "buyer_name_conflicts", "source_language", "procedure_id", "procedure_identifiers",
    "lots", "lot_award_baseline", "procedure_history", "buyer_history", "buyer_history_ref",
    "award_date", "winners", "amount", "deadlines", "delivery_role", "participation_requirements",
})


def canonical_signal_json(signal: Signal) -> str:
    """Omit only empty enrichment defaults added with the research workspace.

    Signal validation restores these defaults. Older fields and nested documents
    retain their existing representation; populated source facts are never omitted.
    """
    excluded = {name for name in _ENRICHMENT_FIELDS
                if getattr(signal, name) == Signal.model_fields[name].get_default(call_default_factory=True)}
    return signal.model_dump_json(exclude=excluded)
