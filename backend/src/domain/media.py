"""Media: the titles a profile consumes, as tags on the thoughts of its acts.

The plain-text journal keeps two lists by hand: everything ever watched, read
or played, with an X on what was finished (~/journal/midea), and the few titles
allowed right now (~/journal/consumo). Here each title is a row with a kind and
a status, and the thought of a leisure act carries the one it was about — the
log says JOGOS [1–2h], its tag says Cuphead.

A kind belongs to the actions that consume it: a SÉRIE log is tagged with a
series, a JOGOS log with a game. A patch counts as its base (JOGOS · CUPHEAD is
still JOGOS).

A title that keeps coming back — tagged on PATCH_AFTER_DAYS different days —
can become a patch of its action, free like any patch of a log action: the
title then has an action of its own, and its records separate in the ledger.

Pure logic — no I/O.
"""
from __future__ import annotations

from src.domain.user_attributes import PATCH_SEPARATOR

# kind -> (label, the actions whose logs it tags)
KINDS = {
    "serie": ("série", ("SÉRIE",)),
    "filme": ("filme", ("FILME",)),
    "jogo": ("jogo", ("JOGOS",)),
    "leitura": ("leitura", ("LEITURA", "READ")),
    "musica": ("música", ("MÚSICA",)),
    "video": ("vídeo", ("VÍDEO",)),
}

# the action a title of each kind becomes a patch of
PATCH_BASE = {kind: actions[0] for kind, (_label, actions) in KINDS.items()}

# where a title stands, in the journal's words: allowed now, waiting, done,
# set aside, given up
STATUSES = ("ativo", "fila", "finalizado", "retirado", "morto")

PATCH_AFTER_DAYS = 3

MAX_TITLE = 160


class MediaError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def base_name(log_or_action: str) -> str:
    """The action a log line or an action name runs on: `JOGOS · CUPHEAD [1–2h]
    : nota` is JOGOS."""
    head = str(log_or_action or "").split(" [", 1)[0]
    return head.split(PATCH_SEPARATOR, 1)[0].strip().upper()


def kind_of(log_or_action: str) -> str | None:
    """The kind of title a log of this action is tagged with, or None."""
    name = base_name(log_or_action)
    return next((k for k, (_l, actions) in KINDS.items() if name in actions), None)


def clean_title(raw) -> str:
    title = " ".join(str(raw or "").split())
    if not title:
        raise MediaError("a title needs a name")
    if len(title) > MAX_TITLE:
        raise MediaError(f"a title has at most {MAX_TITLE} characters")
    return title


def check_kind(kind) -> str:
    if kind not in KINDS:
        raise MediaError(f"kind must be one of {', '.join(KINDS)}")
    return kind


def check_status(status) -> str:
    if status not in STATUSES:
        raise MediaError(f"status must be one of {', '.join(STATUSES)}")
    return status


def can_patch(days: int, patch_action_id: str | None) -> bool:
    return patch_action_id is None and int(days) >= PATCH_AFTER_DAYS


def patch_label(title: str, limit: int = 48) -> str:
    """A title cut to fit a patch's name, at a word when it can be."""
    title = " ".join(str(title or "").split())
    if len(title) <= limit:
        return title
    cut = title[:limit].rsplit(" ", 1)[0]
    return cut if len(cut) >= limit // 2 else title[:limit]
