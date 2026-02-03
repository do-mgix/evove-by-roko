import os
import json
from datetime import datetime

class SleepService:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_path = os.path.join(base_dir, "data", "sleep_data.json")
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"logs": []}
        return {"logs": []}

    def _save_data(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
        except IOError as e:
            print(f"Error saving sleep data: {e}")

    def log_sleep(self):
        now = datetime.now()
        entry = {
            "type": "sleep",
            "timestamp": now.isoformat(),
            "date": now.strftime("%d %m %Y")
        }
        self.data["logs"].append(entry)
        self._save_data()
        return now

    def log_wake(self):
        now = datetime.now()
        
        # Find last sleep entry to calculate diff
        last_sleep = None
        for entry in reversed(self.data["logs"]):
            if entry["type"] == "sleep":
                last_sleep = entry
                break
        
        duration_str = "Unknown"
        if last_sleep:
            sleep_time = datetime.fromisoformat(last_sleep["timestamp"])
            diff = now - sleep_time
            hours, remainder = divmod(diff.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{int(hours)}h {int(minutes)}m"

        entry = {
            "type": "wake",
            "timestamp": now.isoformat(),
            "date": now.strftime("%d %m %Y"),
            "duration": duration_str
        }
        self.data["logs"].append(entry)
        self._save_data()
        return now, duration_str

sleep_service = SleepService()
