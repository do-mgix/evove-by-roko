# ==================== USER.PY ====================
import json, os
from datetime import datetime
from src.components.entitys.entity_manager import EntityManager
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.action import Action

class User:
    def __init__(self):
        him = EntityManager().get_entity()
        self._attributes = {} 
        self._actions = {} 
        self._value = 0
        self.messages = []  # Buffer de mensagens para o render
        self.metadata = {
            "mode": "progressive",
            "virtual_agent_active": True,
            "unlocked_packages": ["basics"]
        }
            
    def clear_messages(self):
        """Limpa o buffer de mensagens"""
        self.messages = []
    
    def add_message(self, msg):
        """Adiciona mensagem ao buffer"""
        self.messages.append(msg)
    
    @property
    def next_attr_id(self):        
        if self._attributes:
            higher = max(self._attributes)
            higher = higher[1:3]
            return int(higher) + 1
        else:
            return 1
    
    @property
    def next_action_id(self):
        if self._actions:
            higher = max(self._actions)
            higher = higher[1:3]
            return int(higher) + 1
        else:
            return 1
    
    @property
    def score(self):
        if self._attributes:
            total = sum(attr.total_score for attr in self._attributes.values())
            return total / len(self._attributes)
        else:
            return 0.0
    
    def sleep(self):
        self.add_message(f"sleep at {datetime.now()}")
    
    def wake(self):
        self.add_message(f"woke at {datetime.now()}")
    
    def log(self):
        self.add_message("logged")
    
    def save_user(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Sobe 2 níveis: user/ -> components/ -> src/
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        data_dir = os.path.join(src_dir, "data")    
        data_file = os.path.join(data_dir, "user.json")

        # Cria o diretório se não existir
        os.makedirs(data_dir, exist_ok=True)
            
        data = {
            "score": self.score,
            "value": self._value,
            "attributes": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._attributes.items()
            },
            "actions": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._actions.items()
            },
            "metadata": self.metadata
        }
    
        try:
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            # self.add_message(f"file saved.")
            self.load_user()
        except Exception as e:
            self.add_message(f"Error saving {e}")

    def load_user(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Sobe 2 níveis: user/ -> components/ -> src/
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        data_dir = os.path.join(src_dir, "data")
        data_file = os.path.join(data_dir, "user.json")

        if not os.path.exists(data_file):
            # self.add_message(f"new save file created.")
            self.save_user() 
            return
        
        if os.path.getsize(data_file) == 0:
            self.add_message("empty save file.")
            return
        
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.add_message("corrupted save file.")
            return
        
        self._value = data.get("value", 0)
        self.metadata.update(data.get("metadata", {}))
        
        self._attributes.clear()
        for attr_id, attr_data in data.get("attributes", {}).items():
            new_attr = Attribute.from_dict(attr_data)
            self._attributes[attr_id] = new_attr
        
        self._actions.clear()
        for action_id, action_data in data.get("actions", {}).items():
            new_act = Action.from_dict(action_data)
            self._actions[action_id] = new_act
        
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_related_actions'):
                attr.resolve_related_actions(self._actions)
        
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_children'):
                attr.resolve_children(self._attributes)
        
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_parent'):
                attr.resolve_parent(self._attributes)
    
    def act(self, payloads):
        """Executa ação e retorna mensagens"""
        action_id = f"5{payloads[0]}"  
        action = self._actions.get(action_id)
    
        if not action:
            self.add_message(f"\n [ ERRO ] ID {action_id} not found")
            return None
    
        score_difference, action_messages = action.execution()
    
        # Adiciona mensagens da action
        for msg in action_messages:
            self.add_message(msg)

        # Cálculo de Boost por Satisfação
        him = EntityManager().get_entity()
        current_sat = him.satisfaction
        
        boost_multiplier = 1.0
        if current_sat > 40:
            # Interpolação linear: 40 (0%) -> 100 (50%)
            boost_factor = min(0.5, (current_sat - 40) / 60 * 0.5)
            boost_factor = max(0, boost_factor) # Garante que não é negativo
            boost_multiplier = 1.0 + boost_factor
            
            if boost_factor > 0:
                self.add_message(f"{him.__class__.__name__.upper()} BOOST: +{boost_factor*100:.1f}% score gained!")

        final_score_difference = score_difference * boost_multiplier
    
        self.save_user()
    
        # Returns the score with the applied boost for Roko to process
        return final_score_difference
    

    def create_attribute(self):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        name = input("attribute name: ")
        nextid = self.next_attr_id
        new_id = f"80{nextid}" if nextid < 10 else f"8{nextid}"           
        new_attribute = Attribute(new_id, name, None, None, None)
        self._attributes[new_id] = new_attribute
        
        self.add_message(f"attribute '{name}' created with ID {new_id}")
        self.save_user()
    
    def create_attribute_by_id(self, payloads):
        new_id = f"8{payloads[0]}"        
        
        if new_id not in self._attributes:
            name = input("attribute name: ")
            new_attribute = Attribute(new_id, name, None, None, None)
            self._attributes[new_id] = new_attribute
            self.add_message(f"attribute '{name}' created with ID {new_attribute._id}")
            self.save_user()
        else:
            self.add_message(f"ID ({new_id}) already exists.")
    
    def create_action(self, buffer: str):    
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        try:
            tipo = int(buffer[0])
            diff = int(buffer[1])
            name = input("action name: ")
            nextid = self.next_action_id
            new_id = f"50{nextid}" if nextid < 10 else f"5{nextid}"           
            starter_value = 0
            
            action = Action(new_id, name, tipo, diff, starter_value)
            self._actions[new_id] = action
            
            self.add_message(f"action '{name}' created with ID {new_id}")
            self.save_user()
        except Exception as e:
            self.add_message(f"{e}")
    
    def list_attributes(self):
        if self._attributes:
            from src.components.services.UI.interface import ui
            items = [f"({attr._id}) - {attr._name}" for attr in self._attributes.values()]
            ui.show_list(items, "CURRENT ATTRIBUTES")
        else:
            self.add_message("no attributes available. try creating one with 28...")
    
    def list_actions(self):
        if self._actions:
            from src.components.services.UI.interface import ui
            items = [f"({action._id}) - {action._name}" for action in self._actions.values()]
            ui.show_list(items, "CURRENT ACTIONS")
        else:
            self.add_message("no actions available. try creating one with 25...")
    
    def drop_attributes(self):
        from src.components.services.UI.interface import ui
        if ui.ask_confirmation("This will PERMANENTLY DELETE ALL ATTRIBUTES."):
            self._attributes.clear()
            self.add_message("attributes deleted.")
            self.save_user()
        else:
            self.add_message("the attributes are safe.")
    
    def drop_actions(self):
        from src.components.services.UI.interface import ui
        if ui.ask_confirmation("This will PERMANENTLY DELETE ALL ACTIONS."):
            self._actions.clear()
            self.add_message("actions deleted.")
            self.save_user()
        else:
            self.add_message("the actions are safe.")
    
    def delete_attribute(self, payloads):
        payload_id = f"8{payloads[0]}"   
        attr = self._attributes.get(payload_id)
        
        if not attr:
            self.add_message(f"Attribute ID ({payload_id}) not found")
            return

        from src.components.services.UI.interface import ui
        if ui.ask_confirmation(f"Delete attribute {attr._name} ({attr._id})?"):
            self._attributes.pop(payload_id, None)
            self.add_message(f"Attribute {attr._name} ({attr._id}) deleted.")
            self.save_user()

    def delete_action(self, payloads):
        payload_id = f"5{payloads[0]}"   
        action = self._actions.get(payload_id)

        if not action:
            self.add_message(f"Action ID ({payload_id}) not found")
            return

        from src.components.services.UI.interface import ui
        if ui.ask_confirmation(f"Delete action {action._name} ({action._id})?"):
            self._actions.pop(payload_id, None)
            self.add_message(f"Action {action._name} ({action._id}) deleted.")
            self.save_user()

    def attribute_add_action(self, payloads):
        attr_id = f"8{payloads[0]}"   
        action_id = f"5{payloads[1]}"
        
        attribute = self._attributes.get(attr_id)
        action = self._actions.get(action_id)
        
        if attribute and action:
            attribute.add_related_action(action)
            self.add_message(f"{action._name} -> {attribute._name}")
            self.save_user()
        else:
            self.add_message(f"some of IDs {attr_id} {action_id} not found.")
    
    def attribute_add_child(self, payloads):
        attr_id = f"8{payloads[0]}"   
        child_id = f"8{payloads[1]}"
        
        attribute = self._attributes.get(attr_id)
        child = self._attributes.get(child_id)
        
        if attribute and child:
            if not attribute == child:
                attribute.add_child(child)
                self.add_message(f"{child._name} -> {attribute._name}")
                self.save_user()
            else:        
                self.add_message(f"{attr_id} {child_id} are the same.")   
        else:
            self.add_message(f"some of IDs {attr_id} {child_id} not found.")

user = User()
