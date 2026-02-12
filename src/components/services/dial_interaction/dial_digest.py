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
        if char == "1" and buffer is not None:
            tag_info = self.OBJECTS.get(char)
            if tag_info and len(buffer) >= (1 + tag_info.get("len", 0)):
                return "OBJECT", tag_info
            if char in self.INTERACTIONS:
                return "INTERACTION", self.INTERACTIONS[char]
        if char in self.INTERACTIONS:
            return "INTERACTION", self.INTERACTIONS[char]
        if char in self.OBJECTS:
            return "OBJECT", self.OBJECTS[char]
        if buffer in self.SINGLE_COMMANDS:
            return "SINGLE_COMMAND", self.SINGLE_COMMANDS[buffer]
        return None, None

    def _get_info_for_char(self, buffer, ptr):
        char = buffer[ptr]
        if char == "1":
            tag_info = self.OBJECTS.get(char)
            if tag_info:
                needed = 1 + tag_info.get("len", 0)
                if (len(buffer) - ptr) >= needed:
                    return tag_info
            return self.INTERACTIONS.get(char)
        if char == "5":
            return self._get_action_info(buffer, ptr)
        return self.OBJECTS.get(char) or self.INTERACTIONS.get(char)

    def _is_valid_logic_type(self, logic_type):
        if logic_type is None:
            return False
        return str(logic_type) in getattr(self.user, "logic_types", {})

    def _is_valid_sublogic(self, logic_type, sublogic_type):
        if sublogic_type is None:
            return False
        logic_types = getattr(self.user, "logic_types", {})
        sublogic_types = getattr(self.user, "sublogic_types", {})
        lt = str(logic_type)
        st = str(sublogic_type)
        if st not in sublogic_types:
            return False
        subs = logic_types.get(lt, {}).get("subs", [])
        return st in subs

    def _get_action_info(self, buffer, ptr):
        remaining = len(buffer) - (ptr + 1)
        if remaining < 2:
            return {"label": "action", "len": 2, "ambiguous": False}
        logic_candidate = buffer[ptr + 1 : ptr + 3]
        has_logic = self._is_valid_logic_type(logic_candidate)
        if not has_logic:
            return {"label": "action", "len": 2, "ambiguous": False}

        # Logic type exists; choose id5/id7 if enough digits are present.
        if remaining >= 6:
            sub_candidate = buffer[ptr + 3 : ptr + 5]
            if self._is_valid_sublogic(logic_candidate, sub_candidate):
                return {"label": "action", "len": 6, "ambiguous": False}
            return {"label": "action", "len": 4, "ambiguous": False}
        if remaining > 4:
            sub_candidate = buffer[ptr + 3 : ptr + 5]
            if self._is_valid_sublogic(logic_candidate, sub_candidate):
                return {"label": "action", "len": 6, "ambiguous": False}
            return {"label": "action", "len": 4, "ambiguous": False}
        if remaining == 4:
            return {"label": "action", "len": 4, "ambiguous": False}

        # Not enough digits for id5 yet: treat as id3 but mark ambiguous.
        return {"label": "action", "len": 2, "ambiguous": True}

    def _normalize_buffer(self, buffer):
        if not buffer:
            return buffer
        if all(c.isdigit() or c == " " for c in buffer):
            return buffer.replace(" ", "")
        return buffer

    def get_state(self, buffer):
        buffer = self._normalize_buffer(buffer)
        if not buffer:
            return {"remaining": 0, "ambiguous": False, "complete": False}

        is_prefix = False
        for cmd, info in self.SINGLE_COMMANDS.items():
            if cmd.startswith(buffer):
                is_prefix = True
                if len(buffer) < len(cmd):
                    return {"remaining": len(cmd) - len(buffer), "ambiguous": False, "complete": False}
                total_esperado = len(cmd) + info["len"]
                if len(buffer) < total_esperado:
                    return {"remaining": total_esperado - len(buffer), "ambiguous": False, "complete": False}
                return {"remaining": 0, "ambiguous": False, "complete": True}
            elif buffer.startswith(cmd):
                total_esperado = len(cmd) + info["len"]
                if len(buffer) < total_esperado:
                    return {"remaining": total_esperado - len(buffer), "ambiguous": False, "complete": False}
                return {"remaining": 0, "ambiguous": False, "complete": True}

        if is_prefix:
            return {"remaining": 1, "ambiguous": False, "complete": False}

        ptr = 0
        phrase = []
        ambiguous = False
        
        while ptr < len(buffer):
            char = buffer[ptr]
            info = self._get_info_for_char(buffer, ptr)
            
            if not info:
                return {"remaining": 1, "ambiguous": False, "complete": False}
            phrase.append(info["label"])
            ptr += 1         
           
            payload_needed = info["len"]
            if info.get("ambiguous"):
                ambiguous = True
            chars_restantes = len(buffer) - ptr
            
            if chars_restantes < payload_needed:
                return {"remaining": payload_needed - chars_restantes, "ambiguous": False, "complete": False}
                
            ptr += payload_needed
            
            if " ".join(phrase) in self.COMMANDS:
                if ptr == len(buffer):
                    return {"remaining": 0, "ambiguous": ambiguous, "complete": True}
                return {"remaining": 1, "ambiguous": False, "complete": False}

        return {"remaining": 1, "ambiguous": False, "complete": False}

    def get_length(self, buffer):
        return self.get_state(buffer)["remaining"]

    def parse_buffer(self, buffer):
        buffer = self._normalize_buffer(buffer)
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
            info = self._get_info_for_char(buffer, ptr)
            
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

    def process(self, buffer, force=False):
        buffer = self._normalize_buffer(buffer)
        # Call internal method using self
        state = self.get_state(buffer)
        faltando = state["remaining"]
        
        if faltando == 0 and len(buffer) > 0:
            if state.get("ambiguous") and not force:
                return False, None
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
