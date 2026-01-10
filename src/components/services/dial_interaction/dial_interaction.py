import os
import sys
import time 
import readchar

# importar classe user 
from src.components.user.user import user 

# O 'len' aqui é o tamanho do PAYLOAD (o ID que vem depois do prefixo)
OBJECTS = {
    "8": {"len": 2, "label": "attr"},    # Ex: 8 + 01 = 801
    "5": {"len": 2, "label": "action"},  # Ex: 5 + 01 = 501
}

INTERACTIONS = {
    "2": {"len": 0, "label": "add"},     # Apenas o dígito '2'
    "1": {"len": 0, "label": "act"},     

}

# Comandos de atalho que não seguem a regra de Attr/Action
SINGLE_COMMANDS = {
    "1":  {"len": 0, "func": user.wake},
    "3":  {"len": 0, "func": user.sleep},
    "25": {"len": 2, "func": user.create_action}, 
    "28": {"len": 0, "func": user.create_attribute}, 

}

COMMANDS = {        
    "attr add action": {"func": user.attribute_add_action},
    "action act": {"func": user.act},
}

# --- CONFIGURAÇÕES DE UI ---
CLR = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
WHITE = "\033[37m"
MAGENTA = "\033[35m"

def get_info(char, buffer):
    """Retorna o tipo e os dados do caractere, se existir."""
    if char in INTERACTIONS:
        return "INTERACTION", INTERACTIONS[char]
    if char in OBJECTS:
        return "OBJECT", OBJECTS[char]
    if buffer in SINGLE_COMMANDS:
        return  "SINGLE_COMMAND", SINGLE_COMMANDS[buffer]
    return None, None

def get_length(buffer):
    if not buffer: return 1

    # 1. Checa Comandos Simples (Atalhos)
    for cmd, info in SINGLE_COMMANDS.items():
        if buffer.startswith(cmd):
            total_esperado = len(cmd) + info["len"]
            if len(buffer) < total_esperado:
                return total_esperado - len(buffer)
            return 0

    # 2. Lógica de Montagem de Frase (8xx 2 5xx)
    ptr = 0
    phrase = []
    
    while ptr < len(buffer):
        char = buffer[ptr]
        info = OBJECTS.get(char) or INTERACTIONS.get(char)
        
        if not info: return 0 # Erro: caractere não reconhecido
            
        phrase.append(info["label"])
        ptr += 1 # Pula o identificador (8, 5 ou 2)
        
        # Verifica se os IDs (ex: '01') estão completos
        payload_needed = info["len"]
        chars_restantes = len(buffer) - ptr
        
        if chars_restantes < payload_needed:
            return payload_needed - chars_restantes
            
        ptr += payload_needed # Pula os IDs (xx)
        
        # Se a frase formada (ex: "attr add action") existe, acabou.
        if " ".join(phrase) in COMMANDS:
            return 0

    return 1 # Se saiu do loop, o comando ainda está incompleto

def parse_buffer(buffer):
    ptr = 0
    tokens = []
    payloads = []

    while ptr < len(buffer):
        char = buffer[ptr]
        info = OBJECTS.get(char) or INTERACTIONS.get(char)
        
        if not info: break
            
        tokens.append(info["label"])
        ptr += 1
        
        if info["len"] > 0:
            # Pega os 2 dígitos do ID (ex: '01')
            id_value = buffer[ptr : ptr + info["len"]]
            payloads.append(id_value)
            ptr += info["len"]
            
    return " ".join(tokens), payloads

def process(buffer):
    faltando = get_length(buffer)
    
    # Só agimos se o comando estiver completo (faltando == 0)
    if faltando == 0 and len(buffer) > 0:
        
        # 1. Verifica primeiro se é um SINGLE_COMMAND (Atalho)
        for cmd_prefix, info in SINGLE_COMMANDS.items():
            if buffer.startswith(cmd_prefix):
                # Se o comando tem payload (ex: 25 + 0001), passamos o payload
                payload = buffer[len(cmd_prefix):]
                info["func"](payload if payload else buffer)
                return True

        # 2. Se não for atalho, processa como COMANDO DINÂMICO (Cascata)
        phrase, payloads = parse_buffer(buffer)
        
        if phrase in COMMANDS:
            func = COMMANDS[phrase]["func"]
            
            # EXAME DE PAYLOAD:
            # Se a frase for "attr add action", payloads será algo como ["01", "05"]
            # Passamos a lista de IDs extraídos para a função
            func(payloads) 
            return True

        # Se o comando for completo mas não existir na gramática (ex: "attr add")
        # limpamos o buffer retornando True (falha silenciosa ou erro)
        return True 

    return False # Ainda não está completo

def format_visual_buffer(buffer):
    """Formata o buffer com hífens: 801 - 2 - 50_"""
    res = []
    ptr = 0
    # Esta lógica segue sua regra de 3 para objetos e 1 para interação
    while ptr < len(buffer):
        char = buffer[ptr]
        if char in ["8", "5"]:
            chunk = buffer[ptr:ptr+3]
            res.append(chunk)
            ptr += 3
        elif char == "2":
            res.append("2")
            ptr += 1
        else:
            res.append(char)
            ptr += 1
    
    joined = " - ".join(res)
    return f"{YELLOW}{joined}{WHITE}_"

def render(buffer):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    phrase, payloads = parse_buffer(buffer)
    tokens = phrase.split()
    
    # --- SEÇÃO 1: STATUS DO PROCESSO ---
    # ⚪ (801) -> Add -> ⭐ (501)
    status_parts = []
    p_idx = 0
    for t in tokens:
        if t == "attr":
            id_val = f"8{payloads[p_idx]}" if p_idx < len(payloads) else "???"
            nome = user.attributes.get(id_val, "...")
            if hasattr(nome, 'attr_name'): nome = nome.attr_name # Se for objeto
            status_parts.append(f"{WHITE}⚪ ({nome}){CLR}")
            p_idx += 1
        elif t == "add":
            status_parts.append(f"{CYAN}Add{CLR}")
        elif t == "action":
            id_val = f"5{payloads[p_idx]}" if p_idx < len(payloads) else "???"
            nome = user.actions.get(id_val, "...")
            if hasattr(nome, 'name'): nome = nome.name
            status_parts.append(f"{MAGENTA}⭐ ({nome}){CLR}")
            p_idx += 1
    
    process_view = " -> ".join(status_parts) if status_parts else ""
    
    # --- SEÇÃO 2: DISPLAY DO BUFFER ---
    buffer_view = format_visual_buffer(buffer)

    # --- SEÇÃO 4: METADADOS / LOG ---
    faltando = get_length(buffer)
    log_view = f"Faltando: {faltando} dígitos | Buffer Raw: {buffer}"

    # --- IMPRESSÃO DAS TELAS ---
    print(f"{MAGENTA}INPUT BUFFER")
    print(f"{buffer_view}")
    print(f"{process_view}")


def dial_start():

    # carrega os dados do usuário antes de começar o programa
    user.load_user()

    try:

        buffer = ""

        while True:
            render(buffer)
        
            if process(buffer):

                buffer = "" 
                import time
                time.sleep(3) 

                continue 

            key = readchar.readkey()

            if key in (readchar.key.BACKSPACE, '\x7f'):
                buffer = buffer[:-1]

            elif key.isdigit():
                buffer += key

    except KeyboardInterrupt:
        print(f"bye")
        sys.exit(0)

