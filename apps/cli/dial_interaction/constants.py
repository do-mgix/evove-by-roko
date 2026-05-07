from src.domain.user import user
from src.domain.action import action
from src.domain.attribute import attribute
from src.domain.agenda import agenda
from src.domain.log import log
from src.domain.parameter import param
from src.domain.sequence import sequence
from src.domain.status import status
from src.domain.tag import tag

from src.domain.entities.entity_manager import EntityManager
him = EntityManager().get_entity()

OBJECTS = {
    "8": {"len": 2, "label": "attr"},
    "5": {"len": 2, "label": "action"},
    "6": {"len": 2, "label": "param"},
    "4": {"len": 2, "label": "sequence"},
    "1": {"len": 2, "label": "tag"},
    "3": {"len": 2, "label": "shop_item"},
    "7": {"len": 5, "label": "log"},
}

INTERACTIONS = {
    "2": {"len": 0, "label": "add"},   
    "1": {"len": 0, "label": "act"},     
    "0": {"len": 0, "label": "delete"},     

}

SINGLE_COMMANDS = {
    "93": {"len": 0, "func": shop.open_shop, "label": "list_shop"},
    "23": {"len": 0, "func": shop.create_shop_item, "label": "create_shop_item"},
    "25": {"len": 0, "func": action.create_action, "label": "create_action"},
    "28": {"len": 0, "func": attribute.create_attribute, "label": "create_attr"},
    "24": {"len": 0, "func": sequence.new_sequence, "label": "new_sequence"},
    "21": {"len": 0, "func": tag.create_tag, "label": "create_tag"},
    "26": {"len": 0, "func": param.create_parameter, "label": "create_param"},
    "91": {"len": 0, "func": tag.list_tags, "label": "list_tags"},
    "98": {"len": 0, "func": attribute.list_attributes, "label": "list_attr"},
    "95": {"len": 0, "func": action.list_actions, "label": "list_actions"},
    "96": {"len": 0, "func": param.list_parameters, "label": "list_params"},
    "94": {"len": 0, "func": sequence.list_sequences, "label": "list_sequences"},
    "27": {"len": 0, "func": log.add_log_entry, "label": "add_log"},
    "97": {"len": 0, "func": log.list_logs, "label": "list_logs"},
    "995": {"len": 0, "func": action.list_actions_detailed, "label": "list_actions_detailed"},
    "996": {"len": 0, "func": param.list_params_full, "label": "list_params_full"},
    "998": {"len": 0, "func": attriubute.list_attributes_detailed, "label": "list_attributes_detailed"},
    "991": {"len": 0, "func": tag.list_tags_detailed, "label": "list_tags_detailed"},
    "994": {"len": 0, "func": sequence.list_sequences_detailed, "label": "list_sequences_detailed"},
    "999": {"len": 0, "func": composer.show_object_tree, "label": "object_tree"},
    "997": {"len": 0, "func": log.list_days, "label": "list_days"},
    "077": {"len": 0, "func": log.drop_last_log_buffer, "label": "drop_log"},
    "17": {"len": 0, "func": log.up_current_day, "label": "up_day"},
    "007": {"len": 0, "func": log.drop_last_day, "label": "drop_day"},
    "005": {"len": 0, "func": action.drop_actions, "label": "drop_actions"},
    "008": {"len": 0, "func": attribute.drop_attributes, "label": "drop_attr"},
    "006": {"len": 0, "func": param.drop_parameters, "label": "drop_params"},
}

COMMANDS = {
    "attr add action": {"func": composer.attribute_add_action},
    "action act": {"func": action.act},
    "delete attr": {"func": attribute.delete_attribute},
    "delete action": {"func": action.delete_action},
    "delete param": {"func": param.delete_parameter},
    "delete tag": {"func": tag.delete_tag},
    "delete sequence": {"func": sequence.delete_sequence},
    "sequence add action": {"func": sequence.sequence_add_action},
    "add add attr": {"func": attribute.create_attribute_by_id},
    "attr add attr": {"func": attribute.attribute_add_child},
    "param act act": {"func": param.init_parameter},
    "action add tag": {"func": action.action_add_tag},
    "param add tag": {"func": action.parameter_add_tag},
    "shop_item add action": {"func": composer.shop_item_add_action},
    "shop_item act": {"func": shop.buy_shop_item},
    "action delete": {"func": action.edit_action},
    "attr delete": {"func": attribute.edit_attribute},
    "param delete": {"func": param.edit_parameter},
    "tag delete": {"func": tag.edit_tag},
    "log act": {"func": log.up_log_day},
    "delete log": {"func": log.delete_log},
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
