from src.components.user.actions.base_action import BaseAction

class SecAction(BaseAction):
    
    # cálculo de score = value * diff - Considera balanceamento por medidas de tempo 
    @property
    def score(self) -> float:
        return self.value * self.diff_multiplier




