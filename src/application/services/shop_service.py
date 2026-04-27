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


def _normalize_item_id(item_id):
    if isinstance(item_id, str):
        return item_id.lstrip("0") or "0"
    return str(item_id).lstrip("0") or "0"

class ShopService:
    def __init__(self, user):
        self.user = user

    @staticmethod
    def get_items_for_user(user):
        items = {
            _normalize_item_id(item_id): {
                "name": info["name"],
                "cost": int(info["cost"]),
            }
            for item_id, info in SHOP_ITEMS.items()
        }
        custom_items = getattr(user, "_shop_items", {}) or {}
        for item_id, info in custom_items.items():
            norm_id = _normalize_item_id(item_id)
            name = str(info.get("name", "")).strip()
            if not name:
                continue
            try:
                cost = int(info.get("cost", 0))
            except Exception:
                continue
            if cost < 0:
                continue
            items[norm_id] = {"name": name, "cost": cost}
        return dict(sorted(items.items(), key=lambda pair: int(pair[0])))

    def get_items(self):
        return self.get_items_for_user(self.user)

    def get_item(self, item_id):
        return self.get_items().get(_normalize_item_id(item_id))

    def show_items(self):
        from src.interfaces.cli.ui.interface import ui
        tokens = self.user.metadata.get("tokens", 0)
        max_t = self.user.metadata.get("max_tokens", 50)
        shop_items = self.get_items()

        items = []
        for item_id, info in shop_items.items():
            purchased = False
            if hasattr(self.user, "is_shop_item_purchased"):
                purchased = self.user.is_shop_item_purchased(item_id)
            star = " (*)" if purchased else ""
            items.append(f"({item_id}) - {info['name']}{star} [{info['cost']}T]")
        
        # Balance is at the top title now
        ui.show_list(items, f"EVOVE SHOP [{tokens}/{max_t}T]")

    def buy_item(self, item_id):
        item_id = _normalize_item_id(item_id)
        item = self.get_item(item_id)
        if not item:
            self.user.add_message(f"Item {item_id} not found.")
            return False

        if self.user.spend_tokens(item['cost']):
            new_tokens = self.user.metadata.get("tokens", 0)
            self.user.add_message(f"Purchased: {item['name']}! Balance: {new_tokens}T")
            
            # Log immediately as TO PROCESS
            # Format: "qtd x ITEM" (We log 1 unit per purchase call usually, aggregation happens later)
            from src.application.services.journal_service import journal_service
            journal_service.add_log(f"1 x {item['name'].upper()}", auto_confirm=True, custom_status="[CLOUD/TO PROCESS]")
            
            return True
        return False
