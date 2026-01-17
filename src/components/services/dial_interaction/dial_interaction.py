import os
import sys
import time 
import readchar

from src.components.user.user import user 
from src.components.entitys.entity_manager import EntityManager
from src.components.services.wizard.wizard import wizard
him = EntityManager().get_entity()

# O 'len' aqui é o tamanho do PAYLOAD (o ID que vem depois do prefixo)
OBJECTS = {
    "8": {"len": 2, "label": "attr"},    # Ex: 8 + 01 = 801
    "5": {"len": 2, "label": "action"},  # Ex: 5 + 01 = 501
}

INTERACTIONS = {
    "2": {"len": 0, "label": "add"},     # Apenas o dígito '2'
    "1": {"len": 0, "label": "act"},     
    "0": {"len": 0, "label": "delete"},     
    "4": {"len": 0, "label": "configure"},     

}

# Comandos de atalho que não seguem a regra de Attr/Action
SINGLE_COMMANDS = {
    "1":  {"len": 0, "func": him.cutucar, "label": ""},
    "25": {"len": 2, "func": user.create_action, "label": "create_action"}, 
    "28": {"len": 0, "func": user.create_attribute, "label": "create_attr"}, 
    "4":  {"len": 0, "func": wizard.start, "label": "super_create_attr"},
    "98": {"len": 0, "func": user.list_attributes, "label": "list_attr"}, 
    "95": {"len": 0, "func": user.list_actions, "label": "list_actions"}, 
    "005": {"len": 0, "func": user.drop_actions, "label": "drop_actions"}, 
    "008": {"len": 0, "func": user.drop_attributes, "label": "drop_attr"}, 
}

