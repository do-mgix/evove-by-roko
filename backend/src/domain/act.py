"""Single source of truth for the `act` flow.

Both web and CLI delegate here so token cost, energy penalty, skill
multipliers and attribute updates are computed identically.

Pure logic on dicts — no I/O. The host loads/saves user.json and supplies
the lookup callables.
"""
from dataclasses import dataclass, field

from src.domain.action import Action
from src.domain.agenda import is_action_in_agenda
from src.domain.skills import aggregate_bonuses


ENERGY_PENALTY_OUT_OF_AGENDA = 10


class ActError(Exception):
    """Raised when the act cannot proceed (missing/deleted action)."""


@dataclass
class ActOutcome:
    score_diff: float
    raw_diff: float
    log_content: str
    note_info: dict
    units: int
    token_cost: int
    energy_penalty: int
    in_agenda: bool
    bonuses: dict = field(default_factory=dict)


def apply_act(
    data: dict,
    action_id: str,
    manual_value=1,
    *,
    today_agenda_labels: set[str] | None = None,
    token_cost_lookup=None,
    skill_nodes_by_id: dict | None = None,
    energy_penalty: int = ENERGY_PENALTY_OUT_OF_AGENDA,
) -> ActOutcome:
    """Apply the act in-place on `data`. Returns ActOutcome.

    Mutations:
      - data['actions'][action_id]: value, max_value, score (and token_cost if hydrated)
      - data['metadata']: tokens (deducted), energy (penalty), score
      - data['score']: accumulated
      - data['attributes'][*]: total_score (for related actions)
    """
    action = (data.get("actions") or {}).get(action_id)
    if not action or action.get("deleted"):
        raise ActError(f"action {action_id} not found")

    metadata = data.setdefault("metadata", {})

    # Score and value via domain Action
    domain_action = Action.from_dict(action)
    raw_diff, _msgs, note_info = domain_action.execution(manual_value=manual_value)
    state = domain_action.to_dict()
    action["value"] = state["value"]
    action["max_value"] = state["max_value"]
    action["score"] = state["score"]

    info = note_info or {}
    is_numeric = bool(info.get("is_numeric"))
    note_text = info.get("text") or ""
    units = int(info.get("value", 1)) if is_numeric and info.get("value") is not None else 1

    # Token cost (per unit × units), allows negative balance
    per_unit = action.get("token_cost")
    if per_unit is None and token_cost_lookup:
        per_unit = token_cost_lookup(action.get("name", "")) or 0
        if per_unit > 0:
            action["token_cost"] = per_unit
    per_unit = int(per_unit or 0)
    token_cost = per_unit * max(1, abs(units))
    if token_cost > 0:
        cur = int(metadata.get("tokens", 0) or 0)
        metadata["tokens"] = cur - token_cost

    # Skill xp_multiplier
    bonuses = aggregate_bonuses(set(data.get("skills") or []), skill_nodes_by_id or {})
    score_diff = raw_diff * bonuses.get("xp_multiplier", 1.0)
    data["score"] = float(data.get("score", 0) or 0) + score_diff
    metadata["score"] = data["score"]

    # Energy penalty when outside today's agenda
    in_agenda = is_action_in_agenda(
        action_id,
        action.get("name", ""),
        data.get("attributes") or {},
        today_agenda_labels or set(),
    )
    applied_energy_penalty = 0
    if not in_agenda:
        cur = int(metadata.get("energy", 0) or 0)
        metadata["energy"] = max(0, cur - energy_penalty)
        applied_energy_penalty = energy_penalty

    # Attribute total_score
    for attr in (data.get("attributes") or {}).values():
        if action_id in (attr.get("related_actions") or []):
            attr["total_score"] = float(attr.get("total_score", 0) or 0) + score_diff

    # Log content
    name = action.get("name", "")
    if note_text and not is_numeric:
        log_content = f"{name} : {note_text}".strip()
    else:
        log_content = f"{int(units)} X {name}".strip()

    return ActOutcome(
        score_diff=score_diff,
        raw_diff=raw_diff,
        log_content=log_content,
        note_info=info,
        units=units,
        token_cost=token_cost,
        energy_penalty=applied_energy_penalty,
        in_agenda=in_agenda,
        bonuses=bonuses,
    )
