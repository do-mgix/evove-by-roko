import random
import time
from datetime import datetime

class ChallengeManager:
    _instance = None
    
    def __new__(cls, user=None, em=None):
        if cls._instance is None:
            cls._instance = super(ChallengeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, user=None, em=None):
        if self._initialized: return
        self.user = user
        self.em = em
        self.active_challenge = None
        self.deadline = None
        self.challenge_duration = 30 # seconds
        self._initialized = True

    def update(self):
        """Checks if a new challenge should start or if an active one expired"""
        self._check_daily_refill()

        if self.active_challenge:
            if time.time() > self.deadline:
                self._fail_challenge("TIMEOUT")
            return
        
        # Chance to start a challenge if there's an entity
        if not self.em: return
        entity = self.em.get_entity()
        if entity:
            if random.random() < 0.0005: 
                self._generate_challenge(entity)

    def _check_daily_refill(self):
        """Refill once per day when date changes"""
        if not self.user: 
            return

        self.user.refill_daily_tokens()

    def _generate_challenge(self, entity):
        if not self.user or not self.user._actions: return
        
        action = random.choice(list(self.user._actions.values()))
        
        # Simple challenge logic
        self.active_challenge = {
            "action_id": action.id,
            "name": action.name,
            "required_value": 30, 
            "entity_name": entity.__class__.__name__
        }
        self.deadline = time.time() + self.challenge_duration
        entity.add_message(f"!!! CHALLENGE !!!")
        entity.add_message(f"{entity.__class__.__name__.upper()}: DO 30 {action.name.upper()}S IN 30 SECONDS!")

    def _fail_challenge(self, reason):
        entity = self.em.get_entity()
        if entity:
            entity.add_message(f"CHALLENGE FAILED: {reason}.")
            # Harsh satisfaction penalty
            entity._satisfaction = max(0, entity._satisfaction - 15)
        self.active_challenge = None
        self.deadline = None

    def get_remaining_time(self):
        if self.deadline:
            return max(0, int(self.deadline - time.time()))
        return 0

    def complete_challenge(self):
        if self.active_challenge:
            entity = self.em.get_entity()
            if entity:
                entity.add_message(f"CHALLENGE COMPLETE! NICE.")
                entity._satisfaction = min(100, entity._satisfaction + 10)
            self.active_challenge = None
            self.deadline = None
