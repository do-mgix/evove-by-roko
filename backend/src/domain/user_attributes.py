"""Patches and the attributes users create for them.

A patch specializes a catalog action: it runs on the base's engine (xp, tokens,
default-graph contributions) and also trains attributes the user created. Those
attributes follow the engine's rules with equal weights — only a leaf (an
attribute without children) holds a score, and a parent is worth the mean of
its children.

Pure functions over plain dicts; the repository loads and writes. An attribute
here is {"id", "parent_id", "name", "score", "permanent_level", "last_updated_at"}.
"""
from __future__ import annotations

from datetime import datetime

from src.domain.attributes import (
    CUSTOM_FLOOR,
    CUSTOM_HALF_LIFE_HOURS,
    CUSTOM_MAX_LEVEL,
    CUSTOM_THRESHOLD,
    apply_decay,
    apply_level_ups,
    level_threshold,
)


MAX_PATCHES = 99
PATCH_SEPARATOR = " · "


class PatchError(ValueError):
    """A patch or attribute request that cannot be honored. `status` is the HTTP
    status the API answers with."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- patches

def patch_name(base_name: str, label: str) -> str:
    """Stored name of a patch: `ESTUDO · FÍSICA`. Logs stay readable and sorting by
    name keeps the patch next to its base."""
    return f"{base_name}{PATCH_SEPARATOR}{label}"


def engine_name(actions: dict, action: dict) -> str:
    """Name of the catalog action an act runs on: the base's for a patch.

    Contributions to the default graph and agenda matching are looked up by this
    name, so a patch moves exactly what its base would."""
    base_id = action.get("base_action_id")
    if base_id:
        base = actions.get(base_id)
        if base:
            return base.get("name", "")
        return str(action.get("name", "")).split(PATCH_SEPARATOR)[0]
    return action.get("name", "")


# ---------------------------------------------------------------- attribute tree

def children_of(attrs: list[dict]) -> dict[int | None, list[dict]]:
    """{parent_id: [child, ...]}, roots under None, children by name."""
    out: dict[int | None, list[dict]] = {}
    for a in attrs:
        out.setdefault(a["parent_id"], []).append(a)
    for kids in out.values():
        kids.sort(key=lambda a: a["name"].casefold())
    return out


def decayed_score(attr: dict, now: datetime) -> float:
    return apply_decay(float(attr["score"]), attr["last_updated_at"], now,
                       CUSTOM_HALF_LIFE_HOURS, CUSTOM_FLOOR)


def power(attr_id: int, by_id: dict, kids: dict, now: datetime, memo: dict | None = None) -> float:
    """A leaf's decayed score, or the mean of its children's power."""
    memo = {} if memo is None else memo
    if attr_id in memo:
        return memo[attr_id]
    children = kids.get(attr_id) or []
    if not children:
        value = decayed_score(by_id[attr_id], now)
    else:
        value = sum(power(c["id"], by_id, kids, now, memo) for c in children) / len(children)
    memo[attr_id] = value
    return value


def weighted_leaves(attr_id: int, kids: dict) -> list[tuple[int, float]]:
    """Leaves under an attribute with their share of it (1/n at each level)."""
    children = kids.get(attr_id) or []
    if not children:
        return [(attr_id, 1.0)]
    out = []
    for c in children:
        out.extend((leaf, w / len(children)) for leaf, w in weighted_leaves(c["id"], kids))
    return out


def reached_leaves(attr_ids: list[int], kids: dict) -> list[int]:
    """Every leaf under the given attributes, each once. An attribute that is a
    leaf reaches itself; a patch on Ciências and on Física reaches Física once."""
    seen: set[int] = set()
    leaves: list[int] = []
    stack = list(attr_ids)
    while stack:
        a = stack.pop()
        if a in seen:
            continue
        seen.add(a)
        children = kids.get(a) or []
        if children:
            stack.extend(c["id"] for c in children)
        else:
            leaves.append(a)
    return sorted(leaves)


def stimulate(attr: dict, stimulus: float, now: datetime) -> tuple[float, int] | None:
    """(score, permanent_level) of a leaf after one act, or None under threshold.
    Every leaf a patch reaches receives the whole stimulus."""
    if stimulus < CUSTOM_THRESHOLD:
        return None
    score = decayed_score(attr, now) + stimulus
    return apply_level_ups(score, int(attr["permanent_level"] or 0), CUSTOM_MAX_LEVEL)


def new_child_start(parent: dict, by_id: dict, kids: dict, now: datetime) -> tuple[dict, bool]:
    """What a new child of `parent` starts with, so the parent's value does not
    move at that moment. Returns (fields, inherits).

    The first child of a leaf inherits the leaf whole — score, level and timestamp —
    and the caller clears the parent, which becomes computed. A child of a parent
    that already has children starts at the parent's current power, which leaves
    the mean where it was."""
    if not kids.get(parent["id"]):
        return ({"score": float(parent["score"]),
                 "permanent_level": int(parent["permanent_level"] or 0),
                 "last_updated_at": parent["last_updated_at"]}, True)
    return ({"score": power(parent["id"], by_id, kids, now),
             "permanent_level": 0,
             "last_updated_at": now}, False)


def view(attr_id: int, by_id: dict, kids: dict, now: datetime, memo: dict) -> dict:
    """An attribute and everything under it, with power and level. A parent's level
    is the weighted mean of its leaves' levels."""
    level = progress = 0.0
    for leaf_id, w in weighted_leaves(attr_id, kids):
        leaf = by_id[leaf_id]
        perm = int(leaf["permanent_level"] or 0)
        level += w * perm
        if perm >= CUSTOM_MAX_LEVEL:
            progress += w
        else:
            progress += w * max(0.0, min(1.0, decayed_score(leaf, now) / level_threshold(perm + 1)))
    attr = by_id[attr_id]
    children = kids.get(attr_id) or []
    return {
        "id": attr_id,
        "name": attr["name"],
        "parent_id": attr["parent_id"],
        "is_leaf": not children,
        "power": round(power(attr_id, by_id, kids, now, memo), 2),
        "level": round(level, 2),
        "max_level": CUSTOM_MAX_LEVEL,
        "progress_to_next": round(progress, 4),
        "children": [view(c["id"], by_id, kids, now, memo) for c in children],
    }
