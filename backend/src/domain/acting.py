"""One act, end to end — the same for the web API and the CLI.

Picks the action's tiers (the base's, for a patch), reads its marks window,
decides the marks, applies the act to the user aggregate and saves it, records
the mark event, then moves the default graph and the patch's own attributes.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from src.domain.act import ActError, ActOutcome, apply_act
from src.domain.contributions import apply_action_contributions, apply_patch_attributes
from src.domain.marks import DEFAULT_TIERS, MARK_WINDOW_HOURS, MARKS_PER_WINDOW, marks_for, options
from src.domain.user_attributes import engine_name
from src.infrastructure import repos
from src.infrastructure.static_data import skill_nodes_by_id


def engine_action_id(action_id: str, action: dict) -> str:
    """The window an act counts against: the base's, for a patch — otherwise two
    patches of one action would each get their own 5 marks."""
    return action.get("base_action_id") or action_id


def tiers_for(data: dict, action: dict, templates: dict | None = None) -> dict:
    templates = repos.load_action_templates() if templates is None else templates
    meta = templates.get(engine_name(data.get("actions") or {}, action)) or {}
    return meta.get("tiers") or DEFAULT_TIERS


def _window(username: str, action_id: str, action: dict, now: datetime) -> list[dict]:
    since = now - timedelta(hours=MARK_WINDOW_HOURS)
    return repos.load_mark_window(username, engine_action_id(action_id, action), since)


def _action(data: dict, action_id: str) -> dict:
    action = (data.get("actions") or {}).get(action_id)
    if not action or action.get("deleted"):
        raise ActError(f"action {action_id} not found")
    return action


def window_state(username: str, data: dict, action_id: str, now: datetime | None = None) -> dict:
    """Marks the action already earned in the current window, and its tiers."""
    action = _action(data, action_id)
    events = _window(username, action_id, action, now or datetime.now())
    return {
        "window_marks": sum(int(e["marks"]) for e in events),
        "limit": MARKS_PER_WINDOW,
        "hours": MARK_WINDOW_HOURS,
        "options": options(tiers_for(data, action)),
    }


def perform_act(username: str, data: dict, action_id: str, option, note: str = "", *,
                today_labels: set[str], in_agenda_extra: bool = False, save) -> ActOutcome:
    """Run one act. `save(data)` persists the aggregate — each host has its own.
    Raises MarkError for an invalid tier before anything changes."""
    action = _action(data, action_id)
    now = datetime.now()
    tiers = tiers_for(data, action)
    decided = marks_for(tiers, option, _window(username, action_id, action, now))

    outcome = apply_act(
        data, action_id,
        marks=decided["marks"],
        option_label=options(tiers)[int(option)]["label"],
        note=note,
        today_agenda_labels=today_labels,
        in_agenda_extra=in_agenda_extra,
        token_cost_lookup=repos.lookup_token_cost,
        token_gain_lookup=repos.lookup_token_gain,
        skill_nodes_by_id=skill_nodes_by_id(),
    )
    outcome.window_marks = decided["window_marks"]
    save(data)

    engine_id = engine_action_id(action_id, action)
    repos.record_mark_event(username, engine_id, action_id, now, int(option), decided["amount"], decided["marks"])
    apply_action_contributions(username, engine_name(data.get("actions") or {}, action), decided["marks"], now)
    if action.get("base_action_id"):
        apply_patch_attributes(username, action_id, decided["marks"], now)
    return outcome
