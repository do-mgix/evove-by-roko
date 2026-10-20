"""Recoveries: tokens bought back into hp.

Two sizes, each on a cooldown of its own: the small one heals 5 for 3 tokens and
comes back after 6 hours, the large one heals 15 for 8 and comes back after 12.
Healing never goes past the profile's max hp, and a full tank takes none.

Pure logic on the metadata dict — no I/O. The moment each was last used lives
in `metadata["recover_<kind>_at"]`, ISO text like `journey_started_at`.
"""
from __future__ import annotations

from datetime import datetime, timedelta


RECOVERIES = {
    "small": {"cost": 3, "heal": 5, "cooldown_hours": 6},
    "large": {"cost": 8, "heal": 15, "cooldown_hours": 12},
}


class RecoverError(ValueError):
    """A recovery that cannot be taken now: unknown, cooling down, unpaid or useless."""


def _used_at(metadata: dict, kind: str) -> datetime | None:
    raw = metadata.get(f"recover_{kind}_at")
    try:
        return datetime.fromisoformat(str(raw)) if raw else None
    except ValueError:
        return None


def seconds_left(metadata: dict, kind: str, now: datetime) -> int:
    """Seconds until `kind` can be taken again; 0 when it is ready."""
    used = _used_at(metadata, kind)
    if not used:
        return 0
    ready = used + timedelta(hours=RECOVERIES[kind]["cooldown_hours"])
    return max(0, int((ready - now).total_seconds()))


def view(metadata: dict, now: datetime, max_energy: int) -> list[dict]:
    """Both recoveries as the interface shows them, with why one is not ready."""
    energy = int(metadata.get("energy", 0) or 0)
    tokens = int(metadata.get("tokens", 0) or 0)
    out = []
    for kind, r in RECOVERIES.items():
        wait = seconds_left(metadata, kind, now)
        blocked = "cooldown" if wait else "tokens" if tokens < r["cost"] else "full" if energy >= max_energy else None
        out.append({"kind": kind, **r, "seconds_left": wait, "ready": blocked is None, "blocked": blocked})
    return out


def recover(metadata: dict, kind: str, now: datetime, max_energy: int) -> int:
    """Takes recovery `kind`: spends its tokens, heals and starts its cooldown.
    Mutates `metadata` and returns the hp healed."""
    r = RECOVERIES.get(kind)
    if not r:
        raise RecoverError(f"unknown recovery '{kind}'")
    if seconds_left(metadata, kind, now):
        raise RecoverError("still cooling down")
    tokens = int(metadata.get("tokens", 0) or 0)
    if tokens < r["cost"]:
        raise RecoverError(f"not enough tokens (have {tokens}, need {r['cost']})")
    energy = int(metadata.get("energy", 0) or 0)
    healed = min(r["heal"], max(0, max_energy - energy))
    if not healed:
        raise RecoverError("hp is already full")
    metadata["tokens"] = tokens - r["cost"]
    metadata["energy"] = energy + healed
    metadata[f"recover_{kind}_at"] = now.isoformat(timespec="seconds")
    metadata["recover_uses"] = int(metadata.get("recover_uses", 0) or 0) + 1
    return healed
