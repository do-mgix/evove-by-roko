import json
import os
from src.components.data.constants import user


class FountainService:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_path = os.path.join(base_dir, "data", "fountain.json")
        self.total_offer = 0
        self._load()

    def _load(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.total_offer = int(data.get("total_offer", 0))
            except Exception:
                self.total_offer = 0

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump({"total_offer": self.total_offer}, f, indent=4)
        except Exception:
            pass

    def offer(self, value):
        value = int(value)
        if value <= 0:
            return 0

        if not user._attributes:
            current = user.metadata.get("score", 0) or 0
            spend = min(current, value)
            user.metadata["score"] = current - spend
            user.save_user()
        else:
            spend = value

        self.total_offer += spend
        self._save()
        return spend


fountain_service = FountainService()
