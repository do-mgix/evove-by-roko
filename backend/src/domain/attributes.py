"""The attribute graph: marks, ranks and aggregation.

Every attribute is the same kind of thing. Any attribute can have weighted
children; one without children is a leaf, and leaves are the only place marks
are stored. A parent's total is the weighted mean of its children's totals,
rounded down, so `braço = ⌊antebraço·½ + braço·½⌋`.

Marks move an attribute through ranks A→Z: rank index i asks for `3 + i` marks
(A 0/3, B 0/4 … Z 0/28, 403 in all). A rank is a permanent checkpoint. The marks
above it are progress that later triggers may take away (`lose_progress`), never
the rank itself.

A node may have several parents (Força draws on peitoral, which also sits under
Tronco) but at most one *primary* parent. The primary chain defines its degree:
depth from the root, root = 1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property


WEIGHT_TOLERANCE = 1e-3
_EPS = 1e-9

RANK_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MAX_RANK = len(RANK_LETTERS) - 1


# ---------------------------------------------------------------- ranks

def rank_need(rank_index: int) -> int:
    """Marks rank `rank_index` asks for before the next one: A 3, B 4 … Z 28."""
    return 3 + rank_index


def rank_base(rank_index: int) -> int:
    """Marks spent on every rank below `rank_index`."""
    return sum(rank_need(i) for i in range(rank_index))


RANK_TOTAL = rank_base(MAX_RANK) + rank_need(MAX_RANK)


def apply_rank_ups(marks: float, rank_index: int) -> tuple[float, int]:
    """Spend marks on ranks while they cover the current one. Returns (marks left,
    rank index). At Z the progress stops at 28/28."""
    while rank_index < MAX_RANK and marks + _EPS >= rank_need(rank_index):
        marks -= rank_need(rank_index)
        rank_index += 1
    if rank_index == MAX_RANK:
        marks = min(marks, float(rank_need(MAX_RANK)))
    return max(0.0, marks), rank_index


def total_marks(marks: float, rank_index: int) -> float:
    return rank_base(rank_index) + marks


def split_total(total: float) -> tuple[float, int]:
    return apply_rank_ups(max(0.0, total), 0)


def rank_view(total: float) -> dict:
    """What the interface shows for any attribute holding `total` marks."""
    marks, rank_index = split_total(total)
    need = rank_need(rank_index)
    return {
        "rank": RANK_LETTERS[rank_index],
        "rank_index": rank_index,
        "marks": int(math.floor(marks + _EPS)),
        "need": need,
        "total_marks": int(math.floor(total + _EPS)),
        "max": rank_index == MAX_RANK and marks + _EPS >= need,
    }


# ---------------------------------------------------------------- losing marks

def apply_decay(value: float, last_updated: datetime, now: datetime,
                half_life_hours: float, floor: float = 0.0) -> float:
    """Half-life math. Nothing decays continuously any more; this stays for a
    time-based trigger (see `lose_progress`)."""
    if half_life_hours <= 0:
        return value
    dh = (now - last_updated).total_seconds() / 3600.0
    if dh <= 0:
        return value
    return max(floor, value * (0.5 ** (dh / half_life_hours)))


def lose_progress(marks: float, rule: dict, last_updated: datetime | None = None,
                  now: datetime | None = None, half_life_hours: float = 0.0) -> float:
    """Marks left above the rank checkpoint after a loss — the rank never moves.

    Nothing calls this yet. It is the hook for triggers still to be defined: the
    end of a journey stage, a soft reset, time passing. Rules:
      {"kind": "all"}                        every mark above the rank
      {"kind": "fraction", "fraction": 0.5}  a share of them
      {"kind": "half_life"}                  decay since `last_updated`, by the
                                             attribute's half-life
    """
    kind = rule.get("kind")
    if kind == "all":
        return 0.0
    if kind == "fraction":
        f = float(rule.get("fraction", 0))
        if not 0.0 <= f <= 1.0:
            raise ValueError("fraction must be between 0 and 1")
        return marks * (1.0 - f)
    if kind == "half_life":
        if last_updated is None or now is None:
            raise ValueError("half_life needs last_updated and now")
        return apply_decay(marks, last_updated, now, half_life_hours)
    raise ValueError(f"unknown loss rule {kind!r}")


# ---------------------------------------------------------------- graph

@dataclass(frozen=True)
class Node:
    id: int
    key: str
    name: str
    half_life_hours: float = 0.0
    shop_group: bool = False


@dataclass
class Tree:
    nodes_by_key: dict[str, Node]
    children: dict[str, list[tuple[str, float]]]       # parent -> [(child, weight)], every link
    primary_parent: dict[str, str] = field(default_factory=dict)
    parents: dict[str, list[tuple[str, float, bool]]] = field(default_factory=dict)

    def is_leaf(self, key: str) -> bool:
        return not self.children.get(key)

    @cached_property
    def nodes_by_id(self) -> dict[int, Node]:
        return {n.id: n for n in self.nodes_by_key.values()}

    @cached_property
    def leaves_by_key(self) -> dict[str, Node]:
        return {k: n for k, n in self.nodes_by_key.items() if self.is_leaf(k)}

    @cached_property
    def leaves_by_id(self) -> dict[int, Node]:
        return {n.id: n for n in self.leaves_by_key.values()}

    @cached_property
    def roots(self) -> list[str]:
        return [k for k in self.nodes_by_key if k not in self.primary_parent]

    def primary_chain(self, key: str) -> list[str]:
        """Root first, `key` last, following primary parents only."""
        out = [key]
        while out[-1] in self.primary_parent:
            out.append(self.primary_parent[out[-1]])
            if len(out) > len(self.nodes_by_key):
                raise ValueError(f"primary chain through {key} loops")
        return list(reversed(out))

    def degree(self, key: str) -> int:
        return len(self.primary_chain(key))

    def root_of(self, key: str) -> str:
        return self.primary_chain(key)[0]

    def descendants(self, key: str) -> set[str]:
        seen: set[str] = set()
        stack = [c for c, _ in self.children.get(key, [])]
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            stack.extend(c for c, _ in self.children.get(k, []))
        return seen


def node_total(node_key: str, leaf_totals: dict[str, float], tree: Tree,
               memo: dict[str, float] | None = None) -> float:
    """Total marks of a node: a leaf's own, or the weighted mean of its children's
    rounded down. Pass a shared `memo` when computing many nodes."""
    if memo is None:
        memo = {}
    return _total(node_key, leaf_totals, tree, memo, frozenset())


def _total(key, leaf_totals, tree, memo, path) -> float:
    if key in memo:
        return memo[key]
    if key not in tree.nodes_by_key:
        return 0.0
    kids = tree.children.get(key)
    if not kids:
        value = float(leaf_totals.get(key, 0.0))
    else:
        if key in path:
            raise ValueError(f"cycle through {key}")
        inner = path | {key}
        value = float(math.floor(sum(w * _total(c, leaf_totals, tree, memo, inner) for c, w in kids) + _EPS))
    memo[key] = value
    return value


# ---------------------------------------------------------------- action ids

def id_classes(tree: Tree, parent_key: str) -> tuple[str, str | None]:
    """(class1, class2) of an action registered under `parent_key`.

    With N the parent's degree: class1 is the ancestor at degree max(2, ceil(N/2)) —
    the root never enters an id — and class2 is the parent itself, or None when it
    already is the class1 (written as 00).
    """
    chain = tree.primary_chain(parent_key)
    n = len(chain)
    if n < 2:
        raise ValueError(f"an action cannot be registered under a root ({parent_key})")
    c1 = chain[max(2, math.ceil(n / 2)) - 1]
    return c1, (None if c1 == parent_key else parent_key)


# ---------------------------------------------------------------- registration rules

class RegistrationError(ValueError):
    """A child registration that would leave the graph inconsistent."""


def _check_weights(weights: list[float], what: str):
    if any(w <= 0 for w in weights):
        raise RegistrationError(f"{what}: every weight must be positive")
    total = sum(weights)
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise RegistrationError(f"{what}: weights sum to {total:.4f}, not 1")


def check_subdivide(tree: Tree, parent_key: str, children: list[tuple[str, str, float]]) -> None:
    """A leaf becomes a parent. Its children's weights must sum to 1."""
    _check_new_keys(tree, parent_key, children)
    if not tree.is_leaf(parent_key):
        raise RegistrationError(f"'{parent_key}' already has children; use add")
    _check_weights([w for _, _, w in children], parent_key)


