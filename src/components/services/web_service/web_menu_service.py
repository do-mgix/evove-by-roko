import json
import os
from pathlib import Path

from src.components.data.constants import user, MODES
from src.components.user.actions.action import Action
from src.components.user.attributes.attribute import Attribute


def _packages_dir():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "data", "packages")


def _load_templates():
    templates = {}
    packages_dir = Path(_packages_dir())
    if not packages_dir.exists():
        return templates
    for file in packages_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                templates[file.stem] = json.load(f)
        except Exception:
            continue
    return templates


def _template_owned(template):
    attrs = template.get("attributes", {})
    root_names = [
        attr["name"]
        for attr in attrs.values()
        if not attr.get("parent") or len(attr.get("parent", [])) == 0
    ]
    user_attr_names = [attr._name for attr in user._attributes.values()]
    return all(name in user_attr_names for name in root_names)


def get_settings():
    return {
        "virtual_agent_active": user.metadata.get("virtual_agent_active", True),
        "mode": user.metadata.get("mode", "progressive"),
        "modes": list(MODES.values()),
    }


def toggle_agent():
    current = user.metadata.get("virtual_agent_active", True)
    user.metadata["virtual_agent_active"] = not current
    user.add_message(f"Agent {'enabled' if not current else 'disabled'}.")
    user.save_user()
    return get_settings()


def cycle_mode():
    modes = list(MODES.values())
    current = user.metadata.get("mode", modes[0])
    try:
        idx = modes.index(current)
    except ValueError:
        idx = 0
    new_mode = modes[(idx + 1) % len(modes)]
    user.metadata["mode"] = new_mode
    user.add_message(f"Mode changed to {new_mode.upper()}.")
    user.save_user()
    return get_settings()


def list_packages():
    templates = _load_templates()
    results = []
    for key, data in templates.items():
        results.append({
            "key": key,
            "name": data.get("name", key),
            "owned": _template_owned(data),
        })
    return results


def import_package(key):
    templates = _load_templates()
    template = templates.get(key)
    if not template:
        return {"ok": False, "error": "Template not found."}

    attributes = template.get("attributes", {})
    actions = template.get("actions", {})

    attr_id_map = {}
    action_id_map = {}

    for old_action_id, action_data in actions.items():
        new_action_id = _get_next_action_id()
        action_id_map[old_action_id] = new_action_id
        new_action = Action(
            action_id=new_action_id,
            name=action_data["name"],
            tipo=action_data["type"],
            diff=action_data["diff"],
            value=action_data.get("value", 0),
        )
        user._actions[new_action_id] = new_action

    for old_attr_id, attr_data in attributes.items():
        new_attr_id = _get_next_attr_id()
        attr_id_map[old_attr_id] = new_attr_id
        new_attr = Attribute(new_attr_id, attr_data["name"], None, None, None)
        user._attributes[new_attr_id] = new_attr

    for old_attr_id, attr_data in attributes.items():
        new_attr_id = attr_id_map[old_attr_id]
        new_attr = user._attributes[new_attr_id]

        for old_action_id in attr_data.get("related_actions", []):
            if old_action_id in action_id_map:
                new_action_id = action_id_map[old_action_id]
                new_action = user._actions[new_action_id]
                new_attr.add_related_action(new_action)

        for old_child_id in attr_data.get("children", []):
            if old_child_id in attr_id_map:
                new_child_id = attr_id_map[old_child_id]
                new_child = user._attributes[new_child_id]
                new_attr.add_child(new_child)

        for old_parent_id in attr_data.get("parent", []):
            if old_parent_id in attr_id_map:
                new_parent_id = attr_id_map[old_parent_id]
                new_parent = user._attributes[new_parent_id]
                new_attr._parent.append(new_parent)

    user.add_message(f"Template {template.get('name', key)} imported.")
    user.save_user()
    return {"ok": True}


def _get_next_attr_id():
    next_id = user.next_attr_id
    return f"80{next_id}" if next_id < 10 else f"8{next_id}"


def _get_next_action_id():
    next_id = user.next_action_id
    return f"50{next_id}" if next_id < 10 else f"5{next_id}"
