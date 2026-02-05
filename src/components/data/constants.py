from src.components.user.user import user


from src.components.entitys.entity_manager import EntityManager
him = EntityManager().get_entity()

OBJECTS = {
    "8": {"len": 2, "label": "attr"},    
    "5": {"len": 2, "label": "action"}, 
    "3": {"len": 1, "label": "shop_item"}, 
    "7": {"len": 0, "label": "log"},
    "47": {"len": 0, "label": "sequence"},
}

INTERACTIONS = {
    "2": {"len": 0, "label": "add"},   
    "1": {"len": 0, "label": "act"},     
    "0": {"len": 0, "label": "delete"},     
    "6": {"len": 0, "label": "configure"},     

}

SINGLE_COMMANDS = {
    "1":  {"len": 0, "func": him.cutucar, "label": ""},
    "93": {"len": 0, "func": user.open_shop, "label": "list_shop"},
    "25": {"len": 2, "func": user.create_action, "label": "create_action"}, 
    "28": {"len": 0, "func": user.create_attribute, "label": "create_attr"}, 
    "4":  {"len": 0, "func": lambda: __import__("src.components.services.wizard.wizard", fromlist=["wizard"]).wizard.start(), "label": "super_create_attr"},
    "6":  {"len": 0, "func": lambda: __import__("src.components.services.settings_service", fromlist=["settings_service"]).settings_service.start(), "label": "configure"},
    "98": {"len": 0, "func": user.list_attributes, "label": "list_attr"}, 
    "95": {"len": 0, "func": user.list_actions, "label": "list_actions"}, 
    "27": {"len": 0, "func": user.add_log_entry, "label": "add_log"},
    "97": {"len": 0, "func": user.list_logs, "label": "list_logs"},
    "997": {"len": 0, "func": user.list_days, "label": "list_days"},
    "07": {"len": 0, "func": user.drop_last_log_buffer, "label": "drop_log"},
    "007": {"len": 0, "func": user.drop_last_day, "label": "drop_day"},
    "71": {"len": 0, "func": user.wake, "label": "wake"},
    "70": {"len": 0, "func": user.sleep, "label": "sleep"},
    "770": {"len": 0, "func": user.nap, "label": "nap"},
    "247": {"len": 0, "func": user.new_sequence, "label": "new_sequence"},
    "947": {"len": 0, "func": user.list_sequences, "label": "list_sequences"},
    "047": {"len": 0, "func": user.delete_sequence, "label": "drop_sequence"},
    "005": {"len": 0, "func": user.drop_actions, "label": "drop_actions"}, 
    "008": {"len": 0, "func": user.drop_attributes, "label": "drop_attr"}, 
}

COMMANDS = {        
    "attr add action": {"func": user.attribute_add_action},
    "action act": {"func": user.act},
    "delete attr": {"func": user.delete_attribute},
    "delete action": {"func": user.delete_action},
    "add add attr": {"func": user.create_attribute_by_id},
    "attr add attr": {"func": user.attribute_add_child},
    "shop_item act": {"func": user.buy_shop_item},

}

MODES = {
    "PROGRESSIVE": "progressive",
    "SEMI_PROGRESSIVE": "semi-progressive",
    "FREE": "free"
}

# Package prices (example placeholders)
PACKAGE_PRICES = {
    "basics": 0,
    "health": 500,
    "productivity": 1000,
    "bits_and_bytes": 5000
}
