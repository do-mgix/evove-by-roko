"""Loaders for the static game data shipped with the backend.

Skills tree and action packages live under `backend/data/`. Both web and
CLI hosts read them via these helpers.
"""
import json
import os
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data"


def _data_root() -> Path:
    override = os.environ.get("EVOVE_STATIC_DATA_DIR")
    return Path(override) if override else _DEFAULT_DIR


def load_skill_tree() -> dict:
    path = _data_root() / "skills.json"
    if not path.exists():
        return {"nodes": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"nodes": []}


def skill_nodes_by_id() -> dict:
    return {n["id"]: n for n in load_skill_tree().get("nodes", []) if n.get("id")}


def load_packages() -> list[dict]:
    pkg_dir = _data_root() / "packages"
    if not pkg_dir.is_dir():
        return []
    out = []
    for path in sorted(pkg_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            continue
    return out


def lookup_token_cost(action_name: str) -> int:
    if not action_name:
        return 0
    target = action_name.strip().upper()
    for pkg in load_packages():
        for a in pkg.get("actions", []) or []:
            if str(a.get("name", "")).strip().upper() == target:
                return int(a.get("token_cost", 0) or 0)
    return 0
