
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
        
        self.action_id = action_id
        self.name = name
        self.value = 0
        self.diff = diff
    
        self.diff_multiplier = self._DIFFICULTY_MULTIPLIER_MAP[diff] 

    @property
    @abstractmethod
    def score(self) -> float:
        pass

    def execution(self, exec_value: int):
        self.value += exec_value
    
    @property
    def id(self):
        return self.id

