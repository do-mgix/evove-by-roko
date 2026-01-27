import os
import sys
import time 
import readchar

class DialDigest:
    def __init__(self):
        # Import and assign to instances
        from src.components.data.constants import (
            user, 
            him,
            SINGLE_COMMANDS, 
            OBJECTS, 
            INTERACTIONS,
            COMMANDS  # Added to avoid NameError
        )
        
        self.user = user
        self.SINGLE_COMMANDS = SINGLE_COMMANDS
        self.OBJECTS = OBJECTS
        self.INTERACTIONS = INTERACTIONS
        self.COMMANDS = COMMANDS
    

    def get_info(self, char, buffer):
        """Returns the type and data of the character, if it exists."""
        if char in self.INTERACTIONS:
            return "INTERACTION", self.INTERACTIONS[char]
        if char in self.OBJECTS:
            return "OBJECT", self.OBJECTS[char]
        if buffer in self.SINGLE_COMMANDS:
            return "SINGLE_COMMAND", self.SINGLE_COMMANDS[buffer]
        return None, None

    def get_length(self, buffer):
        if not buffer: return 1

        is_prefix = False
        for cmd, info in self.SINGLE_COMMANDS.items():
            if cmd.startswith(buffer):
                is_prefix = True
                if len(buffer) < len(cmd):
                     continue 
                else:
                    total_esperado = len(cmd) + info["len"]
                    if len(buffer) < total_esperado:
                        return total_esperado - len(buffer)
                    return 0
            elif buffer.startswith(cmd):
                total_esperado = len(cmd) + info["len"]
                if len(buffer) < total_esperado:
                    return total_esperado - len(buffer)
                return 0

        if is_prefix:
            return 1

        ptr = 0
        phrase = []
        
        while ptr < len(buffer):
            char = buffer[ptr]
            info = self.OBJECTS.get(char) or self.INTERACTIONS.get(char)
            
            if not info: return 1            
            phrase.append(info["label"])
            ptr += 1         
           
            payload_needed = info["len"]
            chars_restantes = len(buffer) - ptr
            
            if chars_restantes < payload_needed:
                return payload_needed - chars_restantes
                
            ptr += payload_needed
            
            if " ".join(phrase) in self.COMMANDS:
                return 0

        return 1 

    def parse_buffer(self, buffer):
        for cmd_prefix, info in self.SINGLE_COMMANDS.items():
            if buffer.startswith(cmd_prefix):
                payload_len = info["len"]
                cmd_len = len(cmd_prefix)
                payload = buffer[cmd_len : cmd_len + payload_len]
                label = info.get("label", info["func"].__name__)
                return label, [payload] if payload else [], True
        
        ptr = 0
        tokens = []
        payloads = []

        while ptr < len(buffer):
            char = buffer[ptr]
            info = self.OBJECTS.get(char) or self.INTERACTIONS.get(char)
            
            if not info: 
                break
                
            tokens.append(info["label"])
            ptr += 1
            
            if info["len"] > 0:
                id_value = buffer[ptr : ptr + info["len"]]
                if id_value:
                    payloads.append(id_value)
                ptr += info["len"]
                
        return " ".join(tokens), payloads, False

    def process(self, buffer):
        # Call internal method using self
        faltando = self.get_length(buffer)
        
        if faltando == 0 and len(buffer) > 0:
            phrase, payloads, is_single = self.parse_buffer(buffer)
            
            if is_single:
                for cmd_prefix, info in self.SINGLE_COMMANDS.items():
                    if buffer.startswith(cmd_prefix):
                        if info["len"] > 0:
                            payload = payloads[0] if payloads else ""
                            result = info["func"](payload if payload else buffer)
                        else:
                            result = info["func"]()
                        return True, result
            
            if phrase in self.COMMANDS:
                func = self.COMMANDS[phrase]["func"]
                result = func(payloads) 
                return True, result
            
            return True, None
        return False, None

dial = DialDigest()
