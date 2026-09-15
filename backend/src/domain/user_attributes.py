"""Patches and the attributes users create for them.

A patch specializes a catalog action: it runs on the base's engine (marks
window, tokens, default-graph contributions) and also trains attributes the
user created, each at the weight of its link. Those follow the engine's rules
with equal weights — only a leaf holds marks, a parent's total is the mean of
its children's rounded down, and ranks work the same way.

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


def patch_label(name) -> str:
    """The part of a patch's name after its base's: whitespace collapsed, upper case."""
    label = " ".join(str(name or "").split()).upper()
    if not label or len(label) > 48:
        raise PatchError("patch name must be 1-48 characters")
    return label


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


def link_weight(raw) -> float:
    """A patch link's weight: the share of the patch's marks its attribute receives."""
    try:
        weight = float(raw)
    except (TypeError, ValueError):
        raise PatchError("weight must be a number")
    if not 0 < weight <= 1:
        raise PatchError("weight must be above 0 and at most 1")
    return round(weight, 2)


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


def subtree(attr_id: int, kids: dict) -> set[int]:
    """The attribute and everything under it."""
    seen: set[int] = set()
    stack = [attr_id]
    while stack:
        a = stack.pop()
        if a not in seen:
            seen.add(a)
            stack.extend(c["id"] for c in kids.get(a) or [])
    return seen


def reached_leaves(links: dict[int, float], kids: dict) -> dict[int, float]:
    """{leaf_id: weight} for every leaf under the linked attributes, each once, at
    the weight of the heaviest link that reaches it. An attribute that is a leaf
    reaches itself; a patch on Ciências at 50% and on Física at 100% reaches Física
    once, at 100%."""
    out: dict[int, float] = {}
    for attr_id, weight in links.items():
        for a in subtree(attr_id, kids):
            if not kids.get(a):
                out[a] = max(out.get(a, 0.0), float(weight))
    return dict(sorted(out.items()))


def stimulate(attr: dict, amount: float) -> tuple[float, int] | None:
    """(marks, rank_index) of a leaf after an act, or None when it brought nothing.
    A leaf receives the act's marks times the weight of its link; fractions
    accumulate, as in the default graph."""
    if amount <= 0:
        return None
    return apply_rank_ups(float(attr["marks"]) + amount, int(attr["rank_index"]))


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


def check_move(attr_id: int, parent_id: int | None, by_id: dict, kids: dict) -> None:
    """Refuse a move that would close a loop or hide marks: a leaf holding marks
    takes no children, since its own marks would vanish behind their mean."""
    if attr_id not in by_id:
        raise PatchError(f"attribute {attr_id} not found", 404)
    if parent_id is None:
        return
    if parent_id not in by_id:
        raise PatchError(f"attribute {parent_id} not found", 404)
    if parent_id in subtree(attr_id, kids):
        raise PatchError("an attribute cannot move under itself or its own children")
    parent = by_id[parent_id]
    if not kids.get(parent_id) and (float(parent["marks"]) > 0 or int(parent["rank_index"]) > 0):
        raise PatchError(f"'{parent['name']}' holds marks of its own and takes no children", 409)


def left_behind(attr_id: int, by_id: dict, kids: dict) -> tuple[float, int] | None:
    """(marks, rank_index) the parent of `attr_id` keeps when the attribute leaves.
    When it was the only child the parent becomes a leaf again at the total it has
    now, so it does not drop; with other children left, None — their mean moves."""
    parent_id = by_id[attr_id]["parent_id"]
    if parent_id is None or len(kids.get(parent_id) or []) != 1:
        return None
    return split_total(total(parent_id, by_id, kids))


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
