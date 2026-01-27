import os
import sys

# Standard shop items
SHOP_ITEMS = {
    "1": {"name": "Watch a Movie", "cost": 20},
    "2": {"name": "Play Video Games (1h)", "cost": 15},
    "3": {"name": "Social Media (30m)", "cost": 10},
    "4": {"name": "Read Manga/Book", "cost": 5},
    "5": {"name": "Snack/Treat", "cost": 15},
}

class ShopService:
    def __init__(self, user):
        self.user = user

    def show_items(self):
        from src.components.services.UI.interface import ui
        tokens = self.user.metadata.get("tokens", 0)
        max_t = self.user.metadata.get("max_tokens", 100)
        
        items = [f"({item_id}) - {info['name']} [{info['cost']}T]" for item_id, info in SHOP_ITEMS.items()]
        
        # Balance is at the top title now
        ui.show_list(items, f"EVOVE SHOP [{tokens}/{max_t}T]")

    def buy_item(self, item_id):
        if item_id not in SHOP_ITEMS:
            self.user.add_message(f"Item {item_id} not found.")
            return False

        item = SHOP_ITEMS[item_id]
        if self.user.spend_tokens(item['cost']):
            new_tokens = self.user.metadata.get("tokens", 0)
            self.user.add_message(f"Purchased: {item['name']}! Balance: {new_tokens}T")
            
            # Add to journal as a manual log
            from src.components.services.journal_service import journal_service
            journal_service.add_log(f"Entertainment: {item['name']} (-{item['cost']} tokens)")
            return True
        return False
