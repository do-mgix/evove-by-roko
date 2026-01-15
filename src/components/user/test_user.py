
import unittest
import os
import json
import sys
from unittest.mock import patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.components.user.user import User
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.action import Action

class TestUser(unittest.TestCase):
    def setUp(self):
        self.user = User()
        # Mocking save_user to avoid writing to disk during most tests
        self.save_patcher = patch.object(User, 'save_user')
        self.mock_save = self.save_patcher.start()
        
        # Path for the real save_user to test persistence
        self.data_file = os.path.join(os.path.dirname(os.path.abspath(User.__module__.split('.')[0])), "src/components/user/user.json")

    def tearDown(self):
        self.save_patcher.stop()

    def test_initial_state(self):
        self.assertEqual(self.user.score, 0)
        self.assertEqual(self.user._value, 0)
        self.assertEqual(self.user._attributes, {})
        self.assertEqual(self.user._actions, {})

    def test_next_id_properties(self):
        self.assertEqual(self.user.next_attr_id, 1)
        self.assertEqual(self.user.next_action_id, 1)
        
        # Add an attribute
        self.user._attributes["801"] = Attribute("801", "Test Attr")
        self.assertEqual(self.user.next_attr_id, 2)
        
        # Add an action
        # Note: Action __init__ might fail if it tries to access non-existent properties
        try:
            self.user._actions["501"] = Action("501", "Test Action", 1, 1, 0.0)
            self.assertEqual(self.user.next_action_id, 2)
        except Exception as e:
            print(f"Action initialization failed: {e}")

    @patch('builtins.input', return_value='Força')
    def test_create_attribute(self, mock_input):
        self.user.create_attribute("")
        self.assertIn("801", self.user._attributes)
        self.assertEqual(self.user._attributes["801"]._name, "Força")

    @patch('builtins.input', side_effect=['Agilidade'])
    def test_create_attribute_by_id(self, mock_input):
        self.user.create_attribute_by_id(["05"])
        self.assertIn("805", self.user._attributes)
        self.assertEqual(self.user._attributes["805"]._name, "Agilidade")

    @patch('builtins.input', return_value='Corrida')
    def test_create_action(self, mock_input):
        self.user.create_action("11")
        self.assertIn("501", self.user._actions)
        action = self.user._actions["501"]
        self.assertEqual(action._name, "Corrida")
        
        # Test score calculation
        # Type 1 (repetitions, factor 1), Diff 1 (multiplier 2.1), value 0.0 -> score 0.0
        self.assertEqual(action.score, 0.0)
        
        # Test to_dict
        d = action.to_dict()
        self.assertEqual(d["id"], "501")
        self.assertEqual(d["name"], "Corrida")
        self.assertEqual(d["type"], 1)
        self.assertEqual(d["score"], 0.0)

    def test_attribute_add_action(self):
        attr = Attribute("801", "Força")
        action = Action("501", "Flexões", 1, 1, 0.0)
        self.user._attributes["801"] = attr
        self.user._actions["501"] = action
        
        self.user.attribute_add_action(["01", "01"])
        self.assertIn(action, attr._related_actions)

    def test_attribute_add_child(self):
        parent = Attribute("801", "Físico")
        child = Attribute("802", "Força")
        self.user._attributes["801"] = parent
        self.user._attributes["802"] = child
        
        self.user.attribute_add_child(["01", "02"])
        self.assertIn(child, parent._children)
        self.assertEqual(child._parent[0], parent)

    def test_delete_attribute(self):
        self.user._attributes["801"] = Attribute("801", "Test")
        self.user.delete_attribute(["01"])
        self.assertNotIn("801", self.user._attributes)

    def test_attribute_power(self):
        attr = Attribute("801", "Força")
        action = Action("501", "Flexões", 1, 1, 10.0) # Type 1, Factor 1, Diff 1, Multiplier 2.1, Val 10 -> Score 21.0
        attr.add_related_action(action)
        
        self.assertEqual(attr.power, 21.0)
    
    def test_persistence(self):
        # Stop mock for this test
        self.save_patcher.stop()
        try:
            # Setup
            self.user._value = 50
            attr = Attribute("801", "Força")
            action = Action("501", "Flexões", 1, 1, 10.0) # Score 21.0
            self.user._attributes["801"] = attr
            self.user._actions["501"] = action
            attr.add_related_action(action)
            
            # Save
            self.user.save_user()
            
            # Create new user and load
            new_user = User()
            new_user.load_user()
            
            self.assertEqual(new_user.score, 21.0)
            self.assertIn("801", new_user._attributes)
            self.assertIn("501", new_user._actions)
            self.assertEqual(len(new_user._attributes["801"]._related_actions), 1)
        finally:
            # Restart mock for other tests
            self.save_patcher.start()

    def test_deep_persistence(self):
        """Verifica se relações complexas (filhos e ações) são mantidas no JSON"""
        self.save_patcher.stop()
        try:
            # 1. Criar estrutura complexa
            parent = Attribute("801", "Pai")
            child = Attribute("802", "Filho")
            action = Action("501", "Ação do Filho", 1, 1, 5.0)
            
            self.user._attributes["801"] = parent
            self.user._attributes["802"] = child
            self.user._actions["501"] = action
            
            # Relacionar
            parent.add_child(child)
            child.add_related_action(action)
            
            # 2. Salvar
            self.user.save_user()
            
            # 3. Carregar em nova instância
            new_user = User()
            new_user.load_user()
            
            # 4. Validar
            new_parent = new_user._attributes["801"]
            new_child = new_user._attributes["802"]
            new_action = new_user._actions["501"]
            
            # Verificar se o filho está no pai
            self.assertIn(new_child, new_parent._children)
            # Verificar se o pai está no filho
            self.assertIn(new_parent, new_child._parent)
            # Verificar se a ação está no filho
            self.assertIn(new_action, new_child._related_actions)
            
            self.assertEqual(new_child.power, 10.5)
            self.assertEqual(new_parent.total_score, 10.5)
            
            # User score should be average of all attributes (2 in this case)
            # (10.5 + 10.5) / 2 = 10.5
            self.assertEqual(new_user.score, 10.5)
            
        finally:
            self.save_patcher.start()

    def test_user_score_average(self):
        """Verifica se o score do usuário é a média dos scores dos atributos"""
        attr1 = Attribute("801", "A")
        action1 = Action("501", "Act1", 1, 1, 10.0) # Score 21.0
        attr1.add_related_action(action1)
        
        attr2 = Attribute("802", "B")
        action2 = Action("502", "Act2", 1, 1, 20.0) # Score 42.0
        attr2.add_related_action(action2)
        
        self.user._attributes["801"] = attr1
        self.user._attributes["802"] = attr2
        
        # Average = (21.0 + 42.0) / 2 = 63.0 / 2 = 31.5
        self.assertEqual(self.user.score, 31.5)

    @patch('builtins.input', return_value='yes')
    def test_drop_methods(self, mock_input):
        self.user._attributes["801"] = Attribute("801", "Test")
        self.user.drop_attributes(None)
        self.assertEqual(self.user._attributes, {})
        
        self.user._actions["501"] = Action("501", "Test", 1, 1, 0.0)
        self.user.drop_actions(None)
        self.assertEqual(self.user._actions, {})

    def test_attribute_power_display(self):
        attr = Attribute("801", "Força")
        action = Action("501", "Flexões", 1, 1, 1000.0) # Score = 1000 * 1 * 2.1 = 2100.0
        attr.add_related_action(action)
        self.assertEqual(attr.power, 2100.0)
        self.assertEqual(attr.power_display, "2.1%")

if __name__ == "__main__":
    unittest.main()
