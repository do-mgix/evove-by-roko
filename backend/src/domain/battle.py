"""The journey's autobattler: bosses between the checkpoints.

Every stretch of a stage — from one point to the next, the last one up to the
checkpoint — holds a boss. A boss is drawn from a seed (the profile, its run,
the stage, the stretch), so it is the same boss every time it is looked at.

A boss has generic stats — hp, mp, attack, special attack, defense — and one to
three types, which are attributes of the graph: CARDIOVASCULAR-DOCS. The types
are what it attacks with and also where it is weak. Its abilities are actions
filed under its types, each with a Greek letter: CAMINHADA (ω). The higher the
star level of the type (the more it gathers, like Físico), the rarer the letter
and the harder the blow.

The profile attacks with its actions. Actions hold no rank of their own, only a
count of marks, so an attack takes the rank of the attribute the action is
registered under: CORRIDA (α) hits for 15, CORRIDA (δ) for 312. Against a type,
the closer the kinship between the attack's attribute and the type, the larger
the multiplier: the same attribute ×4, its parent or its child ×2, a grandparent
or grandchild ×1.25.

Before the fight the autobattler picks the best lineup by itself — the four
attacks that hit this boss hardest — and then the fight plays out on its own.
A quick act on something of the boss's type is the way to a bonus; the profile
can always go in with its specialities and no bonus at all.

Pure logic — no I/O. The host loads the tree, the templates and the profile's
attribute totals, and stores the result.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.domain.attributes import MAX_RANK, RANK_LETTERS, RANK_NAMES, Tree


RANK_DAMAGE_BASE = 15
RANK_DAMAGE_GROWTH = 2.75

KINSHIP = {"igual": 4.0, "pai": 2.0, "filho": 2.0, "avô": 1.25, "neto": 1.25}

LINEUP_SIZE = 4
MAX_ROUNDS = 6
SPECIAL_MP = 10

# what a victory pays, in points, within the bounds of any gain
WIN_POINTS_BASE = 100
WIN_POINTS_PER_STAGE = 100
WIN_POINTS_PER_SLOT = 50
WIN_POINTS_MAX = 2000

_SYLLABLES = ("vor", "gath", "zel", "mok", "thar", "ix", "dru", "kael", "sor", "nyx",
              "bra", "ul", "gor", "vex", "ra", "ku", "zar", "om", "tey", "rho")


def rank_damage(rank_index: int) -> int:
    """What an attack of rank `rank_index` hits for: α 15, β 41, γ 113, δ 312…"""
    return int(round(RANK_DAMAGE_BASE * RANK_DAMAGE_GROWTH ** max(0, min(rank_index, MAX_RANK))))


def letter(rank_index: int) -> str:
    return RANK_LETTERS[max(0, min(rank_index, MAX_RANK))]


def _parents(tree: Tree, key: str) -> set[str]:
    return {p for p, _w, _primary in tree.parents.get(key, [])}


def kinship(tree: Tree, attack: str, target: str) -> tuple[float, str | None]:
    """The multiplier of an attack whose attribute is `attack` on the type
    `target`, and the kinship that gives it."""
    if attack == target:
        return KINSHIP["igual"], "igual"
    up = _parents(tree, target)
    if attack in up:
        return KINSHIP["pai"], "pai"
    if target in _parents(tree, attack):
        return KINSHIP["filho"], "filho"
    if any(attack in _parents(tree, p) for p in up):
        return KINSHIP["avô"], "avô"
    if any(target in _parents(tree, p) for p in _parents(tree, attack)):
        return KINSHIP["neto"], "neto"
    return 1.0, None


@dataclass
class Boss:
    name: str
    stage: int
    slot: int
    rank_index: int
    types: list[dict]
    hp: int
    mp: int
    attack: int
    defense: float
    abilities: list[dict] = field(default_factory=list)

    def view(self) -> dict:
        return {
            "name": self.name,
            "stage": self.stage,
            "slot": self.slot,
            "rank": letter(self.rank_index),
            "rank_name": RANK_NAMES[self.rank_index],
            "type": "-".join(t["name"].upper() for t in self.types),
            "types": self.types,
            "hp": self.hp,
            "mp": self.mp,
            "attack": self.attack,
            "special": max((a["power"] for a in self.abilities), default=self.attack),
            "defense": round(self.defense * 100),
            "abilities": self.abilities,
        }


def boss_seed(user_id: int, run: int, stage: int, slot: int) -> str:
    return f"{user_id}:{run}:{stage}:{slot}"


def make_boss(tree: Tree, templates: dict, seed: str, stage: int, slot: int) -> Boss:
    """The boss of stretch `slot` of `stage`. `templates` is
    {ACTION_NAME: {"parent": node_key, ...}}, the catalog its abilities come from."""
    rng = random.Random(seed)
    rank_index = min(MAX_RANK, (max(1, stage) - 1) // 2)

    candidates = sorted(k for k in tree.nodes_by_key if 1 <= tree.degree(k) <= 3 and not tree.is_leaf(k))
    if not candidates:
        candidates = sorted(tree.nodes_by_key)
    most = 1 if stage < 3 else 2 if stage < 5 else 3
    count = min(len(candidates), rng.randint(1, most))
    picked = rng.sample(candidates, count) if candidates else []
    types = [{"key": k, "name": tree.nodes_by_key[k].name, "star": tree.star(k)} for k in picked]

    attack = 1 + rank_index // 3
    by_parent: dict[str, list[str]] = {}
    for name, meta in templates.items():
        if meta.get("parent") and not meta.get("log_only"):
            by_parent.setdefault(meta["parent"], []).append(name)
    abilities = []
    for t in types:
        under = {t["key"]} | tree.descendants(t["key"])
        names = sorted(n for k in under for n in by_parent.get(k, []))
        base = rng.choice(names) if names else t["name"].upper()
        ability_rank = min(MAX_RANK, rank_index + t["star"] - 1)
        abilities.append({
            "name": f"{base} ({letter(ability_rank)})",
            "type": t["key"],
            "rank": letter(ability_rank),
            "power": attack + t["star"] - 1,
        })

    name = "".join(rng.choice(_SYLLABLES) for _ in range(rng.randint(2, 3))).upper()
    hp = int(round(4 * rank_damage(rank_index) * (1 + 0.15 * slot)))
    return Boss(
        name=name,
        stage=stage,
        slot=slot,
        rank_index=rank_index,
        types=types,
        hp=hp,
        mp=20 + 10 * rank_index,
        attack=attack,
        defense=rng.choice((0.0, 0.05, 0.1, 0.15, 0.2)),
        abilities=abilities,
    )


def moves_for(tree: Tree, templates: dict, actions: dict, node_rank) -> list[dict]:
    """Every attack the profile has: one per action registered under an
    attribute, at that attribute's rank. `node_rank(key)` is the rank index of
    an attribute; a patch attacks as its base."""
    out = []
    for action_id, a in sorted(actions.items()):
        if a.get("deleted"):
            continue
        base = actions.get(a.get("base_action_id")) if a.get("base_action_id") else a
        meta = templates.get(str((base or {}).get("name", "")).upper()) or {}
        key = meta.get("parent")
        if not key or meta.get("log_only") or key not in tree.nodes_by_key:
            continue
        rank_index = int(node_rank(key))
        out.append({
            "action_id": action_id,
            "name": f"{a.get('name')} ({letter(rank_index)})",
            "attribute": key,
            "attribute_name": tree.nodes_by_key[key].name,
            "rank": letter(rank_index),
            "rank_index": rank_index,
            "base_damage": rank_damage(rank_index),
        })
    return out


def score_move(tree: Tree, move: dict, boss: Boss, damage_bonus: float = 0.0) -> dict:
    """A move against this boss: its best multiplier over the boss's types and
    the damage one hit does through the boss's defense."""
    best, relation, against = 1.0, None, None
    for t in boss.types:
        m, rel = kinship(tree, move["attribute"], t["key"])
        if m > best:
            best, relation, against = m, rel, t["name"]
    hit = int(round(move["base_damage"] * best * (1 + damage_bonus) * (1 - boss.defense)))
    return {**move, "multiplier": best, "kinship": relation, "against": against, "damage": max(1, hit)}


