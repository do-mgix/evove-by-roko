import os
import time
import readchar
import random
import sys
import select


class UI:
    def __init__(self):
        # Cores (propriedades da instância)
        self.CLR = "\033[0m"
        self.BOLD = "\033[1m"
        self.CYAN = "\033[36m"
        self.GREEN = "\033[32m"
        self.YELLOW = "\033[33m"
        self.WHITE = "\033[37m"
        self.MAGENTA = "\033[35m"

        # Importa apenas das constantes
        from src.components.data.constants import (
            user, 
            SINGLE_COMMANDS, 
            OBJECTS, 
            INTERACTIONS
        )
        
        self.user = user
        self.SINGLE_COMMANDS = SINGLE_COMMANDS
        self.OBJECTS = OBJECTS
        self.INTERACTIONS = INTERACTIONS

    
    def format_visual_buffer(self, buffer):
        """Formata o buffer dinamicamente: 801 - 2 - 50_"""
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
            info = self.OBJECTS.get(char) or self.INTERACTIONS.get(char)
            
            if info:
                chunk_len = 1 + info["len"]
                chunk = buffer[ptr : ptr + chunk_len]
                res.append(chunk)
                ptr += chunk_len
            else:
                # Caso o caractere não seja reconhecido, avança 1
                res.append(buffer[ptr])
                ptr += 1
        
        joined = " - ".join(res)
        return f"{self.YELLOW}{joined}{self.WHITE}_"
    
    def process_view(self, buffer):
        if not buffer:
            return ""
            
        from src.components.services.dial_interaction.dial_digest import dial
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
                    status_parts.append(f"{self.WHITE}⚪ ({nome}){self.CLR}")
                    p_idx += 1
                elif t == "add":
                    status_parts.append(f"{self.CYAN}Add{self.CLR}")
                elif t == "action":
                    id_val = f"5{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._actions.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{self.MAGENTA}⭐ ({nome}){self.CLR}")
                    p_idx += 1
                elif t == "act":
                    status_parts.append(f"{self.GREEN}Act{self.CLR}")
                elif t == "delete":
                    status_parts.append(f"{self.YELLOW}Delete{self.CLR}")
        
        return " -> ".join(status_parts) if status_parts else ""
    
    def show_messages_animated(self, messages):
        """Mostra mensagens uma por uma, cada mensagem sozinha na tela"""
        for msg in messages:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(msg)
            
            # Calcula tempo de espera baseado no tamanho da mensagem
            wait_time = len(msg) * 0.05  # 0.05 segundos por caractere
            time.sleep(wait_time)

    def show_list(self, items, title, limit=20):
        """Show items in pages and cycle every 1 second until a key is pressed"""
        if not items:
            self.clear_screen()
            print(f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{self.CLR}\n")
            print(f"{self.WHITE}No items to display.{self.CLR}")
            print(f"\n{self.GREEN}[ Press any key to continue ]{self.CLR}")
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
                print(f"{self.CYAN}{self.BOLD}{' ' * 8}{title} (Page {page_idx + 1}/{num_pages}){self.CLR}\n")
                
                current_page = pages[page_idx]
                col_width = 30
                
                for i in range(0, len(current_page), 2):
                    col1 = current_page[i]
                    line = f"{self.WHITE}{col1}{self.CLR}".ljust(col_width + 10)
                    
                    if i + 1 < len(current_page):
                        col2 = current_page[i+1]
                        line += f"{self.WHITE}{col2}{self.CLR}"
                    
                    print(line)
                
                if num_pages > 1:
                    print(f"\n{self.YELLOW}>>> Cycling pages every 1s... Press any key to stop <<<{self.CLR}")
                else:
                    print(f"\n{self.GREEN}[ Press any key to continue ]{self.CLR}")

                # Wait 1s or until key press
                start_time = time.time()
                while time.time() - start_time < 2.0:
                    # Non-blocking check for key press on Linux
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        readchar.readkey() # Consume the key
                        return
                
                if num_pages > 1:
                    page_idx = (page_idx + 1) % num_pages
                else:
                    # If only one page, we could either return after 1s or keep showing it.
                    # Usually for 1 page, waiting for a key is better, but to be consistent:
                    pass
        except Exception as e:
            # Fallback if cycling fails (e.g. terminal issues)
            print(f"\nError: {e}")
            readchar.readkey()

    def ask_confirmation(self, message):
        """Asks for a 3-digit random code confirmation without enter"""
        self.clear_screen()
        code = "".join([str(random.randint(0, 9)) for _ in range(3)])
        
        print(f"{self.WHITE}{message}{self.CLR}")
        print(f"\nType the code: {self.CYAN}{self.BOLD}{code}{self.CLR}")
        print(f"Input: {self.YELLOW}", end="", flush=True)
        
        user_input = ""
        for _ in range(3):
            char = readchar.readkey()
            if char.isdigit():
                user_input += char
                print(char, end="", flush=True)
            else:
                # If non-digit, still count as a character but it will fail comparison
                user_input += char
                print("*", end="", flush=True)
        
        time.sleep(0.3) # Brief pause for user to see their input
        
        if user_input == code:
            print(f"\n\n{self.GREEN}CONFIRMED.{self.CLR}")
            time.sleep(0.5)
            return True
        else:
            print(f"\n\n{self.MAGENTA}FAILED. Operation cancelled.{self.CLR}")
            time.sleep(1.0)
            return False

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def show_tree(self, nodes, title="TREE VIEW"):
        """Recursive tree display with prefix lines"""
        self.clear_screen()
        print(f"{self.CYAN}{self.BOLD}{' ' * 4}{title}{self.CLR}\n")
        self.print_tree(nodes)
        print(f"\n{self.WHITE}[ Press any key to return ]{self.CLR}")
        readchar.readkey()

    def print_tree(self, nodes):
        """Prints tree without clearing or waiting"""
        for idx, (label, children) in enumerate(nodes):
            self._print_tree_node(label, children, "", idx == len(nodes) - 1)

    def _print_tree_node(self, label, children, prefix, is_last):
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{label}")
        
        new_prefix = prefix + ("    " if is_last else "│   ")
        for idx, (child_label, child_children) in enumerate(children):
            self._print_tree_node(child_label, child_children, new_prefix, idx == len(children) - 1)

    def show_menu(self, title, options, footer=None):
        """Standardized menu display"""
        self.clear_screen()
        print(f"{self.CYAN}{self.BOLD}{' ' * 8}{title}{self.CLR}\n")
        
        for key, label in options.items():
            print(f" {self.YELLOW}{self.BOLD}{key}{self.CLR} - {self.WHITE}{label}{self.CLR}")
            
        if footer:
            print(f"\n{footer}")
            
        print(f"\n{self.CYAN}Selection: {self.CLR}", end="", flush=True)
        return readchar.readkey()

    def render(self, buffer, skip_clear=False, show_animated=False):
        if not skip_clear:
            os.system('cls' if os.name == 'nt' else 'clear')
        
        buffer_view = self.format_visual_buffer(buffer)
        process_view_result = self.process_view(buffer)
        
        print(f"{buffer_view}")
        print(f"{process_view_result}")
        
        debug = ""
        if debug:
            print(f"DEBUG")
            print(f"{debug}")

# Instância global
ui = UI()
