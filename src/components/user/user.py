
import json, os
from datetime import datetime
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.repetition_action import RepetitionAction
from src.components.user.actions.sec_action import SecAction
from src.components.user.actions.min_action import MinAction
from src.components.user.actions.hour_action import HourAction

ACTION_PROMPT_MAP = {
    RepetitionAction: ("insira repetições (inteiro): ", int),
    SecAction: ("insira segundos (float): ", float),
    MinAction: ("insira minutos (float): ", float),
    HourAction: ("insira horas (float): ", float),
}

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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_file = os.path.join(base_dir, "user.json")

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

        self._score = data.get("score", 0)
        self._value = data.get("value", 0)
        
        self._attributes.clear()
        for attr_id, attr_data in data.get("attributes", {}).items():
            new_attr = Attribute(attr_id, attr_data['name'])
            self._attributes[attr_id] = new_attr

        self._actions.clear()
        for action_id, action_data in data.get("actions", {}).items():
            action_map = {
                "RepetitionAction": RepetitionAction,
                "SecAction": SecAction,
                "MinAction": MinAction,
                "HourAction": HourAction
            }
            action_type = action_map[action_data['type']]
            new_act = action_type(act_id, act_data['name'], act_data['diff'], act_data['value'], None)
            self._attributes[attr_id] = new_attr

        # class_map = {
        #     "RepetitionAction": RepetitionAction,
        #     "SecAction": SecAction,
        #     "MinAction": MinAction,
        #     "HourAction": HourAction
        # }
        #
        # for act_id, act_data in data.get("actions", {}).items():
        #     class_name = act_data.get("class_type") 
        #     action_class = class_map.get(class_name)
        #
        #     if action_class:
        #         self._actions[act_id] = action_class(act_id, act_data['name'])          


    def act(self, payloads):
        action_id = f"5{payloads[0]}"  
        action = self._actions.get(action_id)

        if not action:
            print(f"\n [ ERRO ] Ação com ID {action_id} não encontrada.")
            return

        prompt_message, value_type = ACTION_PROMPT_MAP.get(type(action), ("Valor: ", str))

        while True:
            try:
                value_str = input(prompt_message)
                value = value_type(value_str)  
                break 
            except ValueError:
                print(f"Entrada inválida. Por favor, insira um valor do tipo '{value_type.__name__}'.")
        
        print(f"Ação {action.name} (ID: {action_id}) executada com valor: {value}")
        
        self.save_user()

    def create_attribute(self, buffer: str):
        name = input("nome do atributo: ")
        new_id = f"8{self.next_attr_id:02d}"
        
        new_attribute = Attribute(new_id, name)
        self._attributes[new_id] = new_attribute
        
        print(f"Atributo '{name}' criado com ID: {new_id}")
        actions = self.actions
        
        self.save_user()

    def create_action(self, buffer: str):    
        type_map = {
            "1": RepetitionAction,  
            "2": SecAction, 
            "3": MinAction, 
            "4": HourAction, 
        }

        try:
            action_type_char = buffer[0]
            diff_value = int(buffer[1]) if len(buffer) > 1 else 0
            
            tipo_classe = type_map.get(action_type_char, RepetitionAction)
            name = input("Nome da ação: ")
            new_id = f"5{self.next_action_id:02d}"
            
            action_obj = tipo_classe(new_id, name, diff_value, 0)
            self._actions[new_id] = action_obj
            
            print(f"Ação '{name}' ({tipo_classe.__name__}) criada com ID: {new_id}")
        except Exception as e:
            print(f"Erro ao criar ação: {e}")

        self.save_user()

    def attribute_add_action(self, payloads):
        attr_id = f"8{payloads[0]}"   
        action_id = f"5{payloads[1]}"
    
        attribute = self._attributes.get(attr_id)
        action = self._actions.get(action_id)
    
        if attribute and action:
            attribute.AddRelatedAction(action)
            print(f"\n [ SUCESSO ] '{action.name}' vinculada a '{attribute.attr_name}'")
        else:
            print(f"\n [ ERRO ] IDs não encontrados: Attr:{attr_id}, Action:{action_id}")
    
        self.save_user()


user = User()


