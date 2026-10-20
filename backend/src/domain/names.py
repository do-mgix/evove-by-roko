"""Nicknames and passcodes.

Every profile gets a short random nickname, a word or two glued together —
LUME, VEXO, TARNBRU — which is how other profiles and the entities call it,
whatever its login. A passcode is what another profile types to find it: six
characters from an alphabet without look-alikes (no 0/O, 1/I/L).

Pure functions on a `random.Random`, so a migration can seed them.
"""
from __future__ import annotations

import random


_WORDS = (
    "lume", "vexo", "tarn", "bru", "kiro", "nox", "sal", "duna", "ferro", "orla",
    "pico", "rumo", "silo", "tufo", "vau", "zin", "brasa", "cume", "eco", "farol",
    "grou", "ilha", "jade", "lince", "mote", "nimbo", "onda", "prumo", "quilha", "rocha",
    "sopro", "trilho", "urze", "vulto", "xisto", "zelo", "alvo", "bico", "cais", "dardo",
)
_SHORT = tuple(w for w in _WORDS if len(w) <= 4)

PASSCODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
PASSCODE_LENGTH = 6
NICKNAME_MAX = 12


def nickname(rng: random.Random) -> str:
    """A word alone, or two short ones glued: at most NICKNAME_MAX letters."""
    if rng.random() < 0.5:
        return rng.choice(_WORDS).upper()
    a, b = rng.choice(_SHORT), rng.choice(_SHORT)
    return (a + b)[:NICKNAME_MAX].upper()


def unique_nickname(rng: random.Random, taken: set[str]) -> str:
    """A nickname no one in `taken` has; a digit joins in when the words run out."""
    for _ in range(200):
        name = nickname(rng)
        if name not in taken:
            return name
    while True:
        name = f"{nickname(rng)[:NICKNAME_MAX - 1]}{rng.randint(2, 9)}"
        if name not in taken:
            return name


def passcode(rng: random.Random) -> str:
    return "".join(rng.choice(PASSCODE_ALPHABET) for _ in range(PASSCODE_LENGTH))


def unique_passcode(rng: random.Random, taken: set[str]) -> str:
    while True:
        code = passcode(rng)
        if code not in taken:
            return code
