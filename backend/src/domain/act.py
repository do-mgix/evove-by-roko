"""What an act changes in the user aggregate.

Pure logic on dicts — no I/O. How many marks the act is worth is decided before,
by src.domain.marks, because that needs the action's window. This applies them
together with the flat token flow, the energy penalty and the log line.
src.domain.acting runs a whole act for both the web API and the CLI.
"""
from dataclasses import dataclass, field

from src.domain.agenda import is_action_in_agenda
from src.domain.skills import aggregate_bonuses


ENERGY_PENALTY_OUT_OF_AGENDA = 10


class ActError(Exception):
    """Raised when the act cannot proceed (missing/deleted action)."""


@dataclass
class ActOutcome:
    marks: int
    log_content: str
    token_cost: int
    energy_penalty: int
    in_agenda: bool
    token_gain: int = 0
    tokens_wasted: int = 0
    window_marks: int = 0
    bonuses: dict = field(default_factory=dict)


def apply_act(
    data: dict,
    action_id: str,
    *,
    marks: int,
    option_label: str,
    note: str = "",
    today_agenda_labels: set[str] | None = None,
    in_agenda_extra: bool = False,
    token_cost_lookup=None,
    token_gain_lookup=None,
    skill_nodes_by_id: dict | None = None,
    energy_penalty: int = ENERGY_PENALTY_OUT_OF_AGENDA,
) -> ActOutcome:
    """Apply the act in place on `data`.

    Mutations:
      - data['actions'][action_id]: value (executions), score (marks earned on it)
      - data['marks']: the user's total marks
      - data['metadata']: tokens (earned or spent), energy (penalty)

    Tokens are flat per execution: productivity actions release `token_gain`, leisure
    actions charge `token_cost`, whatever the tier and even at 0 marks. Earning is
    capped at `metadata['max_tokens']`; whatever would go past the cap is reported
    as `tokens_wasted` and dropped.
    """
    action = (data.get("actions") or {}).get(action_id)
    if not action or action.get("deleted"):
        raise ActError(f"action {action_id} not found")

    metadata = data.setdefault("metadata", {})
    marks = max(0, int(marks))

    action["value"] = float(action.get("value", 0) or 0) + 1
    action["score"] = float(action.get("score", 0) or 0) + marks
    data["marks"] = int(data.get("marks", 0) or 0) + marks

    bonuses = aggregate_bonuses(set(data.get("skills") or []), skill_nodes_by_id or {})

    def _hydrate(field_name: str, lookup) -> int:
        stored = action.get(field_name)
        if not stored and lookup:
            stored = lookup(action.get("name", "")) or 0
            if stored > 0:
                action[field_name] = stored
        return int(stored or 0)

    token_cost = _hydrate("token_cost", token_cost_lookup)
    token_gain = _hydrate("token_gain", token_gain_lookup)

    tokens = int(metadata.get("tokens", 0) or 0)
    tokens_wasted = 0
    if token_cost > 0:
        tokens -= token_cost          # may go negative: spending is not gated here
    if token_gain > 0:
        cap = int(metadata.get("max_tokens", 100) or 100) + int(bonuses.get("max_tokens", 0) or 0)
        room = max(0, cap - tokens)
        tokens_wasted = max(0, token_gain - room)
        tokens += token_gain - tokens_wasted
    if token_cost > 0 or token_gain > 0:
        metadata["tokens"] = tokens

    in_agenda = is_action_in_agenda(
        action_id,
        action.get("name", ""),
        data.get("attributes") or {},
        today_agenda_labels or set(),
    ) or bool(in_agenda_extra)
    applied_energy_penalty = 0
    if not in_agenda:
        cur = int(metadata.get("energy", 0) or 0)
        metadata["energy"] = max(0, cur - energy_penalty)
        applied_energy_penalty = energy_penalty

    head = f"{action.get('name', '')} [{option_label}]"
    note = (note or "").strip()
    log_content = f"{head} : {note}" if note else head

    return ActOutcome(
        marks=marks,
        log_content=log_content,
        token_cost=token_cost,
        token_gain=token_gain,
        tokens_wasted=tokens_wasted,
        energy_penalty=applied_energy_penalty,
        in_agenda=in_agenda,
        bonuses=bonuses,
    )
