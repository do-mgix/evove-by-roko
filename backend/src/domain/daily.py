"""Daily tick: journey progress and the current date.

Pure logic on dicts — no I/O. Safe to call on every load: it only changes
something when a journey point or checkpoint was reached, or the day turned.
Returns True if `data` was mutated and needs to be persisted.

Tokens are not refilled here: they are earned by executing productivity actions
and spent on leisure ones (see `src/domain/act.py`).
"""
from __future__ import annotations

from datetime import datetime

from src.domain import journey


def apply_daily_tick(data: dict, now: datetime | None = None,
                     max_energy: int = journey.BASE_MAX_ENERGY) -> bool:
    """Mutates `data` in place: pays journey points and checkpoints reached by
    `now` (see src.domain.journey) and keeps `metadata['date']` current.
    Returns True if any field was changed.
    """
    now = now or datetime.now()
    today_str = now.date().isoformat()
    metadata = data.setdefault("metadata", {})
    mutated = not metadata.get("journey_started_at")

    if journey.advance(metadata, now, max_energy):
        mutated = True

    # ---- keep date field current ----
    if metadata.get("date") != today_str:
        metadata["date"] = today_str
        mutated = True

    return mutated
