"""Saves: a whole evove carried by one code.

The short passcodes open a module or hand over a build (src.domain.engine).
A save code carries everything of a profile that is not its own words: the
catalog actions it owns and what it did with them, the ranks of every
attribute of the graph, the ranks already claimed, its points, tokens, hp and
skills, what it discovered, the equipment, and its evove — modules, entity,
story, sandbox, journey. It leaves out what only that person wrote: patches
and their attributes, thoughts, the history of logs, the agenda.

The code is the data itself, compressed and signed, so the server keeps
nothing for it: typed into any profile, it mounts the save there — on a new
device, after starting over, or long after. The signature keeps it from being
edited by hand; the letters are base32, so case, spaces, dashes and line
breaks typed or pasted along with it do not matter.

Pure logic — no I/O. The host gathers the snapshot and applies it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import zlib


PREFIX = "EVS1"
SIG_BYTES = 10
VERSION = 1


class SaveError(ValueError):
    """A code that is not a save, was cut short or was changed."""


def is_save(raw) -> bool:
    return _clean(raw).startswith(PREFIX)


def _clean(raw) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())


def _sign(body: bytes, secret: bytes) -> bytes:
    return hmac.new(secret, body, hashlib.sha256).digest()[:SIG_BYTES]


def pack(snapshot: dict, secret: bytes) -> str:
    """The code of `snapshot`: the prefix, then base32 of the signature and
    the compressed JSON, without padding."""
    body = zlib.compress(json.dumps({"v": VERSION, **snapshot}, separators=(",", ":"), ensure_ascii=False).encode(), 9)
    return PREFIX + base64.b32encode(_sign(body, secret) + body).decode().rstrip("=")


def unpack(raw, secret: bytes) -> dict:
    """The snapshot a code carries; SaveError when it is not a valid one."""
    code = _clean(raw)
    if not code.startswith(PREFIX):
        raise SaveError("not a save")
    letters = code[len(PREFIX):]
    try:
        blob = base64.b32decode(letters + "=" * (-len(letters) % 8))
    except Exception:
        raise SaveError("broken save")
    sig, body = blob[:SIG_BYTES], blob[SIG_BYTES:]
    if not hmac.compare_digest(sig, _sign(body, secret)):
        raise SaveError("broken save")
    try:
        snap = json.loads(zlib.decompress(body).decode())
    except Exception:
        raise SaveError("broken save")
    if int(snap.get("v", 0) or 0) > VERSION:
        raise SaveError("save from a newer evove")
    return snap


def group(code: str, size: int = 4) -> str:
    """The code in groups of letters, for the eye; mounting ignores the spaces."""
    return " ".join(code[i:i + size] for i in range(0, len(code), size))
