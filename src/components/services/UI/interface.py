import os
import time

CLR = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
WHITE = "\033[37m"
MAGENTA = "\033[35m"

from src.components.services.dial_interaction.dial_digest import dial

class UI:
    def __init__(self):
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
                return f"{YELLOW}{joined}{WHITE}_"
        
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
        return f"{YELLOW}{joined}{WHITE}_"
    
    def process_view(self, buffer):
        if not buffer:
            return ""
            
        phrase, payloads, is_single = dial.parse_buffer(buffer)
        tokens = phrase.split(" ")
        
        status_parts = []
        if is_single:
            label = phrase.upper()
            status_parts.append(f"{CYAN}{label}{CLR}")
            if payloads and payloads[0]:
                status_parts.append(f"{WHITE}({payloads[0]}){CLR}")
        else:
            p_idx = 0
            for t in tokens:
                if t == "attr":
                    id_val = f"8{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._attributes.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{WHITE}⚪ ({nome}){CLR}")
                    p_idx += 1
                elif t == "add":
                    status_parts.append(f"{CYAN}Add{CLR}")
                elif t == "action":
                    id_val = f"5{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                    nome = self.user._actions.get(id_val, "...")
                    if hasattr(nome, '_name'): nome = nome._name
                    status_parts.append(f"{MAGENTA}⭐ ({nome}){CLR}")
                    p_idx += 1
                elif t == "act":
                    status_parts.append(f"{GREEN}Act{CLR}")
                elif t == "delete":
                    status_parts.append(f"{YELLOW}Delete{CLR}")
        
        return " -> ".join(status_parts) if status_parts else ""
    
    def show_messages_animated(self, messages):
        """Mostra mensagens uma por uma, cada mensagem sozinha na tela"""
        for msg in messages:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(msg)
            
            # Calcula tempo de espera baseado no tamanho da mensagem
            wait_time = len(msg) * 0.05  # 0.05 segundos por caractere
            time.sleep(wait_time)
    
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
