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
    token_gain: int = 0
    tokens_wasted: int = 0
    bonuses: dict = field(default_factory=dict)


def apply_act(
    data: dict,
    action_id: str,
    manual_value=1,
    *,
    today_agenda_labels: set[str] | None = None,
    in_agenda_extra: bool = False,
    token_cost_lookup=None,
    token_gain_lookup=None,
    skill_nodes_by_id: dict | None = None,
    energy_penalty: int = ENERGY_PENALTY_OUT_OF_AGENDA,
) -> ActOutcome:
    """Apply the act in-place on `data`. Returns ActOutcome.

    Mutations:
      - data['actions'][action_id]: value, max_value, score (and token/price fields if hydrated)
      - data['metadata']: tokens (earned or spent), energy (penalty), score
      - data['score']: accumulated
      - data['attributes'][*]: total_score (for related actions)

    Tokens are flat per execution on both sides: productivity actions release
    `token_gain`, leisure actions charge `token_cost`, and the note never
    multiplies either. Earning is capped at `metadata['max_tokens']`; whatever
    would go past the cap is reported as `tokens_wasted` and dropped.
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

    bonuses = aggregate_bonuses(set(data.get("skills") or []), skill_nodes_by_id or {})

    # Token flow: flat per execution, never multiplied by the note.
    def _hydrate(field: str, lookup) -> int:
        stored = action.get(field)
        if not stored and lookup:
            stored = lookup(action.get("name", "")) or 0
            if stored > 0:
                action[field] = stored
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

    # Skill xp_multiplier
    score_diff = raw_diff * bonuses.get("xp_multiplier", 1.0)
    data["score"] = float(data.get("score", 0) or 0) + score_diff
    metadata["score"] = data["score"]

    # Energy penalty when outside today's agenda
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

    # Note: leaf score contributions are applied by the host (web/CLI) after this call
    # since they require DB I/O. apply_act stays pure.

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
        token_gain=token_gain,
        tokens_wasted=tokens_wasted,
        energy_penalty=applied_energy_penalty,
        in_agenda=in_agenda,
        bonuses=bonuses,
    )
