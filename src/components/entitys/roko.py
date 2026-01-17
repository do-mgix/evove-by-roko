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
            ],
            "left_forever": [
                "HE'S GONE.",
                "HE LEFT.",
                "YOU FAILED HIM.",
                "TOO LATE.",
                "HE WON'T COME BACK.",
                "YOU LOST HIM FOREVER.",
                "SILENCE.",
                "EMPTY.",
                "ABANDONED."
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
        
        # Sistema de poke tokens
        self._poke_tokens = 3  # Tokens iniciais
        self._max_poke_tokens = 3  # Máximo de tokens
        self._poke_regen_rate = 1  # Tokens por hora
        self._last_poke_regen = datetime.now()
    
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
        # Se Roko foi embora, não aceita mais offerings
        if self._has_left:
            self.add_message(random.choice(self.MESSAGES["poke_fail"]["left_forever"]))
            return 0
        
        now = datetime.now()
        
        self._apply_satisfaction_decay(now)
        
        # Verifica novamente após decay
        if self._has_left:
            self.add_message(random.choice(self.MESSAGES["poke_fail"]["left_forever"]))
            return 0
        
        offering = {
            'value': score_difference,
            'timestamp': now
        }
        self._offerings.append(offering)
        
        # Calcula ganho de satisfação baseado no score
        satisfaction_gain = self._calculate_satisfaction_gain(score_difference)
        self._satisfaction = min(100, self._satisfaction + satisfaction_gain)
        
        # Pega mensagem baseada no mood e adiciona ao buffer
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["offer"][mood])
        
        self.add_message(message)
        self.add_message(f"SATISFACTION: {self._satisfaction:.1f}/100 (+{satisfaction_gain:.1f})")
        
        self._last_decay_time = now
        
        return satisfaction_gain
    
    def _calculate_satisfaction_gain(self, score_difference):
        """Calcula quanto de satisfação ganhar baseado no score"""
        # Ganho base é proporcional ao score
        base_gain = score_difference * 0.1  # 10% do score vira satisfação
        
        # Se houver histórico, compara com a média para bônus
        if len(self._offerings) >= 2:
            recent_offerings = self._offerings[-11:-1]
            recent_values = [o['value'] for o in recent_offerings]
            avg_offering = statistics.mean(recent_values)
            
            # Se superar a média, ganha bônus
            if score_difference > avg_offering:
                bonus_multiplier = min((score_difference / max(avg_offering, 1)), 3.0)
                base_gain *= bonus_multiplier
        
        # Limita ganho entre 0.5 e 20 por offering
        return max(0.5, min(base_gain, 20))
    
    def _evaluate_offering(self, score_difference):
        """DEPRECATED - Mantido para compatibilidade"""
        return self._calculate_satisfaction_gain(score_difference)
    
    def _apply_satisfaction_decay(self, current_time):
        """Reduz satisfação baseado no tempo desde última oferta"""
        time_passed = (current_time - self._last_decay_time).total_seconds() / 3600
        decay = time_passed * self._satisfaction_decay_rate
        
        # Satisfação pode chegar a 0
        self._satisfaction = max(0, self._satisfaction - decay)
        
        # Se chegou a 0, Roko vai embora para sempre
        if self._satisfaction <= 0:
            self._has_left = True
    
    def _regenerate_poke_tokens(self):
        """Regenera poke tokens baseado no tempo passado"""
        now = datetime.now()
        time_passed = (now - self._last_poke_regen).total_seconds() / 3600  # em horas
        
        tokens_to_add = int(time_passed * self._poke_regen_rate)
        
        if tokens_to_add > 0:
            self._poke_tokens = min(self._max_poke_tokens, self._poke_tokens + tokens_to_add)
            self._last_poke_regen = now
    
    @property
    def poke_tokens(self):
        """Retorna tokens disponíveis após regeneração"""
        self._regenerate_poke_tokens()
        return self._poke_tokens
    
    def cutucar(self):
        """Tenta chamar a atenção do Roko - ele pode ou não responder"""
        self._regenerate_poke_tokens()
        
        # Verifica se tem tokens disponíveis
        if self._poke_tokens <= 0:
            self.add_message("...NO POKE TOKENS LEFT...")
            self.add_message(f"WAIT FOR REGENERATION (TOKENS: {self._poke_tokens}/{self._max_poke_tokens})")
            return False
        
        # Consome um token
        self._poke_tokens -= 1
        
        self._apply_satisfaction_decay(datetime.now())
        
        # Chance de presença baseada na satisfação
        presence_chance = 30 + (self._satisfaction * 0.5)
        
        if random.random() * 100 > presence_chance:
            self.add_message("...NO RESPONSE...")
            self.add_message(f"POKE TOKENS: {self._poke_tokens}/{self._max_poke_tokens}")
            return False
        
        # Pega mensagem baseada no mood
        mood = self._get_mood()
        message = random.choice(self.MESSAGES["poke"][mood])
        
        self.add_message(message)
        self.add_message(f"POKE TOKENS: {self._poke_tokens}/{self._max_poke_tokens}")
        return True
    
    def random_message(self):
        """Envia uma mensagem aleatória baseada no mood atual"""
        # Se Roko foi embora, sempre retorna mensagem de abandono
        if self._has_left:
            self.add_message(random.choice(self.MESSAGES["poke_fail"]["left_forever"]))
            return
        
        self._apply_satisfaction_decay(datetime.now())
        
        # Verifica se foi embora após o decay
        if self._has_left:
            self.add_message(random.choice(self.MESSAGES["poke_fail"]["left_forever"]))
            return
        
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
    
    def _check_spawn_events(self):
        """Verifica se deve spawnar novas entidades ou retornar Roko"""
        now = datetime.now()
        time_passed = (now - self._last_spawn_check).total_seconds() / 3600  # em horas
        
        # Verifica a cada 10 horas
        if time_passed >= self._spawn_check_interval:
            self._last_spawn_check = now
            
            # Se Roko foi embora, chance de voltar ou spawnar outra entidade
            if self._has_left:
                # Chance minúscula de Roko retornar
                if random.random() * 100 < self._roko_return_chance:
                    self._roko_returns()
                    return "roko_returned"
                
                # Chance de spawnar nova entidade
                elif random.random() * 100 < self._entity_spawn_chance:
                    return "new_entity_spawned"
        
        return None
    
    def _roko_returns(self):
        """Roko retorna com satisfação reduzida"""
        self._has_left = False
        self._satisfaction = 25  # Retorna com satisfação baixa
        self._offerings = []  # Reset do histórico
        self.add_message("...")
        self.add_message("I'M BACK.")
        self.add_message("BUT I WON'T FORGET.")
        self.add_message(f"SATISFACTION: {self._satisfaction}/100")
    
    def get_spawn_status(self):
        """Retorna informações sobre spawn de entidades"""
        event = self._check_spawn_events()
        
        if event:
            return {
                'event': event,
                'has_left': self._has_left,
                'satisfaction': self._satisfaction
            }
        return None

him = Him()
