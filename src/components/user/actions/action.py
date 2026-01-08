
from abc import ABC, abstractmethod

class Action:
    _DIFFICULTY_MULTIPLIER_MAP = {
        4: 5.4,
        3: 4.3,
        2: 3.2,
        1: 2.1,
    }

    def __init__(self, action_id, name: str, tipo: int, diff: int, value: float):
        if not (1 <= diff <= 4):
            raise ValueError("Difficulty 'diff' must be an integer between 1 and 4.")
        
        self._id = action_id
        self._name = name
        self._tipo = tipo
        self._diff = diff
        self._value = value
        self._score = score
        self._diff_multiplier = self._DIFFICULTY_MULTIPLIER_MAP[diff] 

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def value(self):
        return self._value

    @property
    def diff(self):
        return self._diff
    
    @property
    def diff_multiplier(self):
        return self._diff_multiplier

    @property
    def score(self) -> float:
        action_multiplier_map = {
            1: { "multiplier": 1 }, #repetition 
            2: { "multiplier": 1 }, #sec 
            3: { "multiplier": 60 }, #min
            4: { "multiplier": 360 }, #hour 
        }      
        return    

    def execution(self, exec_value: int):
        self.value += exec_value

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "diff": self.diff,
            "type": self.__class__.__name__,           
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data):
        action_map = {
            "RepetitionAction": RepetitionAction,
            "SecAction": SecAction,
            "MinAction": MinAction,
            "HourAction": HourAction,
        }
        action_cls = action_map[data["type"]]
        return action_cls(data["id"], data["name"], data["diff"], data["value"], data["score"],)
