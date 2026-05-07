import os
import shutil

import readchar
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from src.infrastructure.storage import (
    get_evove_root_dir,
    migrate_legacy_root_data,
    normalize_username,
    set_current_username,
)

MAX_USER_SLOTS = 4


class UserSelector:
    def __init__(self):
        self.console = Console()
        self.selected_index = 0

    def _list_profiles(self):
        migrate_legacy_root_data()
        root = get_evove_root_dir()
        profiles = []
        for entry in os.scandir(root):
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            user_json = os.path.join(entry.path, "user.json")
            if not os.path.exists(user_json):
                continue
            profiles.append({
                "username": entry.name,
                "path": entry.path,
                "mtime": os.path.getmtime(user_json),
            })
        profiles.sort(key=lambda item: (-item["mtime"], item["username"].lower()))
        return profiles[:MAX_USER_SLOTS]

    def _build_slot_panel(self, label, body, selected=False, style="white"):
        border = "bright_green" if selected else style
        title = f"[bold]{label}[/bold]" if selected else label
        return Panel(
            Align.left(Text.from_markup(body)),
            border_style=border,
            title=title,
            padding=(0, 1),
        )

    def _render(self, profiles):
        self.console.clear()
        rows = []
        for idx, profile in enumerate(profiles):
            rows.append(
                self._build_slot_panel(
                    f"{idx + 1}. {profile['username']}",
                    "[dim]Local profile[/dim]",
                    selected=idx == self.selected_index,
                )
            )

        new_enabled = len(profiles) < MAX_USER_SLOTS
        new_index = len(profiles)
        new_body = "[dim]Create a new local profile[/dim]" if new_enabled else "[dim]Maximum of 4 users reached[/dim]"
        rows.append(
            self._build_slot_panel(
                "+ New User" if new_enabled else "User Limit",
                new_body,
                selected=new_index == self.selected_index,
                style="cyan" if new_enabled else "dim",
            )
        )

        hint = "[bold]J/K[/bold] move  [bold]Enter[/bold] open  [bold]D[/bold] delete user  [bold]Q[/bold] quit"
        content = Group(*rows)
        screen = Panel(
            content,
            title="EVOVE USERS",
            subtitle=hint,
            border_style="bright_blue",
            padding=(1, 2),
        )
        self.console.print(Align.center(screen, vertical="middle"))

    def _prompt_new_username(self):
        self.console.clear()
        self.console.print(Panel("Create New User\n\nAllowed: letters, numbers, `_` and `-`.", border_style="cyan"))
        while True:
            raw = input("username: ").strip()
            normalized = normalize_username(raw)
            if not normalized:
                self.console.print("[red]Invalid username.[/red]")
                continue
            target = os.path.join(get_evove_root_dir(), normalized)
            if os.path.exists(target):
                self.console.print("[red]User already exists.[/red]")
                continue
            os.makedirs(target, exist_ok=True)
            return normalized

    def _confirm_delete(self, username):
        self.console.clear()
        prompt = Panel(
            f"Delete user [bold]{username}[/bold]?\n\nPress [bold]Y[/bold] to confirm or [bold]N[/bold] to cancel.",
            border_style="red",
            title="CONFIRM DELETE",
        )
        self.console.print(Align.center(prompt, vertical="middle"))
        while True:
            key = readchar.readkey()
            if not key:
                continue
            lower = key.lower()
            if lower == "y":
                return True
            if lower == "n":
                return False

    def run(self):
        while True:
            profiles = self._list_profiles()
            max_index = len(profiles)
            self.selected_index = min(self.selected_index, max_index)
            self._render(profiles)

            key = readchar.readkey()
            if key in ("k", "\x1b[A"):
                self.selected_index = max(0, self.selected_index - 1)
                continue
            if key in ("j", "\x1b[B"):
                self.selected_index = min(max_index, self.selected_index + 1)
                continue
            if key in ("\r", "\n"):
                if self.selected_index < len(profiles):
                    return set_current_username(profiles[self.selected_index]["username"])
                if len(profiles) < MAX_USER_SLOTS:
                    username = self._prompt_new_username()
                    return set_current_username(username)
                continue
            if key in ("d", "D") and self.selected_index < len(profiles):
                username = profiles[self.selected_index]["username"]
                if self._confirm_delete(username):
                    shutil.rmtree(profiles[self.selected_index]["path"], ignore_errors=True)
                    self.selected_index = max(0, self.selected_index - 1)
                continue
            if key in ("q", "Q"):
                self.console.clear()
                raise SystemExit(0)


def select_user_profile():
    selector = UserSelector()
    return selector.run()
