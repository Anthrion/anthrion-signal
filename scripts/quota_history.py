"""Keep old quota evidence in snapshots without resetting any current reservation."""
import gzip
import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def _atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def archive_quota_history(root, now=None):
    """Move history older than two previous Pacific days; upload before committing it."""
    path = root / "data/translation_quota.json"
    if not path.exists():
        return False
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != 1 or not isinstance(state.get("models"), dict):
        raise ValueError("Invalid quota ledger; refusing to archive or reset usage")
    cutoff = ((now or datetime.now(UTC)).astimezone(ZoneInfo("America/Los_Angeles")).date()
              - timedelta(days=2))
    histories = {}

    def month_for(day):
        try:
            parsed = date.fromisoformat(day)
        except (TypeError, ValueError):
            return None  # Retain unfamiliar keys rather than discard evidence.
        return day[:7] if parsed < cutoff and parsed.isoformat() == day else None

    def history(month):
        if month not in histories:
            target = root / f"data/translation/quota-history/{month}.json.gz"
            value = json.loads(gzip.decompress(target.read_bytes())) if target.exists() else {
                "version": 1, "allocations": {}, "model_days": {},
            }
            if value.get("version") != 1 or not isinstance(value.get("allocations"), dict) or not isinstance(value.get("model_days"), dict):
                raise ValueError("Invalid archived quota evidence")
            histories[month] = (target, value)
        return histories[month][1]

    def merge(target, key, value):
        if key in target and target[key] != value:
            raise ValueError("Archived quota evidence conflicts; no usage was reset")
        target[key] = value

    allocations = state.get("allocations", {})
    for identifier, allocation in list(allocations.items()):
        if month := month_for(allocation.get("day")):
            merge(history(month)["allocations"], identifier, allocation)
            del allocations[identifier]
    for model, entry in state["models"].items():
        days = entry.get("days", {})
        for day, used in list(days.items()):
            if month := month_for(day):
                merge(history(month)["model_days"].setdefault(model, {}), day, used)
                del days[day]
    if not histories:
        return False
    # Every archive is prepared and checked before any live ledger write. An
    # interrupted archive write leaves the old ledger intact and can be retried.
    for target, value in histories.values():
        _atomic(target, gzip.compress(json.dumps(value, sort_keys=True, separators=(",", ":")).encode(), mtime=0))
    _atomic(path, (json.dumps(state, indent=2) + "\n").encode())
    return True
