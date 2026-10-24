"""The engine: what a profile's evove is made of, and how it grows.

The app no longer carries a fixed set of screens. It is an engine that draws
modules — agir, shop, roko, agenda… — and the server says which of them a
profile has, where each one stands on the home, which entities it has met and
how far the interface has evolved. All of that is the profile's *evove*, kept
as one JSON state per profile (`user_engine`). The evove is one of three
modes, picked on the app's first screen: once its story is told the sandbox
opens beside it — every action free and unlimited, kept apart from the real
data — and the journey (src.domain.dungeon) is a mode of its own.

Every module has a passcode. Typing one unlocks the module, so a friend can be
handed the shop without going through the story; and every evove has a
passcode of its own, which hands over the whole build — modules, entities,
selector — though never the data behind it.

Things are revealed a little at a time, by a story and by rules:

- the story is a line of steps. Each waits for one kind of event — a visit, an
  act, a purchase, a talk, a plan — and, when it comes, an entity says
  something and a module opens. It starts with agir alone and a few actions
  the profile was given, not chosen — a climb, a song, whatever the draw
  brought. Acting on one pays its marks like any act, but roko did not see it
  happen: someone real holds the phone, and roko counts what that person does
  out there. The shop opens; an action the person chose is bought, acted on,
  and roko believes it — then roko can be talked to, and so on;
- a given action stays in doubt until it comes back on other days: roko
  comments on it, the marks come all the same, and on its third day roko
  believes it. The evove ends up showing what its person really does;
- the rules watch counters — visits, opens of each module, page turns, acts,
  talks — and change the interface when one crosses its mark: the selector
  becomes a slider after 1000 turns, and then, at each new visit, has a chance
  of becoming the third one;
- a profile carries one entity at a time, roko first. Once the story is told,
  every new session weighs how the profile used the evove since the last one
  — acting, asking, coming back on other days, hurrying, collecting — and the
  entity whose trait it showed most can take roko's place: a personality test
  played out over weeks. A profile that only looks, session after session, is
  left with no entity at all, and the system answers alone, mute.

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

from src.domain import entities as voices
from src.domain.names import PASSCODE_ALPHABET


COLS, ROWS = 5.0, 7.0

# a new session starts when the app comes back after this long
SESSION_GAP_MINUTES = 20

SELECTOR_2_TURNS = 1000
SELECTOR_3_CHANCE = 0.12

# the personality test: at each new session after the story, what the profile
# did since the last one adds to each entity's affinity, the old fading by
# DECAY. Another entity takes the place of the one carried when its affinity is
# at least SWITCH_MIN and SWITCH_RATIO times the carried one's; with none, one
# arrives at ARRIVE. IDLE_SESSIONS sessions in a row with nothing done leave
# the profile with no entity.
AFFINITY_DECAY = 0.85
SWITCH_MIN = 3.0
SWITCH_RATIO = 1.6
ARRIVE = 2.0
IDLE_SESSIONS = 3
# roko's head start when the story ends
ROKO_START = 5.0

# a given action is believed once acted on, on this many different days
BELIEVE_AFTER_DAYS = 3
# after the story, how often roko still comments on a doubted act
DOUBT_CHANCE = 0.4

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

# codes that change the interface rather than add a module: the selector's
# levels, the entity carried (or none), the sandbox, a fast journey
UPGRADES: dict[str, dict] = {
    "selector2": {"code": "SELE-2R", "label": "seletor nível 2"},
    "selector3": {"code": "SELE-3V", "label": "seletor nível 3"},
    "eve": {"code": "EVE-5HZ", "label": "eve", "entity": "eve"},
    "roko": {"code": "ROKO-1A", "label": "roko", "entity": "roko"},
    "osso": {"code": "OSSO-3T", "label": "osso", "entity": "osso"},
    "zira": {"code": "ZIRA-8N", "label": "zira", "entity": "zira"},
    "mura": {"code": "MURA-6D", "label": "mura", "entity": "mura"},
    "mute": {"code": "MUDO-0X", "label": "sem entidade", "entity": None},
    "sandbox": {"code": "SAND-9B", "label": "sandbox"},
    "fast": {"code": "RAPD-4J", "label": "jornada rápida"},
}

# the sandbox's own home: agir free, its attributes, every entity met, coleto
SANDBOX_MODULES: dict[str, dict] = {
    "act": {"kind": "sandbox_act", "label": "agir", "color": "#7dff6b", "glyph": "act", "tone": 1, "weight": 2.2},
    "attributes": {"kind": "sandbox_attributes", "label": "atributos", "color": "#5cffb0", "glyph": "attributes", "tone": 5, "weight": 1.0},
    "entities": {"kind": "sandbox_entities", "label": "entidades", "color": "#b0ff5c", "glyph": "roko", "tone": 3, "weight": 1.0},
    "coleto": {"kind": "coleto", "label": "coleto", "color": "#7dff6b", "glyph": "coleto", "tone": 7, "weight": 0.9},
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
        # the actions handed out at the start: name -> the days it was acted on
        "given": {},
        # the one entity carried, None for none; `entities` are all ever met
        "entity": "roko",
        "affinity": {},
        "idle": 0,
        # the counters as they were at the last weighing of the personality
        "since": {},
        "flags": {},
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
    out["given"] = dict(state.get("given") or {})
    if "entity" not in state:
        # before one entity at a time: the first one met, roko for all of them
        out["entity"] = "roko"
    if out["entity"] is not None and out["entity"] not in voices.EVOVE:
        out["entity"] = "roko"
    out["affinity"] = dict(state.get("affinity") or {})
    out["since"] = dict(state.get("since") or {})
    out["flags"] = dict(state.get("flags") or {})
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
    # any act will do: one of the given ones, most likely, but a given action
    # deleted, or none to give, must not leave the story waiting forever
    "start": ("act", None, {
        "lines": lambda st, ev: [
            _say("roko", f"{ev['name']}."),
            _say("roko", "AS MARCAS SÃO SUAS. MAS DAQUI EU NÃO VI ACONTECER."),
            _say("roko", "DO OUTRO LADO DO VIDRO TEM ALGUÉM. É ESSA PESSOA QUE EU CONTO."),
            _say("roko", "O QUE ELA FAZ DE VERDADE? PROCURE NO SHOP."),
        ],
        "unlock": ["shop"], "next": "buy",
    }),
    "buy": ("buy", None, {
        "lines": [_say("roko", "ESSA FOI VOCÊ QUEM ESCOLHEU."), _say("roko", "QUANDO ACONTECER LÁ FORA, AJA.")],
        "next": "prove",
    }),
    "prove": ("act", lambda st, ev: ev.get("name") not in st["given"], {
        "lines": [_say("roko", "ESSA EU ACREDITO."), _say("roko", "PODE FALAR COMIGO.")],
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
        "lines": [_say("roko", "VOCÊ SEMPRE VOLTA. CONSTRUA ENTÃO A SUA INTERFACE."),
                  _say("system", "O TUTORIAL ACABOU. NA TELA INICIAL, O SANDBOX ESTÁ ABERTO.")],
        "unlock": ["build"], "next": "done",
    }),
}

STORY_ORDER = ["start", "buy", "prove", "listen", "plan", "walk", "build", "done"]


def story_progress(state: dict) -> tuple[int, int]:
    step = state.get("story", "done")
    return (STORY_ORDER.index(step) if step in STORY_ORDER else len(STORY_ORDER) - 1), len(STORY_ORDER) - 1


def _apply(state: dict, effect: dict, ev: dict, out: list[dict]) -> None:
    for m in effect.get("unlock", []):
        unlock(state, m)
    for e in effect.get("meet", []):
        meet(state, e)
    lines = effect.get("lines", [])
    out.extend(lines(state, ev) if callable(lines) else lines)
    if "next" in effect:
        state["story"] = effect["next"]


# the rules: each looks at the event and the state, and may change and say
def _selector(state: dict, ev: dict, rng: random.Random, out: list[dict]) -> None:
    if state["selector"] < 2 and counter(state, "turns") >= SELECTOR_2_TURNS:
        state["selector"] = 2
        out.append(_say("system", "O SELETOR MUDOU: DESLIZE."))
    elif state["selector"] == 2 and ev["kind"] == "visit" and ev.get("new_session") and rng.random() < SELECTOR_3_CHANCE:
        state["selector"] = 3
        out.append(_say("system", "O SELETOR MUDOU: TOQUE ONDE QUISER IR."))


_NUMBERS = {2: "DOIS", 3: "TRÊS", 4: "QUATRO", 5: "CINCO"}


def doubted(state: dict) -> list[str]:
    """The given actions roko does not believe yet."""
    return [n for n, days in (state.get("given") or {}).items() if days is not None]


def _doubt(state: dict, ev: dict, rng: random.Random, out: list[dict]) -> None:
    """An act on a given action: its day is kept, and it is believed on the
    third one. Until then the entity carried — roko, while the story is told —
    may say something about it, always during the story, unless the story just
    spoke. With no entity, the system notes it, mute."""
    name = ev.get("name")
    days = (state.get("given") or {}).get(name, None) if ev["kind"] == "act" else None
    if days is None:
        return
    spoke, new = bool(out), ev["day"] not in days
    if new:
        days.append(ev["day"])
    who = state.get("entity")
    if len(days) >= BELIEVE_AFTER_DAYS:
        state["given"][name] = None
        out.append(voices.say(who, "believe", rng, a=name, n=_NUMBERS.get(len(days), len(days))))
    elif spoke:
        return
    elif new and len(days) > 1:
        out.append(voices.say(who, "another_day", rng, a=name))
    elif state.get("story") != "done" or rng.random() < DOUBT_CHANCE:
        out.append(voices.say(who, "doubt", rng, a=name))


# what the personality test reads, from the counters: name -> how to read it
_SINCE = {
    "acts": lambda st: counter(st, "acts"),
    "talks": lambda st: counter(st, "talks"),
    "plans": lambda st: counter(st, "plans"),
    "buys": lambda st: counter(st, "buys"),
    "turns": lambda st: counter(st, "turns"),
    "days": lambda st: counter(st, "days"),
    "agenda": lambda st: counter(st, "opens", "agenda"),
    "attributes": lambda st: counter(st, "opens", "attributes"),
    "journey": lambda st: counter(st, "opens", "journey"),
    "shop": lambda st: counter(st, "opens", "shop"),
}

# each entity's trait, as what a session's differences add to its affinity
TRAITS = {
    "roko": lambda d: d["acts"] / 3 + d["agenda"] / 3,
    "eve": lambda d: d["talks"] / 2 + d["plans"] + d["attributes"] / 2,
    "osso": lambda d: 1.5 if d["days"] and d["acts"] else 0.0,
    "zira": lambda d: d["turns"] / 150 + d["journey"] / 2,
    "mura": lambda d: d["buys"] * 1.5 + d["shop"] / 3,
}


def carry(state: dict, entity: str | None, rng: random.Random, out: list[dict]) -> None:
    """The profile now carries `entity`, or none: the one leaving says goodbye
    — naming the next — and the one arriving says hello, naming the last."""
    was = state.get("entity")
    if was == entity:
        return
    if entity is None:
        out.append(voices.say(was, "abandon", rng))
        out.append(_say("system", "SEM ENTIDADE."))
    elif was is None:
        if entity in state["entities"]:
            out.append(voices.say(entity, "return", rng))
        else:
            out.append(_say("system", f"UMA ENTIDADE CHEGOU: {voices.name_of(entity)}."))
            out.append(voices.say(entity, "greet", rng))
    else:
        out.append(voices.say(was, "leave", rng, other=voices.name_of(entity)))
        out.append(voices.say(entity, "arrive", rng, other=voices.name_of(was)))
    state["entity"] = entity
    if entity is not None:
        meet(state, entity)


def _personality(state: dict, ev: dict, rng: random.Random, out: list[dict]) -> None:
    """At a new session after the story: what the profile did since the last
    weighing adds to each entity's affinity, and the entity carried may change,
    arrive or leave (see the constants)."""
    if ev["kind"] != "visit" or not ev.get("new_session") or state.get("story") != "done":
        return
    now = {k: read(state) for k, read in _SINCE.items()}
    since = state.get("since") or {}
    state["since"] = now
    if not since:
        # the first weighing: the story just ended, and roko has a head start
        state["affinity"] = {**{e: 0.0 for e in voices.EVOVE}, "roko": ROKO_START, **(state.get("affinity") or {})}
        return
    d = {k: max(0, now[k] - int(since.get(k, 0) or 0)) for k in now}
    aff = state.setdefault("affinity", {})
    for e in voices.EVOVE:
        aff[e] = round(float(aff.get(e, 0) or 0) * AFFINITY_DECAY + TRAITS[e](d), 3)
    active = d["acts"] + d["talks"] + d["plans"] + d["buys"]
    state["idle"] = 0 if active else int(state.get("idle", 0) or 0) + 1
    cur = state.get("entity")
    best = max(voices.EVOVE, key=lambda e: (aff[e], -voices.EVOVE.index(e)))
    if cur is not None and state["idle"] >= IDLE_SESSIONS:
        carry(state, None, rng, out)
    elif cur is None:
        if active and aff[best] >= ARRIVE:
            carry(state, best, rng, out)
    elif best != cur and aff[best] >= max(SWITCH_MIN, float(aff.get(cur, 0) or 0) * SWITCH_RATIO):
        carry(state, best, rng, out)


RULES = (_doubt, _personality, _selector)


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
            if state.get("day") != now.date().isoformat():
                state["day"] = now.date().isoformat()
                _count(state, "days")
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
        ev["day"] = now.date().isoformat()
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
            _apply(state, effect, ev, out)
    for rule in RULES:
        rule(state, ev, rng, out)
    if out:
        state["line"] = {**out[-1], "at": now.isoformat(timespec="seconds")}
    return out


def modes(state: dict) -> dict:
    """The modes of the app's first screen this profile can enter: the evove
    always, the sandbox once the story is told, the journey once its module
    is open."""
    return {
        "evove": True,
        "sandbox": state.get("story") == "done" or bool(state["flags"].get("sandbox")),
        "journey": "journey" in state["modules"],
    }


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
    elif upgrade == "sandbox":
        state["flags"]["sandbox"] = True
    elif upgrade == "fast":
        state["flags"]["fast"] = not state["flags"].get("fast")
    out = [_say("system", f"CÓDIGO ACEITO: {UPGRADES[upgrade]['label'].upper()}.")]
    if "entity" in UPGRADES[upgrade]:
        meet(state, "roko")
        unlock(state, "roko")
        carry(state, UPGRADES[upgrade]["entity"], random.Random(), out)
    return out


def take_build(state: dict, other: dict) -> list[dict]:
    """Another profile's evove, typed by its code: its modules, entities and
    selector, the story told. Counters and data stay this profile's own."""
    for m in other.get("modules") or []:
        unlock(state, m)
    for e in other.get("entities") or []:
        meet(state, e)
    if "entity" in other and other["entity"] in (*voices.EVOVE, None):
        state["entity"] = other["entity"]
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


