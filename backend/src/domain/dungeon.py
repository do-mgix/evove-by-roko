"""The journey as a mode: a dungeon walked step by step, and a story in three acts.

Many people are trapped in a place far too big. All of them carry the same
technology: they act, gain abilities with it and hunt for entities, to get out
or to grow stronger. Every opponent met down there is one of them.

Each floor is a maze of corridors that turn, and of rooms, seen from inside
(`floor_map`): the profile walks it a step at a time — forward, or turning —
and in the room farthest from where it starts another person waits, until
the fight is started (src.domain.fight). The other rooms keep a chest each,
with an item. Steps come with time: walking the shortest way to whoever waits
takes as long as the journey's checkpoints say — ten minutes for each day of
the stage the floor stands for (1, 3, 7… days, as src.domain.journey counts
them), up to WALK_CAP — and a detour into a room costs the steps it takes.
The journey's button carries a hint when someone waits, or steps do.

- **Act 1**: the first floors, the profile's entity at its side. At the end,
  the way out: whoever leaves is gone — the journey, opened again, shows
  nothing but a code. Whoever stays goes on.
- **Act 2**: roko is gone, from here to the end. Without a way out there is
  only power left; at the end of the act an entity, nó, falls, and can be
  killed — becoming an entity oneself, which ends it again, with a code — or
  let go.
- **Act 3**: nó comes back, and not alone: the profile carries two entities
  at once. Each one it meets has an objective — beat people in a certain way,
  gather fragments — and finishing one brings the next. With all of them
  done, the last one missing shows up: the true roko. Beating him undoes the
  evove and frees everyone; the app closes by itself, and comes back with no
  code at all.

The journey has a level of its own: every blow that lands in a fight is
experience, three or four levels a fight, each raising the bar (from 100) and
the stats; the opponents mirror it, and the entities carried grow levels too.
A fight lost sends the journey back to its very beginning: the first floor,
the first level, nothing carried. A fight won may drop an item
(src.domain.items).

Kept inside the profile's evove state (`state["dungeon"]`). Pure logic — no I/O.
"""
from __future__ import annotations

import math
import random
from datetime import datetime

from src.domain import fight, names
from src.domain.journey import stage_days


ACT_FLOORS = 6
WALK_SECONDS_PER_DAY = 600
WALK_CAP = 6 * 3600
FAST = 60

# a floor's maze: cells of corridor or room, walls between them — 13×13 tiles
MAP_CELLS = 6
WALL, FLOOR, DOOR = "#", ".", "D"
# walls taken down past the maze's own, so it has a loop or two
LOOPS = 3
# the steps a floor starts with, before time brings the rest
FIRST_STEPS = 3
# the floors' looks, one for each floor of an act: tones of green and grey
THEMES = 6
# north, east, south, west
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))

# who comes after whom in the third act; each finished objective brings the next
CHAIN = ("no", "eve", "osso", "zira", "mura", "vela")

# entity -> (what to do, how many times)
OBJECTIVES = {
    "no": ("vença 3 lutas com nó ao seu lado", 3),
    "eve": ("vença uma luta sem curar", 1),
    "osso": ("vença com menos de 25% da barra", 1),
    "zira": ("vença em menos de 50 segundos de luta", 1),
    "mura": ("junte 3 fragmentos (caem das lutas vencidas com mura)", 3),
    "vela": ("vença jogando 8 truques numa luta", 1),
}
FRAGMENT_CHANCE = 0.5

FOE_ENTITIES = ("ALGO INCOMPREENSÍVEL", "AJUDA DO ALÉM", "UMA PRESENÇA", "O QUE NÃO TEM NOME")

# The journey's level: blows landed in fights are its experience, about three
# or four levels a fight, and each level raises the bar and the stats.
XP_NEED = 5
BASE = {"hp": 100, "resist": 100, "defense": 2, "absorb": 80, "bonus": 0}
PER_LEVEL = {"hp": 6, "resist": 5, "defense": 1, "bonus": 4}
DEFENSE_CAP = 60
# what an opponent's attack hits for, before its type's stars
FOE_DAMAGE = 6
# the chance an opponent's attack of a type that gathers more lands a critical
FOE_CRIT = 10
# an entity at level n: força and agilidade over its own (src.domain.fight)
ALLY_FORCA = 5
ALLY_AGILIDADE = 1


