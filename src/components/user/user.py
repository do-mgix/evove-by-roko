
import json, os
from datetime import datetime
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.repetition_action import RepetitionAction
from src.components.user.actions.sec_action import SecAction
from src.components.user.actions.min_action import MinAction
from src.components.user.actions.hour_action import HourAction


# Mapeamento de classes de Ação para suas mensagens de prompt e tipos de valor
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
        self._next_attr_id = 1
        self._next_action_id = 1
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

    def sleep(self, buffer: str):
        print(f"sleep at {datetime.now()}")

    def wake(self, buffer: str):
        print(f"woke at {datetime.now()}")       

    def log(self, buffer: str):
        print(f"logged")

    def save_user(self):
        # 1. Descobre o diretório onde este arquivo (user.py) está
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Cria o caminho completo para o arquivo user.json no mesmo diretório
        data_file = os.path.join(base_dir, "user.json")

        data = {
            "score": self._score,
            "value": self._value,
            "next_attr_id": self._next_attr_id,
            "next_action_id": self._next_action_id,
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
            print("[!] Arquivo não encontrado. Mantendo dados atuais.")
            return

        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Atualiza o estado do objeto atual (self)
        self._score = data.get("score", 0)
        self._value = data.get("value", 0)
        self._next_attr_id = data.get("next_attr_id", 1)
        self._next_action_id = data.get("next_action_id", 1)

        # Reconstrói os atributos no dicionário existente
        # Importante: limpamos o dicionário antes para não duplicar se carregar duas vezes
        self._attributes.clear()
        for attr_id, attr_data in data.get("attributes", {}).items():
            # Aqui você instancia seu objeto Attribute real
            new_attr = Attribute(attr_id, attr_data['name'])
            self._attributes[attr_id] = new_attr
            
        print(f"[*] Dados carregados com sucesso. Próximo ID de Atributo: {self._next_attr_id}")
 
    def act(self, payloads):
        action_id = f"5{payloads[0]}"  # Resulta em "501"
        action = self._actions.get(action_id)

        if not action:
            print(f"\n [ ERRO ] Ação com ID {action_id} não encontrada.")
            return

        # Busca a mensagem e o tipo do nosso mapa usando a classe do objeto
        prompt_message, value_type = ACTION_PROMPT_MAP.get(type(action), ("Valor: ", str))

        while True:
            try:
                value_str = input(prompt_message)
                value = value_type(value_str)  # Converte para int ou float
                break  # Sai do loop se a conversão for bem-sucedida
            except ValueError:
                print(f"Entrada inválida. Por favor, insira um valor do tipo '{value_type.__name__}'.")
        
        # Aqui você chamaria a execução da ação com o valor validado
        # action.execution(value) 
        print(f"Ação {action.name} (ID: {action_id}) executada com valor: {value}")

 # --- Criação de Objetos ---
    def create_attribute(self, buffer: str):
        # O buffer aqui pode vir vazio ou com prefixo, 
        # mas o nome pedimos via input por enquanto
        name = input("nome do atributo: ")
        
        new_id = f"8{self._next_attr_id:02d}"
        
        # Instancia o objeto e guarda no dicionário usando o ID como chave
        new_attribute = Attribute(new_id, name)
        self._attributes[new_id] = new_attribute
        
        print(f"Atributo '{name}' criado com ID: {new_id}")
        self._next_attr_id += 1
        
        self.save_user()

    def create_action(self, buffer: str):    
        type_map = {
            "1": RepetitionAction,  
            "2": SecAction, 
            "3": MinAction, 
            "4": HourAction, 
        }

        # Exemplo de buffer para criação: "25" (tipo) + "1" (diff) -> "251"
        # Ajuste conforme sua necessidade de criação
        try:
            action_type_char = buffer[0]
            diff_value = int(buffer[1]) if len(buffer) > 1 else 0
            
            tipo_classe = type_map.get(action_type_char, RepetitionAction)
            name = input("Nome da ação: ")
            
            new_id = f"5{self._next_action_id:02d}"
            
            # Instancia a classe de ação correspondente
            action_obj = tipo_classe(new_id, name, diff_value)
            self._actions[new_id] = action_obj
            
            print(f"Ação '{name}' ({tipo_classe.__name__}) criada com ID: {new_id}")
            self._next_action_id += 1
        except Exception as e:
            print(f"Erro ao criar ação: {e}")

        self.save_user()

    def attribute_add_action(self, payloads):
        """
         Recebe payloads = ['01', '01']
        """
        # 1. Reconstrói os IDs completos usando os prefixos
        attr_id = f"8{payloads[0]}"   # Resulta em "801"
        action_id = f"5{payloads[1]}" # Resulta em "501"
    
        # 2. Busca os objetos nos dicionários (Agora funciona!)
        attribute = self._attributes.get(attr_id)
        action = self._actions.get(action_id)
    
        if attribute and action:
            attribute.AddRelatedAction(action)
            print(f"\n [ SUCESSO ] '{action.name}' vinculada a '{attribute.attr_name}'")
        else:
            print(f"\n [ ERRO ] IDs não encontrados: Attr:{attr_id}, Action:{action_id}")
    
        self.save_user()


user = User()


