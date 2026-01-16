# ==================== USER.PY ====================
import json, os
from datetime import datetime
from src.components.roko.roko import him
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.action import Action

class User:
    def __init__(self):
        self.him = him
        self._attributes = {} 
        self._actions = {} 
        self._value = 0
        self.messages = []  # Buffer de mensagens para o render
    
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
        data_file = os.path.join(base_dir, "user.json")
        
        data = {
            "score": self.score,
            "value": self._value,
            "attributes": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._attributes.items()
            },
            "actions": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._actions.items()
            }
        }
        
        try:
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self.add_message(f"file saved.")
            self.load_user()
        except Exception as e:
            self.add_message(f"Error saving {e}")
    
    def load_user(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_file = os.path.join(base_dir, "user.json")
        
        if not os.path.exists(data_file):
            self.add_message(f"new save file created.")
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
    
        self.save_user()
    
        # Retorna score_difference para o Roko processar depois
        return score_difference
    

    def create_attribute(self):
        name = input("nome do atributo: ")
        nextid = self.next_attr_id
        new_id = f"80{nextid}" if nextid < 10 else f"8{nextid}"           
        new_attribute = Attribute(new_id, name, None, None, None)
        self._attributes[new_id] = new_attribute
        
        self.add_message(f"attribute '{name}' created with ID {new_id}")
        self.save_user()
    
    def create_attribute_by_id(self, payloads):
        new_id = f"8{payloads[0]}"        
        
        if new_id not in self._attributes:
            name = input("nome do atributo: ")
            new_attribute = Attribute(new_id, name, None, None, None)
            self._attributes[new_id] = new_attribute
            self.add_message(f"attribute '{name}' created with ID {new_id}")
            self.save_user()
        else:
            self.add_message(f"ID ({new_id}) alread exists.")
    
    def create_action(self, buffer: str):    
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
            self.add_message("        CURRENT ATTRIBUTES        ")
            for attr in self._attributes.values():
                self.add_message(f"({attr._id}) - {attr._name}")
        else:
            self.add_message("none attribute available. try creating one with 28...")
    
    def list_actions(self):
        if self._actions:
            self.add_message("        CURRENT ACTIONS        ")
            for action in self._actions.values():
                self.add_message(f"({action._id}) - {action._name}")
        else:
            self.add_message("none action available. try creating one with 25...")
    
    def drop_attributes(self):
        self.add_message("drop attributes? type yes to confirm:")
        if input() == "yes":
            self._attributes.clear()
            self.add_message("attributes deleted.")
            self.save_user()
        else:
            self.add_message("the attributes are safe.")
    
    def drop_actions(self):
        self.add_message("drop actions? type yes to confirm:")
        if input() == "yes":
            self._actions.clear()
            self.add_message("actions deleted.")
            self.save_user()
        else:
            self.add_message("the actions are safe.")
    
    def delete_attribute(self, payloads):
        payload_id = f"8{payloads[0]}"   
        
        for attr in self._attributes.values():
            if attr._id == payload_id:
                self._attributes.pop(payload_id, None)
                self.add_message(f"Attribute {attr._name}({attr._id}) deleted.")
                self.save_user()
                return
        
        self.add_message(f"attribute ID ({payload_id}) not found")
    
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