def check_add(tree: Tree, parent_key: str, children: list[tuple[str, str, float]]) -> float:
    """More children for a node that already has some.

    The new weights must leave room (sum below 1): existing children are scaled by
    what is left, so the parent keeps its value. Returns that scale factor.
    """
    _check_new_keys(tree, parent_key, children)
    if tree.is_leaf(parent_key):
        raise RegistrationError(f"'{parent_key}' is a leaf; use subdivide")
    new = [w for _, _, w in children]
    if any(w <= 0 for w in new):
        raise RegistrationError("every weight must be positive")
    room = 1.0 - sum(new)
    if room <= WEIGHT_TOLERANCE:
        raise RegistrationError(f"new weights sum to {sum(new):.4f}; they must leave room for the existing children")
    return room


def check_reweight(tree: Tree, parent_key: str, weights: dict[str, float]) -> None:
    if parent_key not in tree.nodes_by_key:
        raise RegistrationError(f"unknown attribute '{parent_key}'")
    current = {c for c, _ in tree.children.get(parent_key, [])}
    if set(weights) != current:
        raise RegistrationError(f"give every child of '{parent_key}' a weight: {sorted(current)}")
    _check_weights(list(weights.values()), parent_key)


def _check_new_keys(tree: Tree, parent_key: str, children: list[tuple[str, str, float]]) -> None:
    if parent_key not in tree.nodes_by_key:
        raise RegistrationError(f"unknown parent '{parent_key}'")
    if not children:
        raise RegistrationError("no children given")
    keys = [k for k, _, _ in children]
    if len(set(keys)) != len(keys):
        raise RegistrationError("a child is listed twice")
    for k in keys:
        if k in tree.nodes_by_key:
            raise RegistrationError(f"'{k}' already exists")


def check_link(tree: Tree, parent_key: str, child_key: str, weight: float) -> None:
    for k in (parent_key, child_key):
        if k not in tree.nodes_by_key:
            raise RegistrationError(f"unknown attribute '{k}'")
    if parent_key == child_key:
        raise RegistrationError("an attribute cannot be its own child")
    if any(c == child_key for c, _ in tree.children.get(parent_key, [])):
        raise RegistrationError(f"'{child_key}' is already a child of '{parent_key}'")
    if parent_key in tree.descendants(child_key):
        raise RegistrationError(f"linking would make a cycle: '{parent_key}' is under '{child_key}'")
    if weight <= 0:
        raise RegistrationError("weight must be positive")
