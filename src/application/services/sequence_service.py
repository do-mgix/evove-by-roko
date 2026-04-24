import os
import json
from datetime import datetime

from src.infrastructure.storage import get_evove_data_dir

DATE_FMT = "%d %m %Y"

class SequenceService:
    def __init__(self):
        data_dir = get_evove_data_dir()
        self.data_path = os.path.join(data_dir, "sequences.json")
        self.sequences = self._load_data()

    def _load_data(self):
        default = {"sequences": [], "first_activity_date": None}
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data.setdefault("sequences", [])
                    data.setdefault("first_activity_date", None)
                    return data
            except (json.JSONDecodeError, IOError):
                return default
        return default

    def _save_data(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.sequences, f, indent=4)
            from src.infrastructure.backup_service import backup_json
            backup_json(self.data_path)
        except IOError as e:
            print(f"Error saving sequences: {e}")

    def record_activity(self, now=None):
        """Stamps the first-ever activity date. Subsequent calls are no-ops."""
        if self.sequences.get("first_activity_date"):
            return
        if now is None:
            now = datetime.now()
        self.sequences["first_activity_date"] = now.strftime(DATE_FMT)
        self._save_data()

    def days_since_first_activity(self, now=None):
        """Calendar days since first activity (day 1 = first activity day).
        Counts inactive days. Returns 0 if no activity yet."""
        first_str = self.sequences.get("first_activity_date")
        if not first_str:
            return 0
        try:
            first = datetime.strptime(first_str, DATE_FMT).date()
        except (ValueError, TypeError):
            return 0
        if now is None:
            now = datetime.now()
        return (now.date() - first).days + 1

    def create_sequence(self, label, start_value):
        now = datetime.now()
        date_str = now.strftime(DATE_FMT)
        new_seq = {
            "label": label,
            "start_date": date_str,
            "start_value": int(start_value),
            "current_value": int(start_value)
        }
        self.sequences["sequences"].append(new_seq)
        self._save_data()
        return f"Sequence '{label}' created starting at {start_value} on {date_str}."

    def update_sequences(self):
        """Increments each sequence by calendar days since its start_date."""
        now = datetime.now()
        updated_count = 0
        for seq in self.sequences["sequences"]:
            start_date = datetime.strptime(seq["start_date"], DATE_FMT)
            days_passed = (now - start_date).days
            new_current = seq["start_value"] + days_passed
            if new_current != seq["current_value"]:
                seq["current_value"] = new_current
                updated_count += 1

        if updated_count > 0:
            self._save_data()
        return updated_count

    def get_current_sequences_str(self):
        if not self.sequences["sequences"]:
            return "No sequences found."

        parts = []
        for i, seq in enumerate(self.sequences["sequences"]):
            parts.append(f"[{i}] {seq['label']}: {seq['current_value']}")
        return " | ".join(parts)

    def delete_sequence(self, index):
        if 0 <= index < len(self.sequences["sequences"]):
            removed = self.sequences["sequences"].pop(index)
            self._save_data()
            return f"Sequence '{removed['label']}' deleted."
        return f"Index {index} out of range."

sequence_service = SequenceService()
