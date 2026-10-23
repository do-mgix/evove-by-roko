"""The engine: what a profile's evove is made of, and how it grows.

The app no longer carries a fixed set of screens. It is an engine that draws
modules — agir, shop, roko, agenda… — and the server says which of them a
profile has, where each one stands on the home, which entities it has met and
how far the interface has evolved. All of that is the profile's *evove*, kept
as one JSON state per profile (`user_engine`).

Every module has a passcode. Typing one unlocks the module, so a friend can be
handed the shop without going through the story; and every evove has a
passcode of its own, which hands over the whole build — modules, entities,
selector — though never the data behind it.

Things are revealed a little at a time, by a story and by rules:

- the story is a line of steps. Each waits for one kind of event — a visit, an
  act, a purchase, a talk, a plan — and, when it comes, an entity says
  something and a module opens. It starts with agir alone: acting on an action
  the profile does not own makes roko call it a lie; the shop opens, the action
  is bought, acted on, and roko believes it — then roko can be talked to, and
  so on;
- the rules watch counters — visits, opens of each module, page turns, acts,
  talks — and change the interface when one crosses its mark: the selector
  becomes a slider after 1000 turns, and then, at each new visit, has a chance
  of becoming the third one; eve appears after five talks with roko.

The home's layout is drawn here too, from a seed renewed at every session, so
it is not a fixed design: each visit tiles the same area again, the modules
used most taking more of it.

Pure logic — no I/O. The host loads the state, calls `event`, saves it.
"""
from __future__ import annotations

import copy
import math
import random
import re
from datetime import datetime

from src.domain.names import PASSCODE_ALPHABET


COLS, ROWS = 5.0, 7.0

# a new session starts when the app comes back after this long
SESSION_GAP_MINUTES = 20

SELECTOR_2_TURNS = 1000
SELECTOR_3_CHANCE = 0.12
EVE_AFTER_TALKS = 5

EVOVE_CODE_LENGTH = 8

# what the app knows how to draw: `kind` is the screen, the rest dresses it
MODULES: dict[str, dict] = {
    "act": {"kind": "act", "label": "agir", "color": "#00f0ff", "glyph": "act", "tone": 1, "code": "AGIR-7Q", "weight": 2.2},
    "shop": {"kind": "shop", "label": "shop", "color": "#7af9ff", "glyph": "shop", "tone": 2, "code": "LOJA-3K", "weight": 1.0},
    "roko": {"kind": "entity", "label": "roko", "color": "#3dfff0", "glyph": "roko", "tone": 3, "code": "ROKO-9X", "weight": 0.8},
    "agenda": {"kind": "agenda", "label": "agenda", "color": "#00a8e8", "glyph": "logs", "tone": 4, "code": "AGND-4M", "weight": 1.0},
    "attributes": {"kind": "attributes", "label": "atributos", "color": "#00c8ff", "glyph": "attributes", "tone": 5, "code": "ATRB-6P", "weight": 0.9},
    "journey": {"kind": "journey", "label": "jornada", "color": "#00ffd0", "glyph": "journey", "tone": 6, "code": "JRND-8T", "weight": 1.0},
    "build": {"kind": "build", "label": "construir", "color": "#00e0ff", "glyph": "build", "tone": 7, "code": "CNST-2W", "weight": 0.8},
}

# codes that change the interface rather than add a module
UPGRADES: dict[str, dict] = {
    "selector2": {"code": "SELE-2R", "label": "seletor nível 2"},
    "selector3": {"code": "SELE-3V", "label": "seletor nível 3"},
    "eve": {"code": "EVE-5HZ", "label": "eve"},
}

ALL_MODULES = list(MODULES)


def clean_code(raw) -> str:
    """A code as typed — any case, spaces, dashes or a leading # — reduced to
    its letters and digits."""
    return re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())


def module_for_code(raw) -> str | None:
    code = clean_code(raw)
    return next((m for m, d in MODULES.items() if clean_code(d["code"]) == code), None)


def upgrade_for_code(raw) -> str | None:
    code = clean_code(raw)
    return next((u for u, d in UPGRADES.items() if clean_code(d["code"]) == code), None)


def evove_code(rng: random.Random) -> str:
    return "".join(rng.choice(PASSCODE_ALPHABET) for _ in range(EVOVE_CODE_LENGTH))


# ---------------------------------------------------------------- state

def fresh(rng: random.Random) -> dict:
    """A profile that starts from the beginning: agir alone, the story at its
    first step."""
    return {
        "v": 1,
        "modules": ["act"],
        "fresh": [],
        "story": "start",
        "entities": [],
        "selector": 1,
        "counters": {},
        "session": {"n": 0, "at": None, "seed": rng.randrange(1 << 30)},
        "ghosts": [],
        # the first thing a new profile reads, above agir alone
        "line": {"entity": "roko", "text": "AGE."},
    }


