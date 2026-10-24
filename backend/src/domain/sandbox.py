"""The sandbox: the evove with nothing at stake.

Once the story is told (src.domain.engine) the first screen opens a second
mode beside the evove. In it every action of the catalog is there, bought or
not, and acting is free: no tokens, no hp, no window of marks — each act pays
the marks of its tier, as many times as wanted. Its marks reach the
attributes as a real act's would, through the same contributions, but into the
sandbox's own tree of scores: the real one, which mirrors what the person
does, is never touched, and neither are the logs.

It also opens every entity the profile has met, to be talked to at will, and
one of its own, coleto, who serves, and is thrilled about everything.

Kept inside the profile's evove state (`state["sandbox"]`). Pure logic — no I/O.
"""
from __future__ import annotations

import random

from src.domain import engine
from src.domain.attributes import apply_rank_ups, total_marks
from src.domain.marks import TIER_COUNT, MarkError


def state_of(evove: dict) -> dict:
    """The sandbox inside a profile's evove, made on first use."""
    sb = evove.get("sandbox")
    if not isinstance(sb, dict):
        sb = evove["sandbox"] = {}
    sb.setdefault("acts", 0)
    sb.setdefault("actions", {})
    sb.setdefault("leaves", {})
    sb.setdefault("talks", 0)
    sb.setdefault("opens", {})
    sb.setdefault("seed", random.Random().randrange(1 << 30))
    return sb


def totals(sb: dict) -> dict[str, float]:
    """Every leaf's total marks in the sandbox."""
    return {k: total_marks(float(m), int(r)) for k, (m, r) in (sb.get("leaves") or {}).items()}


def act(sb: dict, name: str, option, contributions: list[tuple[str, float]], leaves: set[str]) -> dict:
    """An act on `name` at tier `option`: its marks — the tier's, whole — go to
    every leaf it feeds, times the weight. Returns the marks and, by leaf, the
    total before and after."""
    try:
        option = int(option)
    except (TypeError, ValueError):
        raise MarkError("choose a tier from 0 to 5")
    if not 0 <= option < TIER_COUNT:
        raise MarkError("choose a tier from 0 to 5")
    marks = option
    a = sb["actions"].setdefault(name, {"value": 0, "score": 0})
    a["value"] += 1
    a["score"] += marks
    sb["acts"] += 1
    gains: dict[str, tuple[float, float]] = {}
    for key, weight in contributions:
        if key not in leaves or marks <= 0:
            continue
        m, r = sb["leaves"].get(key, (0.0, 0))
        before = total_marks(float(m), int(r))
        m, r = apply_rank_ups(float(m) + marks * float(weight), int(r))
        sb["leaves"][key] = [round(m, 4), r]
        gains[key] = (before, total_marks(m, r))
    return {"marks": marks, "gains": gains}


def view(evove: dict, sb: dict) -> dict:
    """The sandbox's home: its modules tiled like the evove's, a layout of its
    own, kept per sandbox."""
    mods = list(engine.SANDBOX_MODULES)
    shapes = engine.layout(mods, sb.get("opens") or {}, int(sb["seed"]), engine.SANDBOX_MODULES)
    rng = random.Random(int(sb["seed"]) + 1)
    tiles = []
    for m in mods:
        d = engine.SANDBOX_MODULES[m]
        tiles.append({"id": m, "kind": d["kind"], "label": d["label"], "color": d["color"], "glyph": d["glyph"],
                      "tone": d["tone"], "polygon": shapes[m], "delay": rng.randrange(0, 360), "fresh": False, "code": None})
    return {
        "tiles": tiles,
        "acts": sb["acts"],
        "actions": len(sb["actions"]),
        "talks": sb["talks"],
        "entities": [e for e in evove.get("entities") or []],
    }


def open_module(sb: dict, module: str) -> None:
    if module in engine.SANDBOX_MODULES:
        sb["opens"][module] = int(sb["opens"].get(module, 0) or 0) + 1


def renew(sb: dict, rng: random.Random) -> None:
    """A new session: a new layout."""
    sb["seed"] = rng.randrange(1 << 30)
