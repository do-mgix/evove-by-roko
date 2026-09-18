"""Static metadata that is not user data and not the attribute graph.

Action metadata (unit, difficulty, prices) comes from `repos.load_action_templates`.
What is left lives here: the skill tree, small enough to be a literal below, and
the attribute suggestion catalog, read from backend/data/attribute_suggestions.json
because it is a few hundred lines of hand-curated text.

The catalog is **not** a seed: no migration reads it and nothing it contains
reaches `attr_nodes`. It is a list of names the interface offers when the user
creates their own attributes, and only the text is copied — renaming a label here
later renames nobody's attribute.
"""
import json
from pathlib import Path

_SUGGESTIONS_FILE = Path(__file__).resolve().parents[2] / "data" / "attribute_suggestions.json"
_SUGGESTIONS: dict | None = None

_SKILL_TREE = {
    "nodes": [
        {"id": "root", "label": "Skills", "x": 0, "y": 0, "cost": 0, "parent": None, "effect": None},
        {"id": "energy_1", "label": "Energy I", "x": 320, "y": 0, "cost": 1, "parent": "root", "effect": {"type": "max_energy", "value": 100}},
        {"id": "energy_2", "label": "Energy II", "x": 640, "y": 0, "cost": 1, "parent": "energy_1", "effect": {"type": "max_energy", "value": 100}},
        {"id": "energy_3", "label": "Energy III", "x": 960, "y": 0, "cost": 1, "parent": "energy_2", "effect": {"type": "max_energy", "value": 100}},
        {"id": "energy_4", "label": "Energy IV", "x": 1280, "y": 0, "cost": 1, "parent": "energy_3", "effect": {"type": "max_energy", "value": 100}},
        {"id": "energy_5", "label": "Energy V", "x": 1600, "y": 0, "cost": 1, "parent": "energy_4", "effect": {"type": "max_energy", "value": 100}},
        {"id": "tokens_1", "label": "Tokens I", "x": 0, "y": -320, "cost": 1, "parent": "root", "effect": {"type": "max_tokens", "value": 5}},
        {"id": "tokens_2", "label": "Tokens II", "x": 0, "y": -640, "cost": 1, "parent": "tokens_1", "effect": {"type": "max_tokens", "value": 5}},
        {"id": "tokens_3", "label": "Tokens III", "x": 0, "y": -960, "cost": 1, "parent": "tokens_2", "effect": {"type": "max_tokens", "value": 5}},
        {"id": "tokens_4", "label": "Tokens IV", "x": 0, "y": -1280, "cost": 1, "parent": "tokens_3", "effect": {"type": "max_tokens", "value": 5}},
        {"id": "tokens_5", "label": "Tokens V", "x": 0, "y": -1600, "cost": 1, "parent": "tokens_4", "effect": {"type": "max_tokens", "value": 5}},
        {"id": "xp_1", "label": "XP I", "x": -320, "y": 0, "cost": 1, "parent": "root", "effect": {"type": "xp_multiplier", "value": 1.25}},
        {"id": "xp_2", "label": "XP II", "x": -640, "y": 0, "cost": 1, "parent": "xp_1", "effect": {"type": "xp_multiplier", "value": 1.25}},
        {"id": "xp_3", "label": "XP III", "x": -960, "y": 0, "cost": 1, "parent": "xp_2", "effect": {"type": "xp_multiplier", "value": 1.25}},
        {"id": "xp_4", "label": "XP IV", "x": -1280, "y": 0, "cost": 1, "parent": "xp_3", "effect": {"type": "xp_multiplier", "value": 1.25}},
        {"id": "xp_5", "label": "XP V", "x": -1600, "y": 0, "cost": 1, "parent": "xp_4", "effect": {"type": "xp_multiplier", "value": 1.25}},
        {"id": "points_1", "label": "Points I", "x": 0, "y": 320, "cost": 1, "parent": "root", "effect": {"type": "points_multiplier", "value": 1.25}},
        {"id": "points_2", "label": "Points II", "x": 0, "y": 640, "cost": 1, "parent": "points_1", "effect": {"type": "points_multiplier", "value": 1.25}},
        {"id": "points_3", "label": "Points III", "x": 0, "y": 960, "cost": 1, "parent": "points_2", "effect": {"type": "points_multiplier", "value": 1.25}},
        {"id": "points_4", "label": "Points IV", "x": 0, "y": 1280, "cost": 1, "parent": "points_3", "effect": {"type": "points_multiplier", "value": 1.25}},
        {"id": "points_5", "label": "Points V", "x": 0, "y": 1600, "cost": 1, "parent": "points_4", "effect": {"type": "points_multiplier", "value": 1.25}},
    ]
}


def load_skill_tree() -> dict:
    return _SKILL_TREE


def skill_nodes_by_id() -> dict:
    return {n["id"]: n for n in _SKILL_TREE["nodes"] if n.get("id")}



def load_attribute_suggestions() -> dict:
    """The suggestion catalog, validated once and cached.

    The checks are the ones that would otherwise fail much later, as a 400 when
    someone picks the offending entry: a label the user attribute column cannot
    hold (1-64 characters), a duplicate key, a parent outside its own catalog.
    """
    global _SUGGESTIONS
    if _SUGGESTIONS is None:
        with _SUGGESTIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for catalog in data.get("catalogs", []):
            keys = set()
            for node in catalog.get("nodes", []):
                label = " ".join(str(node.get("label", "")).split())
                if not 1 <= len(label) <= 64:
                    raise ValueError(f"{node.get('key')}: label must be 1-64 characters")
                if node["key"] in keys:
                    raise ValueError(f"duplicate suggestion key {node['key']}")
                keys.add(node["key"])
            for node in catalog.get("nodes", []):
                if node.get("parent") and node["parent"] not in keys:
                    raise ValueError(f"{node['key']}: parent {node['parent']} is not in the catalog")
        _SUGGESTIONS = data
    return _SUGGESTIONS
