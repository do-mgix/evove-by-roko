# ==================== ACTION.PY ====================
from abc import ABC, abstractmethod

class Action:
    _DIFFICULTY_MULTIPLIER_MAP = {
        4: 5.4,
        3: 4.3,
        2: 3.2,
        1: 2.1,
    }
    _TYPE_MAP = {
        1: {"label": "repetitions", "factor": 1},
        2: {"label": "seconds", "factor": 1}, 
        3: {"label": "minutes", "factor": 60}, 
        4: {"label": "hours", "factor": 360}, 
        5: {"label": "letters", "factor": 1}, 
    }
    
    def __init__(self, action_id, name: str, tipo: int, diff: int, value: float):
        if not (1 <= diff <= 4):
            raise ValueError("Difficulty 'diff' must be an integer between 1 and 4.")
        if tipo not in self._TYPE_MAP:
            raise ValueError(f"Invalid action type: {tipo}")
        self._id = action_id
        self._name = name
        self._tipo = tipo
        self._diff = diff
        self._value = value
        self._diff_multiplier = self._DIFFICULTY_MULTIPLIER_MAP[diff] 
    
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
    def diff_multiplier(self):
        return self._diff_multiplier
    
    @property
    def score(self) -> float: 
        action = self._TYPE_MAP[self.type] 
        type_factor = action["factor"]
        diff_factor = self.diff_multiplier
        score = self.value * type_factor * diff_factor
        return score 
    
    def execution(self):
        """Executa a ação e retorna (score_difference, messages)"""
        action_data = self._TYPE_MAP[self.type]
        messages = []
        
        original_value = self.value
        original_score = self.score
        label = action_data["label"]
        
        # Timer support for time-based actions (2: seconds, 3: minutes, 4: hours)
        if self.type in [2, 3, 4]:
            from src.components.services.UI.interface import ui
            import time
            
            print(f"\n[ TIMER MODE ] Action: {self.name.upper()}")
            print(f"Press any key to START timer, or 'm' for Manual input.")
            key = readchar.readkey()
            
            if key.lower() != 'm':
                start_time = time.time()
                print(f"Timer started. Press any key to STOP...")
                readchar.readkey()
                duration = time.time() - start_time
                
                # Convert duration based on type factor
                # minutes (3) has factor 60, hours (4) has factor 360
                # But self._value stores the magnitude in label units?
                # Actually, self.score uses self.value * factor.
                # So if label is 'minutes', value should be in minutes.
                
                if self.type == 2: # seconds
                    added_value = duration
                elif self.type == 3: # minutes
                    added_value = duration / 60
                elif self.type == 4: # hours
                    added_value = duration / 3600
                
                self._value += added_value
                messages.append(f"Timer stopped. Total time added: {added_value:.2f} {label}")
            else:
                self._manual_input(messages, label)
        else:
            self._manual_input(messages, label)
        
        value_difference = self.value - original_value
        messages.append(f"{self.name} increase by {value_difference:.2f}! {original_value:.2f} -> {self.value:.2f}")
        
        score_difference = self.score - original_score
        messages.append(f"score plus {score_difference:.2f}! {original_score:.2f} -> {self.score:.2f}")

        # Check for active challenge
        from src.components.services.challenge_service import ChallengeManager
        cm = ChallengeManager()
        if cm.active_challenge and cm.active_challenge["action_id"] == self.id:
            # For simplicity, if they did ANY amount during the challenge, we count progress?
            # README says "se aceitar, deve fazer e confirmar que foi feito"
            # Here we simplify: if value_difference >= required_value, complete it.
            if value_difference >= cm.active_challenge["required_value"]:
                cm.complete_challenge()
        
        return score_difference, messages

    def _manual_input(self, messages, label):
        prompt_message = f"insert {label}: "
        while True:
            try:
                input_value = input(prompt_message)
                if input_value:
                    self._value += int(input_value)
                break 
            except ValueError:
                messages.append(f"Invalid enter, insert integer for {label}.")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type, 
            "diff": self.diff,
            "value": self.value,             
            "score": self.score,
        }
    
    @classmethod
    def from_dict(cls, data):
        action = cls(
            data["id"], 
            data["name"], 
            data["type"], 
            data["diff"], 
            data["value"], 
        )
        return action