def legacy() -> dict:
    """A profile from before the engine: everything it already had, the story
    told."""
    s = fresh(random.Random(0))
    s["modules"] = list(ALL_MODULES)
    s["story"] = "done"
    s["entities"] = ["roko"]
    s["line"] = None
    return s


def normalized(state: dict | None, rng: random.Random) -> dict:
    """The state with every field it should have, whatever version wrote it."""
    base = fresh(rng)
    if not state:
        return base
    out = {**base, **state}
    out["counters"] = dict(state.get("counters") or {})
    out["session"] = {**base["session"], **(state.get("session") or {})}
    out["modules"] = [m for m in out.get("modules") or [] if m in MODULES] or ["act"]
    return out


def _count(state: dict, key: str, by: int = 1, sub: str | None = None) -> int:
    c = state["counters"]
    if sub is None:
        c[key] = int(c.get(key, 0) or 0) + by
        return c[key]
    d = c.setdefault(key, {})
    d[sub] = int(d.get(sub, 0) or 0) + by
    return d[sub]


def counter(state: dict, key: str, sub: str | None = None) -> int:
    v = state["counters"].get(key, 0)
    if sub is None:
        return int(v or 0) if not isinstance(v, dict) else sum(v.values())
    return int((v or {}).get(sub, 0) or 0) if isinstance(v, dict) else 0


def unlock(state: dict, module: str) -> bool:
    if module not in MODULES or module in state["modules"]:
        return False
    state["modules"].append(module)
    state["fresh"] = [*state.get("fresh", []), module]
    return True


def meet(state: dict, entity: str) -> bool:
    if entity in state["entities"]:
        return False
    state["entities"].append(entity)
    return True


# ---------------------------------------------------------------- the story

def _say(entity: str, text: str) -> dict:
    return {"entity": entity, "text": text}


# step -> (the event it waits for, whether the event fits, what happens)
STORY: dict[str, tuple] = {
    "start": ("ghost_act", None, {
        "lines": [_say("roko", "MENTIRA."), _say("roko", "ESSA AÇÃO NÃO É SUA. COMPRE-A. DEPOIS AJA DE NOVO.")],
        "unlock": ["shop"], "next": "buy",
    }),
    "buy": ("buy", None, {
        "lines": [_say("roko", "AGORA ELA É SUA. PROVE.")], "next": "prove",
    }),
    "prove": ("act", None, {
        "lines": [_say("roko", "AGORA EU ACREDITO."), _say("roko", "PODE FALAR COMIGO.")],
        "unlock": ["roko"], "meet": ["roko"], "next": "listen",
    }),
    "listen": ("talk", lambda st, ev: ev.get("entity") == "roko", {
        "lines": [_say("roko", "VOCÊ ME OUVE. ENTÃO PLANEJE: ESCREVA O QUE PENSA DO QUE FEZ.")],
        "unlock": ["agenda"], "next": "plan",
    }),
    "plan": ("plan", None, {
        "lines": [_say("roko", "UM PENSAMENTO. VEJA AGORA O QUE VOCÊ ESTÁ SE TORNANDO.")],
        "unlock": ["attributes"], "next": "walk",
    }),
    "walk": ("act", lambda st, ev: counter(st, "acts") >= 5, {
        "lines": [_say("roko", "CINCO ATOS. O CAMINHO É LONGO: ANDE.")],
        "unlock": ["journey"], "next": "build",
    }),
    "build": ("visit", lambda st, ev: counter(st, "visits") >= 3 and counter(st, "opens", "journey") >= 1, {
        "lines": [_say("roko", "VOCÊ SEMPRE VOLTA. CONSTRUA ENTÃO A SUA INTERFACE.")],
        "unlock": ["build"], "next": "done",
    }),
}

STORY_ORDER = ["start", "buy", "prove", "listen", "plan", "walk", "build", "done"]


def story_progress(state: dict) -> tuple[int, int]:
    step = state.get("story", "done")
    return (STORY_ORDER.index(step) if step in STORY_ORDER else len(STORY_ORDER) - 1), len(STORY_ORDER) - 1


def _apply(state: dict, effect: dict, out: list[dict]) -> None:
    for m in effect.get("unlock", []):
        unlock(state, m)
    for e in effect.get("meet", []):
        meet(state, e)
    out.extend(effect.get("lines", []))
    if "next" in effect:
        state["story"] = effect["next"]


