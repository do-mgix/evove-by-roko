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
        data = default
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data.setdefault("sequences", [])
                    data.setdefault("first_activity_date", None)
            except (json.JSONDecodeError, IOError):
                data = default
        if self._backfill_ids(data["sequences"]):
            self._write(data)
        return data

    @staticmethod
    def _backfill_ids(sequences):
        changed = False
        taken = {str(s.get("id")) for s in sequences if s.get("id")}
        n = 1
        for s in sequences:
            if s.get("id"):
                continue
            while f"{n:02d}" in taken:
                n += 1
            s["id"] = f"{n:02d}"
            taken.add(s["id"])
            n += 1
            changed = True
        return changed

    def _next_id(self):
        taken = {str(s.get("id")) for s in self.sequences["sequences"] if s.get("id")}
        n = 1
        while f"{n:02d}" in taken:
            n += 1
        return f"{n:02d}"

    def _write(self, data):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            from src.infrastructure.backup_service import backup_json
            backup_json(self.data_path)
        except IOError as e:
            print(f"Error saving sequences: {e}")

    def _save_data(self):
        self._write(self.sequences)

    def _find_index(self, seq_id):
        for i, s in enumerate(self.sequences["sequences"]):
            if str(s.get("id")) == str(seq_id):
                return i
        return -1

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
            "id": self._next_id(),
            "label": label,
            "start_date": date_str,
            "start_value": int(start_value),
            "current_value": int(start_value),
            "actions": [],
        }
        self.sequences["sequences"].append(new_seq)
        self._save_data()
        return f"Sequence '{label}' [{new_seq['id']}] created starting at {start_value} on {date_str}."

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
        seqs = self.sequences.get("sequences", [])
        if not seqs:
            return "No sequences found."
        parts = []
        for seq in seqs:
            parts.append(f"[{seq.get('id', '??')}] {seq['label']}: {seq['current_value']}")
        return " | ".join(parts)

    def get_sequences_rows(self, include_actions=False):
        """Returns a list of row dicts suitable for table display."""
        rows = []
        for seq in self.sequences.get("sequences", []):
            row = {
                "id": seq.get("id", "??"),
                "label": seq.get("label", "?"),
                "value": seq.get("current_value", 0),
            }
            if include_actions:
                actions = seq.get("actions", []) or []
                row["actions"] = ", ".join(actions) if actions else "—"
            rows.append(row)
        return rows

    def delete_sequence(self, seq_id):
        idx = self._find_index(seq_id)
        if idx == -1:
            return f"Sequence id {seq_id} not found."
        removed = self.sequences["sequences"].pop(idx)
        self._save_data()
        return f"Sequence '{removed['label']}' [{removed.get('id')}] deleted."

    def add_action_to_sequence(self, seq_id, action_id):
        idx = self._find_index(seq_id)
        if idx == -1:
            return f"Sequence id {seq_id} not found."
        seq = self.sequences["sequences"][idx]
        actions = seq.setdefault("actions", [])
        if action_id in actions:
            return f"Action {action_id} already linked to '{seq['label']}'."
        actions.append(action_id)
        self._save_data()
        return f"Action {action_id} linked to sequence '{seq['label']}' [{seq_id}]."

sequence_service = SequenceService()
