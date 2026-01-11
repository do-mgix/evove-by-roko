
import json, os
from datetime import datetime
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.action import Action

class User:
    def __init__(self):
        self._attributes = {} 
        self._actions = {} 
        self._score = 0
        self._value = 0

    @property
    def score(self):        
        return self._score

    @property
    def value(self):
        return self._value

    @property 
    def attributes(self):
        return self._attributes

    @property
    def actions(self):
        return self._actions

    @property
    def next_attr_id(self):
        attributes = self.attributes
        next = len(attributes) + 1
        return next

    @property
    def next_action_id(self):
        actions = self.actions
        next = len(actions) + 1
        return next

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
            "score": self._score,
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
        self._score = data.get("score", 0)
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


    def act(self, payloads):
        action_id = f"5{payloads[0]}"  
        action = self.actions.get(action_id)
        
        if not action:
                print(f"\n [ ERRO ] ID {action_id} not found")
        else:
            action.execution()
            self.save_user()

    def create_attribute(self, buffer: str):
        name = input("nome do atributo: ")
        new_id = f"8{self.next_attr_id:02d}"
        
        new_attribute = Attribute(new_id, name, None, None, None)
        self._attributes[new_id] = new_attribute
        
        print(f"Atributo '{name}' criado com ID: {new_id}")
        actions = self.actions
        
        self.save_user()

    def create_action(self, buffer:str):    
        
        try:
            tipo = int(buffer[0])
            diff = int(buffer[1])
            name = input("Nome da ação: ")
            new_id = f"5{self.next_action_id:02d}"
            starter_value = 0
            
            action = Action(new_id, name, tipo, diff, starter_value)

            self._actions[new_id] = action
            
            print(f"Action '{name}' created. ID {new_id}")

            self.save_user()

        except Exception as e:
            print(f"[Error] something went wrong {e}")

    def attribute_add_action(self, payloads):
        attr_id = f"8{payloads[0]}"   
        action_id = f"5{payloads[1]}"
    
        attribute = self._attributes.get(attr_id)
        action = self._actions.get(action_id)
    
        if attribute and action:
            attribute.AddRelatedAction(action)
            print(f"\n [ SUCESS ] {action.name} -> {attribute.attr_name}")
            self.save_user()
        else:
            print(f"\n [ ERROR ] Some of IDs {attr_id} {action_id} not found.")
    

user = User()


