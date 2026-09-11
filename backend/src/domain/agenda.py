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


def leaves_for_labels(
    labels: set[str],
    nodes_by_name: dict[str, list[str]],
    children: dict[str, list],
) -> set[str]:
    """Leaves under every attribute whose name matches one of today's labels.

    Any attribute can be scheduled — "Musculatura" covers every strength move.
    Several attributes may share a display name (there are three "Mobilidade");
    a label matching several takes the union of all their subtrees.

    Args:
      labels: already normalized labels.
      nodes_by_name: {NORMALIZED_NAME: [node_key, ...]}.
      children: {parent_key: [(child_key, weight), ...]} from the graph.
    """
    out: set[str] = set()
    seen: set[str] = set()

    def descend(key: str) -> None:
        if key in seen:           # the graph shares nodes; visit each once
            return
        seen.add(key)
        kids = children.get(key, [])
        if not kids:
            out.add(key)
            return
        for child_key, _w in kids:
            descend(child_key)

    for label in labels:
        for node_key in nodes_by_name.get(label, []):
            descend(node_key)
    return out