COMMANDS = {        
    "attr add action": {"func": user.attribute_add_action},
    "action act": {"func": user.act},
    "delete attr": {"func": user.delete_attribute},
    "add add attr": {"func": user.create_attribute_by_id},
    "attr add attr": {"func": user.attribute_add_child},

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

    # 1. Checa Comandos Simples (Atalhos) - Prefixo ou Completo
    is_prefix = False
    for cmd, info in SINGLE_COMMANDS.items():
        if cmd.startswith(buffer):
            is_prefix = True
            if len(buffer) < len(cmd):
                # Ainda digitando o prefixo do comando (ex: "9" de "98")
                continue 
            else:
                # Comando completo, verifica se precisa de mais dígitos (payload)
                total_esperado = len(cmd) + info["len"]
                if len(buffer) < total_esperado:
                    return total_esperado - len(buffer)
                return 0
        elif buffer.startswith(cmd):
            # Se o buffer já passou do comando (ex: payload sendo digitado)
            total_esperado = len(cmd) + info["len"]
            if len(buffer) < total_esperado:
                return total_esperado - len(buffer)
            return 0

    if is_prefix:
        # Se o buffer é prefixo de algum comando mas não o comando completo ainda
        # Precisamos de pelo menos mais um dígito para ver se forma o comando
        # Note: Esta lógica assume comandos de comprimento variado.
        # Se '9' é prefixo de '98', retornamos 1 para esperar o próximo.
        return 1

    # 2. Lógica de Montagem de Frase (8xx 2 5xx)
    ptr = 0
    phrase = []
    
    while ptr < len(buffer):
        char = buffer[ptr]
        info = OBJECTS.get(char) or INTERACTIONS.get(char)
        
        if not info: return 1 # Erro: caractere não reconhecido, continua esperando ou trata como erro
            
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
    """
    Analisa o buffer e retorna (phrase, payloads, is_single_command).
    """
    # 1. Tenta encontrar um comando simples (Single Command)
    for cmd_prefix, info in SINGLE_COMMANDS.items():
        if buffer.startswith(cmd_prefix):
            payload_len = info["len"]
            cmd_len = len(cmd_prefix)
            payload = buffer[cmd_len : cmd_len + payload_len]
            # Retorna o label ou nome da função para o "phrase"
            label = info.get("label", info["func"].__name__)
            return label, [payload] if payload else [], True

    # 2. Processamento Cascata (Dinâmico)
    ptr = 0
    tokens = []
    payloads = []

    while ptr < len(buffer):
        char = buffer[ptr]
        info = OBJECTS.get(char) or INTERACTIONS.get(char)
        
        if not info: 
            # Se não reconhecer o caractere, adiciona como raw e para ou continua
            break
            
        tokens.append(info["label"])
        ptr += 1
        
        if info["len"] > 0:
            id_value = buffer[ptr : ptr + info["len"]]
            if id_value:
                payloads.append(id_value)
            ptr += info["len"]
            
    return " ".join(tokens), payloads, False

def process(buffer):
    faltando = get_length(buffer)
    
    if faltando == 0 and len(buffer) > 0:
        phrase, payloads, is_single = parse_buffer(buffer)
        
        if is_single:
            for cmd_prefix, info in SINGLE_COMMANDS.items():
                if buffer.startswith(cmd_prefix):
                    if info["len"] > 0:
                        payload = payloads[0] if payloads else ""
                        result = info["func"](payload if payload else buffer)
                    else:
                        result = info["func"]()
                    return True, result
        
        if phrase in COMMANDS:
            func = COMMANDS[phrase]["func"]
            result = func(payloads) 
            return True, result
        
        return True, None
    return False, None

def format_visual_buffer(buffer):
    """Formata o buffer dinamicamente: 801 - 2 - 50_"""
    res = []
    ptr = 0
    
    # 1. Tenta formatar como comando simples primeiro se o buffer começar com um
    for cmd, info in SINGLE_COMMANDS.items():
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
        info = OBJECTS.get(char) or INTERACTIONS.get(char)
        
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



def show_messages_animated(messages):
    """Mostra mensagens uma por uma, cada mensagem sozinha na tela"""
    for msg in messages:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(msg)
        
        # Calcula tempo de espera baseado no tamanho da mensagem
        wait_time = len(msg) * 0.05  # 0.05 segundos por caractere
        time.sleep(wait_time)

def render(buffer, skip_clear=False, show_animated=False):
    if not skip_clear:
        os.system('cls' if os.name == 'nt' else 'clear')
    
    # Imprime as mensagens acumuladas do user
    if user.messages:
        if show_animated:
            show_messages_animated(user.messages)
        else:
            for msg in user.messages:
                print(msg)
        print()  # Linha em branco para separar
    
    phrase, payloads, is_single = parse_buffer(buffer)
    tokens = phrase.split()
    
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
                nome = user._attributes.get(id_val, "...")
                if hasattr(nome, '_name'): nome = nome._name
                status_parts.append(f"{WHITE}⚪ ({nome}){CLR}")
                p_idx += 1
            elif t == "add":
                status_parts.append(f"{CYAN}Add{CLR}")
            elif t == "action":
                id_val = f"5{payloads[p_idx]}" if p_idx < len(payloads) else "???"
                nome = user._actions.get(id_val, "...")
                if hasattr(nome, '_name'): nome = nome._name
                status_parts.append(f"{MAGENTA}⭐ ({nome}){CLR}")
                p_idx += 1
            elif t == "act":
                status_parts.append(f"{GREEN}Act{CLR}")
            elif t == "delete":
                status_parts.append(f"{YELLOW}Delete{CLR}")
    
    process_view = " -> ".join(status_parts) if status_parts else ""
    buffer_view = format_visual_buffer(buffer)
    
    print(f"{buffer_view}")
    print(f"{process_view}")

    debug=""
    if debug:
        print(f"DEBUG")
        print(f"{debug}")


def dial_start():
    user.load_user()
    try:
        buffer = ""
        while True:
            render(buffer)
        
            completed, result = process(buffer)
            
            if completed:
                buffer = ""

                # Mostra mensagens do Roko PRIMEIRO (cutucar, random_message, etc)
                if him.messages:
                    show_messages_animated(him.messages)
                    him.clear_messages()

                # Se result é um score (de uma action), oferece ao Roko
                if isinstance(result, (int, float)) and result > 0:
                    him.offer(result)
                    
                    # Mostra mensagens do offer
                    if him.messages:
                        show_messages_animated(him.messages)
                        him.clear_messages()            

                # Se há mensagens do user, mostra elas com animação
                if user.messages:
                    show_messages_animated(user.messages)
                    user.clear_messages()
                
                continue 
            
            key = readchar.readkey()
            if key in (readchar.key.BACKSPACE, '\x7f'):
                buffer = buffer[:-1]
            elif key.isdigit():
                buffer += key
    except KeyboardInterrupt:
        print("BYE")
        sys.exit(0)