# the rules: (name, the events that make it look, whether it holds, what it does)
def _eve(state: dict, ev: dict, rng: random.Random, out: list[dict]) -> None:
    if "roko" in state["entities"] and "eve" not in state["entities"] and counter(state, "talks", "roko") >= EVE_AFTER_TALKS:
        meet(state, "eve")
        out.append(_say("roko", "HÁ OUTRA VOZ AQUI. NÃO CONFIE NELA."))
        out.append(_say("eve", "oi. ele fala alto, né? eu só pergunto coisas."))


def _selector(state: dict, ev: dict, rng: random.Random, out: list[dict]) -> None:
    if state["selector"] < 2 and counter(state, "turns") >= SELECTOR_2_TURNS:
        state["selector"] = 2
        out.append(_say("system", "O SELETOR MUDOU: DESLIZE."))
    elif state["selector"] == 2 and ev["kind"] == "visit" and ev.get("new_session") and rng.random() < SELECTOR_3_CHANCE:
        state["selector"] = 3
        out.append(_say("system", "O SELETOR MUDOU: TOQUE ONDE QUISER IR."))


RULES = (_eve, _selector)


def event(state: dict, ev: dict, rng: random.Random, now: datetime) -> list[dict]:
    """Counts the event, moves the story if it is what the step waits for, runs
    the rules. Returns what the entities say about it, in order, and keeps the
    last line on the state for the home to show."""
    kind = ev["kind"]
    out: list[dict] = []
    if kind == "visit":
        last = state["session"].get("at")
        gap = (now - datetime.fromisoformat(last)).total_seconds() / 60 if last else math.inf
        ev["new_session"] = bool(ev.get("cold")) or gap >= SESSION_GAP_MINUTES
        if ev["new_session"]:
            _count(state, "visits")
            state["session"] = {"n": int(state["session"].get("n", 0)) + 1, "seed": rng.randrange(1 << 30),
                                "at": now.isoformat(timespec="seconds")}
        else:
            state["session"]["at"] = now.isoformat(timespec="seconds")
        if ev.get("turns"):
            # turns counted on the device before the engine existed
            state["counters"]["turns"] = max(counter(state, "turns"), int(ev["turns"]))
    elif kind == "open":
        m = ev.get("module")
        if m in MODULES:
            _count(state, "opens", sub=m)
            _count(state, "opens_" + str(ev.get("period") or "mo"), sub=m)
            state["fresh"] = [f for f in state.get("fresh", []) if f != m]
    elif kind == "turn":
        _count(state, "turns", int(ev.get("n", 1) or 1))
    elif kind == "act":
        _count(state, "acts")
    elif kind == "ghost_act":
        _count(state, "ghost_acts")
    elif kind == "buy":
        _count(state, "buys")
    elif kind == "talk":
        _count(state, "talks", sub=str(ev.get("entity") or "roko"))
    elif kind == "plan":
        _count(state, "plans")
    elif kind == "dismiss":
        state["line"] = None
        return out

    step = state.get("story")
    if step in STORY:
        waits, fits, effect = STORY[step]
        if waits == kind and (fits is None or fits(state, ev)):
            _apply(state, effect, out)
    for rule in RULES:
        rule(state, ev, rng, out)
    if out:
        state["line"] = {**out[-1], "at": now.isoformat(timespec="seconds")}
    return out


def entity_presence(state: dict) -> bool:
    """While the story is told the entities are always there and always answer:
    a tutorial that hides its teacher teaches nothing."""
    return state.get("story") != "done"


# ---------------------------------------------------------------- passcodes

def take_module(state: dict, module: str) -> list[dict]:
    unlock(state, module)
    if MODULES[module]["kind"] == "entity":
        meet(state, module)
    return [_say("system", f"CÓDIGO ACEITO: {MODULES[module]['label'].upper()}.")]


def take_upgrade(state: dict, upgrade: str) -> list[dict]:
    if upgrade == "selector2":
        state["selector"] = max(state["selector"], 2)
    elif upgrade == "selector3":
        state["selector"] = 3
    elif upgrade == "eve":
        meet(state, "roko")
        meet(state, "eve")
        unlock(state, "roko")
    return [_say("system", f"CÓDIGO ACEITO: {UPGRADES[upgrade]['label'].upper()}.")]


def take_build(state: dict, other: dict) -> list[dict]:
    """Another profile's evove, typed by its code: its modules, entities and
    selector, the story told. Counters and data stay this profile's own."""
    for m in other.get("modules") or []:
        unlock(state, m)
    for e in other.get("entities") or []:
        meet(state, e)
    state["selector"] = max(state["selector"], int(other.get("selector", 1) or 1))
    state["story"] = "done"
    return [_say("system", "EVOVE CARREGADO.")]


# ---------------------------------------------------------------- the home

