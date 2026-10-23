"""Equipment for the journey: what points buy for the battles.

Three slots, one item worn in each: a vetor adds to every hit, a filtro takes
from every blow the ruído lands, a pulso raises the max hp or what a victory
pays. Bought once with points, kept for good, changed at will.

The items have no theme: each is named by a word drawn at random, and only its
effect says what it does. The ids are older than the names and stay as they
were, since they are what `user_equipment` holds.

Pure data and arithmetic; the host stores what is owned and worn.
"""
from __future__ import annotations


SLOTS = ("vetor", "filtro", "pulso")

ITEMS: list[dict] = [
    {"id": "lamina", "slot": "vetor", "name": "URZE", "price": 800,
     "effect": {"damage": 0.10}, "text": "+10% de dano"},
    {"id": "vetor_2", "slot": "vetor", "name": "QUILHA", "price": 1600,
     "effect": {"damage": 0.18}, "text": "+18% de dano"},
    {"id": "lamina_runica", "slot": "vetor", "name": "NIMBO", "price": 2500,
     "effect": {"damage": 0.25}, "text": "+25% de dano"},
    {"id": "vetor_4", "slot": "vetor", "name": "XISTO", "price": 4000,
     "effect": {"damage": 0.35}, "text": "+35% de dano"},
    {"id": "manto", "slot": "filtro", "name": "PRUMO", "price": 900,
     "effect": {"armor": 1}, "text": "−1 por golpe recebido"},
    {"id": "couraca", "slot": "filtro", "name": "LINCE", "price": 3000,
     "effect": {"armor": 2}, "text": "−2 por golpe recebido"},
    {"id": "filtro_3", "slot": "filtro", "name": "DARDO", "price": 5000,
     "effect": {"armor": 3}, "text": "−3 por golpe recebido"},
    {"id": "amuleto_folego", "slot": "pulso", "name": "SOPRO", "price": 1500,
     "effect": {"hp": 3}, "text": "+3 de hp máximo"},
    {"id": "pulso_hp_2", "slot": "pulso", "name": "FAROL", "price": 3500,
     "effect": {"hp": 6}, "text": "+6 de hp máximo"},
    {"id": "amuleto_dourado", "slot": "pulso", "name": "TUFO", "price": 1200,
     "effect": {"points": 0.20}, "text": "+20% de pontos por vitória"},
    {"id": "pulso_pts_2", "slot": "pulso", "name": "ORLA", "price": 3000,
     "effect": {"points": 0.35}, "text": "+35% de pontos por vitória"},
    {"id": "pulso_mix", "slot": "pulso", "name": "GROU", "price": 4500,
     "effect": {"hp": 3, "points": 0.15}, "text": "+3 de hp e +15% de pontos"},
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
