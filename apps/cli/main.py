"""Minimal Evove CLI: select user, list/act actions, view logs.

Shares the domain (src/) with the FastAPI backend so the score formula and
file persistence are identical.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
CLI_DIR = REPO_ROOT / "apps" / "cli"
for p in (str(BACKEND_DIR), str(CLI_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import readchar
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from src.domain.action import Action
from src.infrastructure.storage import (
    get_current_username,
    get_user_data_dir,
)
from user_selector import select_user_profile

console = Console()


def _data_dir() -> Path:
    return Path(get_user_data_dir(get_current_username()))


def _user_path() -> Path:
    return _data_dir() / "user.json"


def _logs_path() -> Path:
    return _data_dir() / "logs.json"


def load_user() -> dict:
    p = _user_path()
    if not p.exists():
        return {"actions": {}, "metadata": {}, "score": 0}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_user(data: dict) -> None:
    with _user_path().open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_logs() -> list:
    p = _logs_path()
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_logs(logs: list) -> None:
    with _logs_path().open("w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)


_LOG_ID_PREFIX = 73
_LOG_ID_WIDTH = 4


def append_log(content: str, xp: int) -> dict:
    logs = load_logs()
    prefix = str(_LOG_ID_PREFIX)
    nums = []
    for log in logs:
        s = str(log.get("id", ""))
        if s.startswith(prefix):
            try:
                nums.append(int(s[len(prefix):]))
            except ValueError:
                pass
    next_num = (max(nums) + 1) if nums else 1
    next_id = int(f"{prefix}{next_num:0{_LOG_ID_WIDTH}d}")
    today = datetime.now()
    entry = {
        "id": next_id,
        "timestamp": today.strftime("%d %m %Y : %H:%M:%S"),
        "content": content,
        "xp": int(xp),
    }
    logs.append(entry)
    save_logs(logs)
    return entry


def cmd_list_actions(data: dict) -> None:
    actions = (data.get("actions") or {})
    rows = [(aid, a) for aid, a in actions.items() if not a.get("deleted")]
    rows.sort(key=lambda r: str(r[1].get("name", "")).upper())
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("id", style="dim")
    table.add_column("name")
    table.add_column("type", justify="right")
    table.add_column("diff", justify="right")
    table.add_column("value", justify="right")
    table.add_column("score", justify="right", style="cyan")
    for aid, a in rows:
        table.add_row(
            aid,
            str(a.get("name", "")),
            str(a.get("type", "")),
            f"d{a.get('diff', 0)}",
            f"{a.get('value', 0):g}",
            f"{a.get('score', 0):g}",
        )
    console.print(table)


def cmd_act(data: dict) -> None:
    aid = console.input("[cyan]action id:[/cyan] ").strip()
    action = (data.get("actions") or {}).get(aid)
    if not action or action.get("deleted"):
        console.print(f"[red]action {aid} not found[/red]")
        return
    note = console.input(f"[cyan]nota para {action.get('name')} (vazio=1):[/cyan] ").strip()
    manual_value = note if note else 1

    domain_action = Action.from_dict(action)
    raw_diff, _msgs, note_info = domain_action.execution(manual_value=manual_value)
    state = domain_action.to_dict()
    action["value"] = state["value"]
    action["max_value"] = state["max_value"]
    action["score"] = state["score"]

    data["score"] = float(data.get("score", 0) or 0) + raw_diff
    data.setdefault("metadata", {})["score"] = data["score"]

    for attr in (data.get("attributes") or {}).values():
        if aid in (attr.get("related_actions") or []):
            attr["total_score"] = float(attr.get("total_score", 0) or 0) + raw_diff

    save_user(data)

    is_numeric = bool((note_info or {}).get("is_numeric"))
    text = (note_info or {}).get("text") or ""
    units = int((note_info or {}).get("value", 1)) if is_numeric else 1
    if text and not is_numeric:
        log_content = f"{action.get('name', '')} : {text}".strip()
    else:
        log_content = f"{units} X {action.get('name', '')}".strip()
    append_log(log_content, int(round(raw_diff)))

    console.print(
        f"[green]+{int(round(raw_diff))} xp[/green] · "
        f"[bold]{action.get('name')}[/bold] "
        f"value={action['value']:g} score={action['score']:g}"
    )


def cmd_logs() -> None:
    logs = load_logs()
    today = datetime.now().strftime("%d %m %Y")
    today_logs = [l for l in logs if str(l.get("timestamp", "")).startswith(today)]
    if not today_logs:
        console.print("[dim]sem logs hoje[/dim]")
        return
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("time", style="dim")
    table.add_column("content")
    table.add_column("xp", justify="right", style="green")
    for log in today_logs[-30:]:
        ts = str(log.get("timestamp", ""))
        time_part = ts.split(" : ")[1] if " : " in ts else ts
        table.add_row(time_part, str(log.get("content", "")), f"+{log.get('xp', 0)}")
    console.print(table)


def cmd_status(data: dict) -> None:
    md = data.get("metadata") or {}
    info = [
        f"[cyan]user[/cyan]   {get_current_username()}",
        f"[cyan]score[/cyan]  {data.get('score', 0):g}",
        f"[cyan]energy[/cyan] {md.get('energy', 0)}",
        f"[cyan]tokens[/cyan] {md.get('tokens', 0)}/{md.get('max_tokens', 50)}",
        f"[cyan]bp[/cyan]     {md.get('build_points', 0)}",
        f"[cyan]sp[/cyan]     {md.get('skill_points', 0)}",
        f"[cyan]stage[/cyan]  {md.get('stage', 1)}",
    ]
    console.print(Panel("\n".join(info), title=f"status", border_style="bright_blue"))


MENU = """
[bold cyan]EVOVE CLI[/bold cyan]  ·  user: [bold]{user}[/bold]

  [yellow]l[/yellow] list actions
  [yellow]a[/yellow] act on action
  [yellow]g[/yellow] today's logs
  [yellow]s[/yellow] status
  [yellow]u[/yellow] switch user
  [yellow]q[/yellow] quit
"""


def session_loop():
    while True:
        data = load_user()
        console.clear()
        console.print(MENU.format(user=get_current_username()))
        key = readchar.readkey()
        if key in ("q", "Q", "\x03"):
            return "quit"
        if key in ("u", "U"):
            return "user_selection"
        console.clear()
        if key in ("l", "L"):
            cmd_list_actions(data)
        elif key in ("a", "A"):
            cmd_act(data)
        elif key in ("g", "G"):
            cmd_logs()
        elif key in ("s", "S"):
            cmd_status(data)
        else:
            continue
        console.print("\n[dim][ press any key to continue ][/dim]")
        readchar.readkey()


def main():
    while True:
        select_user_profile()
        result = session_loop()
        if result != "user_selection":
            break


if __name__ == "__main__":
    main()