def level_stats(level: int) -> dict:
    """What a fighter of the journey's `level` has before items."""
    k = max(1, int(level)) - 1
    return {
        "hp": BASE["hp"] + PER_LEVEL["hp"] * k,
        "resist": BASE["resist"] + PER_LEVEL["resist"] * k,
        "defense": min(DEFENSE_CAP, BASE["defense"] + PER_LEVEL["defense"] * k),
        "absorb": BASE["absorb"],
        "bonus": BASE["bonus"] + PER_LEVEL["bonus"] * k,
    }


def ally_battle(battle: dict, level: int) -> dict:
    """An entity's battle stats at its journey `level`."""
    k = max(1, int(level)) - 1
    return {**battle, "forca": int(battle["forca"]) + ALLY_FORCA * k,
            "agilidade": min(12, int(battle["agilidade"]) + ALLY_AGILIDADE * k), "level": k + 1}


def fresh(now: datetime) -> dict:
    return {
        "act": 1,
        "floor": 1,
        "walk_from": now.isoformat(timespec="seconds"),
        "pos": None,
        "face": 1,
        "spent": 0,
        "seen": "",
        "opened": [],
        "seed": random.Random().randrange(1 << 30),
        "pending": None,
        "ending": None,
        "wins": 0,
        "losses": 0,
        "act3": None,
        "battle": None,
        "level": 1,
        "xp": 0,
        "allies": {},
        "items": [],
        "worn": {},
    }


def state_of(evove: dict, now: datetime) -> dict:
    d = evove.get("dungeon")
    if not isinstance(d, dict):
        d = evove["dungeon"] = fresh(now)
    for k, v in (("level", 1), ("xp", 0), ("allies", {}), ("items", []), ("worn", {}), ("pos", None), ("face", 1),
                 ("spent", 0), ("seen", ""), ("opened", [])):
        d.setdefault(k, v)
    if not d["pos"]:
        _enter(d)
    return d


def floor_in_act(d: dict) -> int:
    """1 to ACT_FLOORS in the first two acts; the third counts on."""
    f = int(d["floor"])
    return f - ACT_FLOORS * (int(d["act"]) - 1) if int(d["act"]) < 3 else f - 2 * ACT_FLOORS