def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _split(quad, items, weights, rng, out):
    """Tiles `quad` (clockwise from the top left) with `items`: each cut joins
    two opposite edges, so every piece is a quadrilateral again and neighbours
    share their vertices."""
    if len(items) == 1:
        out[items[0]] = [list(map(lambda v: round(v, 3), p)) for p in quad]
        return
    total = sum(weights[i] for i in items)
    best, cut = None, 1
    acc = 0.0
    for k in range(1, len(items)):
        acc += weights[items[k - 1]]
        d = abs(acc / total - 0.5)
        if best is None or d < best:
            best, cut = d, k
    first, second = items[:cut], items[cut:]
    f = sum(weights[i] for i in first) / total
    tl, tr, br, bl = quad
    width = ((tr[0] - tl[0]) + (br[0] - bl[0])) / 2
    height = ((bl[1] - tl[1]) + (br[1] - tr[1])) / 2
    j1 = min(0.82, max(0.18, f + rng.uniform(-0.07, 0.07)))
    j2 = min(0.82, max(0.18, f + rng.uniform(-0.07, 0.07)))
    if height >= width * 0.8:
        a, b = _lerp(tl, bl, j1), _lerp(tr, br, j2)
        _split([tl, tr, b, a], first, weights, rng, out)
        _split([a, b, br, bl], second, weights, rng, out)
    else:
        a, b = _lerp(tl, tr, j1), _lerp(bl, br, j2)
        _split([tl, a, b, bl], first, weights, rng, out)
        _split([a, tr, br, b], second, weights, rng, out)


def layout(modules: list[str], opens: dict[str, int], seed: int) -> dict[str, list[list[float]]]:
    """Polygons in the home's grid, five squares across and seven down, for this
    session. Agir stands tall on the right, under the thumb; the rest tile the
    left in an order and with cuts drawn from `seed`, each sized by its weight
    and by how often it is opened."""
    rng = random.Random(seed)
    out: dict[str, list[list[float]]] = {}
    xt = 2.75 + rng.uniform(-0.3, 0.2)
    xb = xt + rng.uniform(0.25, 0.65)
    rest = [m for m in modules if m != "act" and m in MODULES]
    if "act" in modules:
        out["act"] = [[round(xt, 3), 0.0], [COLS, 0.0], [COLS, ROWS], [round(xb, 3), ROWS]]
    else:
        xt = xb = COLS
    if rest:
        rng.shuffle(rest)
        weights = {m: MODULES[m]["weight"] * (1 + 0.35 * math.log1p(int(opens.get(m, 0) or 0))) for m in rest}
        _split([(0.0, 0.0), (xt, 0.0), (xb, ROWS), (0.0, ROWS)], rest, weights, rng, out)
    return out


def view(state: dict, passcode: str, period: str) -> dict:
    """What the app reads to draw itself."""
    seed = int(state["session"].get("seed", 0) or 0)
    opens = state["counters"].get("opens") or {}
    shapes = layout(state["modules"], opens, seed)
    rng = random.Random(seed + 1)
    here = state["counters"].get("opens_" + period) or {}
    shown = [m for m in state["modules"] if m in shapes]
    hint = max(shown, key=lambda m: (int(here.get(m, 0) or 0), m == "act")) if shown else None
    tiles = []
    for m in shown:
        d = MODULES[m]
        tiles.append({
            "id": m, "kind": d["kind"], "label": d["label"], "color": d["color"], "glyph": d["glyph"],
            "tone": d["tone"], "polygon": shapes[m], "delay": rng.randrange(0, 360),
            "fresh": m in state.get("fresh", []), "code": d["code"],
        })
    step, steps = story_progress(state)
    turns = counter(state, "turns")
    level = int(state.get("selector", 1) or 1)
    return {
        "passcode": passcode,
        "session": int(state["session"].get("n", 0) or 0),
        "seed": seed,
        "tiles": tiles,
        "hint": hint,
        "modules": [{"id": m, "label": d["label"], "code": d["code"] if m in state["modules"] else None,
                     "on": m in state["modules"]} for m, d in MODULES.items()],
        "entities": list(state["entities"]),
        "story": {"step": state.get("story", "done"), "at": step, "of": steps, "done": state.get("story") == "done"},
        "ghosts": list(state.get("ghosts") or []) if state.get("story") == "start" else [],
        "line": state.get("line"),
        "selector": {
            "level": level,
            "turns": turns,
            "next_at": SELECTOR_2_TURNS if level < 2 else None,
            "chance": SELECTOR_3_CHANCE if level == 2 else None,
        },
        "counters": {
            "visits": counter(state, "visits"),
            "acts": counter(state, "acts"),
            "opens": counter(state, "opens"),
            "turns": turns,
            "talks": counter(state, "talks"),
            "buys": counter(state, "buys"),
            "plans": counter(state, "plans"),
        },
    }


def copy_state(state: dict) -> dict:
    return copy.deepcopy(state)
