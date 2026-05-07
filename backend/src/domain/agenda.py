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
