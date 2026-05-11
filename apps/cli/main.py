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

from src.domain.act import apply_act, ActError
from src.domain.agenda import collect_labels, DAY_NAMES
from src.domain.daily import apply_daily_tick
from src.infrastructure.static_data import (
    skill_nodes_by_id,
    lookup_token_cost,
)
from src.infrastructure.storage import get_current_username
from src.infrastructure import repos
from user_selector import select_user_profile

console = Console()


def load_user() -> dict:
    username = get_current_username()
    data = repos.load_user_dict(username)
    if data is None:
        return {"actions": {}, "metadata": {}, "score": 0}
    if apply_daily_tick(data):
        repos.save_user_dict(username, data)
    return data


def save_user(data: dict) -> None:
    repos.save_user_dict(get_current_username(), data)


def load_logs() -> list:
    return repos.load_logs(get_current_username())


_LOG_ID_PREFIX = 73
_LOG_ID_WIDTH = 4


def append_log(content: str, xp: int) -> dict:
    username = get_current_username()
    logs = load_logs()
    today = datetime.now()
    today_day = repos.day_for_user(username, today.date())

    max_id = 0
    next_order = 0
    for log in logs:
        try:
            v = int(log.get("id", 0) or 0)
        except (TypeError, ValueError):
            v = 0
        if v > max_id:
            max_id = v
        coord = log.get("coord")
        if isinstance(coord, list) and len(coord) >= 2:
            try:
                if int(coord[0]) == today_day and int(coord[1]) > next_order:
                    next_order = int(coord[1])
            except (TypeError, ValueError):
                pass

    next_id = max_id + 1 if max_id else int(f"{_LOG_ID_PREFIX}{1:0{_LOG_ID_WIDTH}d}")
    entry = {
        "id": next_id,
        "timestamp": today.strftime("%d %m %Y : %H:%M:%S"),
        "content": content,
        "xp": int(xp),
        "coord": [today_day, next_order + 1],
    }
    repos.append_log(username, entry)
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


def _today_agenda_labels() -> set[str]:
    items = repos.load_agenda_items(get_current_username())
    now = datetime.now()
    return collect_labels(items, day_name=DAY_NAMES[now.weekday()], iso_date=now.strftime("%Y-%m-%d"))


def cmd_act(data: dict) -> None:
    aid = console.input("[cyan]action id:[/cyan] ").strip()
    action = (data.get("actions") or {}).get(aid)
    if not action or action.get("deleted"):
        console.print(f"[red]action {aid} not found[/red]")
        return
    note = console.input(f"[cyan]nota para {action.get('name')} (vazio=1):[/cyan] ").strip()
    manual_value = note if note else 1

    try:
        outcome = apply_act(
            data,
            aid,
            manual_value=manual_value,
            today_agenda_labels=_today_agenda_labels(),
            token_cost_lookup=lookup_token_cost,
            skill_nodes_by_id=skill_nodes_by_id(),
        )
    except ActError as e:
        console.print(f"[red]{e}[/red]")
        return

    save_user(data)
    append_log(outcome.log_content, int(round(outcome.score_diff)))

    parts = [
        f"[green]+{int(round(outcome.score_diff))} xp[/green]",
        f"[bold]{action.get('name')}[/bold]",
        f"value={action['value']:g}",
    ]
    if outcome.token_cost > 0:
        parts.append(f"[yellow]-{outcome.token_cost} tokens[/yellow]")
    if outcome.energy_penalty > 0:
        parts.append(f"[red]-{outcome.energy_penalty} energy[/red] (fora da agenda)")
    mult = outcome.bonuses.get("xp_multiplier", 1.0)
    if mult and abs(mult - 1.0) > 1e-9:
        parts.append(f"[dim]×{mult:g}[/dim]")
    console.print(" · ".join(parts))


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
