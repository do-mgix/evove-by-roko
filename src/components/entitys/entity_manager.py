# ==================== ENTITY MANAGER ====================

from src.components.entitys.roko import Him
from src.components.entitys.sorbet import Sorbet

class EntityManager:
    """Manages which entity is active and spawns"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EntityManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.current_entity = Him()  # Starts with Roko
        self.entity_type = "roko"
        self._initialized = True
        
    def check_and_spawn(self):
        """Checks for spawn events and returns true if there was a change"""
        from src.components.data.constants import user
        if not user.metadata.get("virtual_agent_active", True):
            return False

        if self.current_entity:
            # Check for abandonment
            if self.current_entity.satisfaction <= 0:
                self.current_entity.add_message("I'VE HAD ENOUGH. GOODBYE.")
                self.current_entity = None
                self.entity_type = None
                return True

            status = self.current_entity.get_spawn_status()
            
            if status:
                if status['event'] == 'roko_returned':
                    self.entity_type = "roko"
                    count = user.metadata.get("roko_appearance_count", 0) + 1
                    user.metadata["roko_appearance_count"] = count
                    user.save_user()
                    self.current_entity = Him(appearance_count=count)
                    return True
                    
                elif status['event'] == 'new_entity_spawned':
                    self.current_entity = Sorbet()
                    self.entity_type = "sorbet"
                    self.current_entity.spawn_message()
                    return True
        else:
            # No entity state - check for spawn every 12h
            from src.components.data.constants import user
            from datetime import datetime, timedelta
            
            last_check_str = user.metadata.get("last_spawn_check")
            now = datetime.now()
            
            should_check = False
            if not last_check_str:
                should_check = True
            else:
                last_check = datetime.fromisoformat(last_check_str)
                if now - last_check > timedelta(hours=12):
                    should_check = True
            
            if should_check:
                user.metadata["last_spawn_check"] = now.isoformat()
                user.save_user()
                
                # Appearance chance logic
                chance = user.metadata.get("spawn_chance", 0.005) # Start at 0.5%
                import random
                if random.random() < chance:
                    # Spawn someone!
                    self.entity_type = "roko"
                    count = user.metadata.get("roko_appearance_count", 0) + 1
                    user.metadata["roko_appearance_count"] = count
                    user.metadata["spawn_chance"] = 0.005 # Reset chance
                    user.save_user()
                    self.current_entity = Him(appearance_count=count)
                    return True
                else:
                    # Increase chance for next time
                    user.metadata["spawn_chance"] = min(0.5, chance + 0.01)
                    user.save_user()
        
        return False
    
    def get_entity(self):
        """Returns the current entity"""
        return self.current_entity
    
    def get_entity_type(self):
        """Returns the active entity type"""
        return self.entity_type
