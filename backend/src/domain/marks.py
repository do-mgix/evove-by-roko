"""Marks: what an act is worth.

A mark is the smallest execution that counts as a real achievement. Every
catalog action has six tiers — `<10m · 10–30m · 30m–1h · 1–2h · 2–3h · >3h` for
estudo — worth 0 to 5 marks, and the user picks the one that fits instead of
counting exactly.

An action yields at most MARKS_PER_WINDOW marks per MARK_WINDOW_HOURS, and the
window is cumulative, so splitting a session does not pay more. In `sum` mode a
choice is worth the lower bound of its tier and the window pays the tier of the
total: five "20–50" push-up records add up to 100, the 100–150 tier — 3 marks,
not 5. `max` mode is for events that do not add up, like meals: the window pays
the best tier chosen.

Pure functions; the host loads the window and records the event.
"""
from __future__ import annotations


TIER_COUNT = 6
MARKS_PER_WINDOW = 5
MARK_WINDOW_HOURS = 6

# an action with no tiers of its own
DEFAULT_TIERS = {"unit": "min", "bounds": [10, 30, 60, 120, 180]}

_SUFFIX = {"reps": "", "km": " km", "m": " m"}


class MarkError(ValueError):
    """An act that names no valid tier, or tiers that cannot be used."""


def mode(tiers: dict) -> str:
    return "max" if tiers.get("mode") == "max" else "sum"


def validate(tiers: dict) -> None:
    if mode(tiers) == "max":
        if len(tiers.get("labels") or []) != TIER_COUNT:
            raise MarkError("max tiers need 6 labels")
        return
    bounds = tiers.get("bounds") or []
    if (len(bounds) != TIER_COUNT - 1 or bounds[0] <= 0
            or any(b <= a for a, b in zip(bounds, bounds[1:]))):
        raise MarkError("sum tiers need 5 increasing positive bounds")


def _minutes(v: int) -> str:
    if v < 60:
        return f"{v}m"
    h, m = divmod(v, 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


def _minute_range(a: int, b: int) -> str:
    if b < 60:
        return f"{a}–{b}m"
    if a >= 60 and a % 60 == 0 and b % 60 == 0:
        return f"{a // 60}–{b // 60}h"
    return f"{_minutes(a)}–{_minutes(b)}"


def labels(tiers: dict) -> list[str]:
    """Six labels. Never contains ':' — the log line uses it to set off the note."""
    if tiers.get("labels"):
        return list(tiers["labels"])
    b = [int(x) for x in tiers["bounds"]]
    unit = tiers.get("unit", "")
    if unit == "min":
        return ([f"<{_minutes(b[0])}"]
                + [_minute_range(b[i], b[i + 1]) for i in range(TIER_COUNT - 2)]
                + [f">{_minutes(b[-1])}"])
    suffix = _SUFFIX.get(unit, f" {unit}")
    return ([f"<{b[0]}{suffix}"]
            + [f"{b[i]}–{b[i + 1]}{suffix}" for i in range(TIER_COUNT - 2)]
            + [f">{b[-1]}{suffix}"])


def options(tiers: dict) -> list[dict]:
    """The six choices shown when acting, each with the marks it is worth alone."""
    return [{"index": i, "label": label, "marks": i} for i, label in enumerate(labels(tiers))]


def amount(tiers: dict, option: int) -> float:
    """What a choice adds to the window: the lower bound of its tier (`sum`), or the
    tier itself (`max`)."""
    if mode(tiers) == "max":
        return float(option)
    return 0.0 if option == 0 else float(tiers["bounds"][option - 1])


def reached(tiers: dict, total: float) -> int:
    """The tier a window total falls in."""
    if mode(tiers) == "max":
        return int(total)
    return sum(1 for b in tiers["bounds"] if total >= b)


def marks_for(tiers: dict, option, window: list[dict]) -> dict:
    """Marks one act yields.

    `window` holds this action's earlier events inside the window, each
    {"amount", "marks"}. Returns {"marks", "amount", "window_marks"}, the last being
    the window's marks after this act."""
    try:
        option = int(option)
    except (TypeError, ValueError):
        raise MarkError("choose a tier from 0 to 5")
    if not 0 <= option < TIER_COUNT:
        raise MarkError("choose a tier from 0 to 5")
    add = amount(tiers, option)
    already = sum(int(e["marks"]) for e in window)
    if mode(tiers) == "max":
        best = max([option] + [int(e["amount"]) for e in window])
    else:
        best = reached(tiers, sum(float(e["amount"]) for e in window) + add)
    granted = max(0, min(best, MARKS_PER_WINDOW) - already)
    return {"marks": granted, "amount": add, "window_marks": already + granted}
