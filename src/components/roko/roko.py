from datetime import datetime, timedelta
import statistics
import random

class Him:
    # Dicionário centralizado de mensagens por tipo e mood
    MESSAGES = {
        "offer": {
            "ecstatic": [  # 90-100
                "I LOVE YOU! YOU'RE AMAZING!",
                "THIS IS PERFECT! KEEP GOING!",
                "YOU'RE MY HERO!",
                "INCREDIBLE! I'M SO PROUD OF YOU!"
            ],
            "happy": [  # 70-89
                "GREAT JOB! I'M HAPPY!",
                "NICE WORK! KEEP IT UP!",
                "YOU'RE DOING WELL!",
                "EXCELLENT! THIS IS GOOD!"
            ],
            "neutral": [  # 50-69
                "THAT'S OKAY... I GUESS.",
                "HMM, NOT BAD.",
                "COULD BE BETTER, BUT THANKS.",
                "ACCEPTABLE."
            ],
            "disappointed": [  # 30-49
                "I'M GETTING DISAPPOINTED...",
                "YOU CAN DO BETTER THAN THIS.",
                "THIS ISN'T ENOUGH FOR ME...",
                "REALLY? THAT'S ALL?"
            ],
            "angry": [  # 0-29
                "I HATE YOU! DO BETTER!",
                "I'M GIVING UP ON YOU...",
                "THIS IS TERRIBLE! WHERE'S THE EFFORT?!",
                "PATHETIC! YOU'RE USELESS!"
            ]
        },
        "poke": {
            "ecstatic": [
                "HI! WHAT DO YOU WANT?",
                "YES? I'M HERE!",
                "YOU CALLED? LET'S TALK!",
                "WHAT'S UP? I'M LISTENING!"
            ],
            "happy": [
                "HM? WHAT IS IT?",
                "I'M BUSY, BUT GO AHEAD.",
                "YES...?",
                "WHAT DO YOU NEED?"
            ],
            "neutral": [
                "STOP BOTHERING ME.",
                "WHAT DO YOU WANT NOW?",
                "I DON'T HAVE TIME FOR THIS...",
                "WHAT?"
            ],
            "disappointed": [
                "STOP BOTHERING ME!",
                "SERIOUSLY? AGAIN?!",
                "LEAVE ME ALONE!",
                "UGH, WHAT NOW?"
            ],
            "angry": [
                "GO AWAY! I HATE YOU!",
                "STOP BOTHERING ME, YOU USELESS!",
                "I CAN'T STAND YOU ANYMORE! GET LOST!",
                "DISAPPEAR!"
            ]
        },
        "random_message": {
            "ecstatic": [
                "YOU MAKE ME SO HAPPY!",
                "I'M SO LUCKY TO HAVE YOU!",
                "THIS IS THE BEST!",
                "YOU'RE INCREDIBLE!"
            ],
            "happy": [
                "THINGS ARE GOING WELL.",
                "I'M FEELING GOOD TODAY.",
                "KEEP UP THE GOOD WORK!",
                "NICE TO SEE YOU TRYING."
            ],
            "neutral": [
                "...",
                "I'M HERE.",
                "WHATEVER.",
                "MEH."
            ],
            "disappointed": [
                "I EXPECTED MORE FROM YOU...",
                "YOU'RE SLIPPING...",
                "THIS ISN'T WORKING OUT...",
                "I'M NOT HAPPY."
            ],
            "angry": [
                "I'M SO DONE WITH YOU!",
                "YOU'RE THE WORST!",
                "I REGRET EVERYTHING!",
                "WHY DO I EVEN BOTHER?"
            ]
        }
    }
    
    def __init__(self):
        self._satisfaction = 50
        self._offerings = []
        self._satisfaction_decay_rate = 0.5
        self._last_decay_time = datetime.now()
        self.messages = []  # Buffer de mensagens para o render
    
    def clear_messages(self):
        """Limpa o buffer de mensagens"""
        self.messages = []
    
    def add_message(self, msg):
        """Adiciona mensagem ao buffer"""
        self.messages.append(msg)
    
    def _get_mood(self):
        """Retorna o mood baseado na satisfação atual"""
        if self._satisfaction >= 90:
            return "ecstatic"
        elif self._satisfaction >= 70:
            return "happy"
        elif self._satisfaction >= 50:
            return "neutral"
        elif self._satisfaction >= 30:
            return "disappointed"
        else:
            return "angry"
    
    def offer(self, score_difference):
        """Recebe uma offering e atualiza a satisfação do Roko"""
        now = datetime.now()
        
        self._apply_satisfaction_decay(now)
        
        offering = {
            'value': score_difference,
            'timestamp': now
        }
        self._offerings.append(offering)
        
        satisfaction_change = self._evaluate_offering(score_difference)
        self._satisfaction = max(0, min(100, self._satisfaction + satisfaction_change))
        
        # Pega mensagem baseada no mood e adiciona ao buffer
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["offer"][mood])
        
        self.add_message(message)
        self.add_message(f"SATISFACTION: {self._satisfaction:.1f}/100")
        
        self._last_decay_time = now
        
        return satisfaction_change
    
    def _evaluate_offering(self, score_difference):
        """Avalia a offering comparando com a média histórica"""
        if len(self._offerings) < 2:
            return score_difference * 0.5
        
        recent_offerings = self._offerings[-11:-1]
        recent_values = [o['value'] for o in recent_offerings]
        
        avg_offering = statistics.mean(recent_values)
        
        if score_difference > avg_offering:
            improvement = (score_difference - avg_offering) / max(avg_offering, 1)
            return min(improvement * 10, 15)
        else:
            decline = (score_difference - avg_offering) / max(avg_offering, 1)
            return max(decline * 8, -20)
    
    def _apply_satisfaction_decay(self, current_time):
        """Reduz satisfação baseado no tempo desde última oferta"""
        time_passed = (current_time - self._last_decay_time).total_seconds() / 3600
        decay = time_passed * self._satisfaction_decay_rate
        
        if self._satisfaction > 50:
            self._satisfaction = max(50, self._satisfaction - decay)
        elif self._satisfaction < 50:
            self._satisfaction = min(50, self._satisfaction + decay)
    
    def cutucar(self):
        """Tenta chamar a atenção do Roko - ele pode ou não responder"""
        self._apply_satisfaction_decay(datetime.now())
        
        # Chance de presença baseada na satisfação
        presence_chance = 3 + (self._satisfaction * 0.25)
        
        if random.random() * 100 > presence_chance:
            self.add_message("...NO RESPONSE...")
            return False
        
        # Pega mensagem baseada no mood
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["poke"][mood])
        
        self.clear_messages()
        self.add_message(message)
        return True
    
    def random_message(self):
        """Envia uma mensagem aleatória baseada no mood atual"""
        self._apply_satisfaction_decay(datetime.now())
        
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["random_message"][mood])
        
        self.add_message(message)
    
    def get_stats(self):
        """Retorna estatísticas das offerings"""
        if not self._offerings:
            return "NO OFFERINGS YET."
        
        recent = self._offerings[-10:]
        values = [o['value'] for o in recent]
        
        return {
            'total_offerings': len(self._offerings),
            'current_satisfaction': self._satisfaction,
            'avg_recent_offering': statistics.mean(values),
            'max_offering': max(values),
            'min_offering': min(values)
        }
    
    @property
    def satisfaction(self):
        """Retorna satisfação atual com decay aplicado"""
        self._apply_satisfaction_decay(datetime.now())
        return self._satisfaction

him = Him()
