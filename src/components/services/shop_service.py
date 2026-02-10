import os
import sys

# Standard shop items
SHOP_ITEMS = {
    "1": {"name": "Movie", "cost": 10},
    "2": {"name": "Video Games", "cost": 30},
    "3": {"name": "Social Media", "cost": 20},
    "4": {"name": "Manga/Book", "cost": 5},
    "5": {"name": "Music", "cost": 5},
}

class ShopService:
    def __init__(self, user):
        self.user = user

    def show_items(self):
        from src.components.services.UI.interface import ui
        tokens = self.user.metadata.get("tokens", 0)
        max_t = self.user.metadata.get("max_tokens", 50)
        
        items = []
        for item_id, info in SHOP_ITEMS.items():
            purchased = False
            if hasattr(self.user, "is_shop_item_purchased"):
                purchased = self.user.is_shop_item_purchased(item_id)
            star = " (*)" if purchased else ""
            items.append(f"({item_id}) - {info['name']}{star} [{info['cost']}T]")
        
        # Balance is at the top title now
        ui.show_list(items, f"EVOVE SHOP [{tokens}/{max_t}T]")

    def buy_item(self, item_id):
        if isinstance(item_id, str):
            item_id = item_id.lstrip("0") or "0"
        if item_id not in SHOP_ITEMS:
            self.user.add_message(f"Item {item_id} not found.")
            return False

        item = SHOP_ITEMS[item_id]
        if self.user.spend_tokens(item['cost']):
            new_tokens = self.user.metadata.get("tokens", 0)
            self.user.add_message(f"Purchased: {item['name']}! Balance: {new_tokens}T")
            
            # Log immediately as TO PROCESS
            # Format: "qtd x ITEM" (We log 1 unit per purchase call usually, aggregation happens later)
            from src.components.services.journal_service import journal_service
            journal_service.add_log(f"1 x {item['name'].upper()}", auto_confirm=True, custom_status="[TO PROCESS]")
            
            return True
        return False
