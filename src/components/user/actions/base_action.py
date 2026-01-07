
from abc import ABC, abstractmethod

class BaseAction:
    _DIFFICULTY_MULTIPLIER_MAP = {
        4: 5.4,
        3: 4.3,
        2: 3.2,
        1: 2.1,
    }

    def __init__(self, action_id, name: str, diff: int):
        if not (1 <= diff <= 4):
            raise ValueError("Difficulty 'diff' must be an integer between 1 and 4.")
        
        self._id = action_id
        self._name = name
        self._value = 0
        self._diff = diff
    
        self._diff_multiplier = self._DIFFICULTY_MULTIPLIER_MAP[diff] 

    @property
    @abstractmethod
    def score(self) -> float:
        pass

    def execution(self, exec_value: int):
        self.value += exec_value
    
    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def diff(self):
        return self._diff
    
    # json things 
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "diff": self.diff,
            "type": self.__class__.__name__
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
        return action_cls(data["id"], data["name"], data["diff"])
