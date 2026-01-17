# ==================== GERENCIADOR DE ENTIDADES ====================

from src.components.entitys.roko import Him
from src.components.entitys.sorbet import Sorbet

class EntityManager:
    """Gerencia qual entidade está ativa e spawns"""
    
    def __init__(self):
        self.current_entity = Him()  # Começa com Roko
        self.entity_type = "roko"
        
    def check_and_spawn(self):
        """Verifica spawn events e retorna se houve mudança"""
        status = self.current_entity.get_spawn_status()
        
        if status:
            if status['event'] == 'roko_returned':
                # Roko voltou
                self.entity_type = "roko"
                return True
                
            elif status['event'] == 'new_entity_spawned':
                # Spawna Sorbet (ou outra entidade futura)
                old_entity = self.entity_type
                self.current_entity = Sorbet()
                self.entity_type = "sorbet"
                self.current_entity.spawn_message()
                
                return True
        
        return False
    
    def get_entity(self):
        """Retorna a entidade atual"""
        return self.current_entity
    
    def get_entity_type(self):
        """Retorna o tipo de entidade ativa"""
        return self.entity_type
