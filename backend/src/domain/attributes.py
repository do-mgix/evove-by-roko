"""The attribute graph: decay, levels and aggregated power.

Every attribute is the same kind of thing. Any attribute can have weighted
children; one without children is a leaf, and leaves are the only place a
score is stored. Everything else is computed: a parent's power is the weighted
mean of its children's, so `braço = antebraço·½ + braço·½`.

A node may have several parents (Força draws on peitoral, which also sits under
Tronco) but at most one *primary* parent. The primary chain defines its degree:
depth from the root, root = 1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property


LEVEL_BASE = 100
LEVELED_SHARE = 0.8   # a node shows a level when leveled leaves carry this much of its weight
WEIGHT_TOLERANCE = 1e-3


def level_threshold(next_level: int) -> float:
    """Superficial score required to advance from (next_level - 1) into next_level."""
    return LEVEL_BASE * next_level * next_level


def apply_level_ups(score: float, permanent_level: int, max_level: int) -> tuple[float, int]:
    """Consume superficial score into permanent levels until insufficient or capped.

    Returns (remaining_score, new_permanent_level). Multiple level-ups possible in one call.
    """
    while permanent_level < max_level and score >= level_threshold(permanent_level + 1):
        score -= level_threshold(permanent_level + 1)
        permanent_level += 1
    return score, permanent_level


def apply_decay(score: float, last_updated: datetime, now: datetime,
                half_life_hours: float, floor: float) -> float:
    if half_life_hours <= 0:
        return score
    dh = (now - last_updated).total_seconds() / 3600.0
    if dh <= 0:
        return score
    decayed = score * (0.5 ** (dh / half_life_hours))
    return max(floor, decayed)


# ---------------------------------------------------------------- graph

@dataclass(frozen=True)
class Node:
    id: int
    key: str
    name: str
    half_life_hours: float = 0.0
    floor: float = 0.0
    threshold: float = 0.0
    max_level: int | None = None
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


def compute_node_score(node_key: str, leaf_scores: dict[str, float], tree: Tree,
                       memo: dict[str, float] | None = None) -> float:
    """Power of a node: its own score if it is a leaf, else the weighted mean of its
    children. Pass a shared `memo` when computing many nodes — shared subtrees are
    then evaluated once."""
    if memo is None:
        memo = {}
    return _score(node_key, leaf_scores, tree, memo, frozenset())


def _score(key, leaf_scores, tree, memo, path) -> float:
    if key in memo:
        return memo[key]
    node = tree.nodes_by_key.get(key)
    if node is None:
        return 0.0
    kids = tree.children.get(key)
    if not kids:
        value = leaf_scores.get(key, node.floor)
    else:
        if key in path:
            raise ValueError(f"cycle through {key}")
        inner = path | {key}
        value = sum(w * _score(c, leaf_scores, tree, memo, inner) for c, w in kids)
    memo[key] = value
    return value


def weighted_leaves(tree: Tree, key: str) -> list[tuple[str, float]]:
    """Every leaf under `key` with its effective weight — the product of the link
    weights along the way, summed over every path that reaches it."""
    acc: dict[str, float] = {}

    def walk(k: str, w: float, path: frozenset):
        if tree.is_leaf(k):
            acc[k] = acc.get(k, 0.0) + w
            return
        if k in path:
            raise ValueError(f"cycle through {k}")
        for c, cw in tree.children.get(k, []):
            walk(c, w * cw, path | {k})

    walk(key, 1.0, frozenset())
    return list(acc.items())


def aggregate_level(tree: Tree, key: str, leaf_scores: dict[str, float],
                    leaf_perm: dict[str, int]) -> dict | None:
    """Level of any node: the weighted mean of its leveled leaves' levels.

    A leaf with no `max_level` has no level at all. An internal node shows one only
    when leveled leaves carry at least LEVELED_SHARE of its weight; otherwise None.
    """
    total = leveled = lvl = prog = 0.0
    max_lvl = 0
    for lk, w in weighted_leaves(tree, key):
        total += w
        leaf = tree.nodes_by_key[lk]
        if leaf.max_level is None:
            continue
        leveled += w
        perm = leaf_perm.get(lk, 0)
        lvl += w * perm
        if perm >= leaf.max_level:
            prog += w
        else:
            prog += w * max(0.0, min(1.0, leaf_scores.get(lk, 0.0) / level_threshold(perm + 1)))
        max_lvl = max(max_lvl, leaf.max_level)
    if total <= 0 or leveled / total < LEVELED_SHARE:
        return None
    return {"level": lvl / leveled, "max_level": max_lvl, "progress_to_next": prog / leveled}


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
