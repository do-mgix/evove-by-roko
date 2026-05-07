"""Skill tree rules and bonus aggregation."""


def aggregate_bonuses(acquired_ids, nodes_by_id):
    """Aggregate effects from a set of acquired skill ids.

    `nodes_by_id`: dict of skill_id -> node dict (with optional `effect`).
    Returns: {max_energy, max_tokens, xp_multiplier, points_multiplier}.
    """
    bonuses = {
        "max_energy": 0,
        "max_tokens": 0,
        "xp_multiplier": 1.0,
        "points_multiplier": 1.0,
    }
    if not acquired_ids:
        return bonuses
    for sid in acquired_ids:
        node = nodes_by_id.get(sid)
        if not node:
            continue
        effect = node.get("effect")
        if not effect:
            continue
        t = effect.get("type")
        v = effect.get("value", 0)
        if t == "max_energy":
            bonuses["max_energy"] += v
        elif t == "max_tokens":
            bonuses["max_tokens"] += v
        elif t == "xp_multiplier":
            bonuses["xp_multiplier"] *= v
        elif t == "points_multiplier":
            bonuses["points_multiplier"] *= v
    return bonuses


class SkillError(Exception):
    """Raised when a skill operation fails (invalid id, missing parent, no SP)."""


def acquire_skill(data: dict, skill_id: str, nodes_by_id: dict) -> dict:
    """Mutates `data`: validates parent + cost, marks acquired, deducts SP.

    Returns dict with `acquired` (sorted list), `skill_points`, `bonuses`.
    Raises SkillError on validation failure.
    """
    node = nodes_by_id.get(skill_id)
    if not node:
        raise SkillError(f"skill '{skill_id}' not found")
    acquired = set(data.get("skills") or [])
    if skill_id in acquired:
        raise SkillError("already acquired")
    parent = node.get("parent")
    if parent and parent not in acquired and parent != "root":
        raise SkillError(f"requires parent '{parent}'")
    metadata = data.setdefault("metadata", {})
    sp = int(metadata.get("skill_points", 0) or 0)
    cost = int(node.get("cost", 0))
    if sp < cost:
        raise SkillError(f"need {cost} sp (have {sp})")
    acquired.add(skill_id)
    data["skills"] = sorted(acquired)
    metadata["skill_points"] = sp - cost
    return {
        "acquired": data["skills"],
        "skill_points": metadata["skill_points"],
        "bonuses": aggregate_bonuses(acquired, nodes_by_id),
    }
