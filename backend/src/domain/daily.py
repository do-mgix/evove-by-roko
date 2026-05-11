"""Daily tick: checkpoint countdown and token refill.

Pure logic on dicts — no I/O. Call once per day (idempotent within the same day).
Returns True if `data` was mutated and needs to be persisted.
"""
from __future__ import annotations

import math
from datetime import datetime


def _checkpoint_interval_for_stage(stage: int) -> int:
    return 19 + max(1, int(stage or 1))


def apply_daily_tick(data: dict, now: datetime | None = None) -> bool:
    """Mutates `data` in-place with daily state transitions.

    Idempotent: exits early if both checkpoint and refill already ran today.
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

    # ---- token refill (once per day) ----
    last_refill = _to_date(metadata.get("last_token_refill"))
    if last_refill is None or last_refill < today:
        daily_refill = int(metadata.get("daily_refill", 20) or 20)
        max_tokens = int(metadata.get("max_tokens", 50) or 50)
        metadata["tokens"] = min(max_tokens, int(metadata.get("tokens", 0) or 0) + daily_refill)
        metadata["last_token_refill"] = today_str
        mutated = True

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
            days_until = _checkpoint_interval_for_stage(stage)

        metadata["days_until_next_checkpoint"] = days_until
        metadata["last_checkpoint_check"] = today_str
        mutated = True

    # ---- keep date field current ----
    if metadata.get("date") != today_str:
        metadata["date"] = today_str
        mutated = True

    return mutated