def walk_seconds(d: dict, fast: bool) -> int:
    """How long walking the floor takes: the days of the stage it stands for."""
    stage = (floor_in_act(d) - 1) % ACT_FLOORS + 1
    secs = min(WALK_CAP, stage_days(stage) * WALK_SECONDS_PER_DAY)
    return max(1, secs // FAST) if fast else secs


def floor_map(d: dict) -> dict:
    """The floor's maze, the same every time it is asked for: a randomized
    spanning tree over the cells — two or three rooms counting as one cell
    each, a door on every wall the tree takes down next to a room — and a few
    walls more taken down for loops. The profile starts at the west edge; whoever
    waits stands in the middle of the room farthest from it; the other rooms
    keep a chest each. `need` is the steps of the shortest way to stand in
    front of them."""
    rng = random.Random(f"{d['seed']}:{d['floor']}:maze")
    n = MAP_CELLS
    size = 2 * n + 1
    g = [[WALL] * size for _ in range(size)]
    # the rooms: 2×2 or 2×3 cells, apart from each other and from the west edge
    rooms: list[tuple[int, int, int, int]] = []
    room_of: dict[tuple[int, int], int] = {}
    want = rng.randint(2, 3)
    for _ in range(60):
        if len(rooms) >= want:
            break
        rw, rh = rng.choice(((2, 2), (2, 2), (3, 2), (2, 3)))
        rx, ry = rng.randrange(1, n - rw + 1), rng.randrange(0, n - rh + 1)
        if any((x, y) in room_of for x in range(rx - 1, rx + rw + 1) for y in range(ry - 1, ry + rh + 1)):
            continue
        for x in range(rx, rx + rw):
            for y in range(ry, ry + rh):
                room_of[(x, y)] = len(rooms)
        rooms.append((rx, ry, rw, rh))
    for (x, y) in [(x, y) for x in range(n) for y in range(n)]:
        g[2 * y + 1][2 * x + 1] = FLOOR
    for (x, y), r in room_of.items():
        # inside a room, the walls between its cells are floor too
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            if all(room_of.get((x + a, y + b)) == r for a, b in ((dx, 0), (0, dy), (dx, dy))):
                g[2 * y + 1 + dy][2 * x + 1 + dx] = FLOOR

    def node(c):
        return ("room", room_of[c]) if c in room_of else c

    parent: dict = {}

    def find(a):
        while parent.get(a, a) != a:
            a = parent[a]
        return a

    edges = [((x, y), (x + dx, y + dy)) for x in range(n) for y in range(n) for dx, dy in ((1, 0), (0, 1))
             if x + dx < n and y + dy < n and node((x, y)) != node((x + dx, y + dy))]
    rng.shuffle(edges)
    left = []
    for a, b in edges:
        ra, rb = find(node(a)), find(node(b))
        if ra == rb:
            left.append((a, b))
            continue
        parent[ra] = rb
        _open(g, a, b, a in room_of or b in room_of)
    for a, b in rng.sample(left, min(LOOPS, len(left))):
        _open(g, a, b, a in room_of or b in room_of)
    start = (1, 2 * rng.choice([y for y in range(n) if (0, y) not in room_of]) + 1)
    dist = _distances(g, start, None)
    centers = [(2 * rx + rw, 2 * ry + rh) for rx, ry, rw, rh in rooms]
    boss = max(centers, key=lambda c: (dist.get(c, -1), c)) if centers else max(dist, key=lambda c: (dist[c], c))
    chests = [list(c) for c in centers if c != boss]
    near = _distances(g, start, boss)
    need = min((near[(boss[0] + dx, boss[1] + dy)] for dx, dy in DIRS if (boss[0] + dx, boss[1] + dy) in near), default=1)
    return {"size": size, "tiles": ["".join(r) for r in g], "start": list(start), "boss": list(boss),
            "chests": chests, "rooms": [list(r) for r in rooms], "need": max(1, need)}


def _open(g: list[list[str]], a: tuple[int, int], b: tuple[int, int], door: bool) -> None:
    """Takes down the wall between cells `a` and `b`: a door, by a room."""
    g[a[1] + b[1] + 1][a[0] + b[0] + 1] = DOOR if door else FLOOR


def passable(m: dict, x: int, y: int) -> bool:
    if not (0 <= x < m["size"] and 0 <= y < m["size"]) or [x, y] == m["boss"]:
        return False
    return m["tiles"][y][x] != WALL


def _distances(g: list[list[str]], start: tuple[int, int], block: tuple[int, int] | None) -> dict:
    out = {start: 0}
    todo = [start]
    for c in todo:
        for dx, dy in DIRS:
            nxt = (c[0] + dx, c[1] + dy)
            if nxt in out or nxt == block or g[nxt[1]][nxt[0]] == WALL:
                continue
            out[nxt] = out[c] + 1
            todo.append(nxt)
    return out


def theme(d: dict) -> int:
    """Which of the floors' looks this one wears."""
    return (int(d["floor"]) - 1) % THEMES


def _enter(d: dict) -> None:
    """The profile at the floor's start, facing east, nothing walked."""
    m = floor_map(d)
    d["pos"], d["face"], d["spent"], d["opened"] = list(m["start"]), 1, 0, []
    d["seen"] = ""
    _look(d, m)


def _look(d: dict, m: dict) -> None:
    """What the profile sees from where it stands joins the map it drew: the
    tiles around it, and ahead as far as the corridor goes."""
    size = m["size"]
    seen = list(d.get("seen") or "0" * size * size)
    if len(seen) != size * size:
        seen = ["0"] * size * size
    x, y = d["pos"]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if 0 <= x + dx < size and 0 <= y + dy < size:
                seen[(y + dy) * size + x + dx] = "1"
    fx, fy = DIRS[int(d["face"])]
    for k in range(1, 5):
        cx, cy = x + fx * k, y + fy * k
        if not (0 <= cx < size and 0 <= cy < size):
            break
        seen[cy * size + cx] = "1"
        if m["tiles"][cy][cx] == WALL or [cx, cy] == m["boss"]:
            break
    d["seen"] = "".join(seen)


def steps(d: dict, now: datetime, fast: bool) -> dict:
    """The floor's steps: how many came with time — a few to start, then the
    shortest way to whoever waits over the floor's walk — how many are left,
    and in how many seconds the next one comes."""
    m = floor_map(d)
    secs = walk_seconds(d, fast)
    elapsed = max(0.0, (now - datetime.fromisoformat(d["walk_from"])).total_seconds())
    every = secs / m["need"]
    came = FIRST_STEPS + int(elapsed / every)
    left = max(0, came - int(d.get("spent", 0) or 0))
    return {"left": left, "came": came, "spent": int(d.get("spent", 0) or 0), "need": m["need"],
            "every": round(every, 2), "next_in": max(0, int(math.ceil((came - FIRST_STEPS + 1) * every - elapsed)))}


def walk(d: dict, moves: str, now: datetime, fast: bool) -> list[dict]:
    """The profile's moves, in order — F a step forward, L and R a quarter turn,
    B a half one — up to the first that cannot be made: a step into a wall, or
    with none left. Returns what happened on the way: the chests stepped on."""
    if d.get("ending") or d.get("pending"):
        return []
    m = floor_map(d)
    left = steps(d, now, fast)["left"]
    out = []
    opened = d.setdefault("opened", [])
    for mv in str(moves or "")[:64].upper():
        if mv in "LRB":
            d["face"] = (int(d["face"]) + {"L": 3, "R": 1, "B": 2}[mv]) % 4
        elif mv == "F":
            dx, dy = DIRS[int(d["face"])]
            x, y = d["pos"][0] + dx, d["pos"][1] + dy
            if left <= 0 or not passable(m, x, y):
                break
            d["pos"] = [x, y]
            d["spent"] = int(d.get("spent", 0) or 0) + 1
            left -= 1
            if [x, y] in m["chests"] and [x, y] not in opened:
                opened.append([x, y])
                out.append({"chest": [x, y]})
        else:
            break
        _look(d, m)
    return out


def waiting(d: dict, now: datetime, fast: bool) -> bool:
    """Whether the profile stands in front of someone, waiting for the fight."""
    if d.get("ending") or d.get("pending") or not d.get("pos"):
        return False
    bx, by = floor_map(d)["boss"]
    return abs(d["pos"][0] - bx) + abs(d["pos"][1] - by) == 1


def alert(d: dict | None, now: datetime, fast: bool) -> bool:
    """What the journey's button hints at: someone waits, a choice does, or
    steps to walk."""
    if not isinstance(d, dict) or d.get("ending"):
        return False
    return bool(d.get("pending")) or waiting(d, now, fast) or steps(d, now, fast)["left"] >= FIRST_STEPS


# ---------------------------------------------------------------- who waits

def final(d: dict) -> bool:
    """Whether the floor's opponent is the true roko."""
    a3 = d.get("act3") or {}
    return int(d["act"]) == 3 and bool(a3) and set(a3.get("done") or []) >= set(CHAIN)


def opponent(d: dict) -> dict:
    """Who waits at the end of the floor: a name, a title, and what helps them."""
    rng = random.Random(f"{d['seed']}:{d['floor']}:foe")
    act, k = int(d["act"]), floor_in_act(d)
    if final(d):
        return {"name": "ROKO", "title": "O VERDADEIRO", "entity": "roko", "kind": "roko"}
    if act == 1 and k == ACT_FLOORS:
        return {"name": "GUARDIÃO", "title": "DA SAÍDA", "entity": None, "label": rng.choice(FOE_ENTITIES), "kind": "guard"}
    if act == 2 and k == ACT_FLOORS:
        return {"name": "NÓ", "title": "O QUE PRENDE", "entity": "no", "kind": "entity"}
    return {"name": names.nickname(rng), "title": "PRESO COMO VOCÊ", "entity": None,
            "label": rng.choice(FOE_ENTITIES), "kind": "person"}


def companions(d: dict, carried: str | None) -> list[str]:
    """The entities on the profile's side: the one it carries in the first act
    — not roko any more in the second — and the pair chosen in the third."""
    act = int(d["act"])
    if act == 3:
        return list((d.get("act3") or {}).get("pair") or [])[:2]
    if carried is None or (act == 2 and carried == "roko"):
        return []
    return [carried]


def foe_hp_factor(d: dict) -> float:
    if final(d):
        return 4.4
    # the first floors gentle — losing starts the journey over — the rest steeper
    base = {1: 1.4, 2: 2.9, 3: 3.2}[min(3, int(d["act"]))]
    per = 0.25 if int(d["act"]) == 1 else 0.15
    return base + per * min(ACT_FLOORS - 1, floor_in_act(d) - 1)


# ---------------------------------------------------------------- the story

def intro(d: dict) -> list[str]:
    """What is told on arriving at the floor."""
    act, k = int(d["act"]), floor_in_act(d)
    if final(d):
        return ["TODAS AS ENTIDADES ESTÃO AQUI. MENOS UMA.", "NO FIM DO CORREDOR, ALGUÉM CONSTRUIU TUDO ISSO."]
    if act == 1 and k == 1:
        return ["VOCÊ ACORDA NUM LUGAR GRANDE DEMAIS.",
                "HÁ OUTROS PRESOS AQUI. TODOS CARREGAM A MESMA TECNOLOGIA.",
                "ELES AGEM, GANHAM HABILIDADES E PROCURAM ENTIDADES.",
                "UNS QUEREM SAIR. OUTROS, MAIS PODER."]
    if act == 2 and k == 1:
        return ["A PORTA SE FECHOU ATRÁS DE VOCÊ.", "ROKO NÃO RESPONDE MAIS. ROKO SUMIU.",
                "SEM SAÍDA, SÓ RESTA O PODER. OS OUTROS AGORA CAÇAM ENTIDADES."]
    if act == 3 and k == 1:
        return ["NÓ VOLTOU. E NÃO VEIO SOZINHO.", "AGORA VOCÊ CARREGA DUAS ENTIDADES.",
                "CADA UMA QUER ALGUMA COISA. DÊ A ELAS, E ELAS TRAZEM AS OUTRAS."]
    return [{1: "O CORREDOR CONTINUA.", 2: "MAIS FUNDO.", 3: "OS FIOS DE NÓ AINDA ESTÃO NAS PAREDES."}[min(3, act)]]


def waiting_line(d: dict) -> str:
    o = opponent(d)
    if o["kind"] == "roko":
        return "ROKO. O VERDADEIRO. ELE ESPERA HÁ MAIS TEMPO QUE TODOS."
    if o["kind"] == "guard":
        return "O GUARDIÃO DA SAÍDA ESTÁ PARADO NA SUA FRENTE."
    if o["kind"] == "entity":
        return "NÓ ESTÁ PARADO NA SUA FRENTE. UMA ENTIDADE, NÃO UMA PESSOA."
    return f"{o['name']} ESTÁ PARADO NA SUA FRENTE. ELE TAMBÉM QUER SAIR."


CHOICES = {
    "door": {"text": "UMA PORTA. DO OUTRO LADO, O MUNDO DE ANTES.",
             "options": [{"id": "leave", "label": "ir embora"}, {"id": "stay", "label": "ficar"}]},
    "entity": {"text": "NÓ ESTÁ CAÍDO. VOCÊ PODE TOMAR O QUE ELE É.",
               "options": [{"id": "become", "label": "tornar-se entidade"}, {"id": "escape", "label": "deixar escapar"}]},
}

ENDINGS = {
    "left": ["VOCÊ SAIU.", "AQUI DENTRO, SÓ FICOU UM CÓDIGO."],
    "entity": ["VOCÊ MATOU NÓ E TOMOU O QUE ELE ERA.", "AGORA VOCÊ É UMA ENTIDADE. NÃO HÁ MAIS CAMINHO. SÓ UM CÓDIGO."],
    "free": ["O EVOVE SE DESFAZ.", "TODOS ESTÃO LIVRES."],
}


def _next_floor(d: dict, now: datetime) -> None:
    d["floor"] = int(d["floor"]) + 1
    d["walk_from"] = now.isoformat(timespec="seconds")
    _enter(d)


def _start_act3(d: dict, carried: str | None) -> None:
    first = carried if carried in CHAIN and carried != "no" else "eve"
    d["act3"] = {"unlocked": ["no", first], "done": [], "pair": ["no", first], "progress": {}, "fragments": 0}


def won(d: dict, result: dict, rng: random.Random, now: datetime) -> list[str]:
    """A fight won: the floor is passed, or a choice waits. Returns what is told."""
    d["wins"] = int(d.get("wins", 0) or 0) + 1
    out: list[str] = []
    kind = opponent(d)["kind"]
    if kind == "roko":
        d["ending"] = "free"
        return list(ENDINGS["free"])
    if int(d["act"]) == 3:
        out += _objectives(d, result, rng)
    if kind == "guard":
        d["pending"] = "door"
        return out + [CHOICES["door"]["text"]]
    if kind == "entity":
        d["pending"] = "entity"
        return out + [CHOICES["entity"]["text"]]
    _next_floor(d, now)
    return out


def lost(d: dict, now: datetime) -> None:
    """A fight lost: the journey starts over — the first floor of the first act,
    on new floors, the first level, no items, entities back at their first
    level. Only the count of wins and losses stays."""
    wins, losses = int(d.get("wins", 0) or 0), int(d.get("losses", 0) or 0) + 1
    d.clear()
    d.update(fresh(now))
    d["wins"], d["losses"] = wins, losses
    _enter(d)


def _objectives(d: dict, result: dict, rng: random.Random) -> list[str]:
    """What a third-act win does for the objectives of the pair at its side."""
    a3 = d["act3"]
    out = []
    pair = list(a3.get("pair") or [])
    prog = a3.setdefault("progress", {})
    you_hp, max_hp = result.get("hp", [0])[0], max(1, int(result.get("max_hp", 1) or 1))
    for e in pair:
        if e in a3["done"]:
            continue
        hit = {
            "no": True,
            "eve": result.get("heals", [0])[0] == 0,
            "osso": you_hp * 4 < max_hp,
            "zira": result.get("ticks", 9999) < 500,
            "mura": rng.random() < FRAGMENT_CHANCE,
            "vela": result.get("tricks", [0])[0] >= 8,
        }[e]
        if not hit:
            continue
        prog[e] = int(prog.get(e, 0) or 0) + 1
        if e == "mura":
            a3["fragments"] = int(a3.get("fragments", 0) or 0) + 1
            out.append(f"UM FRAGMENTO CAIU. MURA GUARDA ({prog[e]}/{OBJECTIVES['mura'][1]}).")
        if prog[e] >= OBJECTIVES[e][1]:
            a3["done"].append(e)
            out.append(f"{e.upper()} CONSEGUIU O QUE QUERIA.")
            nxt = next((c for c in CHAIN if c not in a3["unlocked"]), None)
            if nxt:
                a3["unlocked"].append(nxt)
                out.append(f"UMA ENTIDADE APARECEU: {nxt.upper()}.")
    if set(a3["done"]) >= set(CHAIN):
        out.append("TODAS AS ENTIDADES ESTÃO COM VOCÊ. FALTA UMA.")
    return out


def choose(d: dict, option: str, carried: str | None, now: datetime) -> list[str]:
    """The answer to the choice that waits. Raises ValueError when there is
    none, or the option is not one of it."""
    pending = d.get("pending")
    if pending not in CHOICES or option not in {o["id"] for o in CHOICES[pending]["options"]}:
        raise ValueError("no such choice")
    d["pending"] = None
    if option == "leave":
        d["ending"] = "left"
        return list(ENDINGS["left"])
    if option == "become":
        d["ending"] = "entity"
        return list(ENDINGS["entity"])
    if option == "stay":
        d["act"] = 2
        _next_floor(d, now)
        return ["VOCÊ FICOU. ATO 2."]
    d["act"] = 3
    _start_act3(d, carried)
    _next_floor(d, now)
    return ["NÓ ESCAPA ENTRE OS FIOS. ATO 3."]


def set_pair(d: dict, pair: list[str]) -> None:
    a3 = d.get("act3")
    if not a3:
        raise ValueError("only in the third act")
    pair = [p for p in dict.fromkeys(pair) if p in a3["unlocked"]][:2]
    if len(pair) != 2:
        raise ValueError("choose two entities met")
    a3["pair"] = pair


# ---------------------------------------------------------------- the foe

def foe_setup(d: dict, abilities: list[dict], defense: float, entity_battle) -> dict:
    """The opponent's side of the fight, mirrored on the profile's journey
    level: the people trapped here grew as it did, and grow in the fight as it
    does. `abilities` are its attacks (from src.domain.battle's boss of the
    floor), `entity_battle(id)` an entity's battle stats."""
    rng = random.Random(f"{d['seed']}:{d['floor']}:fight")
    o = opponent(d)
    level = int(d.get("level", 1)) + (2 if o["kind"] == "roko" else 0)
    st = level_stats(level)
    hp = int(st["hp"] * foe_hp_factor(d))
    moves = []
    for a in abilities[:3]:
        # past the first act, a type that gathers more hits harder, and may
        # land a critical
        up = a.get("star", 1) - 1 if int(d["act"]) > 1 else 0
        moves.append({"name": a["name"], "dmg": FOE_DAMAGE + 2 * up, "cd": rng.randint(100, 120), "crit": FOE_CRIT if up else 0})
    stage = floor_in_act(d)
    if o.get("entity"):
        ents = [{"id": o["entity"], "name": o["name"], **entity_battle(o["entity"]), "level": 1}]
    else:
        ents = [{"id": "foe", "name": o["label"], "forca": 40 + min(10, stage + int(d["act"]) - 1),
                 "agilidade": 3 + min(5, stage // 2), "skill": rng.choice(fight.SKILLS), "ability": "interferencia", "level": 1}]
    return {
        "name": o["name"], "hp": hp, "max_hp": hp, "resist": st["resist"], "defense": int(round(defense * 100)),
        "absorb": st["absorb"], "bonus": st["bonus"], "moves": moves,
        "heal": {"name": "RECOMPOR", "amount": hp * 12 // 100, "cd": 180},
        "entities": ents, "tricks": True, "level": level, "xp": 0, "xp_need": XP_NEED, "per_level": PER_LEVEL,
    }


def view(d: dict, now: datetime, fast: bool) -> dict:
    m = floor_map(d)
    out = {
        "act": int(d["act"]),
        "floor": int(d["floor"]),
        "floor_in_act": floor_in_act(d),
        "of": ACT_FLOORS if int(d["act"]) < 3 else None,
        "map": {**m, "chests": [c for c in m["chests"] if c not in (d.get("opened") or [])]},
        "pos": d["pos"],
        "face": int(d["face"]),
        "seen": d.get("seen") or "",
        "steps": steps(d, now, fast),
        "theme": theme(d),
        "walk_seconds": walk_seconds(d, fast),
        "waiting": waiting(d, now, fast),
        "opponent": {k: v for k, v in opponent(d).items() if k in ("name", "title", "kind")},
        "pending": {"kind": d["pending"], **CHOICES[d["pending"]]} if d.get("pending") in CHOICES else None,
        "ending": d.get("ending"),
        "ending_lines": ENDINGS.get(d.get("ending") or "", []),
        "intro": intro(d),
        "waiting_line": waiting_line(d),
        "wins": int(d.get("wins", 0) or 0),
        "losses": int(d.get("losses", 0) or 0),
        "level": int(d.get("level", 1)),
        "xp": int(d.get("xp", 0)),
        "xp_need": XP_NEED,
        "stats": level_stats(int(d.get("level", 1))),
        "fast": fast,
    }
    a3 = d.get("act3")
    if a3:
        out["act3"] = {
            "pair": a3["pair"],
            "unlocked": a3["unlocked"],
            "done": a3["done"],
            "fragments": a3.get("fragments", 0),
            "objectives": [{"entity": e, "text": OBJECTIVES[e][0], "need": OBJECTIVES[e][1],
                            "have": int((a3.get("progress") or {}).get(e, 0) or 0), "done": e in a3["done"],
                            "unlocked": e in a3["unlocked"]} for e in CHAIN],
        }
    return out
