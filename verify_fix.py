import sys
import os

sys.path.append(os.getcwd())

from src.components.user.user import User
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.action import Action

def verify_fix():
    print("--- Starting Verification ---")
    u = User()
    
    # 1. Clear existing data
    u._attributes = {}
    u._actions = {}
    u.save_user()
    
    # 2. Create an action and an attribute
    print("Step 2: Creating objects...")
    a1 = Action("501", "Test Action", 1, 1, 10.0)
    attr1 = Attribute("801", "Test Attribute")
    
    u._actions[a1.id] = a1
    u._attributes[attr1.attr_id] = attr1
    
    # 3. Link them
    print(f"Step 3: Linking {a1.name} to {attr1.attr_name}...")
    attr1.AddRelatedAction(a1)
    
    # Verify score before save
    print(f"Score before save: {attr1.total_score}")
    assert attr1.total_score > 0, "Score should be > 0 before save"
    
    # 4. Save
    print("Step 4: Saving...")
    u.save_user()
    
    # 5. Reload in a new instance
    print("Step 5: Reloading...")
    u2 = User()
    u2.load_user()
    
    # 6. Check results
    print("Step 6: Verifying...")
    reloaded_attr = u2.attributes.get("801")
    if not reloaded_attr:
        print("FAIL: Attribute 801 not found after reload")
        return
    
    print(f"Reloaded attribute: {reloaded_attr.attr_name}")
    print(f"Related actions count: {len(reloaded_attr.related_actions)}")
    print(f"Total score: {reloaded_attr.total_score}")
    
    if len(reloaded_attr.related_actions) == 1 and reloaded_attr.total_score > 0:
        print("\n[ SUCCESS ] Data persisted correctly!")
    else:
        print("\n[ FAILURE ] Data lost after reload.")
        if len(reloaded_attr.related_actions) == 0:
            print("Reason: related_actions list is empty.")
        elif reloaded_attr.total_score == 0:
            print("Reason: total_score is 0 (check object resolution).")

if __name__ == "__main__":
    verify_fix()
