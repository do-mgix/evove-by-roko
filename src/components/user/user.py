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
            "unlocked_packages": ["basics"],
            "tokens": 0,
            "max_tokens": 100,
            "daily_refill": 50,
            "last_token_refill": datetime.now().strftime("%Y-%m-%d")
        }

    def add_tokens(self, amount):
        """Adds tokens up to max_tokens limit"""
        max_t = self.metadata.get("max_tokens", 100)
        current = self.metadata.get("tokens", 0)
        new_total = min(max_t, current + amount)
        self.metadata["tokens"] = new_total
        self.add_message(f"Tokens added: {amount}. Current balance: {new_total}/{max_t}")
        self.save_user()

    def spend_tokens(self, amount):
        """Spends tokens if possible. Returns True if successful."""
        current = self.metadata.get("tokens", 0)
        if current >= amount:
            self.metadata["tokens"] = current - amount
            self.add_message(f"Tokens spent: {amount}. Current balance: {self.metadata['tokens']}")
            self.save_user()
            return True
        else:
            self.add_message(f"Insufficient tokens! Needed: {amount}, Current: {current}")
            return False
            
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
    
    def act(self, payloads, value=None):
        """Executa ação e retorna mensagens"""
        action_id = f"5{payloads[0]}"  
        action = self._actions.get(action_id)

        if not action:
            self.add_message(f"\n [ ERRO ] ID {action_id} not found")
            return None

        score_difference, action_messages = action.execution(manual_value=value)
    
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
    

    def open_shop(self):
        """Displays shop items"""
        from src.components.services.shop_service import ShopService
        shop = ShopService(self)
        shop.show_items()

    def buy_shop_item(self, item_id=None):
        """Buys a shop item. item_id can be passed from dial or buffer."""
        from src.components.services.shop_service import ShopService
        shop = ShopService(self)
        
        # If called from list_actions/dial, it might be a list
        target_id = item_id
        if isinstance(item_id, list) and item_id:
            target_id = item_id[0]
            
        if shop.buy_item(target_id):
            self.save_user()

    def create_attribute(self, name=None):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        if name is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("attribute name", type="text")

        nextid = self.next_attr_id
        new_id = f"80{nextid}" if nextid < 10 else f"8{nextid}"           
        new_attribute = Attribute(new_id, name, None, None, None)
        self._attributes[new_id] = new_attribute
        
        self.add_message(f"attribute '{name}' created with ID {new_id}")
        self.save_user()
    
    def create_attribute_by_id(self, payloads, name=None):
        new_id = f"8{payloads[0]}"        
        
        if new_id not in self._attributes:
            if name is None:
                from src.components.services.UI.interface import WebInputInterrupt
                raise WebInputInterrupt("attribute name", type="text", options={"payloads": payloads})
            new_attribute = Attribute(new_id, name, None, None, None)
            self._attributes[new_id] = new_attribute
            self.add_message(f"attribute '{name}' created with ID {new_attribute._id}")
            self.save_user()
        else:
            self.add_message(f"ID ({new_id}) already exists.")
    
    def create_action(self, buffer: str, name=None):    
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        if name is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("action name", type="text", options={"buffer": buffer})

        try:
            tipo = int(buffer[0])
            diff = int(buffer[1])
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
    
    def delete_attribute(self, payloads, confirmed=None):
        payload_id = f"8{payloads[0]}"   
        attr = self._attributes.get(payload_id)
        
        if not attr:
            self.add_message(f"Attribute ID ({payload_id}) not found")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt
        if confirmed is True:
            pass
        elif ui.web_mode:
            import random
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.add_message(f"Delete {attr._name} ({attr._id})?")
            self.add_message(f"Type the code: {code}")
            raise WebInputInterrupt(f"Confirm code: {code}", type="confirm", options={"code": code, "payloads": payloads, "action": "delete_attribute"})
        elif not ui.ask_confirmation(f"Delete attribute {attr._name} ({attr._id})?"):
            return

        self._attributes.pop(payload_id, None)
        self.add_message(f"Attribute {attr._name} ({attr._id}) deleted.")
        self.save_user()

    def delete_action(self, payloads, confirmed=None):
        payload_id = f"5{payloads[0]}"   
        action = self._actions.get(payload_id)

        if not action:
            self.add_message(f"Action ID ({payload_id}) not found")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt
        if confirmed is True:
            pass
        elif ui.web_mode:
            import random
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.add_message(f"Delete {action._name} ({action._id})?")
            self.add_message(f"Type the code: {code}")
            raise WebInputInterrupt(f"Confirm code: {code}", type="confirm", options={"code": code, "payloads": payloads, "action": "delete_action"})
        elif not ui.ask_confirmation(f"Delete action {action._name} ({action._id})?"):
            return

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
