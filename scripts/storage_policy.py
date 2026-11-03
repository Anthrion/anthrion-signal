"""Reviewed boundary between small Git control files and retained snapshot data."""
CONTROL_FILES = frozenset({
    "data/validated_data.json", "data/publication_state.json", "data/published_release.json",
    "data/verification_state.json", "data/ui_verification_state.json",
    "data/translation_quota.json", "data/retained_state.json", "data/storage_health.json",
})
CONTROL_LIMIT = 256 * 1024
STATE_POINTER = "data/retained_state.json"
PART_BYTES = 1024 * 1024 * 1024
MAX_STATE_BYTES = 4 * PART_BYTES
MAX_STATE_FILES = 10_000
PREFIX = "signal-data-v1-"
