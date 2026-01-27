from datetime import datetime, timedelta
import statistics
import random

class Him:
    # Centralized dictionary of messages by type and mood
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
        "poke_fail": {
            "no_tokens": [
                "BETTER NOT MESS WITH HIM.",
                "LETS GIVE HIM A BREAK.",
                "KNOCK KNOCK?",
                "HE ISN'T HERE."    
            ],
            "no_response": [
                "...NO RESPONSE...",
                "...SILENCE...",
                "...NOTHING...",
                "...NOBODY HOME..."
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
    
    def __init__(self, appearance_count=1):
        self._appearance_count = appearance_count
        self._satisfaction = 50
        self._offerings = []
        
        # Roko completo (2nd appearance) is easier to maintain
        if appearance_count >= 2:
            self._satisfaction_decay_rate = 0.2 # 0.2 per hour instead of 0.5
            self._max_poke_tokens = 5
            self._poke_tokens = 5
        else:
            self._satisfaction_decay_rate = 0.5
            self._max_poke_tokens = 3
            self._poke_tokens = 3

        self._last_decay_time = datetime.now()
        self.messages = []  # Buffer de mensagens para o render
        
        # Sistema de poke tokens
        self._poke_regen_rate = 1  # Tokens por hora
        self._last_poke_regen = datetime.now()

        self._has_left = 0 
    
    def clear_messages(self):
        """Limpa o buffer de mensagens"""
        self.messages = []
    
    def add_message(self, msg):
        """Adiciona mensagem ao buffer"""
        self.messages.append(msg)
    
    def _get_mood(self):
        """Returns the mood based on current satisfaction"""
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
        """Receives an offering and updates Roko's satisfaction"""
        now = datetime.now()
        
        self._apply_satisfaction_decay(now)
        
        offering = {
            'value': score_difference,
            'timestamp': now
        }
        self._offerings.append(offering)
        
        # Calcula ganho de satisfação baseado no score
        satisfaction_gain = self._calculate_satisfaction_gain(score_difference)
        self._satisfaction = min(100, self._satisfaction + satisfaction_gain)
        
        # Get message based on mood and add to buffer
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["offer"][mood])
        
        self.add_message(message)
        
        self._last_decay_time = now
        
        return satisfaction_gain
    
    def _calculate_satisfaction_gain(self, score_difference):
        """Calculates how much satisfaction to gain based on score"""
        # Base gain is proportional to score
        base_gain = score_difference * 0.1  # 10% of score becomes satisfaction
        
        # If there's history, compare with average for bonus
        if len(self._offerings) >= 2:
            recent_offerings = self._offerings[-11:-1]
            recent_values = [o['value'] for o in recent_offerings]
            avg_offering = statistics.mean(recent_values)
            
            # If it beats the average, gain bonus
            if score_difference > avg_offering:
                bonus_multiplier = min((score_difference / max(avg_offering, 1)), 3.0)
                base_gain *= bonus_multiplier
        
        # Limit gain between 0.5 and 20 per offering
        return base_gain
    
    def _evaluate_offering(self, score_difference):
        """DEPRECATED - kept for compatibility"""
        return self._calculate_satisfaction_gain(score_difference)
    
    def _apply_satisfaction_decay(self, current_time):
        """Reduces satisfaction based on time since last offering"""
        from src.components.data.constants import user
        if not user.metadata.get("virtual_agent_active", True):
            return

        time_passed = (current_time - self._last_decay_time).total_seconds() / 3600
        decay = time_passed * self._satisfaction_decay_rate
        
        self._satisfaction = max(0, self._satisfaction - decay)
    
    def _regenerate_poke_tokens(self):
        """Regenerates poke tokens based on passed time"""
        now = datetime.now()
        time_passed = (now - self._last_poke_regen).total_seconds() / 3600  # in hours
        
        tokens_to_add = int(time_passed * self._poke_regen_rate)
        
        if tokens_to_add > 0:
            self._poke_tokens = min(self._max_poke_tokens, self._poke_tokens + tokens_to_add)
            self._last_poke_regen = now
    
    @property
    def poke_tokens(self):
        """Returns available tokens after regeneration"""
        self._regenerate_poke_tokens()
        return self._poke_tokens
    
    def cutucar(self):
        """Tries to call Roko's attention - he may or may not respond"""
        self._regenerate_poke_tokens()
        
        # Check if there are tokens available
        if self._poke_tokens <= 0:
            message = random.choice(self.MESSAGES["poke_fail"]["no_tokens"])
            self.add_message(message)
            return False
        
        # Consume a token
        self._poke_tokens -= 1
        
        self._apply_satisfaction_decay(datetime.now())
        
        # Presence chance based on satisfaction
        presence_chance = 30 + (self._satisfaction * 0.5)
        
        if random.random() * 100 > presence_chance:
            message = random.choice(self.MESSAGES["poke_fail"]["no_response"])
            self.add_message(message)
            return False
        
        # Get message based on mood
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["poke"][mood])
        
        self.add_message(message)
        return True
    
    def random_message(self):
        """Sends a random message based on current mood"""
        self._apply_satisfaction_decay(datetime.now())
        
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["random_message"][mood])
        
        self.add_message(message)
    
    def get_stats(self):
        """Returns offerings statistics"""
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
        """Returns current satisfaction with decay applied"""
        self._apply_satisfaction_decay(datetime.now())
        return self._satisfaction

    def get_spawn_status(self):
        """Returns dummy spawn status for Roko. Special logic can be added here."""
        # For now, Roko doesn't spontaneously leave unless satisfaction is 0
        return None

him = Him()
