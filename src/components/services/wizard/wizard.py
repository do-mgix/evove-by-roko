import json
import os
from pathlib import Path

from src.components.user.user import user 

class Wizard:
    """Wizard para configuração e setup do sistema - templates, configs, etc."""
    
    def __init__(self, user_instance):
        self.user = user_instance
        self.packages_dir = Path(__file__).parent.parent.parent / "data" / "packages"
        self.available_templates = self._load_available_templates()
        
    def start(self):
        """Inicia o menu principal do wizard"""
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("=" * 50)
            print("        WIZARD")
            print("=" * 50)
            print("\nConfiguration Options:")
            print()
            print("1 - Attribute Templates")
            print("2 - Study and Focus (Coming Soon)")
            print()
            print("0 - Cancel")
            print()
            
            choice = input("Select option: ")
            
            if choice == "0":
                return
            elif choice == "1":
                self.attribute_templates()
            elif choice == "2":
                print("\nComing soon...")
                input("Press ENTER to continue...")
            else:
                print("Invalid option.")
                input("Press ENTER to continue...")
    
    def attribute_templates(self):
        """Gerencia templates de atributos"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 50)
        print("        ATTRIBUTE TEMPLATES")
        print("=" * 50)
        print("\nAvailable Templates:")
        print()
        
        if not self.available_templates:
            print("No templates found in data/packages/")
            print("Press any key to return...")
            input()
            return
        
        # Lista templates disponíveis
        template_list = list(self.available_templates.keys())
        for idx, template_name in enumerate(template_list, 1):
            template_data = self.available_templates[template_name]
            description = template_data.get('description', 'No description')
            print(f"{idx} - {template_data.get('name', template_name)}")
            print(f"    {description}")
            print()
        
        print("0 - Back")
        print()
        
        # Seleção do template
        while True:
            try:
                choice = input("Select template (0 to go back): ")
                choice_num = int(choice)
                
                if choice_num == 0:
                    return
                
                if 1 <= choice_num <= len(template_list):
                    selected_template = template_list[choice_num - 1]
                    self._display_template(selected_template)
                    break
                else:
                    print("Invalid option. Try again.")
            except ValueError:
                print("Please enter a number.")
    def _load_available_templates(self):
        """Carrega todos os templates disponíveis da pasta packages"""
        if not self.packages_dir.exists():
            self.packages_dir.mkdir(parents=True, exist_ok=True)
            return {}
        
        templates = {}
        for file in self.packages_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    templates[file.stem] = data
            except Exception as e:
                print(f"Error loading template {file}: {e}")
        
        return templates
    
        """Mostra a árvore de atributos do template"""
        os.system('cls' if os.name == 'nt' else 'clear')
        template = self.available_templates[template_name]
        
        print("=" * 50)
        print(f"        {template.get('name', template_name).upper()}")
        print("=" * 50)
        print()
        
        # Mostra a estrutura da árvore
        attributes = template.get('attributes', {})
        actions = template.get('actions', {})
        
        # Encontra os atributos raiz (sem parent)
        root_attrs = [attr for attr in attributes.values() 
                     if not attr.get('parent') or len(attr.get('parent', [])) == 0]
        
        print("ATTRIBUTE TREE:")
        print()
        for root in root_attrs:
            self._print_tree(root, attributes, actions, indent=0)
        
        print()
        print("=" * 50)
        print(f"Total Attributes: {len(attributes)}")
        print(f"Total Actions: {len(actions)}")
        print("=" * 50)
        print()
        print("1 - Accept and Import")
        print("0 - Cancel")
        print()
        
        choice = input("Your choice: ")
        
        if choice == "1":
            self._import_template(template)
        
    def _print_tree(self, attr, all_attrs, all_actions, indent=0):
        """Imprime a árvore de atributos recursivamente"""
        prefix = "  " * indent
        
        # Nome do atributo
        print(f"{prefix}• {attr['name']}")
        
        # Ações relacionadas
        for action_id in attr.get('related_actions', []):
            action = all_actions.get(action_id)
            if action:
                action_type = self._get_action_type_label(action['type'])
                diff_stars = "★" * action['diff']
                print(f"{prefix}  ⭐ {action['name']} ({action_type}, {diff_stars})")
        
        # Filhos
        for child_id in attr.get('children', []):
            child = all_attrs.get(child_id)
            if child:
                self._print_tree(child, all_attrs, all_actions, indent + 1)
    
    def _get_action_type_label(self, type_num):
        """Retorna label do tipo de ação"""
        types = {
            1: "reps",
            2: "secs",
            3: "mins",
            4: "hours",
            5: "letters"
        }
        return types.get(type_num, "unknown")
    
    def _import_template(self, template):
        """Importa o template para o usuário"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("Importing template...")
        print()
        
        attributes = template.get('attributes', {})
        actions = template.get('actions', {})
        
        # Mapeia IDs antigos para novos IDs
        attr_id_map = {}
        action_id_map = {}
        
        # Importa actions primeiro
        for old_action_id, action_data in actions.items():
            new_action_id = self._get_next_action_id()
            action_id_map[old_action_id] = new_action_id
            
            from src.components.user.actions.action import Action
            new_action = Action(
                action_id=new_action_id,
                name=action_data['name'],
                tipo=action_data['type'],
                diff=action_data['diff'],
                value=action_data.get('value', 0)
            )
            self.user._actions[new_action_id] = new_action
            print(f"✓ Action imported: {action_data['name']} ({new_action_id})")
        
        # Importa attributes
        for old_attr_id, attr_data in attributes.items():
            new_attr_id = self._get_next_attr_id()
            attr_id_map[old_attr_id] = new_attr_id
            
            from src.components.user.attributes.attribute import Attribute
            new_attr = Attribute(
                attribute_id=new_attr_id,
                name=attr_data['name'],
                related_actions=None,
                children=None,
                parent=None
            )
            self.user._attributes[new_attr_id] = new_attr
            print(f"✓ Attribute imported: {attr_data['name']} ({new_attr_id})")
        
        # Reconstrói relacionamentos
        for old_attr_id, attr_data in attributes.items():
            new_attr_id = attr_id_map[old_attr_id]
            new_attr = self.user._attributes[new_attr_id]
            
            # Related actions
            for old_action_id in attr_data.get('related_actions', []):
                if old_action_id in action_id_map:
                    new_action_id = action_id_map[old_action_id]
                    new_action = self.user._actions[new_action_id]
                    new_attr.add_related_action(new_action)
            
            # Children
            for old_child_id in attr_data.get('children', []):
                if old_child_id in attr_id_map:
                    new_child_id = attr_id_map[old_child_id]
                    new_child = self.user._attributes[new_child_id]
                    new_attr.add_child(new_child)
            
            # Parent
            for old_parent_id in attr_data.get('parent', []):
                if old_parent_id in attr_id_map:
                    new_parent_id = attr_id_map[old_parent_id]
                    new_parent = self.user._attributes[new_parent_id]
                    new_attr._parent.append(new_parent)
        
        print()
        print("=" * 50)
        print("✓ Template imported successfully!")
        print("=" * 50)
        
        self.user.save_user()
        
        print()
        input("Press ENTER to continue...")
    
    def _get_next_attr_id(self):
        """Gera próximo ID de atributo"""
        next_id = self.user.next_attr_id
        return f"80{next_id}" if next_id < 10 else f"8{next_id}"
    
    def _get_next_action_id(self):
        """Gera próximo ID de ação"""
        next_id = self.user.next_action_id
        return f"50{next_id}" if next_id < 10 else f"5{next_id}"

wizard = Wizard(user)    
