# ==================== ACTION.PY ====================
from abc import ABC, abstractmethod
import random

class Action:
    _DIFFICULTY_MULTIPLIER_MAP = {
        0: 1,
        1: 30,
        2: 120,
        3: 400,
        4: 1000,
        5: 2500,
    }
    _TYPE_MAP = {
        0: {"label": "session", "factor": 3},
        1: {"label": "repetitions", "factor": 1},
        2: {"label": "seconds", "factor": 1}, 
        3: {"label": "minutes", "factor": 2}, 
        4: {"label": "hours", "factor": 3}, 
        5: {"label": "letters", "factor": 0.1}, 
        6: {"label": "lines", "factor": 0.5},
        7: {"label": "words", "factor": 0.3},
        8: {"label": "group", "factor": 0},
    }
    
    def __init__(
        self,
        action_id,
        name: str,
        tipo: int,
        diff: int,
        value: float,
        deleted=False,
        logic_type=None,
        sub_logic_type=None,
        max_value=None,
    ):
        if not (0 <= diff <= 5):
            raise ValueError("Difficulty 'diff' must be an integer between 0 and 5.")
        if tipo not in self._TYPE_MAP:
            raise ValueError(f"Invalid action type: {tipo}")
        self._id = action_id
        self._name = str(name).upper()
        self._tipo = tipo
        self._diff = diff
        self._value = value
        if max_value is None:
            self._max_value = value
        else:
            self._max_value = max(max_value, value)
        self._deleted = bool(deleted)
        self._diff_multiplier = self._DIFFICULTY_MULTIPLIER_MAP[diff] 
        self._logic_type = logic_type
        self._sub_logic_type = sub_logic_type
    
    @property
    def id(self):
        return self._id
    
    @property
    def name(self):
        return self._name
    
    @property
    def type(self):
        return self._tipo
    
    @property
    def diff(self):
        return self._diff
    
    @property
    def value(self):
        return self._value

    @property
    def max_value(self):
        return self._max_value

    @property
    def deleted(self):
        return self._deleted

    def set_deleted(self, value=True):
        self._deleted = bool(value)

    def reset_value(self):
        self._value = 0

    def _update_max_value(self):
        if self._value > self._max_value:
            self._max_value = self._value
    
    @property
    def diff_multiplier(self):
        return self._diff_multiplier
    
    @property
    def score(self) -> float: 
        action = self._TYPE_MAP[self.type] 
        type_factor = action["factor"]
        diff_factor = self.diff_multiplier
        score = self.value * type_factor * diff_factor
        return score 
    
    def execution(self, manual_value=None):
        """Executa a ação e retorna (score_difference, messages, note_info)"""
        action_data = self._TYPE_MAP[self.type]
        messages = []
        note_info = None
        
        original_value = self.value
        original_score = self.score
        label = action_data["label"]

        note_info = self._manual_input(messages, label, value=manual_value)
        
        score_difference = self.score - original_score

        return score_difference, messages, note_info

    def _manual_input(self, messages, label, value=None):
        if value is not None:
            note_text = str(value).strip()
            added_value = self._note_to_value(note_text)
            self._value += added_value
            self._update_max_value()
            return {
                "text": note_text,
                "is_numeric": self._is_integer_note(note_text),
                "value": added_value,
            }

        from src.domain.ports import ui, WebInputInterrupt
        if ui.web_mode:
            raise WebInputInterrupt("action note", type="text", options={"action_id": self.id})

        prompt_message = f"insert note for {self.name}: "
        while True:
            try:
                input_value = input(prompt_message)
                if not input_value.strip():
                    continue
                note_text = str(input_value).strip()
                added_value = self._note_to_value(note_text)
                self._value += added_value
                self._update_max_value()
                return {
                    "text": note_text,
                    "is_numeric": self._is_integer_note(note_text),
                    "value": added_value,
                }
            except ValueError:
                messages.append(f"Invalid note for {label}.")

    def _is_integer_note(self, note_text):
        text = str(note_text or "").strip()
        if not text:
            return False
        try:
            int(text)
            return True
        except Exception:
            return False

    def _note_to_value(self, note_text):
        text = str(note_text or "").strip()
        if not text:
            return 1
        if self._is_integer_note(text):
            return int(text)

        normalized = " ".join(text.lower().split())
        seed = f"{self.id}:{self.name}:{normalized}"
        rng = random.Random(seed)
        words = [w for w in normalized.split(" ") if w]
        word_count = len(words)
        char_count = len(normalized)
        base = max(5, min(40, word_count * 4 + char_count // 6))
        spread = max(3, min(25, (self.diff + 1) * 4 + word_count))
        return base + rng.randint(0, spread)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type, 
            "diff": self.diff,
            "value": self.value,             
            "max_value": self.max_value,
            "score": self.score,
            "deleted": self.deleted,
            "logic_type": self._logic_type,
            "sub_logic_type": self._sub_logic_type,
        }
    
    @classmethod
    def from_dict(cls, data):
        action = cls(
            data["id"], 
            data["name"], 
            data["type"], 
            data["diff"], 
            data["value"], 
            data.get("deleted", False),
            data.get("logic_type"),
            data.get("sub_logic_type"),
            data.get("max_value"),
        )
        return action


