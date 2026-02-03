import os
import json
from datetime import datetime

class SequenceService:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_path = os.path.join(base_dir, "data", "sequences.json")
        self.sequences = self._load_data()

    def _load_data(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"sequences": []}
        return {"sequences": []}

    def _save_data(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.sequences, f, indent=4)
        except IOError as e:
            print(f"Error saving sequences: {e}")

    def create_sequence(self, label, start_value):
        now = datetime.now()
        date_str = now.strftime("%d %m %Y")
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
        """Called during sleep to increment day counts based on date difference."""
        now = datetime.now()
        updated_count = 0
        for seq in self.sequences["sequences"]:
            start_date = datetime.strptime(seq["start_date"], "%d %m %Y")
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
