
import json, os
from datetime import datetime
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.action import Action

class User:
    def __init__(self):
        self._attributes = {} 
        self._actions = {} 
        self._value = 0

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

    def sleep(self, buffer: str):
        print(f"sleep at {datetime.now()}")

    def wake(self, buffer: str):
        print(f"woke at {datetime.now()}")       

    def log(self, buffer: str):
        print(f"logged")

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
            print(f"[*] Sucesso: Arquivo salvo em {data_file}")
            self.load_user()
        except Exception as e:
            print(f"[!] Erro ao salvar: {e}")
         

    def load_user(self):
        # dir e nome
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_file = os.path.join(base_dir, "user.json")
        
        # se não existir o arquivo, cria
        if not os.path.exists(data_file):
            print(f"[!] {data_file} não encontrado. Criando arquivo padrão...")
            self.save_user() 
            return

        if os.path.getsize(data_file) == 0:
            print("[!] Arquivo user.json está vazio. Pulando carregamento para evitar erro.")
            return

        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print("[!] Erro: O arquivo existe mas não contém um JSON válido. Carregamento cancelado.")
            return

        # valores únicos
        # self.score is now dynamic, so we just load value
        self._value = data.get("value", 0)
        
        # Cria os atributos do json
        self._attributes.clear()
        for attr_id, attr_data in data.get("attributes", {}).items():
            new_attr = Attribute.from_dict(attr_data)
            self._attributes[attr_id] = new_attr
        
        # Cria as actions do json - recebe from dict
        self._actions.clear()
        for action_id, action_data in data.get("actions", {}).items():
            new_act = Action.from_dict(action_data)
            self._actions[action_id] = new_act
        
        # realaciona as ações realcionadas aos atributos
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_related_actions'):
                attr.resolve_related_actions(self._actions)

        # children fix 
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_children'):
                attr.resolve_children(self._attributes)

        # parent fix 
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_parent'):
                attr.resolve_parent(self._attributes)

    def act(self, payloads):
        action_id = f"5{payloads[0]}"  
        action = self._actions.get(action_id)
        
        if not action:
            print(f"\n [ ERRO ] ID {action_id} not found")
        else:
            action.execution()
            self.save_user()

    def create_attribute(self, buffer: str):
        name = input("nome do atributo: ")

        nextid = self.next_attr_id
        new_id = f"80{nextid}" if nextid < 10 else f"8{nextid}"           

        new_attribute = Attribute(new_id, name, None, None, None)
        self._attributes[new_id] = new_attribute
        
        print(f"Atributo '{name}' criado com ID: {new_id}")
        
        self.save_user()

    def create_attribute_by_id(self, payloads):
        new_id = f"8{payloads[0]}"        

        if new_id not in self._attributes:
    
            name = input("nome do atributo: ")
            new_attribute = Attribute(new_id, name, None, None, None)
            self._attributes[new_id] = new_attribute
        
            print(f"Atributo '{name}' criado com ID: {new_id}")

            self.save_user()
        else:
            print(f"ID ({new_id}) alread exists. ")

    def create_action(self, buffer:str):    
        
        try:
            tipo = int(buffer[0])
            diff = int(buffer[1])
            name = input("Nome da ação: ")
            nextid = self.next_action_id
            new_id = f"50{nextid}" if nextid < 10 else f"5{nextid}"           
            starter_value = 0
            
            action = Action(new_id, name, tipo, diff, starter_value)

            self._actions[new_id] = action
            
            print(f"Action '{name}' created. ID {new_id}")

            self.save_user()

        except Exception as e:
            print(f"[Error] something went wrong {e}")

    def list_attributes(self, buffer):
        if self._attributes:
            print(f"        CURRENT ATTRIBUTES ")        
            for attr in self._attributes.values():
                print(f"({attr._id}) - {attr._name}")

        else:
            print(f"none attribute available. try creating one with 28... ")

    def list_actions(self, nothing):
        if self._actions:
            print(f"        CURRENT ACTIONS        ")
            for action in self._actions.values():
                print(f"({action._id}) - {action._name}")
        else:
            print(f"none action available. try creating one with 25... ")

    def drop_attributes(self, nothing):
        print(f"drop attributes? type: yes ")
        if input() == "yes":
            self._attributes.clear()
            print(f"attributes deleted")
            self.save_user()
        else:
            print(f"the attributes are safe")

    def drop_actions(self, nothing):
        print(f"drop actions? type: yes ")
        if input() == "yes":
            self._actions.clear()
            print(f"actions deleted")
            self.save_user()
        else:
            print(f"the actions are safe")

    def delete_attribute(self, payloads):
        
        payload_id = f"8{payloads[0]}"   
        for attr in self._attributes.values():
            if attr._id == payload_id:
                self._attributes.pop(payload_id, None)
                print(f"Attribute {attr._name}({attr._id}) deleted.")
                self.save_user()
                return 0        

        print(f"Attribute ID ({payload_id}) not found")

    def attribute_add_action(self, payloads):
        attr_id = f"8{payloads[0]}"   
        action_id = f"5{payloads[1]}"
    
        attribute = self._attributes.get(attr_id)
        action = self._actions.get(action_id)
    
        if attribute and action:
            attribute.add_related_action(action)
            print(f"\n [ SUCESS ] {action._name} -> {attribute._name}")
            self.save_user()
        else:
            print(f"\n [ ERROR ] Some of IDs {attr_id} {action_id} not found.")
 
    def attribute_add_child(self, payloads):
        attr_id = f"8{payloads[0]}"   
        child_id = f"8{payloads[1]}"
    
        attribute = self._attributes.get(attr_id)
        child = self._attributes.get(child_id)

        if attribute and child:
            if not attribute == child:
                attribute.add_child(child)
                print(f"\n [ SUCESS ] {child._name} -> {attribute._name}")
                self.save_user()
            else:        
                print(f"\n [ ERROR ] {attr_id} {child_id} are the same.")   
        else:
            print(f"\n [ ERROR ] Some of IDs {attr_id} {child_id} not found.")   

user = User()


