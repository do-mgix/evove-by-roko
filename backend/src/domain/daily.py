"""Daily tick: checkpoint countdown.

Pure logic on dicts — no I/O. Call once per day (idempotent within the same day).
Returns True if `data` was mutated and needs to be persisted.

Tokens are not refilled here: they are earned by executing productivity actions
and spent on leisure ones (see `src/domain/act.py`).
"""
from __future__ import annotations

import math
from datetime import datetime


BUILD_POINTS_PER_CHECKPOINT = 10


def _checkpoint_interval_for_stage(stage: int) -> int:
    return 19 + max(1, int(stage or 1))


def apply_daily_tick(data: dict, now: datetime | None = None) -> bool:
    """Mutates `data` in-place with daily state transitions.

    Idempotent: the checkpoint countdown only moves once per day.
    Returns True if any field was changed.
    """
    now = now or datetime.now()
    today = now.date()
    today_str = today.isoformat()
    metadata = data.setdefault("metadata", {})
    mutated = False

    def _to_date(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s)).date()
        except (TypeError, ValueError):
            return None

    # ---- checkpoint countdown ----
    last_check = _to_date(metadata.get("last_checkpoint_check"))
    if last_check is None or last_check < today:
        elapsed = (today - last_check).days if last_check else 1
        stage = int(metadata.get("stage", 1) or 1)
        interval = _checkpoint_interval_for_stage(stage)
        days_until = int(metadata.get("days_until_next_checkpoint", interval) or interval)
        days_until = max(0, days_until - elapsed)

        if days_until <= 0:
            stage += 1
            reward = 1 + int(math.ceil(stage / 4))
            metadata["energy"] = 1000
            metadata["stage"] = stage
            metadata["skill_points"] = int(metadata.get("skill_points", 0) or 0) + reward
            metadata["build_points"] = (
                int(metadata.get("build_points", 0) or 0) + BUILD_POINTS_PER_CHECKPOINT
            )
            days_until = _checkpoint_interval_for_stage(stage)

        metadata["days_until_next_checkpoint"] = days_until
        metadata["last_checkpoint_check"] = today_str
        mutated = True

    # ---- keep date field current ----
    if metadata.get("date") != today_str:
        metadata["date"] = today_str
        mutated = True

    return mutated