def layout(modules: list[str], opens: dict[str, int], seed: int, table: dict[str, dict] | None = None) -> dict[str, list[list[float]]]:
    """Polygons in the home's grid, five squares across and seven down, for this
    session. Agir stands tall on the right, under the thumb; the rest tile the
    left in an order and with cuts drawn from `seed`, each sized by its weight
    — in `table`, the evove's modules by default — and by how often it is
    opened."""
    table = MODULES if table is None else table
    rng = random.Random(seed)
    out: dict[str, list[list[float]]] = {}
    xt = 2.75 + rng.uniform(-0.3, 0.2)
    xb = xt + rng.uniform(0.25, 0.65)
    rest = [m for m in modules if m != "act" and m in table]
    if "act" in modules:
        out["act"] = [[round(xt, 3), 0.0], [COLS, 0.0], [COLS, ROWS], [round(xb, 3), ROWS]]
    else:
        xt = xb = COLS
    if rest:
        rng.shuffle(rest)
        weights = {m: table[m]["weight"] * (1 + 0.35 * math.log1p(int(opens.get(m, 0) or 0))) for m in rest}
        _split([(0.0, 0.0), (xt, 0.0), (xb, ROWS), (0.0, ROWS)], rest, weights, rng, out)
    return out


MUTE_TILE = {"label": "—", "color": "#5f7373", "glyph": "mute"}


def carried(state: dict) -> dict | None:
    """The entity carried, as the interface shows it, or None."""
    e = voices.entity(state.get("entity") or "")
    return {"id": e["id"], "name": e["name"], "title": e["title"], "color": e["color"], "glyph": e["glyph"],
            "voice": e["voice"]} if e else None


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
    who = carried(state)
    for m in shown:
        d = MODULES[m]
        if d["kind"] == "entity":
            # the module of the entity carried, dressed as it is; mute with none
            d = {**d, **({"label": who["name"].lower(), "color": who["color"], "glyph": who["glyph"]} if who else MUTE_TILE)}
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
        "entity": who,
        "modes": modes(state),
        "story": {"step": state.get("story", "done"), "at": step, "of": steps, "done": state.get("story") == "done"},
        "doubted": doubted(state),
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
