"""Journey mode: survive from one checkpoint to the next.

Pure logic on the metadata dict — no I/O.

A stage lasts a fixed number of days: 1, 3, 7, 14, 30, 60, then doubling
(120, 240, 480...), so a late checkpoint can be a year or more away. Each stage
is cut into smaller points — daily up to 14 days, weekly for 30 and 60, every
30 days after that. Reaching a point refills the energy and pays the build
points of the stretch just survived; reaching the checkpoint does the same, adds
skill points and opens the next stage.

Energy only drains: every act that is not on today's agenda costs some (see
src.domain.act). If it reaches zero, the journey starts over from stage 1, right
then. Points already earned stay earned.

Time runs from `journey_started_at`, the moment the current stage began. A new
stage starts when the previous one ended, not when someone next opens the app,
so a checkpoint passed while away is paid in full on return.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta


BASE_MAX_ENERGY = 1000

_FIRST_STAGES = (1, 3, 7, 14, 30, 60)

# One build point per day survived, paid at every point and at the checkpoint.
BUILD_POINTS_PER_DAY = 1


def stage_days(stage: int) -> int:
    stage = max(1, int(stage))
    if stage <= len(_FIRST_STAGES):
        return _FIRST_STAGES[stage - 1]
    return _FIRST_STAGES[-1] * 2 ** (stage - len(_FIRST_STAGES))


def point_step_days(width: int) -> int:
    if width <= 14:
        return 1
    if width <= 60:
        return 7
    return 30


def point_offsets(stage: int) -> list[int]:
    """Days from the stage's start to each smaller point, the checkpoint excluded."""
    width = stage_days(stage)
    step = point_step_days(width)
    return list(range(step, width, step))


def checkpoint_skill_points(stage: int) -> int:
    """Skill points for completing `stage`."""
    return 1 + int(math.ceil((stage + 1) / 4))


def _parse(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def started_at(metadata: dict, now: datetime) -> datetime:
    return _parse(metadata.get("journey_started_at")) or now


def advance(metadata: dict, now: datetime, max_energy: int) -> list[dict]:
    """Pays every point and checkpoint reached by `now`, in order. Mutates
    `metadata` and returns what happened, oldest first."""
    events: list[dict] = []
    if not metadata.get("journey_started_at"):
        metadata["journey_started_at"] = now.isoformat(timespec="seconds")
        metadata["journey_points"] = 0
    while True:
        stage = int(metadata.get("stage", 1) or 1)
        start = started_at(metadata, now)
        offsets = point_offsets(stage)
        done = int(metadata.get("journey_points", 0) or 0)

        while done < len(offsets) and start + timedelta(days=offsets[done]) <= now:
            days = offsets[done] - (offsets[done - 1] if done else 0)
            _pay(metadata, max_energy, build=days * BUILD_POINTS_PER_DAY)
            done += 1
            metadata["journey_points"] = done
            events.append({"type": "point", "stage": stage, "day": offsets[done - 1]})

        width = stage_days(stage)
        end = start + timedelta(days=width)
        if end > now:
            return events
        days = width - (offsets[-1] if offsets else 0)
        skill = checkpoint_skill_points(stage)
        _pay(metadata, max_energy, build=days * BUILD_POINTS_PER_DAY, skill=skill)
        metadata["stage"] = stage + 1
        metadata["journey_started_at"] = end.isoformat(timespec="seconds")
        metadata["journey_points"] = 0
        events.append({"type": "checkpoint", "stage": stage, "skill_points": skill})


def fail(metadata: dict, now: datetime, max_energy: int) -> None:
    """Energy ran out: back to stage 1, starting now, with a full tank."""
    metadata["stage"] = 1
    metadata["journey_started_at"] = now.isoformat(timespec="seconds")
    metadata["journey_points"] = 0
    metadata["journey_resets"] = int(metadata.get("journey_resets", 0) or 0) + 1
    metadata["energy"] = max_energy


def _pay(metadata: dict, max_energy: int, *, build: int, skill: int = 0) -> None:
    metadata["energy"] = max_energy
    metadata["build_points"] = int(metadata.get("build_points", 0) or 0) + build
    if skill:
        metadata["skill_points"] = int(metadata.get("skill_points", 0) or 0) + skill


def view(metadata: dict, now: datetime, max_energy: int) -> dict:
    """The current stage as the interface shows it."""
    stage = int(metadata.get("stage", 1) or 1)
    start = started_at(metadata, now)
    width = stage_days(stage)
    end = start + timedelta(days=width)
    done = int(metadata.get("journey_points", 0) or 0)
    points = []
    for i, day in enumerate(point_offsets(stage)):
        at = start + timedelta(days=day)
        points.append({"day": day, "at": at.isoformat(timespec="seconds"), "reached": i < done})
    upcoming = next((p for p in points if not p["reached"]), None)
    next_at = datetime.fromisoformat(upcoming["at"]) if upcoming else end
    return {
        "stage": stage,
        "stage_days": width,
        "started_at": start.isoformat(timespec="seconds"),
        "next_checkpoint_at": end.isoformat(timespec="seconds"),
        "seconds_left": max(0, int((end - now).total_seconds())),
        "points": points,
        "next_point_at": next_at.isoformat(timespec="seconds"),
        "seconds_to_next_point": max(0, int((next_at - now).total_seconds())),
        "energy": int(metadata.get("energy", 0) or 0),
        "max_energy": max_energy,
        "resets": int(metadata.get("journey_resets", 0) or 0),
        "checkpoint_skill_points": checkpoint_skill_points(stage),
        "build_points_per_day": BUILD_POINTS_PER_DAY,
    }
