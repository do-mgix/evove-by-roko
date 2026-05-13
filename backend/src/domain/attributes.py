"""Decay + tree score computation for hierarchical attribute nodes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LeafMeta:
    id: int
    key: str
    name: str
    half_life_hours: float
    floor: float
    threshold: float


@dataclass(frozen=True)
class NodeMeta:
    id: int
    key: str
    name: str
    is_leaf: bool


@dataclass
class Tree:
    nodes_by_key: dict[str, NodeMeta]
    leaves_by_key: dict[str, LeafMeta]
    leaves_by_id: dict[int, LeafMeta]
    children: dict[str, list[tuple[str, float]]]  # parent_key -> [(child_key, weight)]
    roots: list[str]


def apply_decay(score: float, last_updated: datetime, now: datetime,
                half_life_hours: float, floor: float) -> float:
    if half_life_hours <= 0:
        return score
    dh = (now - last_updated).total_seconds() / 3600.0
    if dh <= 0:
        return score
    decayed = score * (0.5 ** (dh / half_life_hours))
    return max(floor, decayed)


def compute_node_score(node_key: str, leaf_scores: dict[str, float], tree: Tree) -> float:
    node = tree.nodes_by_key.get(node_key)
    if node is None:
        return 0.0
    if node.is_leaf:
        leaf = tree.leaves_by_key.get(node_key)
        baseline = leaf.floor if leaf else 0.0
        return leaf_scores.get(node_key, baseline)
    total = 0.0
    for child_key, weight in tree.children.get(node_key, []):
        total += weight * compute_node_score(child_key, leaf_scores, tree)
    return total
