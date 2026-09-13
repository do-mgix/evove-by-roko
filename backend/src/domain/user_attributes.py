"""Patches and the attributes users create for them.

A patch specializes a catalog action: it runs on the base's engine (marks
window, tokens, default-graph contributions) and also trains attributes the
user created. Those follow the engine's rules with equal weights — only a leaf
holds marks, a parent's total is the mean of its children's rounded down, and
ranks work the same way.

Pure functions over plain dicts; the repository loads and writes. An attribute
here is {"id", "parent_id", "name", "marks", "rank_index"}.
"""
from __future__ import annotations

import math

from src.domain.attributes import apply_rank_ups, rank_view, split_total, total_marks


MAX_PATCHES = 99
PATCH_SEPARATOR = " · "

# User attributes have no half-life column. A time-based loss trigger would use this.
CUSTOM_HALF_LIFE_HOURS = 2160.0


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

    Tiers, contributions to the default graph and agenda matching are looked up by
    this name, so a patch moves exactly what its base would."""
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


def total(attr_id: int, by_id: dict, kids: dict, memo: dict | None = None) -> float:
    """A leaf's marks over its rank, or the mean of its children's totals rounded down."""
    memo = {} if memo is None else memo
    if attr_id in memo:
        return memo[attr_id]
    children = kids.get(attr_id) or []
    if not children:
        attr = by_id[attr_id]
        value = total_marks(float(attr["marks"]), int(attr["rank_index"]))
    else:
        mean = sum(total(c["id"], by_id, kids, memo) for c in children) / len(children)
        value = float(math.floor(mean + 1e-9))
    memo[attr_id] = value
    return value


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


def stimulate(attr: dict, marks: int) -> tuple[float, int] | None:
    """(marks, rank_index) of a leaf after an act, or None when the act yielded no
    marks. Every leaf a patch reaches receives all of the act's marks."""
    if marks <= 0:
        return None
    return apply_rank_ups(float(attr["marks"]) + marks, int(attr["rank_index"]))


def new_child_start(parent: dict, by_id: dict, kids: dict) -> tuple[dict, bool]:
    """What a new child of `parent` starts with, so the parent's total does not
    move at that moment. Returns (fields, inherits).

    The first child of a leaf inherits its marks and rank, and the caller clears the
    parent, which becomes computed. A child of a parent that already has children
    starts at the parent's current total, which leaves the mean where it was."""
    if not kids.get(parent["id"]):
        return ({"marks": float(parent["marks"]), "rank_index": int(parent["rank_index"])}, True)
    marks, rank_index = split_total(total(parent["id"], by_id, kids))
    return ({"marks": marks, "rank_index": rank_index}, False)


def view(attr_id: int, by_id: dict, kids: dict, memo: dict) -> dict:
    """An attribute and everything under it, with its rank and marks."""
    attr = by_id[attr_id]
    children = kids.get(attr_id) or []
    return {
        "id": attr_id,
        "name": attr["name"],
        "parent_id": attr["parent_id"],
        "is_leaf": not children,
        **rank_view(total(attr_id, by_id, kids, memo)),
        "children": [view(c["id"], by_id, kids, memo) for c in children],
    }
