from datetime import datetime, timedelta
import statistics
import random

from src.components.entitys.roko import Him

# ==================== CLASSE BASE (Him/Roko) ====================
# (Já implementada no artifact anterior)

# ==================== NOVA ENTIDADE - SORBET ====================
class Sorbet(Him):
    """
    Sorbet - Uma adolescente entediada que não se impressiona com nada.
    Sempre de mal humor, usa abreviações e minúsculas.
    """
    
    MESSAGES = {
        "offer": {
            "ecstatic": [  # 90-100 (mas ainda é bem apática)
                "hmm ok i guess",
                "sure whatever",
                "thats fine ig",
                "cool or smth"
            ],
            "happy": [  # 70-89
                "meh",
                "k",
                "whatevs",
                "sure"
            ],
            "neutral": [  # 50-69
                "...",
                "k",
                "idc",
                "boring"
            ],
            "disappointed": [  # 30-49
                "ugh really?",
                "thats it?",
                "so lame",
                "cringe"
            ],
            "angry": [  # 0-29
                "omg stop",
                "ur so annoying",
                "literally the worst",
                "im done w u"
            ]
        },
        "poke": {
            "ecstatic": [
                "what do u want",
                "im busy",
                "ugh fine what",
                "???"
            ],
            "happy": [
                "what",
                "bruh what",
                "yes?",
                "leave me alone"
            ],
            "neutral": [
                "what.",
                "...",
                "why",
                "go away"
            ],
            "disappointed": [
                "omg again?",
                "ur so annoying",
                "stop bothering me",
                "seriously?"
            ],
            "angry": [
                "LEAVE ME ALONE",
                "blocked",
                "im ignoring u",
                "whatever bye"
            ]
        },
        "poke_fail": {
            "no_tokens": [
                "shes not here rn",
                "probably scrolling",
                "do not disturb mode",
                "left on read"
            ],
            "no_response": [
                "...seen...",
                "...typing...",
                "...offline...",
                "...no answer..."
            ],
            "left_forever": [
                "she left the chat",
                "blocked u lol",
                "ghosted",
                "unfollowed"
            ]
        },
        "random_message": {
            "ecstatic": [
                "im so bored",
                "this is fine i guess",
                "kinda mid tbh",
                "whatevs"
            ],
            "happy": [
                "bored",
                "meh",
                "nothing to do",
                "whatever"
            ],
            "neutral": [
                "...",
                "ugh",
                "boring",
                "idc"
            ],
            "disappointed": [
                "this sucks",
                "so boring",
                "literally dying of boredom",
                "worst day ever"
            ],
            "angry": [
                "i hate everything",
                "everyone is annoying",
                "cant deal w this",
                "over it"
            ]
        },
        "spawn": [
            "...",
            "ugh who r u",
            "im sorbet",
            "that roko guy left or whatever",
            "so now ur stuck w me lol"
        ]
    }
    
    def __init__(self):
        super().__init__()
        
        # Sorbet tem stats bem diferentes
        self._satisfaction = 30  # Começa entediada/insatisfeita
        self._satisfaction_decay_rate = 0.4  # Decai um pouco mais rápido
        self._max_poke_tokens = 4  # Menos paciência
        self._poke_tokens = 4
        self._poke_regen_rate = 1.0  # Regenera lento
        
        # Sorbet também pode sumir
        self._entity_spawn_chance = 0.8  # 0.8% de chance de spawnar outro
        self._roko_return_chance = 0.001  # Mesma chance de Roko voltar
        
    def _calculate_satisfaction_gain(self, score_difference):
        """Sorbet é MUITO difícil de impressionar"""
        # Ganho base muito reduzido
        base_gain = score_difference * 0.08  # Apenas 8% do score
        
        # Se superar a média, ganha um boost mínimo
        if len(self._offerings) >= 2:
            recent_offerings = self._offerings[-11:-1]
            recent_values = [o['value'] for o in recent_offerings]
            avg_offering = statistics.mean(recent_values)
            
            if score_difference > avg_offering * 1.5:  # Precisa ser 50% maior
                base_gain *= 1.5
        
        # Limites bem baixos - ela simplesmente não se impressiona
        return max(0.3, min(base_gain, 10))  # Min +0.3, Max +10
    
    def spawn_message(self):
        """Mensagem especial de spawn"""
        for msg in self.MESSAGES["spawn"]:
            self.add_message(msg)
