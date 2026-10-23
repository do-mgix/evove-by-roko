"""Marks reaching attributes after an act."""
from __future__ import annotations

from datetime import datetime

from src.domain.attributes import apply_rank_ups
from src.infrastructure import repos


def apply_action_contributions(username: str, action_name: str, marks: int, now: datetime) -> dict[int, float]:
    """Each leaf `action_name` feeds receives marks × weight. Fractions accumulate;
    the interface shows whole marks. Returns what each leaf received, by leaf id —
    what deleting the act's log takes back."""
    if marks <= 0:
        return {}
    contribs = repos.load_action_contributions(action_name)
    if not contribs:
        return {}
    tree = repos.load_attr_tree()
    current = repos.get_user_leaf_scores(username)
    gains: dict[int, float] = {}
    for leaf_id, leaf_key, weight in contribs:
        if leaf_key not in tree.leaves_by_key:
            continue
        cur = current.get(leaf_key) or {"marks": 0.0, "rank_index": 0}
        new_marks, rank_index = apply_rank_ups(float(cur["marks"]) + marks * float(weight), int(cur["rank_index"]))
        repos.upsert_user_leaf_score(username, leaf_id, new_marks, now, rank_index)
        gains[int(leaf_id)] = marks * float(weight)
    return gains


def apply_patch_attributes(username: str, patch_action_id: str, marks: int, now: datetime) -> dict[int, float]:
    """Train a patch's own attributes: every leaf reached from them receives the
    act's marks times the weight of its link, once — through the heaviest link when
    several reach it. Returns what each leaf received, by user attribute id."""
    from src.domain.user_attributes import children_of, reached_leaves, stimulate

    if marks <= 0:
        return {}
    links = repos.load_patch_links(username).get(patch_action_id)
    if not links:
        return {}
    attrs = repos.load_user_attributes(username)
    by_id = {a["id"]: a for a in attrs}
    kids = children_of(attrs)
    updates: dict[int, tuple[float, int]] = {}
    gains: dict[int, float] = {}
    reached = reached_leaves({a: w for a, w in links.items() if a in by_id}, kids)
    for leaf_id, weight in reached.items():
        result = stimulate(by_id[leaf_id], marks * weight)
        if result is not None:
            updates[leaf_id] = result
            gains[int(leaf_id)] = marks * weight
    if updates:
        repos.save_user_attribute_scores(username, updates, now)
    return gains
