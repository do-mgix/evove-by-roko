"""Import the journal's media lists as a profile's titles.

    python scripts/import_media.py <username> <midea> [<consumo>] [--dry-run]

`midea` is the list of everything (~/journal/midea): sections FILMES, CURTAS,
SÉRIES, LITERATURA and JOGOS, one title per line, an `X ` in front of what was
finished; under JOGOS a line in capitals with no X (PC, NDS, 3DS, MOBILE) opens
a console, kept as the title's note. The rest of a section waits: `fila`.

`consumo` is the list of what is allowed now (~/journal/consumo): its titles
become `ativo`, `[RETIRADO]` ones `retirado`, and the ones under MORTOS
`morto` — but a title midea marks finished stays `finalizado`. The price table
at its end is left alone.

Idempotent: a title already there keeps its row and only takes the status the
lists give it. Run from backend/, with DATABASE_URL set.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure import media_repo  # noqa: E402

SECTIONS = {"FILMES": "filme", "CURTAS": "filme", "SÉRIES": "serie", "LITERATURA": "leitura", "JOGOS": "jogo"}
CONSUMO_KINDS = {"FILME": "filme", "JOGO": "jogo", "LITERATURA": "leitura", "SÉRIE": "serie", "MORTOS": "serie"}
CONSOLES = {"PC", "NDS", "3DS", "MOBILE"}


def parse_midea(text: str) -> list[dict]:
    out, kind, note = [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            note = None          # a blank line closes a console's list
            continue
        if line in SECTIONS:
            kind, note = SECTIONS[line], None
            continue
        if line in ("ESTÚDIOS", "CONSOLES") or line.startswith("Jogos e respectivos"):
            if line == "ESTÚDIOS":
                kind = None
            continue
        if kind is None:
            continue
        if kind == "jogo" and line in CONSOLES:
            note = line
            continue
        done = bool(re.match(r"^[Xx] ", line))
        title = line[2:].strip() if done else line
        out.append({"kind": kind, "title": title, "status": "finalizado" if done else "fila", "note": note})
    return out


def parse_consumo(text: str) -> list[dict]:
    out, kind = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "MIDIAS ATIVAS":
            continue
        if ":" in line:          # the price table: FILME  : 1T/FILME
            break
        if line in CONSUMO_KINDS:
            kind = CONSUMO_KINDS[line]
            dead = line == "MORTOS"
            continue
        if kind is None:
            continue
        retired = "[RETIRADO]" in line.upper()
        title = re.sub(r"\[RETIRADO\]", "", line, flags=re.I).strip()
        if kind == "filme" and " e " in title.lower() and "best" in title.lower():
            continue             # "Clássicos e Best Rotten Tomatoes" is a rule, not a title
        out.append({"kind": kind, "title": title, "status": "morto" if dead else "retirado" if retired else "ativo"})
    return out


def _key(title: str) -> str:
    """A title as the lists may spell it twice: no case, no punctuation."""
    return " ".join(re.sub(r"[^\w ]", " ", title.lower()).split())


def main(argv: list[str]) -> None:
    dry = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    if len(args) < 2:
        sys.exit(__doc__)
    username, midea = args[0], Path(args[1])
    entries = parse_midea(midea.read_text(encoding="utf-8"))
    if len(args) > 2:
        entries += parse_consumo(Path(args[2]).read_text(encoding="utf-8"))
    # the last word on a title wins — consumo comes after midea — except that
    # what midea marks finished stays finished
    final: dict[tuple[str, str], dict] = {}
    for e in entries:
        key = (e["kind"], _key(e["title"]))
        before = final.get(key, {})
        final[key] = {**before, **{k: v for k, v in e.items() if v is not None}}
        if before.get("status") == "finalizado":
            final[key]["status"] = "finalizado"
    have = {(m["kind"], _key(m["title"])): m for m in media_repo.list_media(username)}
    made = changed = 0
    for key, e in final.items():
        if dry:
            print(f"{e['kind']:8} {e['status']:10} {e['title']}" + (f"  ({e['note']})" if e.get("note") else ""))
            continue
        row = have.get(key)
        if row is None:
            media_repo.create_media(username, e["kind"], e["title"], e["status"], e.get("note"))
            made += 1
        elif row["status"] != e["status"]:
            media_repo.update_media(username, row["id"], {"status": e["status"]})
            changed += 1
    print(f"{len(final)} titles: {made} new, {changed} with a new status" if not dry else f"{len(final)} titles")


if __name__ == "__main__":
    main(sys.argv[1:])
