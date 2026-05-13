"""Agenda matching rules.

Pure helpers — no I/O. Hosts (web/CLI) load agenda items from their
preferred storage and pass normalized labels here.
"""

DAY_NAMES = ("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM")


def normalize(label: str) -> str:
    return " ".join(str(label or "").strip().upper().split())


def collect_labels(items, day_name=None, iso_date=None) -> set[str]:
    """Return the set of normalized labels for items matching the given day.

    An item matches when:
      - it has `date == iso_date`, or
      - it has `day == "*"`, or
      - it has `day == day_name`.

    Pass either `iso_date` or `day_name` (or both).
    """
    out = set()
    for it in items or []:
        item_date = it.get("date")
        item_day = it.get("day")
        match = False
        if iso_date and item_date == iso_date:
            match = True
        elif item_day == "*":
            match = True
        elif day_name and item_day == day_name:
            match = True
        if match:
            label = normalize(it.get("label"))
            if label:
                out.add(label)
    return out


def is_action_in_agenda(action_id: str, action_name: str, attributes: dict, labels: set[str]) -> bool:
    """True if action belongs to today's agenda.

    Match by:
      1. Action name directly in labels.
      2. Any attribute whose name is in labels has this action_id in its
         related_actions.
    """
    name_norm = normalize(action_name)
    if not name_norm:
        return False
    if name_norm in labels:
        return True
    for attr in (attributes or {}).values():
        attr_label = normalize(attr.get("name"))
        if attr_label and attr_label in labels and action_id in (attr.get("related_actions") or []):
            return True
    return False


def conceptual_leaves_for_labels(
    labels: set[str],
    concept_node_by_name: dict[str, str],
    children: dict[str, list],
) -> set[str]:
    """For each agenda label that matches a conceptual node name (normalized),
    return the union of all leaf keys reachable downward.

    Args:
      labels: already normalized labels.
      concept_node_by_name: {NORMALIZED_DISPLAY_NAME: node_key} for conceptual nodes.
      children: {parent_key: [(child_key, weight), ...]} from the tree.

    Returns the set of leaf keys covered by those labels.
    """
    out: set[str] = set()

    def _descend(key: str) -> None:
        kids = children.get(key, [])
        if not kids:
            out.add(key)
            return
        for child_key, _w in kids:
            _descend(child_key)

    for label in labels:
        node_key = concept_node_by_name.get(label)
        if node_key:
            _descend(node_key)
    return out