def lineup(tree: Tree, moves: list[dict], boss: Boss, damage_bonus: float = 0.0) -> list[dict]:
    """The autobattler's choice: the LINEUP_SIZE moves that hit this boss hardest."""
    scored = [score_move(tree, m, boss, damage_bonus) for m in moves]
    scored.sort(key=lambda m: (-m["damage"], m["name"]))
    return scored[:LINEUP_SIZE]


def fight(boss: Boss, chosen: list[dict], hp: int, armor: int = 0) -> dict:
    """Plays the fight out. The profile strikes first, its lineup in turn; the
    boss answers with its attack, or every third round with an ability while its
    mp lasts. The profile wins by bringing the boss to 0 within MAX_ROUNDS."""
    boss_hp, mp, my_hp = boss.hp, boss.mp, hp
    log: list[dict] = []
    dealt = taken = 0
    won = False
    for r in range(MAX_ROUNDS):
        move = chosen[r % len(chosen)]
        boss_hp = max(0, boss_hp - move["damage"])
        dealt += move["damage"]
        bonus = f" ×{move['multiplier']:g}" if move["multiplier"] > 1 else ""
        log.append({"who": "you", "text": f"{move['name']}{bonus}", "damage": move["damage"], "boss_hp": boss_hp, "hp": my_hp})
        if boss_hp <= 0:
            won = True
            break
        ability = boss.abilities[r % len(boss.abilities)] if boss.abilities else None
        if ability and r % 3 == 2 and mp >= SPECIAL_MP:
            mp -= SPECIAL_MP
            blow, text = ability["power"], f"{boss.name} USA {ability['name']}"
        else:
            blow, text = boss.attack, f"{boss.name} ATACA"
        blow = max(0, blow - armor)
        my_hp = max(0, my_hp - blow)
        taken += blow
        log.append({"who": "boss", "text": text, "damage": blow, "boss_hp": boss_hp, "hp": my_hp})
        if my_hp <= 0:
            break
    return {"won": won, "log": log, "dealt": dealt, "taken": taken, "rounds": min(len(log), MAX_ROUNDS * 2), "boss_hp": boss_hp}


def win_points(stage: int, slot: int, bonus: float = 0.0) -> int:
    base = WIN_POINTS_BASE + WIN_POINTS_PER_STAGE * stage + WIN_POINTS_PER_SLOT * slot
    return min(WIN_POINTS_MAX, int(round(base * (1 + bonus))))
