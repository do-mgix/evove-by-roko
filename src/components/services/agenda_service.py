import os
import json
from datetime import datetime, time


class AgendaService:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_path = os.path.join(base_dir, "data", "agenda.json")
        self.agenda = self._load_data()

    def _load_data(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"agenda": []}
        return {"agenda": []}

    def _save_data(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self.agenda, f, indent=4)
            from src.components.services.backup_service import backup_json
            backup_json(self.data_path)
        except IOError as exc:
            print(f"Error saving agenda: {exc}")

    def _format_time(self, value):
        if isinstance(value, datetime):
            return value.strftime("%H:%M:%S")
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, str):
            return value.strip()
        raise ValueError("Invalid time value.")

    def _format_execution_date(self, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%d %m %Y : %H:%M:%S")
        if isinstance(value, str):
            return value.strip()
        raise ValueError("Invalid execution date value.")

    def _normalize_day(self, value):
        if value is None:
            return None
        day = str(value).strip().lower()
        if day not in {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }:
            raise ValueError("Invalid day of week.")
        return day

    def _execution_keys(self):
        if not self.agenda.get("agenda"):
            return "first_date", "last_execution"
        sample = self.agenda["agenda"][0]
        if "first_date" in sample:
            first_key = "first_date"
        elif "firt_execution_date" in sample:
            first_key = "firt_execution_date"
        elif "first_execution_date" in sample:
            first_key = "first_execution_date"
        else:
            first_key = "first_date"

        if "last_execution" in sample:
            last_key = "last_execution"
        elif "last_execution_date" in sample:
            last_key = "last_execution_date"
        else:
            last_key = "last_execution"
        return first_key, last_key

    def add_item(
        self,
        label,
        item_type,
        related_action,
        schedule,
        max_value=1,
        current_value=0,
        first_date=None,
        last_execution=None,
    ):
        if not label or not str(label).strip():
            return "Label is required."

        normalized_type = str(item_type).strip().lower()
        if normalized_type == "everyday":
            normalized_type = "daily"
        item = {
            "label": str(label).strip(),
            "type": normalized_type,
            "related_action": related_action,
        }

        first_key, last_key = self._execution_keys()
        if first_date is None:
            first_date = datetime.now()
        if last_execution is None:
            last_execution = first_date
        item[first_key] = self._format_execution_date(first_date)
        item[last_key] = self._format_execution_date(last_execution)

        if normalized_type == "daily":
            if not isinstance(schedule, dict):
                return "Daily schedule must be a dict with start_time/end_time."

            day_input = schedule.get("day")
            if day_input is not None:
                day_value = self._normalize_day(day_input)
                if day_value not in {"monday", "tuesday", "wednesday", "thursday", "friday"}:
                    return "Daily items apply only to weekdays (monday-friday)."

            start_time = schedule.get("start_time") or schedule.get("start_date")
            end_time = schedule.get("end_time") or schedule.get("end_date")

            if not start_time or not end_time:
                return "Daily schedule requires start_time and end_time."

            item["start_date"] = self._format_time(start_time)
            item["end_date"] = self._format_time(end_time)
            item["max_value"] = int(max_value)
            item["current_value"] = int(current_value)
        elif normalized_type == "weekly":
            if not isinstance(schedule, (list, tuple)):
                return "Weekly schedule must be a list of day/time ranges."
            if len(schedule) > 6:
                return "Weekly schedule cannot exceed 6 occurrences."

            for idx, entry in enumerate(schedule, start=1):
                if not isinstance(entry, dict):
                    return "Weekly schedule entries must be dicts."
                day = entry.get("day")
                start_time = entry.get("start_time") or entry.get("start_date")
                end_time = entry.get("end_time") or entry.get("end_date")
                if not day or not start_time or not end_time:
                    return "Weekly schedule entries require day, start_time, and end_time."

                day_value = self._normalize_day(day)
                item[f"start_date{idx}"] = f"{day_value} {self._format_time(start_time)}"
                item[f"end_date{idx}"] = f"{day_value} {self._format_time(end_time)}"

            item["max_value"] = int(max_value)
            item["current_value"] = int(current_value)
        else:
            return "Invalid item type. Use 'daily' or 'weekly'."

        self.agenda.setdefault("agenda", []).append(item)
        self._save_data()
        return item


agenda_service = AgendaService()
