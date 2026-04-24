import os
import json
from datetime import datetime, time as dtime

from src.infrastructure.storage import get_evove_data_dir

# Window: if inactivity covers this hour boundary crossing to the next day,
# the gap is treated as sleep.
SLEEP_START_HOUR = 22

class SleepService:
    def __init__(self):
        data_dir = get_evove_data_dir()
        self.data_path = os.path.join(data_dir, "sleep_data.json")
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data.setdefault("logs", [])
                    data.setdefault("last_activity", None)
                    return data
            except (json.JSONDecodeError, IOError):
                return {"logs": [], "last_activity": None}
        return {"logs": [], "last_activity": None}

    def _save_data(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
            from src.infrastructure.backup_service import backup_json
            backup_json(self.data_path)
        except IOError as e:
            print(f"Error saving sleep data: {e}")

    def record_activity(self, now=None):
        """Registers a user activity. If the inactivity gap since the last
        activity crosses 22:00 into the next day, logs a sleep entry.
        Returns (sleep_detected, duration_str, sleep_start, wake_time).
        """
        if now is None:
            now = datetime.now()

        last_activity = None
        last_str = self.data.get("last_activity")
        if last_str:
            try:
                last_activity = datetime.fromisoformat(last_str)
            except (ValueError, TypeError):
                last_activity = None

        sleep_detected = False
        duration_str = None
        sleep_start = None

        if last_activity:
            days_gap = (now.date() - last_activity.date()).days
            # Only consider sleep when the wake-up log lands on the immediate
            # next day. A longer gap likely means a routine hiccup and is
            # ignored (buffer discarded).
            if days_gap == 1:
                threshold = datetime.combine(last_activity.date(), dtime(SLEEP_START_HOUR, 0))
                # Sleep starts at the later of: last activity or 22:00 of that day.
                sleep_start = last_activity if last_activity >= threshold else threshold
                if sleep_start < now:
                    diff = now - sleep_start
                    hours, remainder = divmod(diff.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    duration_str = f"{int(hours)}h {int(minutes)}m"
                    entry = {
                        "type": "sleep",
                        "sleep_start": sleep_start.isoformat(),
                        "wake": now.isoformat(),
                        "date": now.strftime("%d %m %Y"),
                        "duration": duration_str,
                    }
                    self.data["logs"].append(entry)
                    sleep_detected = True

        self.data["last_activity"] = now.isoformat()
        self._save_data()
        return sleep_detected, duration_str, sleep_start, now

    def get_last_sleep(self):
        """Returns the most recent completed sleep as a normalized dict
        with keys: sleep_start (iso), wake (iso), duration, date. Returns
        None if no completed sleep exists. Handles both the new single-entry
        format and the legacy sleep/wake pair format."""
        logs = self.data.get("logs", [])
        for i in range(len(logs) - 1, -1, -1):
            entry = logs[i]
            etype = entry.get("type")
            # New format: single entry with sleep_start/wake/duration
            if etype == "sleep" and entry.get("wake") and entry.get("duration"):
                return {
                    "sleep_start": entry.get("sleep_start"),
                    "wake": entry.get("wake"),
                    "duration": entry.get("duration"),
                    "date": entry.get("date"),
                }
            # Legacy format: find last wake, pair with preceding sleep
            if etype == "wake":
                sleep_start = None
                for j in range(i - 1, -1, -1):
                    if logs[j].get("type") == "sleep":
                        sleep_start = logs[j].get("timestamp")
                        break
                return {
                    "sleep_start": sleep_start,
                    "wake": entry.get("timestamp"),
                    "duration": entry.get("duration", "?"),
                    "date": entry.get("date"),
                }
        return None

sleep_service = SleepService()
