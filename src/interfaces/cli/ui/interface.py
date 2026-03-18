import os
import time
import readchar
import random
import sys
import select
from rich.align import Align
from rich.console import Console
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

    def _build_commands_side_panel(self):
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE_HEAVY,
            pad_edge=False,
            expand=True,
            collapse_padding=True,
        )
        table.add_column("CMD", justify="left", style="yellow", no_wrap=True)
        table.add_column("LABEL", justify="left", style="white", overflow="fold", no_wrap=False)

        term_height = max(12, self.console.size.height)
        max_rows = max(8, term_height - 14)
        rows = sorted(self.SINGLE_COMMANDS.items(), key=lambda x: (len(x[0]), x[0]))
        for cmd, info in rows[:max_rows]:
            table.add_row(str(cmd), str(info.get("label", "")))

        if len(rows) > max_rows:
            table.add_row("...", f"+{len(rows) - max_rows} comandos")

        return Panel(table, title="[dim]comandos[/]", border_style="blue")

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
        start_idx = max(0, total - window_size)

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

    def show_list(self, items, title, limit=20):
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

        # Split items into pages
        items_list = list(items)
        pages = [items_list[i:i + limit] for i in range(0, len(items_list), limit)]
        num_pages = len(pages)
        page_idx = 0

        try:
            while True:
                self.clear_screen()
                current_page = pages[page_idx]
                table, cols = self._build_excel_table(current_page)
                rows = (len(current_page) + cols - 1) // cols

                if num_pages > 1:
                    footer = f"{self.YELLOW}[ h: previous | l: next | any other key: exit ]{self.CLR}"
                    title_line = f"{self.CYAN}{self.BOLD}{' ' * 8}{title} (Page {page_idx + 1}/{num_pages}){self.CLR}"
                    self._print_list_layout(title_line, table, footer, content_line_estimate=rows + 4)
                    key = readchar.readkey()
                    low_key = key.lower() if isinstance(key, str) else key

                    if low_key == "h":
                        page_idx = (page_idx - 1) % num_pages
                        continue
                    if low_key == "l":
                        page_idx = (page_idx + 1) % num_pages
                        continue
                    return

                title_line = f"{self.CYAN}{self.BOLD}{' ' * 8}{title} (Page {page_idx + 1}/{num_pages}){self.CLR}"
                footer = f"{self.GREEN}[ Press any key to continue ]{self.CLR}"
                self._print_list_layout(title_line, table, footer, content_line_estimate=rows + 4)
                readchar.readkey()
                return
        except Exception as e:
            # Fallback if cycling fails (e.g. terminal issues)
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
        
        # ═══════════════════════════════════════════════════════════
        # EXIBIÇÃO DE TOTAL POINTS
        # Usa self.user que já está disponível na instância UI
        # ═══════════════════════════════════════════════════════════
        points_str = f"P: {self.WHITE}{self.BOLD}{self.user.total_points}{self.CLR}"
        lines = [points_str]
        
        buffer_view = self.format_visual_buffer(buffer)
        process_view_result = self.process_view(buffer)
        
        lines.append(f"{buffer_view}")
        lines.append(f"{process_view_result}")
        
        from src.application.services.challenge_service import ChallengeManager
        cm = ChallengeManager()
        if cm.active_challenge:
            rem = cm.get_remaining_time()
            lines.append("")
            lines.append(f"{self.YELLOW}{self.BOLD}[ CHALLENGE: {rem}s ]{self.CLR}")
            lines.append(f"{self.WHITE}DO: {cm.active_challenge['required_value']} {cm.active_challenge['name'].upper()}{self.CLR}")

        debug = ""
        if debug:
            lines.append("DEBUG")
            lines.append(f"{debug}")
        main_text = Text.from_ansi("\n".join(lines))
        main_panel = Panel(Align.left(main_text), title="[dim]interface[/]", border_style="cyan")
        side_panel = self._build_commands_side_panel()
        self.console.print(
            Padding(Columns([main_panel, side_panel], expand=True, equal=False), (0, self.margin_x)),
            highlight=False,
            soft_wrap=True,
        )

# Global instance
ui = UI()
