"""The journey's items: what the people beaten leave behind.

Every opponent fights with abilities named after catalog actions
(src.domain.battle), and a fight won may drop an item made of one of them: a
ferramenta, a marca or a faixa of CORRIDA, of PIANO… Three slots, one item
worn in each, and each mostly about one thing:

- **arma** (a ferramenta): more damage, in percent;
- **acessório** (a marca): defense;
- **cabeça** (a faixa): max hp.

An item has a level — the journey's level when it dropped, give or take — and
its value grows with it. Worn while its own action is among the attacks the
profile fights with, it counts 1.5 to 2 times (its `synergy`). Items of the
same name and level pile up; the ones far below the journey's level sell
themselves for points; and one key wears the best of each slot.

Kept inside the dungeon's state (`d["items"]`, `d["worn"]`). Pure logic — no I/O.
"""
from __future__ import annotations

import random
import re


SLOTS = ("arma", "acessorio", "cabeca")
NOUN = {"arma": "FERRAMENTA", "acessorio": "MARCA", "cabeca": "FAIXA"}
DROP_CHANCE = 0.75
# an item this many levels below the journey's sells itself
SELL_BELOW = 6
SELL_POINTS_PER_LEVEL = 10


def value(slot: str, level: int) -> int:
    """What an item of `slot` and `level` adds: damage %, defense or hp."""
    level = max(1, int(level))
    if slot == "arma":
        return 5 + (3 * level) // 2
    if slot == "acessorio":
        return 2 + level // 2
    return 8 + 3 * level


def effective(item: dict, attacks: set[str]) -> int:
    """An item's value, its synergy counted when its action is fought with."""
    v = int(item["value"])
    return int(v * float(item.get("synergy", 1.5))) if item.get("action") in attacks else v


def _base(name: str) -> str:
    """`CAMINHADA (ω)` → `CAMINHADA`."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(name or "")).strip().upper()


def drop(rng: random.Random, abilities: list[str], level: int, chance: float = DROP_CHANCE) -> dict | None:
    """What a beaten opponent may leave — or a chest keep: an item of one of
    its abilities."""
    names = [_base(a) for a in abilities if _base(a)]
    if not names or rng.random() >= chance:
        return None
    action = rng.choice(names)
    slot = rng.choice(SLOTS)
    lv = max(1, int(level) + rng.choice((-1, 0, 0, 1)))
    return {
        "name": f"{NOUN[slot]} DE {action}",
        "slot": slot,
        "action": action,
        "level": lv,
        "value": value(slot, lv),
        "synergy": round(1.5 + rng.random() * 0.5, 2),
    }


def add(d: dict, item: dict, rng: random.Random) -> dict:
    """Puts `item` in the inventory, on the pile of its twins when there is one."""
    items = d.setdefault("items", [])
    twin = next((i for i in items if i["name"] == item["name"] and i["level"] == item["level"]), None)
    if twin:
        twin["count"] = int(twin.get("count", 1)) + 1
        return twin
    item = {**item, "id": f"{rng.randrange(16 ** 6):06x}", "count": 1}
    items.append(item)
    return item


def sell_low(d: dict, level: int) -> tuple[int, int]:
    """The items far below `level`, not worn, sold by themselves. Returns how
    many went and the points they paid."""
    worn = set((d.get("worn") or {}).values())
    keep, sold, points = [], 0, 0
    for i in d.get("items") or []:
        if i["id"] not in worn and int(i["level"]) <= int(level) - SELL_BELOW:
            n = int(i.get("count", 1))
            sold += n
            points += n * SELL_POINTS_PER_LEVEL * int(i["level"])
        else:
            keep.append(i)
    d["items"] = keep
    return sold, points


def wear(d: dict, item_id: str) -> None:
    item = next((i for i in d.get("items") or [] if i["id"] == item_id), None)
    if not item:
        raise ValueError("no such item")
    worn = d.setdefault("worn", {})
    if worn.get(item["slot"]) == item_id:
        worn.pop(item["slot"])
    else:
        worn[item["slot"]] = item_id


def wear_best(d: dict, attacks: set[str]) -> None:
    """The best item of each slot worn, synergy counted."""
    worn = {}
    for slot in SLOTS:
        best = max((i for i in d.get("items") or [] if i["slot"] == slot), key=lambda i: (effective(i, attacks), i["level"]), default=None)
        if best:
            worn[slot] = best["id"]
    d["worn"] = worn


def bonuses(d: dict, attacks: set[str]) -> dict:
    """What the items worn add: {damage (%), defense, hp}."""
    by_id = {i["id"]: i for i in d.get("items") or []}
    out = {"damage": 0, "defense": 0, "hp": 0}
    for slot, item_id in (d.get("worn") or {}).items():
        i = by_id.get(item_id)
        if not i:
            continue
        out[{"arma": "damage", "acessorio": "defense", "cabeca": "hp"}[slot]] += effective(i, attacks)
    return out
