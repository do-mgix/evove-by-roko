
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
# Mudamos para dicionários para busca rápida por ID: {"801": objeto, "802": objeto}
        self._attributes = {} 
        self._actions = {}
        
        # Contadores começando em 1
        self._next_attr_id = 1
        self._next_action_id = 1
        
        # Atributos internos para score e valor
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



evove = User()
