import json
import os
from pathlib import Path

from src.components.user.user import user 


class Wizard:
    """Wizard para configuração e setup do sistema - templates, configs, etc."""
    
    def __init__(self, user_instance):
        self.user = user_instance
        self.packages_dir = Path(__file__).parent.parent.parent.parent / "data" / "packages"
        self.available_templates = self._load_available_templates()
        
    def add_message(self, msg):
        """Encaminha mensagem para o buffer do usuário"""
        self.user.add_message(msg)
        
    def start(self):
        """Inicia o menu principal do wizard"""
        from src.components.services.UI.interface import ui
        while True:
            # Check for "new!" status
            is_new = not self.user.metadata.get("starter_packs_seen", False)
            starter_label = f"Starter Packs {'(new!)' if is_new else ''}"
            
            options = {
                "1": starter_label,
                "0": "Back"
            }
            
            choice = ui.show_menu("WIZARD", options)
            
            if choice == "0":
                return
            elif choice == "1":
                # Mark as seen
                if is_new:
                    self.user.metadata["starter_packs_seen"] = True
                    self.user.save_user()
                self.attribute_templates()
            
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
        from src.components.services.UI.interface import ui
        while True:
            if not self.available_templates:
                ui.show_list(["No templates found in data/packages/"], "ATTRIBUTE TEMPLATES")
                return
                
            options = {}
            template_list = list(self.available_templates.keys())
            
            for idx, template_name in enumerate(template_list, 1):
                template_data = self.available_templates[template_name]
                is_owned = self._is_template_owned(template_data)
                status = " [OWNED]" if is_owned else ""
                options[str(idx)] = f"{template_data.get('name', template_name)}{status}"
            
            options["0"] = "Back"
            
            choice = ui.show_menu("STARTER PACKS", options)
            
            if choice == "0":
                return
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(template_list):
                    selected_template = template_list[choice_num - 1]
                    self._display_template(selected_template)
                else:
                    self.add_message("Invalid option.")
            except ValueError:
                self.add_message("Please enter a number.")

    def _is_template_owned(self, template_data):
        """Checks if the user already has the root attributes of this template"""
        from src.components.services.UI.interface import ui
        root_names = [attr['name'] for attr in template_data.get('attributes', {}).values() 
                     if not attr.get('parent') or len(attr.get('parent', [])) == 0]
        
        user_attr_names = [attr._name for attr in self.user._attributes.values()]
        
        return all(name in user_attr_names for name in root_names)

    def _load_available_templates(self):
        """Carrega todos os templates disponíveis da pasta packages"""
        from src.components.services.UI.interface import ui
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
                self.add_message(f"Error loading template {file}: {e}")
    
        return templates

    def _display_template(self, template_name):
        """Mostra a árvore de atributos do template"""
        from src.components.services.UI.interface import ui
        template = self.available_templates[template_name]
        
        # Build tree for UI
        attributes = template.get('attributes', {})
        actions = template.get('actions', {})
        
        root_attrs = [attr for attr in attributes.values() 
                     if not attr.get('parent') or len(attr.get('parent', [])) == 0]
        
        tree_nodes = []
        for root in root_attrs:
            tree_nodes.append(self._build_tree_data(root, attributes, actions))
            
        # Simplified display using show_tree but customized
        ui.clear_screen()
        print(f"{ui.CYAN}{ui.BOLD}        {template.get('name', template_name).upper()}{ui.CLR}\n")
        
        ui.print_tree(tree_nodes)
        
        print(f"\n{ui.WHITE}Total Attributes: {len(attributes)}")
        print(f"Total Actions: {len(actions)}{ui.CLR}")
        
        is_owned = self._is_template_owned(template)
        if is_owned:
            print(f"\n{ui.GREEN}[ ALREADY OWNED ]{ui.CLR}")
            print(f"{ui.WHITE}0 - Back{ui.CLR}")
            choice = ui.show_menu("", {}) # Just to wait for key or input
            return

        options = {
            "1": "Accept and Import",
            "0": "Cancel"
        }
        
        choice = ui.show_menu("IMPORT PACK?", options)
        
        if choice == "1":
            self._import_template(template)

    def _build_tree_data(self, attr, all_attrs, all_actions):
        """Helper to build recursive structure for UI show_tree"""
        label = f"• {attr['name']}"
        children = []
        
        # Add actions first as special pseudo-children
        for action_id in attr.get('related_actions', []):
            action = all_actions.get(action_id)
            if action:
                action_type = self._get_action_type_label(action['type'])
                diff_stars = "★" * action['diff']
                children.append((f"⭐ {action['name']} ({action_type}, {diff_stars})", []))
        
        # Add real child attributes
        for child_id in attr.get('children', []):
            child = all_attrs.get(child_id)
            if child:
                children.append(self._build_tree_data(child, all_attrs, all_actions))
                
        return (label, children)
    
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
        from src.components.services.UI.interface import ui
        ui.clear_screen()
        self.add_message(f"Importing {template.get('name')}...")
        
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
            self.add_message(f"✓ Action imported: {action_data['name']} ({new_action_id})")
        
        # Importa attributes
        for old_attr_id, attr_data in attributes.items():
            new_attr_id = self._get_next_attr_id()
            attr_id_map[old_attr_id] = new_attr_id
            
            from src.components.user.attributes.attribute import Attribute
            new_attr = Attribute(
                new_attr_id,
                attr_data['name'],
                None,
                None,
                None
            )
            self.user._attributes[new_attr_id] = new_attr
            self.add_message(f"✓ Attribute imported: {attr_data['name']} ({new_attr_id})")
        
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
        
        self.add_message("")
        self.add_message("=" * 50)
        self.add_message(f"✓ Template {template.get('name')} imported successfully!")
        self.add_message("=" * 50)
        
        self.user.save_user()
        
        self.add_message("")
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
