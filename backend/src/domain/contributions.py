"""Apply action stimulus to leaves with lazy decay + threshold."""
from __future__ import annotations

from datetime import datetime

from src.domain.attributes import apply_decay
from src.infrastructure import repos


def apply_action_contributions(username: str, action_name: str, score_diff: float, now: datetime) -> int:
    """For each leaf contribution of `action_name`, apply lazy decay then add weighted stimulus.

    Returns number of leaves stimulated (above threshold).
    """
    contribs = repos.load_action_contributions(action_name)
    if not contribs:
        return 0

    tree = repos.load_attr_tree()
    current = repos.get_user_leaf_scores(username)
    touched = 0
    for leaf_id, leaf_key, weight in contribs:
        leaf = tree.leaves_by_key.get(leaf_key)
        if leaf is None:
            continue
        stimulus = float(score_diff) * float(weight)
        if stimulus < leaf.threshold:
            continue
        cur = current.get(leaf_key)
        if cur is None:
            base_score = leaf.floor
            last = now
        else:
            base_score = apply_decay(
                cur["score"], cur["last_updated_at"], now,
                leaf.half_life_hours, leaf.floor,
            )
            last = now
        new_score = base_score + stimulus
        repos.upsert_user_leaf_score(username, leaf_id, new_score, last)
        touched += 1
    return touched
