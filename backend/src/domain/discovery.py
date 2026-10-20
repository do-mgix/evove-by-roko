"""Discovery: not every action is in the shop.

The catalog stays hidden until it is discovered, a few actions at a time. Every
day brings a number of discoveries — the rate, which grows with how much was
already found — and each one draws a random action not yet found. Part of the
draws lean towards the attributes the profile uses most, so the shop slowly
fills with what fits it.

How a discovery is made changes with use, as the whole interface does: first
each one is a frame of static to tap open (`frames`), then a single button opens
the day's all at once (`button`), and at last they open by themselves when the
shop is visited (`auto`).

Pure logic; the host stores what was found and how many of today's were used.
"""
from __future__ import annotations

import random


BUTTON_FROM = 12
AUTO_FROM = 36

BASE_RATE = 3
MAX_RATE = 8
RATE_STEP = 10
# the first day, before anything was found, opens a few more
FIRST_DAY_BONUS = 3
# the share of draws that lean on the favourite attributes
FAVOURITE_SHARE = 0.5


def phase(found: int) -> str:
    if found >= AUTO_FROM:
        return "auto"
    if found >= BUTTON_FROM:
        return "button"
    return "frames"


def rate(found: int) -> int:
    """Discoveries a day, for a profile that already found `found` actions."""
    return min(MAX_RATE, BASE_RATE + found // RATE_STEP)


def left_today(found_before_today: int, used_today: int, first_day: bool) -> int:
    allowance = rate(found_before_today) + (FIRST_DAY_BONUS if first_day else 0)
    return max(0, allowance - used_today)


def draw(rng: random.Random, hidden: list[str], affinity: dict[str, float], count: int) -> list[str]:
    """`count` actions out of `hidden`, without repeats. `affinity` weighs an
    action by how much the profile uses what it trains (0 for nothing)."""
    pool = sorted(hidden)
    out: list[str] = []
    while pool and len(out) < count:
        leaning = [a for a in pool if affinity.get(a, 0) > 0]
        if leaning and rng.random() < FAVOURITE_SHARE:
            pick = rng.choices(leaning, weights=[affinity[a] for a in leaning])[0]
        else:
            pick = rng.choice(pool)
        out.append(pick)
        pool.remove(pick)
    return out
