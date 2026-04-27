import os
import time
import readchar
import random
import sys
import select
from datetime import datetime
from rich.align import Align
from rich.console import Console, Group
from rich.padding import Padding
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich import box


class WebInputInterrupt(Exception):
    def __init__(self, prompt, type="text", options=None):
        self.prompt = prompt
        self.type = type
        self.options = options

class UI:
    def __init__(self):
        # Colors (instance properties)
        self.CLR = "\033[0m"
        self.BOLD = "\033[1m"
        self.CYAN = "\033[36m"
        self.GREEN = "\033[32m"
        self.YELLOW = "\033[33m"
        self.WHITE = "\033[37m"
        self.MAGENTA = "\033[35m"
        
        self.web_mode = False
        self.web_buffer = []
        self.console = Console()
        self.margin_x = 4
        self.command_history = []
        self.command_history_limit = 30
        self.home_input_armed = False
        self.nav_focus = "agenda"
        self._agenda_scroll = 0
        self._agenda_day_offset = 0
        self._commands_scroll = 0

        # Import from constants only
        from src.domain.constants import (
            user, 
            SINGLE_COMMANDS, 
            OBJECTS, 
            INTERACTIONS,
            COMMANDS,
        )
        
        self.user = user
        self.SINGLE_COMMANDS = SINGLE_COMMANDS
        self.OBJECTS = OBJECTS
        self.INTERACTIONS = INTERACTIONS
        self.COMMANDS = COMMANDS

    def _as_rich_text(self, content):
        if isinstance(content, Text):
            return content
        return Text.from_ansi(str(content))

    def _render_line(self, content="", center=True):
        text = self._as_rich_text(content)
        renderable = Align.center(text) if center else text
        return Padding(renderable, (0, self.margin_x))

    def _print_line(self, content="", center=True, end="\n"):
        self.console.print(
            self._render_line(content, center=center),
            end=end,
            highlight=False,
            soft_wrap=True,
        )

    def _print_block(self, lines, center=True, vcenter=True, last_end="\n"):
        lines = list(lines or [])
        if vcenter:
            term_height = max(1, self.console.size.height)
            top_padding = max(0, (term_height - len(lines)) // 2)
            for _ in range(top_padding):
                self.console.print("")

        for idx, line in enumerate(lines):
            end = last_end if idx == len(lines) - 1 else "\n"
            self._print_line(line, center=center, end=end)

    def _get_list_columns(self, items, min_col_width=22, max_cols=6):
        if not items:
            return 1
        term_width = max(40, self.console.size.width - (self.margin_x * 2))
        max_len = max(len(str(item)) for item in items)
        col_width = max(min_col_width, min(48, max_len + 2))
        cols = max(1, term_width // col_width)
        return max(1, min(max_cols, cols, len(items)))

    def _build_excel_table(self, items, columns=None):
        str_items = [str(item) for item in items]
        cols = columns if columns is not None else self._get_list_columns(str_items)
        cols = max(1, min(cols, len(str_items) if str_items else 1))

        table = Table(
            show_header=False,
            box=box.SQUARE,
            pad_edge=False,
            expand=False,
            collapse_padding=False,
        )
        for _ in range(cols):
            table.add_column(justify="left", overflow="fold", no_wrap=False, style="white")

        for i in range(0, len(str_items), cols):
            row = str_items[i:i + cols]
            if len(row) < cols:
                row.extend([""] * (cols - len(row)))
            table.add_row(*row)
        return table, cols

    def _build_labeled_table(self, rows, columns):
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SQUARE,
            pad_edge=False,
            expand=False,
            collapse_padding=False,
        )
        for key, label in columns:
            table.add_column(str(label), justify="left", overflow="fold", no_wrap=False, style="white")

        for row in rows:
            rendered = []
            for key, _ in columns:
                if isinstance(row, dict):
                    rendered.append(str(row.get(key, "")))
                else:
                    rendered.append(str(row))
            table.add_row(*rendered)
        return table

    def _print_list_layout(self, title, table, footer, content_line_estimate):
        term_height = max(1, self.console.size.height)
        top_padding = max(0, (term_height - content_line_estimate) // 2)
        for _ in range(top_padding):
            self.console.print("")

        self._print_line(title)
        self._print_line("")
        self.console.print(
            Padding(Align.center(table), (0, self.margin_x)),
            highlight=False,
            soft_wrap=True,
        )
        self._print_line("")
        self._print_line(footer)

    def add_command_history(self, command):
        cmd = str(command or "").strip()
        if not cmd:
            return
        self.command_history.append(cmd)
        if len(self.command_history) > self.command_history_limit:
            self.command_history = self.command_history[-self.command_history_limit:]

    def _build_marquee_panel(self):
        width = max(20, self.console.size.width - (self.margin_x * 2) - 4)
        if self.command_history:
            base = "  ✦  ".join(self.command_history[-12:])
        else:
            base = "Sem histórico ainda. Digite um comando."
        visible = f" {base} "
        if len(visible) > width:
            visible = visible[: max(0, width - 1)] + "…"

        text = Text(visible, style="bold green", justify="left")
        return Panel(Align.center(text), title="[dim]histórico[/]", border_style="dim")

    _AGENDA_PATHS = ("/home/mgix/jounal/agenda", "/home/mgix/journal/agenda")

    def _load_agenda(self):
        for path in self._AGENDA_PATHS:
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return path, f.read().splitlines()
                except OSError:
                    return path, ["(erro ao ler o ficheiro)"]
        return None, []

    def _sorted_command_pairs(self):
        return sorted(self.SINGLE_COMMANDS.items(), key=lambda x: (len(x[0]), x[0]))

    def _agenda_viewport_cap(self):
        th = max(12, self.console.size.height)
        return max(6, th - 18)

    def _commands_viewport_cap(self):
        th = max(12, self.console.size.height)
        return max(8, th - 14)

    def _nav_scroll_delta(self, delta):
        if self.nav_focus == "agenda":
            from src.application.services.evove_agenda_service import get_today_schedule
            from datetime import datetime, timedelta
            offset = self._agenda_day_offset
            target_dt = datetime.now() + timedelta(days=offset) if offset else None
            _, items, _ = get_today_schedule(now=target_dt)
            total = len(items)
            cap = self._agenda_viewport_cap()
            if total <= cap:
                return
            max_scroll = max(0, total - cap)
            self._agenda_scroll = min(max_scroll, max(0, self._agenda_scroll + delta))
        else:
            pairs = self._sorted_command_pairs()
            total = len(pairs)
            cap = self._commands_viewport_cap()
            if total <= cap:
                return
            data_rows = cap - 1
            max_scroll = max(0, total - data_rows)
            self._commands_scroll = min(max_scroll, max(0, self._commands_scroll + delta))

    def handle_idle_navigation(self, key):
        if key == "h":
            self._agenda_day_offset = (self._agenda_day_offset - 1) % 7
            self._agenda_scroll = 0
        elif key == "l":
            self._agenda_day_offset = (self._agenda_day_offset + 1) % 7
            self._agenda_scroll = 0
        elif key == "j":
            self._nav_scroll_delta(1)
        elif key == "k":
            self._nav_scroll_delta(-1)
        elif key == "i":
            self._agenda_day_offset = 0
            self.home_input_armed = True

    def _build_commands_side_panel(self, evove_lines=None, aux_height=None):
        focused = self.nav_focus == "commands"
        border = "bright_blue" if focused else "dim blue"
        total_height = max(24, self.console.size.height)
        if aux_height is None:
            aux_height = max(5, min(8, total_height // 7))
        top_height = max(12, total_height - aux_height - 6)
        evove_height = 5
        agenda_height = max(8, top_height - evove_height)
        user_height = max(8, int(top_height * 0.53))
        roko_height = max(6, top_height - user_height)

        evove_panel = self._build_evove_panel(evove_lines or [], height=evove_height)
        agenda_panel = self._build_agenda_panel(height=agenda_height)
        user_panel = self._build_user_side_panel(border, height=user_height)
        roko_panel = self._build_roko_side_panel(border, height=roko_height)
        aux_panel = Panel(
            Text("", style="dim"),
            title="[dim]aux[/]",
            border_style="dim blue",
            height=aux_height,
        )

        top_grid = Table.grid(expand=True)
        top_grid.add_column(ratio=48)
        top_grid.add_column(ratio=52)
        top_grid.add_row(Group(evove_panel, agenda_panel), Group(user_panel, roko_panel))
        return Group(top_grid, aux_panel)

    def _build_evove_panel(self, lines, height):
        body_lines = list(lines or [])
        body = Text.from_ansi("\n".join(body_lines))
        return Panel(body, title="[dim]evove[/]", border_style="cyan", height=height)

    def _build_user_side_panel(self, border, height=None):
        from src.application.services.sleep_service import sleep_service
        from src.application.services.sequence_service import sequence_service

        progress = self.user.get_progression_state() if hasattr(self.user, "get_progression_state") else {}
        sleep_info = sleep_service.get_last_sleep()
        sleep_text = sleep_info.get("duration", "no data") if sleep_info else "no data"
        day_text = sequence_service.days_since_first_activity()
        felicity = int(round(self.user.get_user_felicity())) if hasattr(self.user, "get_user_felicity") else 0

        xp_cost = max(1, progress.get('xp_cost', 1))
        next_xp = progress.get('next_xp', 0)
        xp_earned = max(0, xp_cost - next_xp)
        pct = xp_earned / xp_cost
        bar_width = 14
        filled = int(pct * bar_width)
        bar = f"\033[32m{'█' * filled}\033[2m{'░' * (bar_width - filled)}\033[0m"

        stats = [
            f"{self.CYAN}P:{self.CLR} {self.BOLD}{self.user.total_points}{self.CLR}",
            f"{self.GREEN}LEVEL:{self.CLR} {self.BOLD}{progress.get('rank_symbol', 'α')}{self.CLR} {self.WHITE}|{self.CLR} {self.BOLD}{progress.get('local_level_roman', 'I')}{self.CLR}",
            f"{self.CYAN}XP:{self.CLR} {progress.get('xp', 0)}  {self.YELLOW}NEXT:{self.CLR} {self.BOLD}{next_xp}{self.CLR}",
            f"{bar} \033[2m{int(pct * 100)}%\033[0m",
            f"{self.MAGENTA}SAT:{self.CLR} {felicity}%",
            f"{self.WHITE}SLEEP:{self.CLR} {sleep_text}",
            f"{self.WHITE}DAY:{self.CLR} {day_text}",
        ]

        attr_lines = [f"\033[2mATTR\033[0m"]
        if self.user._attributes:
            for attr in self.user._attributes.values():
                attr_lines.append(
                    f"{self.WHITE}{attr._name}{self.CLR}\n{self.CYAN}{attr.power_display}{self.CLR}"
                )
        else:
            attr_lines.append("—")

        left = Text.from_ansi("\n\n".join(stats))
        right = Text.from_ansi("\n\n".join(attr_lines))

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_row(left, right)

        return Panel(grid, title="[dim]user[/]", border_style=border, height=height)

    def _build_roko_side_panel(self, border, height=None):
        from src.domain.entities.entity_manager import EntityManager

        current_entity = EntityManager().get_entity()
        adjective = self.user._get_roko_adjective() if hasattr(self.user, "_get_roko_adjective") else "NEUTRO"
        lines = [
            f"ROKO ({adjective})",
        ]

        if current_entity:
            try:
                sat = int(round(current_entity.satisfaction))
            except Exception:
                sat = 0
            mood = current_entity._get_mood().upper() if hasattr(current_entity, "_get_mood") else "-"
            lines.extend([
                f"SAT: {sat}%",
                f"MOOD: {mood}",
            ])
        else:
            lines.extend([
                "SAT: 0%",
            "MOOD: -",
            ])

        body = Text("\n".join(lines), style="white", overflow="fold", no_wrap=False)
        return Panel(body, title="[dim]roko[/]", border_style=border, height=height)

    def _build_agenda_panel(self, height=None):
        focused = self.nav_focus == "agenda"
        border = "bright_magenta" if focused else "dim magenta"

        from src.application.services.evove_agenda_service import (
            get_today_schedule, parse_agenda, AGENDA_FILE,
        )
        from datetime import datetime, timedelta
        import os as _os

        if not _os.path.isfile(AGENDA_FILE):
            body = Text(
                f"(não encontrado: {AGENDA_FILE})",
                style="dim",
                overflow="fold",
                no_wrap=False,
            )
            return Panel(body, title="[dim]agenda[/]", border_style=border, height=height)

        # In insert mode always show today; in navigation show the offset day.
        offset = 0 if self.home_input_armed else self._agenda_day_offset
        if offset == 0:
            day_name, items, active_idx = get_today_schedule()
        else:
            target_dt = datetime.now() + timedelta(days=offset)
            day_name, items, active_idx = get_today_schedule(now=target_dt)

        if not items:
            body = Text(f"(sem blocos para {day_name})", style="dim white", overflow="fold", no_wrap=False)
            return Panel(body, title=f"[dim]agenda · {day_name}[/]", border_style=border, height=height)

        cap = self._agenda_viewport_cap()
        total = len(items)
        self._agenda_scroll = min(max(self._agenda_scroll, 0), max(0, total - cap))
        start = self._agenda_scroll if total > cap else 0
        visible = items[start:start + cap]

        body = Text(overflow="fold", no_wrap=False)
        for i, (s, e, label) in enumerate(visible):
            real_idx = start + i
            line = f"{s}-{e} : {label}\n"
            if real_idx == active_idx:
                body.append(f"▶ {line}", style="bold yellow")
            else:
                body.append(f"  {line}", style="dim white")

        suffix = f" · {start + 1}-{start + len(visible)}/{total}" if total > cap else ""
        nav_hint = f" ◀▶" if offset != 0 else ""
        title = f"[dim]agenda · {day_name}{nav_hint}{suffix}[/]"
        return Panel(body, title=title, border_style=border, height=height)

    def show_startup_commands(self):
        if self.web_mode:
            return

        self.clear_screen()
        lines = [
            f"{self.CYAN}{self.BOLD}EVOVE CLI - COMMAND REFERENCE{self.CLR}",
            "",
            f"{self.WHITE}Single Commands (from constants):{self.CLR}",
        ]
        self._print_block(lines, vcenter=False)

        single_rows = []
        for cmd, info in sorted(self.SINGLE_COMMANDS.items(), key=lambda x: (len(x[0]), x[0])):
            single_rows.append({
                "cmd": cmd,
                "label": info.get("label", ""),
                "len": info.get("len", 0),
            })
        single_table = self._build_labeled_table(
            single_rows,
            [("cmd", "CMD"), ("label", "LABEL"), ("len", "LEN")],
        )
        self.console.print(Padding(Align.center(single_table), (0, self.margin_x)), highlight=False, soft_wrap=True)

        self._print_block([
            "",
            f"{self.WHITE}Objects:{self.CLR}",
        ], vcenter=False)
        obj_rows = [{"id": k, "label": v.get("label", ""), "len": v.get("len", 0)} for k, v in self.OBJECTS.items()]
        obj_table = self._build_labeled_table(obj_rows, [("id", "ID"), ("label", "LABEL"), ("len", "LEN")])
        self.console.print(Padding(Align.center(obj_table), (0, self.margin_x)), highlight=False, soft_wrap=True)

        self._print_block([
            "",
            f"{self.WHITE}Interactions:{self.CLR}",
        ], vcenter=False)
        int_rows = [{"id": k, "label": v.get("label", ""), "len": v.get("len", 0)} for k, v in self.INTERACTIONS.items()]
        int_table = self._build_labeled_table(int_rows, [("id", "ID"), ("label", "LABEL"), ("len", "LEN")])
        self.console.print(Padding(Align.center(int_table), (0, self.margin_x)), highlight=False, soft_wrap=True)

        self._print_block([
            "",
            f"{self.WHITE}Composed Commands:{self.CLR}",
        ], vcenter=False)
        composed_rows = [
            {"pattern": k, "func": v.get("func").__name__ if v.get("func") else ""}
            for k, v in self.COMMANDS.items()
        ]
        composed_table = self._build_labeled_table(composed_rows, [("pattern", "PATTERN"), ("func", "FUNC")])
        self.console.print(Padding(Align.center(composed_table), (0, self.margin_x)), highlight=False, soft_wrap=True)

        self._print_block([
            "",
            f"{self.GREEN}[ Press any key to continue ]{self.CLR}",
        ], vcenter=False)
        readchar.readkey()

    def log_web(self, msg):
        if self.web_mode:
            self.web_buffer.append(msg)
        else:
            self._print_line(msg)

        # Import from constants only
        from src.domain.constants import (
            user, 
            SINGLE_COMMANDS, 
            OBJECTS, 
            INTERACTIONS,
            COMMANDS,
        )
        
        self.user = user
        self.SINGLE_COMMANDS = SINGLE_COMMANDS
        self.OBJECTS = OBJECTS
        self.INTERACTIONS = INTERACTIONS
        self.COMMANDS = COMMANDS

    
    def format_visual_buffer(self, buffer):
        """Formats the buffer dynamically: 801 - 2 - 50_"""
        if buffer.startswith(':') or buffer.startswith('/'):
            return f"{self.YELLOW}{buffer}{self.WHITE}_"

        res = []
        ptr = 0
        
        # 1. Tenta formatar como comando simples primeiro se o buffer começar com um
        for cmd, info in self.SINGLE_COMMANDS.items():
            if buffer.startswith(cmd):
                res.append(cmd)
                ptr += len(cmd)
                payload_len = info["len"]
                payload = buffer[ptr:ptr+payload_len]
                if payload:
                    res.append(payload)
                    ptr += len(payload)
                # Adiciona o restante se houver (erro ou payload incompleto)
                remaining = buffer[ptr:]
                if remaining:
                    res.append(remaining)
                joined = " - ".join(res)
                return f"{self.YELLOW}{joined}{self.WHITE}_"
        
        # 2. Formata como comando dinâmico
        while ptr < len(buffer):
            char = buffer[ptr]
            if char == "1":
                tag_info = self.OBJECTS.get(char)
                if tag_info and (len(buffer) - ptr) >= (1 + tag_info.get("len", 0)):
                    info = tag_info
                else:
                    info = self.INTERACTIONS.get(char)
            else:
                info = self.OBJECTS.get(char) or self.INTERACTIONS.get(char)
            
            if info:
                chunk_len = 1 + info["len"]
                chunk = buffer[ptr : ptr + chunk_len]
                res.append(chunk)
                ptr += chunk_len
            else:
                # If the character is not recognized, advance 1
                res.append(buffer[ptr])
                ptr += 1
        
        joined = " - ".join(res)
        return f"{self.YELLOW}{joined}{self.WHITE}_"
    
    def process_view(self, buffer):
        if not buffer:
            return ""
            
        from src.application.dial_interaction.dial_digest import dial
        phrase, payloads, is_single = dial.parse_buffer(buffer)
        tokens = phrase.split(" ")
        
        status_parts = []
        if is_single:
            label = phrase.upper()
            status_parts.append(f"{self.CYAN}{label}{self.CLR}")
            if payloads and payloads[0]:
                status_parts.append(f"{self.WHITE}({payloads[0]}){self.CLR}")
        else:
            p_idx = 0
            for t in tokens:
                if t == "attr":
                    id_val = f"8{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._attributes.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{self.WHITE}ATTRIBUTES ({nome}){self.CLR}")
                    p_idx += 1
                elif t == "add":
                    status_parts.append(f"{self.CYAN}Add{self.CLR}")
                elif t == "action":
                    id_val = f"5{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._actions.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{self.MAGENTA}⭐ ({nome}){self.CLR}")
                    p_idx += 1
                elif t == "status":
                    id_val = f"4{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._statuses.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{self.WHITE}◆ ({nome}){self.CLR}")
                    p_idx += 1
                elif t == "tag":
                    id_val = f"1{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._tags.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{self.WHITE}TAG ({nome}){self.CLR}")
                    p_idx += 1
                elif t == "param":
                    id_val = f"6{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._parameters.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{self.WHITE}◆ ({nome}){self.CLR}")
                    p_idx += 1
                elif t == "act":
                    status_parts.append(f"{self.GREEN}Act{self.CLR}")
                elif t == "delete":
                    status_parts.append(f"{self.YELLOW}Delete{self.CLR}")
        
        return " -> ".join(status_parts) if status_parts else ""
    
    def show_messages_animated(self, messages):
        """Shows messages one by one"""
        if self.web_mode:
            self.web_buffer.extend(messages)
            return

        for msg in messages:
            self.clear_screen()
            self._print_block([msg])
            wait_time = len(msg) * 0.05
            time.sleep(wait_time)

    def render_terminal(self, title=None, items=None, messages=None, wait=True):
        """Renders a terminal-style view: clear once, then print content."""
        if self.web_mode:
            if title:
                self.web_buffer.append(f"--- {title} ---")
            if items:
                for item in items:
                    self.web_buffer.append(item)
            if messages:
                for msg in messages:
                    self.web_buffer.append(msg)
            return

        self.clear_screen()
        lines = []
        if title:
            lines.append(f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{self.CLR}")
            lines.append("")

        if items:
            for item in items:
                lines.append(f"{self.WHITE}{item}{self.CLR}")

        if messages:
            for msg in messages:
                lines.append(msg)
        if wait:
            lines.append("")
            lines.append(f"{self.GREEN}[ Press any key to continue ]{self.CLR}")

        self._print_block(lines)
        if wait:
            readchar.readkey()

    def show_vertical_list(self, items, title, window_size=20, mode="plain", columns=None):
        if self.web_mode:
            self.web_buffer.append(f"--- {title} ---")
            for item in items:
                self.web_buffer.append(item)
            return

        if not items:
            self.clear_screen()
            self._print_block([
                f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{self.CLR}",
                "",
                f"{self.WHITE}No items to display.{self.CLR}",
                "",
                f"{self.GREEN}[ Press any key to continue ]{self.CLR}",
            ])
            readchar.readkey()
            return

        items_list = list(items)
        total = len(items_list)
        start_idx = 0 if mode == "raw" else max(0, total - window_size)

        while True:
            self.clear_screen()
            end_idx = min(start_idx + window_size, total)
            current_items = items_list[start_idx:end_idx]
            if mode == "table" and columns:
                table = self._build_labeled_table(current_items, columns)
                rows = len(current_items) + 1
            else:
                lines = [
                    f"{self.CYAN}{self.BOLD}{' ' * 8}{title} "
                    f"({start_idx + 1}-{end_idx}/{total}){self.CLR}",
                    "",
                ]
                for item in current_items:
                    if mode == "raw":
                        lines.append(item)
                    else:
                        lines.append(f"{self.WHITE}{item}{self.CLR}")
                lines.append("")
                lines.append(f"{self.YELLOW}[ k: up | j: down | any other key: exit ]{self.CLR}")
                self._print_block(lines)
                key = readchar.readkey()
                low_key = key.lower() if isinstance(key, str) else key

                if low_key == "k":
                    start_idx = max(0, start_idx - 1)
                    continue
                if low_key == "j":
                    max_start = max(0, total - window_size)
                    start_idx = min(max_start, start_idx + 1)
                    continue
                return

            title_line = (
                f"{self.CYAN}{self.BOLD}{' ' * 8}{title} "
                f"({start_idx + 1}-{end_idx}/{total}){self.CLR}"
            )
            footer = f"{self.YELLOW}[ k: up | j: down | any other key: exit ]{self.CLR}"
            self._print_list_layout(title_line, table, footer, content_line_estimate=rows + 4)
            key = readchar.readkey()
            low_key = key.lower() if isinstance(key, str) else key

            if low_key == "k":
                start_idx = max(0, start_idx - 1)
                continue
            if low_key == "j":
                max_start = max(0, total - window_size)
                start_idx = min(max_start, start_idx + 1)
                continue
            return

    def show_tree_scroll(self, lines, title, window_size=30):
        """Scrollable left-aligned tree display. Lines are ANSI strings with ├── └── │ chars."""
        if self.web_mode:
            self.web_buffer.append(f"--- {title} ---")
            for line in lines:
                self.web_buffer.append(line)
            return

        lines_list = list(lines)
        total = len(lines_list)

        if not total:
            self.clear_screen()
            self._print_line(f"{self.CYAN}{self.BOLD}{title}{self.CLR}", center=False)
            self._print_line(f"{self.WHITE}No objects to display.{self.CLR}", center=False)
            readchar.readkey()
            return

        start_idx = 0

        while True:
            self.clear_screen()
            end_idx = min(start_idx + window_size, total)

            px = self.margin_x
            pad = " " * px

            self.console.print(
                f"{pad}{self.CYAN}{self.BOLD}{title} "
                f"({start_idx + 1}-{end_idx}/{total}){self.CLR}",
                highlight=False,
            )
            self.console.print("", highlight=False)

            for item in lines_list[start_idx:end_idx]:
                text = self._as_rich_text(item)
                from rich.padding import Padding as _Pad
                self.console.print(_Pad(text, (0, px)), highlight=False, soft_wrap=True)

            self.console.print("", highlight=False)
            self.console.print(
                f"{pad}{self.YELLOW}[ k: up | j: down | any other key: exit ]{self.CLR}",
                highlight=False,
            )

            key = readchar.readkey()
            low = key.lower() if isinstance(key, str) else key

            if low == "k":
                start_idx = max(0, start_idx - 1)
            elif low == "j":
                start_idx = min(max(0, total - window_size), start_idx + 1)
            else:
                return

    def show_list(self, items, title, limit=20):
        if self.web_mode:
            self.web_buffer.append(f"--- {title} ---")
            for item in items:
                self.web_buffer.append(item)
            return

        items_list = list(items)

        if not items_list:
            self.clear_screen()
            self._print_block([
                f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{self.CLR}",
                "",
                f"{self.WHITE}No items to display.{self.CLR}",
                "",
                f"{self.GREEN}[ Press any key to continue ]{self.CLR}",
            ])
            readchar.readkey()
            return

        query = ""
        searching = False
        page_idx = 0

        try:
            while True:
                filtered = [it for it in items_list if not query or query.lower() in str(it).lower()]
                pages = [filtered[i:i + limit] for i in range(0, len(filtered), limit)] or [[]]
                num_pages = len(pages)
                page_idx = min(page_idx, max(0, num_pages - 1))

                self.clear_screen()
                current_page = pages[page_idx]
                table, cols = self._build_excel_table(current_page)
                rows = (len(current_page) + cols - 1) // cols if current_page else 0

                if searching:
                    count_str = f" ({len(filtered)}/{len(items_list)})"
                    title_line = f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{count_str}{self.CLR}"
                    footer = f"{self.YELLOW}/ {query}_  \033[2m[ esc: cancel | enter: confirm ]\033[0m{self.CLR}"
                elif query:
                    count_str = f" ({len(filtered)}/{len(items_list)})"
                    title_line = f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{count_str}{self.CLR}"
                    footer = f"{self.YELLOW}/ {query}  \033[2m[ f: edit | esc: clear | h: prev | l: next ]\033[0m{self.CLR}"
                else:
                    title_line = f"{self.CYAN}{self.BOLD}{' ' * 8}{title} ({page_idx + 1}/{num_pages}){self.CLR}"
                    if num_pages > 1:
                        footer = f"{self.YELLOW}[ h: prev | l: next | f: search | other: exit ]{self.CLR}"
                    else:
                        footer = f"{self.GREEN}[ f: search | any key: exit ]{self.CLR}"

                self._print_list_layout(title_line, table, footer, content_line_estimate=rows + 4)
                key = readchar.readkey()

                if not isinstance(key, str):
                    if not searching and not query:
                        return
                    continue

                if key == '\x1b':
                    if searching or query:
                        query = ""
                        searching = False
                        page_idx = 0
                    else:
                        return
                elif key in ('\b', '\x7f', '\x08'):
                    if searching:
                        query = query[:-1]
                    elif not query:
                        return
                elif key in ('\r', '\n'):
                    searching = False
                elif searching:
                    if len(key) == 1 and key.isprintable():
                        query += key
                        page_idx = 0
                elif key == 'f':
                    searching = True
                elif key == 'h':
                    page_idx = (page_idx - 1) % num_pages
                elif key == 'l':
                    page_idx = (page_idx + 1) % num_pages
                else:
                    return

        except Exception as e:
            self._print_block(["", f"Error: {e}"])
            readchar.readkey()

    def ask_confirmation(self, message):
        """Asks for a 3-digit random code confirmation"""
        if self.web_mode:
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.web_buffer.append(f"{message}")
            self.web_buffer.append(f"Type the code: {code}")
            raise WebInputInterrupt(f"Confirm code: {code}", type="confirm", options={"code": code})

        self.clear_screen()
        code = "".join([str(random.randint(0, 9)) for _ in range(3)])
        self._print_block([
            f"{self.WHITE}{message}{self.CLR}",
            "",
            f"Type the code: {self.CYAN}{self.BOLD}{code}{self.CLR}",
            f"Input: {self.YELLOW}",
        ], last_end="")
        
        user_input = ""
        for _ in range(3):
            char = readchar.readkey()
            if char.isdigit():
                user_input += char
                self.console.print(char, end="", highlight=False, soft_wrap=True)
            else:
                # If non-digit, still count as a character but it will fail comparison
                user_input += char
                self.console.print("*", end="", highlight=False, soft_wrap=True)
        
        time.sleep(0.3) # Brief pause for user to see their input
        
        if user_input == code:
            self._print_block(["", "", f"{self.GREEN}CONFIRMED.{self.CLR}"], vcenter=False)
            time.sleep(0.5)
            return True
        else:
            self._print_block(["", "", f"{self.MAGENTA}FAILED. Operation cancelled.{self.CLR}"], vcenter=False)
            time.sleep(1.0)
            return False

    def clear_screen(self):
        self.console.clear()

    def show_tree(self, nodes, title="TREE VIEW"):
        """Recursive tree display with prefix lines"""
        self.clear_screen()
        lines = [f"{self.CYAN}{self.BOLD}{' ' * 4}{title}{self.CLR}", ""]
        lines.extend(self._collect_tree_lines(nodes))
        lines.extend(["", f"{self.WHITE}[ Press any key to return ]{self.CLR}"])
        self._print_block(lines)
        readchar.readkey()

    def print_tree(self, nodes):
        """Prints tree without clearing or waiting"""
        for idx, (label, children) in enumerate(nodes):
            self._print_tree_node(label, children, "", idx == len(nodes) - 1)

    def _collect_tree_lines(self, nodes):
        lines = []
        for idx, (label, children) in enumerate(nodes):
            self._append_tree_lines(lines, label, children, "", idx == len(nodes) - 1)
        return lines

    def _append_tree_lines(self, lines, label, children, prefix, is_last):
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{label}")

        new_prefix = prefix + ("    " if is_last else "│   ")
        for idx, (child_label, child_children) in enumerate(children):
            self._append_tree_lines(lines, child_label, child_children, new_prefix, idx == len(children) - 1)

    def _print_tree_node(self, label, children, prefix, is_last):
        connector = "└── " if is_last else "├── "
        self._print_line(f"{prefix}{connector}{label}")
        
        new_prefix = prefix + ("    " if is_last else "│   ")
        for idx, (child_label, child_children) in enumerate(children):
            self._print_tree_node(child_label, child_children, new_prefix, idx == len(children) - 1)

    def show_menu(self, title, options, footer=None):
        """Standardized menu display"""
        if self.web_mode:
            self.web_buffer.append(f"--- {title} ---")
            for k, v in options.items():
                self.web_buffer.append(f"{k} - {v}")
            raise WebInputInterrupt(f"Select option for {title}", type="menu", options=options)

        self.clear_screen()
        lines = [f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{self.CLR}", ""]
        
        for key, label in options.items():
            lines.append(f" {self.YELLOW}{self.BOLD}{key}{self.CLR} - {self.WHITE}{label}{self.CLR}")
            
        if footer:
            lines.append("")
            lines.append(footer)
            
        lines.append("")
        lines.append(f"{self.CYAN}Selection: {self.CLR}")
        self._print_block(lines, last_end="")
        return readchar.readkey()

    def render(self, buffer, skip_clear=False, show_animated=False, force_print=False):
        if self.web_mode:
             # In web mode, render is handled by the client polling status
             return

        if not skip_clear:
            self.clear_screen()

        marquee_panel = self._build_marquee_panel()
        self.console.print(
            Padding(Align.center(marquee_panel), (0, self.margin_x)),
            highlight=False,
            soft_wrap=True,
        )
        
        total_height = max(24, self.console.size.height)
        aux_height = max(5, min(8, total_height // 7))
        if self.home_input_armed:
            mode_line = f"\033[1;33m-- INSERT --\033[0m"
        else:
            mode_line = f"\033[2m-- NORMAL --\033[0m"
        if buffer:
            visual = self.format_visual_buffer(buffer)
            parsed = self.process_view(buffer)
            evove_lines = [mode_line, visual]
            if parsed:
                evove_lines.append(parsed)
        else:
            evove_lines = [mode_line, f"\033[2m_\033[0m"]
        side_panels = self._build_commands_side_panel(evove_lines=evove_lines, aux_height=aux_height)
        self.console.print(
            Padding(side_panels, (0, self.margin_x)),
            highlight=False,
            soft_wrap=True,
        )

# Global instance
ui = UI()
