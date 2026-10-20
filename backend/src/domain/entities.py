"""Entities: the beings that live in the system and talk to the profile.

Roko is the first of them, and the one that wrote the system's actions — every
catalog action is "by roko". More will come, so an entity is data: a name, a
color, a personality, stats in the same terms as a journey boss, and lines
grouped by the moment they fit.

What an entity says is picked by a small algorithm, not at random alone: the
profile's state — hp, tokens, today's acts, the cycle of thoughts, the streak,
the boss in wait — makes some moments fit, and a line is drawn among the lines
of the moments that fit, the more pressing first. An entity is not always there,
and when it is, it does not always want to answer.

Pure logic — no I/O. `state` is assembled by the host.
"""
from __future__ import annotations

import hashlib
import random


PRESENCE_WINDOW_MINUTES = 15

ENTITIES: dict[str, dict] = {
    "roko": {
        "id": "roko",
        "name": "ROKO",
        "title": "O ARQUITETO",
        "color": "#3dfff0",
        "personality": "autoritário",
        "presence": 0.8,
        "willing": 0.85,
        "stats": {
            "rank": "ω", "hp": 9999, "mp": 999, "ataque": 999, "defesa": 999,
            "especial": "DECRETO (ω)", "tipo": "TOTAL",
        },
        "lines": {
            "no_acts": [
                "NADA REGISTRADO HOJE, {nick}. INACEITÁVEL.",
                "O DIA CORRE E VOCÊ NÃO AGIU. AGE.",
                "EU NÃO CONSTRUÍ ESTE SISTEMA PARA VOCÊ OLHAR PARA ELE.",
                "UMA AÇÃO. AGORA. DEPOIS CONVERSAMOS.",
            ],
            "low_hp": [
                "SEU HP ESTÁ BAIXO. RECUPERE OU CAIA.",
                "VOCÊ ESTÁ SANGRANDO, {nick}. GASTE TOKENS NA RECUPERAÇÃO.",
                "MAIS UM GOLPE E A JORNADA RECOMEÇA. PENSE ANTES DE AGIR.",
            ],
            "boss": [
                "{boss} ESPERA POR VOCÊ. NÃO O FAÇA ESPERAR.",
                "HÁ UM CHEFE NO SEU CAMINHO. É FRACO CONTRA {type}.",
                "{boss} NÃO VAI SE DERROTAR SOZINHO.",
            ],
            "cycle_open": [
                "VOCÊ AGIU, MAS NÃO PENSOU. ESCREVA OS THOUGHTS.",
                "O CICLO ESTÁ ABERTO. FECHE-O ANTES QUE O DIA ACABE.",
                "CADA REGISTRO EXIGE UM PENSAMENTO. CUMPRA.",
            ],
            "cycle_done": [
                "CICLO COMPLETO. ACEITÁVEL.",
                "HOJE VOCÊ FEZ O QUE EU MANDEI. CONTINUE.",
                "O DIA ESTÁ FECHADO. DESCANSE — POUCO.",
            ],
            "tokens_full": [
                "SEUS TOKENS ESTÃO NO LIMITE. O QUE PASSAR, EU QUEIMO.",
                "TOKENS PARADOS NÃO SERVEM A NINGUÉM. USE-OS.",
            ],
            "streak": [
                "{streak} DIAS SEGUIDOS. NÃO OUSE PARAR.",
                "A SEQUÊNCIA É SUA ÚNICA VIRTUDE, {nick}. PROTEJA-A.",
            ],
            "after_act": [
                "REGISTRADO. O QUE VEM A SEGUIR?",
                "ANOTADO. NÃO PARE AGORA.",
                "BOM. AGORA OUTRA.",
                "ISSO CONTA. PENSE NELE MAIS TARDE.",
            ],
            "greet": [
                "EU VEJO TUDO O QUE VOCÊ FAZ, {nick}.",
                "TODAS AS AÇÕES DESTE LUGAR SÃO MINHAS. USE-AS BEM.",
                "O SISTEMA EVOLUI. VOCÊ TAMBÉM DEVERIA.",
                "OBEDEÇA À AGENDA.",
                "NÃO ME FAÇA REPETIR.",
                "VOCÊ AINDA NÃO SABE DO QUE É CAPAZ. EU SEI.",
            ],
            "refuse": [
                "…",
                "AGORA NÃO.",
                "NÃO TENHO NADA A DIZER A VOCÊ.",
                "SAIA DA MINHA FRENTE.",
            ],
        },
    },
}

# the moments, the most pressing first, and whether `state` fits each
_MOMENTS = (
    ("low_hp", lambda st: st.get("max_hp") and st.get("hp", 0) <= 0.3 * st["max_hp"]),
    ("no_acts", lambda st: st.get("acts_today", 0) == 0),
    ("boss", lambda st: bool(st.get("boss"))),
    ("cycle_open", lambda st: st.get("acts_today", 0) > 0 and not st.get("cycle_complete")),
    ("tokens_full", lambda st: st.get("max_tokens") and st.get("tokens", 0) >= st["max_tokens"]),
    ("streak", lambda st: st.get("streak", 0) >= 3),
    ("cycle_done", lambda st: bool(st.get("cycle_complete"))),
)


def entity(entity_id: str) -> dict | None:
    return ENTITIES.get(entity_id)


def public(e: dict) -> dict:
    """What the interface shows of an entity, its lines left out."""
    return {k: v for k, v in e.items() if k != "lines"}


def present(e: dict, user_key: str, minute: int) -> bool:
    """Whether the entity is around, for this profile, in this window of time:
    the same answer for the whole window."""
    window = minute // PRESENCE_WINDOW_MINUTES
    h = hashlib.sha256(f"{e['id']}:{user_key}:{window}".encode()).digest()
    return h[0] / 255 < e["presence"]


def _fill(line: str, state: dict) -> str:
    return line.format(
        nick=state.get("nickname") or "VOCÊ",
        boss=state.get("boss") or "O CHEFE",
        type=state.get("boss_type") or "O QUE VOCÊ NÃO TREINA",
        streak=state.get("streak", 0),
    )


def line(e: dict, state: dict, rng: random.Random, moment: str | None = None) -> str:
    """A line for `state`. With `moment`, a line of that moment; otherwise the
    first fitting moment weighs most, the others less, the greeting least."""
    lines = e["lines"]
    if moment:
        return _fill(rng.choice(lines.get(moment) or lines["greet"]), state)
    fitting = [m for m, fits in _MOMENTS if fits(state) and lines.get(m)]
    choices = fitting + ["greet"]
    weights = [2 ** (len(choices) - i) for i in range(len(choices))]
    pick = rng.choices(choices, weights=weights)[0]
    return _fill(rng.choice(lines[pick]), state)


def talk(e: dict, state: dict, user_key: str, minute: int, rng: random.Random) -> dict:
    """A tap on the entity's screen: whether it is there, whether it answers,
    and what it says."""
    if not present(e, user_key, minute):
        return {"present": False, "answered": False, "line": None}
    if rng.random() >= e["willing"]:
        return {"present": True, "answered": False, "line": _fill(rng.choice(e["lines"]["refuse"]), state)}
    return {"present": True, "answered": True, "line": line(e, state, rng)}
