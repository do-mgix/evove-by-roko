
from abc import ABC, abstractmethod

class Action:

    _DIFFICULTY_MULTIPLIER_MAP = {
        4: 5.4,
        3: 4.3,
        2: 3.2,
        1: 2.1,
    }

    _TYPE_MAP = {
        1: { "label": "repetitions", "factor": 1},
        2: { "label": "seconds", "factor": 1}, 
        3: { "label": "minutes", "factor" : 60}, 
        4: { "label": "hours", "factor": 360}, 
        5: { "label": "letters", "factor": 1}, 
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
    def id(self): return self._id
    
    @property
    def name(self): return self._name
    
    @property
    def type(self): return self._tipo
    
    @property
    def diff(self): return self._diff
    
    @property
    def value(self): return self._value
    
    @property
    def diff_multiplier(self): return self._diff_multiplier

    @property
    def score(self) -> float: 
        action = self._TYPE_MAP[self.type] 
        type_factor = action["factor"]
        diff_factor = self.diff_multiplier
        score = self.value * type_factor * diff_factor
        return score 

    def execution(self):        
        action_data =  self._TYPE_MAP[self.type]
        
        original_value = self.value
        original_score = self.score
        label = action_data["label"]
        prompt_message = f"insert {label}: "
        
        while True:
            try:
                input_value = input(prompt_message)
                
                if input_value:
                    self._value += int(input_value)

                break 
            except ValueError:
                print(f"Invalid enter, insert integer for {label}.")
        
        value_diference = self.value - original_value
        print(f"{self.name} increase by {value_diference}!  {original_value} -> {self.value}")
        
        score_diference = self.score - original_score
        print(f"score plus {score_diference}!  {original_score} ->{self.score}")
        
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
