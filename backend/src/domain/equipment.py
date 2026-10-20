"""Equipment for the journey: what points buy for the battles.

Three slots — a weapon, an armor, an amulet — one item worn in each. A weapon
adds to every hit, an armor takes from every blow the boss lands, an amulet
raises the max hp or what a victory pays. Bought once with points, kept for
good, changed at will.

Pure data and arithmetic; the host stores what is owned and worn.
"""
from __future__ import annotations


SLOTS = ("arma", "armadura", "amuleto")

ITEMS: list[dict] = [
    {"id": "lamina", "slot": "arma", "name": "LÂMINA DE TREINO", "price": 800,
     "effect": {"damage": 0.10}, "text": "+10% de dano"},
    {"id": "lamina_runica", "slot": "arma", "name": "LÂMINA RÚNICA", "price": 2500,
     "effect": {"damage": 0.25}, "text": "+25% de dano"},
    {"id": "manto", "slot": "armadura", "name": "MANTO GASTO", "price": 900,
     "effect": {"armor": 1}, "text": "−1 por golpe recebido"},
    {"id": "couraca", "slot": "armadura", "name": "COURAÇA", "price": 3000,
     "effect": {"armor": 2}, "text": "−2 por golpe recebido"},
    {"id": "amuleto_folego", "slot": "amuleto", "name": "AMULETO DO FÔLEGO", "price": 1500,
     "effect": {"hp": 3}, "text": "+3 de hp máximo"},
    {"id": "amuleto_dourado", "slot": "amuleto", "name": "AMULETO DOURADO", "price": 1200,
     "effect": {"points": 0.20}, "text": "+20% de pontos por vitória"},
]

ITEMS_BY_ID = {i["id"]: i for i in ITEMS}


def bonuses(equipped: set[str] | list[str]) -> dict:
    """What the worn items add up to: {damage, armor, hp, points}."""
    out = {"damage": 0.0, "armor": 0, "hp": 0, "points": 0.0}
    for item_id in equipped:
        item = ITEMS_BY_ID.get(item_id)
        if not item:
            continue
        for k, v in item["effect"].items():
            out[k] += v
    return out
