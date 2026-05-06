import os
import json
import subprocess
import re
from datetime import datetime, timedelta
from src.application.services.sequence_service import sequence_service
from src.infrastructure.storage import get_current_username, get_evove_data_dir

class JournalService:
    def __init__(self):
        self.log_id_prefix = 73
        self.log_id_width = 4
        self.logs_data_path = None
        self.journal_dir = os.path.expanduser("~/journal")
        self.journal_file = None
        self.logs = []
        self.refresh_paths()
        self._load_logs_data()

    def refresh_paths(self):
        data_dir = get_evove_data_dir()
        self.logs_data_path = os.path.join(data_dir, "logs.json")
        self.journal_file = os.path.join(self.journal_dir, f"evove26-{get_current_username()}")

    def _next_log_id(self):
        """Returns the next sequential log id (e.g. 470001)."""
        max_id = 0
        for log in self.logs:
            log_id = log.get("id")
            try:
                val = int(log_id)
            except (TypeError, ValueError):
                continue
            if val > max_id:
                max_id = val
        if max_id <= 0:
            return int(f"{self.log_id_prefix}{1:0{self.log_id_width}d}")
        return max_id + 1

    def _day_number_for(self, dt):
        """Maps a datetime/date to the global DAY index (sequence_service.days_since_first_activity)."""
        from src.application.services.sequence_service import sequence_service
        if hasattr(dt, "date"):
            ref = datetime.combine(dt.date(), datetime.min.time())
        else:
            ref = datetime.combine(dt, datetime.min.time())
        return sequence_service.days_since_first_activity(now=ref)

    def _coord_for_log(self, log):
        """Returns (day, order) for a log, computing from coord field or timestamp."""
        coord = log.get("coord")
        if isinstance(coord, (list, tuple)) and len(coord) >= 2:
            try:
                return int(coord[0]), int(coord[1])
            except (TypeError, ValueError):
                pass
        try:
            dt = datetime.strptime(str(log.get("timestamp", "")), "%d %m %Y : %H:%M:%S")
            return self._day_number_for(dt), 0
        except Exception:
            return 0, 0

    def _next_order_for_day(self, day_num):
        max_order = 0
        for log in self.logs:
            d, o = self._coord_for_log(log)
            if d == day_num and o > max_order:
                max_order = o
        return max_order + 1

    def _backfill_coords(self):
        """Assigns coord to legacy logs lacking it. Mutates self.logs but does not save."""
        from collections import defaultdict
        changed = False
        # Group logs missing coord by day, sorted by timestamp
        missing_by_day = defaultdict(list)
        used_orders_by_day = defaultdict(set)
        for log in self.logs:
            coord = log.get("coord")
            if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                try:
                    d = int(coord[0]); o = int(coord[1])
                    used_orders_by_day[d].add(o)
                    continue
                except (TypeError, ValueError):
                    pass
            try:
                dt = datetime.strptime(str(log.get("timestamp", "")), "%d %m %Y : %H:%M:%S")
            except Exception:
                continue
            d = self._day_number_for(dt)
            missing_by_day[d].append((dt, log))

        for d, items in missing_by_day.items():
            items.sort(key=lambda x: x[0])
            used = used_orders_by_day[d]
            next_o = 1
            for _dt, log in items:
                while next_o in used:
                    next_o += 1
                log["coord"] = [d, next_o]
                used.add(next_o)
                next_o += 1
                changed = True
        return changed

    def _load_logs_data(self):
        """Loads structured log data."""
        self.refresh_paths()
        if os.path.exists(self.logs_data_path):
            try:
                with open(self.logs_data_path, 'r', encoding='utf-8') as f:
                    self.logs = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.logs = []
        else:
            self.logs = []

        # Migrate legacy statuses
        normalized = False
        for log in self.logs:
            status = log.get("status")
            if not isinstance(status, str):
                continue
            if status == "[IN WAIT]":
                log["status"] = "[CLOUD]"
                normalized = True
            elif "TO PROCESS" in status and status != "[CLOUD/TO PROCESS]":
                log["status"] = "[PROCESSED]"
                normalized = True
        if self._backfill_coords():
            normalized = True
        if normalized:
            self._save_logs_data()

    def _save_logs_data(self):
        """Saves structured log data."""
        try:
            os.makedirs(os.path.dirname(self.logs_data_path), exist_ok=True)
            with open(self.logs_data_path, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, indent=4)
            from src.infrastructure.backup_service import backup_json
            backup_json(self.logs_data_path)
        except IOError as e:
            print(f"Error saving logs data: {e}")

    def _get_last_file_date_header(self):
        """Reads the journal file backwards to find the last date header."""
        self.refresh_paths()
        if not os.path.exists(self.journal_file):
            return None
        
        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    line = line.strip()
                    # Check for date format "[dd/mm/yyyy]"
                    # Basic check: starts with [ and ends with ] and has 10 chars inside
                    if line.startswith("[") and line.endswith("]") and len(line) == 12:
                         try:
                             datetime.strptime(line, "[%d/%m/%Y]")
                             return line
                         except ValueError:
                             continue
        except Exception:
            return None
        return None

    def _is_date_header_line(self, line):
        line = line.strip()
        if line.startswith("[") and line.endswith("]") and len(line) == 12:
            try:
                datetime.strptime(line, "[%d/%m/%Y]")
                return True
            except ValueError:
                return False
        return False

    def _find_log_by_id(self, log_id):
        for log in self.logs:
            try:
                if int(log.get("id")) == int(log_id):
                    return log
            except (TypeError, ValueError):
                continue
        return None

    def _normalize_text_key(self, text):
        return " ".join(str(text or "").strip().lower().split())

    def _parse_action_log_content(self, content):
        raw = str(content or "").strip()
        if not raw:
            return None

        value_match = re.match(r"^(\d+)\s*[xX]\s*(.+)$", raw)
        if value_match:
            return {
                "kind": "value",
                "value": int(value_match.group(1)),
                "action": value_match.group(2).strip(),
            }

        legacy_value_match = re.match(r"^(\d+)\s+(.+)$", raw)
        if legacy_value_match:
            return {
                "kind": "value",
                "value": int(legacy_value_match.group(1)),
                "action": legacy_value_match.group(2).strip(),
            }

        note_match = re.match(r"^(.+?)\s*:\s*(.+)$", raw)
        if note_match:
            return {
                "kind": "note",
                "action": note_match.group(1).strip(),
                "note": note_match.group(2).strip(),
            }

        return {"kind": "raw", "content": raw}

    def resolve_note_action(self, note_text):
        target = self._normalize_text_key(note_text)
        if not target:
            return None

        self._load_logs_data()
        for entry in reversed(self.logs):
            if not isinstance(entry, dict):
                continue
            parsed = self._parse_action_log_content(entry.get("content"))
            if not parsed or parsed.get("kind") != "note":
                continue
            if self._normalize_text_key(parsed.get("note")) == target:
                return parsed.get("action")
        return None

    def _insert_under_last_log(self, lines, header_idx):
        header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
        next_header_idx = next((i for i in header_indices if i > header_idx), len(lines))
        insert_idx = next_header_idx
        for i in range(header_idx + 1, next_header_idx):
            if lines[i].strip() == "":
                insert_idx = i
                break
        return insert_idx

    def add_log(self, text, manual_date=None, auto_confirm=False, custom_status=None, is_activity=True, xp=0, logged_for_date=None):
        """Adds a log entry to both evove26 and logs.json."""
        if not text.strip():
            return False

        now = datetime.now()

        # Date Logic
        target_date = now

        if manual_date:
             try:
                target_date = now.replace(day=int(manual_date))
             except ValueError:
                target_date = now
        elif not auto_confirm and self.logs:
             # Logic matching (simplified)
             pass

        # logged_for_date overrides target_date for journaling/coord, but timestamp stays "now"
        attribution_date = logged_for_date if logged_for_date else target_date

        if is_activity:
            self._aggregate_previous_days(attribution_date)
            sequence_service.record_activity(attribution_date)
            sequence_service.update_sequences()

        current_date_header = attribution_date.strftime("[%d/%m/%Y]")
        timestamp_str = now.strftime("%d %m %Y : %H:%M:%S")

        status = custom_status if custom_status else "[CLOUD]"

        # 1. Write to evove26 — append if attribution day == latest header, else insert under existing header
        try:
            os.makedirs(self.journal_dir, exist_ok=True)
            inserted = False
            if os.path.exists(self.journal_file):
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
                hidx = next((i for i in header_indices if lines[i].strip() == current_date_header), None)
                last_header = self._get_last_file_date_header()
                if hidx is not None and current_date_header != last_header:
                    next_hidx = next((i for i in header_indices if i > hidx), len(lines))
                    insert_idx = next_hidx
                    while insert_idx > hidx + 1 and lines[insert_idx - 1].strip() == "":
                        insert_idx -= 1
                    lines.insert(insert_idx, f"{text.strip()}\n")
                    with open(self.journal_file, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    inserted = True
            if not inserted:
                last_header = self._get_last_file_date_header()
                with open(self.journal_file, "a", encoding="utf-8") as f:
                    if last_header != current_date_header:
                        f.write(f"\n{current_date_header}\n")
                    f.write(f"{text.strip()}\n")
        except IOError as e:
            return f"Error writing to file: {e}"

        # 2. Add to logs.json
        day_num = self._day_number_for(attribution_date)
        order = self._next_order_for_day(day_num)
        entry = {
            "id": self._next_log_id(),
            "timestamp": timestamp_str,
            "content": text.strip(),
            "status": status,
            "xp": int(xp),
            "coord": [day_num, order],
        }
        self.logs.append(entry)
        self._save_logs_data()

        # 3. Push to git
        self._git_push()

        return True

    def _aggregate_previous_days(self, target_date):
        """Aggregates [CLOUD/TO PROCESS] logs from previous days into single [CLOUD] entries."""
        today_str = target_date.strftime("%d %m %Y")

        prev_indices = [
            i for i, log in enumerate(self.logs)
            if log.get("status") == "[CLOUD/TO PROCESS]"
            and not str(log.get("timestamp", "")).startswith(today_str)
        ]

        if not prev_indices:
            return

        from collections import defaultdict
        by_date = defaultdict(list)
        for i in prev_indices:
            log = self.logs[i]
            try:
                dt = datetime.strptime(log["timestamp"], "%d %m %Y : %H:%M:%S")
                date_key = dt.strftime("%d/%m/%Y")
            except Exception:
                date_key = target_date.strftime("%d/%m/%Y")
            by_date[date_key].append(i)

        if not os.path.exists(self.journal_file):
            return

        with open(self.journal_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        file_changed = False

        for date_key, indices in by_date.items():
            entries = [self.logs[i] for i in indices]

            # Aggregate by action name
            agg = {}  # name → [total_value, total_xp]
            for log in entries:
                content = str(log.get("content", "")).strip()
                xp = int(log.get("xp", 0))
                parsed = self._parse_action_log_content(content)
                if parsed and parsed.get("kind") == "value":
                    name = parsed["action"]
                    value = int(parsed["value"])
                    if name not in agg:
                        agg[name] = [0, 0]
                    agg[name][0] += value
                    agg[name][1] += xp

            if not agg:
                continue

            # Update evove26: remove individual lines, insert aggregated
            header = f"[{date_key}]"
            header_indices = [j for j, line in enumerate(lines) if self._is_date_header_line(line)]
            hidx = next((j for j in header_indices if lines[j].strip() == header), None)

            if hidx is not None:
                next_hidx = next((j for j in header_indices if j > hidx), len(lines))

                content_count = {}
                for log in entries:
                    c = str(log.get("content", "")).strip()
                    content_count[c] = content_count.get(c, 0) + 1

                remove_set = []
                for j in range(hidx + 1, next_hidx):
                    line = lines[j].strip()
                    if line and content_count.get(line, 0) > 0:
                        remove_set.append(j)
                        content_count[line] -= 1

                for j in reversed(remove_set):
                    lines.pop(j)

                file_changed = True

                header_indices = [j for j, line in enumerate(lines) if self._is_date_header_line(line)]
                hidx = next((j for j in header_indices if lines[j].strip() == header), None)
                if hidx is not None:
                    insert_pos = self._insert_under_last_log(lines, hidx)
                    for name, (total_value, _) in agg.items():
                        lines.insert(insert_pos, f"{total_value} X {name}\n")
                        insert_pos += 1

            # Add aggregated entries to logs.json
            for name, (total_value, total_xp) in agg.items():
                try:
                    dt = datetime.strptime(date_key, "%d/%m/%Y")
                    timestamp_str = dt.strftime("%d %m %Y") + " : 23:59:59"
                except Exception:
                    timestamp_str = datetime.now().strftime("%d %m %Y : %H:%M:%S")
                self.logs.append({
                    "id": self._next_log_id(),
                    "timestamp": timestamp_str,
                    "content": f"{total_value} X {name}",
                    "status": "[CLOUD]",
                    "xp": total_xp,
                })

            for i in indices:
                self.logs[i]["status"] = "[PROCESSED]"

        if file_changed:
            with open(self.journal_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

        self._save_logs_data()

    def list_logs(self):
        """Returns all active logs formatted."""
        self._load_logs_data()
        if not self.logs:
            return ["No logs available."]
        
        # Filter active logs only (ignore DELETED and PROCESSED)
        active_logs = []
        for log in self.logs:
            status = str(log.get("status", "")).upper()
            if "DELETED" in status or "PROCESSED" in status:
                continue
            active_logs.append(log)
        
        if not active_logs:
            return ["No active logs available."]

        formatted = []
        for log in active_logs:
            log_id = log.get("id")
            id_str = f"{log_id}" if log_id is not None else "----"
            raw_status = str(log.get("status", ""))
            display_status = "[CLOUD]" if raw_status == "[CLOUD/TO PROCESS]" else raw_status
            line = f"[{id_str}] [{log['timestamp']} ] {log['content']} {display_status}"
            formatted.append(line)
        return formatted
    
    def list_days(self):
        """Reads the content of evove26 file (Command 997)."""
        if not os.path.exists(self.journal_file):
            return ["Journal file 'evove26' not found."]
        
        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Split by lines for display
            return content.splitlines()
        except Exception as e:
            return [f"Error reading file: {e}"]

    def drop_last_buffer_entry(self):
        """Smart delete: marks as [DELETED], removes from file, pushes if [CLOUD].
        Returns (message, xp) where xp is the XP stored in the dropped entry."""
        if not self.logs:
            return "Log list is empty.", 0

        # Find last non-deleted log
        target_index = -1
        for i in range(len(self.logs) - 1, -1, -1):
            if self.logs[i]["status"] != "[DELETED]":
                target_index = i
                break

        if target_index == -1:
            return "No active logs to delete.", 0
            
        target_log = self.logs[target_index]
        original_status = target_log["status"]
        content_to_match = target_log["content"]
        
        # 1. Update status
        self.logs[target_index]["status"] = "[DELETED]"
        self._save_logs_data()
        
        # 2. Remove from evove26
        file_msg = ""
        try:
            if os.path.exists(self.journal_file):
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                # Find index of last matching line
                idx_to_remove = -1
                for i in range(len(lines) -1, -1, -1):
                    line = lines[i].strip()
                    if not line: continue
                    # Skip headers
                    if line.startswith("[") and line.endswith("]") and len(line) == 12:
                        continue
                    
                    if line == content_to_match:
                        idx_to_remove = i
                        break
                
                if idx_to_remove != -1:
                    lines.pop(idx_to_remove)
                    file_msg = "Removed from file."
                    
                    with open(self.journal_file, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                else:
                     file_msg = "Log not found in file (desync?)."

        except Exception as e:
            file_msg = f"File error: {e}"

        # 3. Auto-push if [CLOUD] (or [SYSTEM - CLOUD])
        git_msg = ""
        if "CLOUD" in original_status and "DELETED" not in original_status:
             res = self._git_push()
             if res is True:
                 git_msg = " | Cloud sync (DELETE) success."
             else:
                 git_msg = f" | Cloud sync failed: {res}"
        
        dropped_xp = int(target_log.get("xp", 0))
        return f"Smart Delete: '{content_to_match}' -> [DELETED]. {file_msg}{git_msg}", dropped_xp

    def drop_last_day(self):
        """Alias for 007 - Drops last, same as 07 in this new single-file context."""
        return self.drop_last_buffer_entry()

    def delete_log_by_id(self, log_id):
        """Soft deletes a log by id and removes it from evove26."""
        self._load_logs_data()
        target = self._find_log_by_id(log_id)

        if not target:
            return f"Log id {log_id} not found."

        status = str(target.get("status", "")).upper()
        if "DELETED" in status:
            return f"Log {log_id} already deleted."

        target["status"] = "[DELETED]"
        self._save_logs_data()

        if not os.path.exists(self.journal_file):
            return f"Log {log_id} deleted in logs.json. Journal file not found."

        content = str(target.get("content", "")).strip()
        if not content:
            return f"Log {log_id} deleted in logs.json. Empty content in journal."

        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            removed = False
            # Try remove within its date section if timestamp is valid
            try:
                dt = datetime.strptime(target["timestamp"], "%d %m %Y : %H:%M:%S")
                header = dt.strftime("[%d/%m/%Y]")
                header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
                hidx = next((i for i in header_indices if lines[i].strip() == header), None)
                if hidx is not None:
                    next_header_idx = next((i for i in header_indices if i > hidx), len(lines))
                    for i in range(next_header_idx - 1, hidx, -1):
                        if lines[i].strip() == content:
                            lines.pop(i)
                            removed = True
                            break
            except Exception:
                pass

            if not removed:
                # Fallback: remove last matching line anywhere
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() == content:
                        lines.pop(i)
                        removed = True
                        break

            if removed:
                with open(self.journal_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            else:
                return f"Log {log_id} deleted in logs.json. Entry not found in evove26."

        except Exception as e:
            return f"Log {log_id} deleted in logs.json. Journal update failed: {e}"

        return f"Log {log_id} deleted."

    def move_log_to_date(self, log_id, target_date):
        """Moves a log entry to an existing date header in evove26."""
        self._load_logs_data()
        target = self._find_log_by_id(log_id)
        if not target:
            return f"Log id {log_id} not found."

        status = str(target.get("status", "")).upper()
        if "DELETED" in status:
            return f"Log {log_id} already deleted."
        if not os.path.exists(self.journal_file):
            return "Journal file not found."

        content = str(target.get("content", "")).strip()
        if not content:
            return "Empty content in log."

        target_header = target_date.strftime("[%d/%m/%Y]")

        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
            target_idx = next((i for i in header_indices if lines[i].strip() == target_header), None)
            if target_idx is None:
                return f"Date header {target_header} not found."

            removed = False
            try:
                dt = datetime.strptime(target["timestamp"], "%d %m %Y : %H:%M:%S")
                old_header = dt.strftime("[%d/%m/%Y]")
                old_idx = next((i for i in header_indices if lines[i].strip() == old_header), None)
                if old_idx is not None:
                    next_old_idx = next((i for i in header_indices if i > old_idx), len(lines))
                    for i in range(next_old_idx - 1, old_idx, -1):
                        if lines[i].strip() == content:
                            lines.pop(i)
                            removed = True
                            break
            except Exception:
                pass

            if not removed:
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() == content:
                        lines.pop(i)
                        removed = True
                        break

            if not removed:
                return "Log entry not found in evove26."

            insert_idx = self._insert_under_last_log(lines, target_idx)
            lines.insert(insert_idx, f"{content}\n")

            with open(self.journal_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception as e:
            return f"Move failed: {e}"

        return f"Log {log_id} moved to {target_header}."

    def update_log_content(self, log_id, old_content, new_content, target_date=None):
        """Updates log content in logs.json and evove26."""
        self._load_logs_data()
        target = self._find_log_by_id(log_id)
        if not target:
            return f"Log id {log_id} not found."

        status = str(target.get("status", "")).upper()
        if "DELETED" in status:
            return f"Log {log_id} already deleted."

        if new_content is None:
            new_content = ""
        new_content = str(new_content).strip()

        if new_content == "":
            return self.delete_log_by_id(log_id)

        target["content"] = new_content
        self._save_logs_data()

        if not os.path.exists(self.journal_file):
            return f"Log {log_id} updated in logs.json. Journal file not found."

        if not old_content:
            return f"Log {log_id} updated in logs.json. Empty old content."

        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
            if target_date:
                header = target_date.strftime("[%d/%m/%Y]")
            else:
                header = None
                try:
                    dt = datetime.strptime(target["timestamp"], "%d %m %Y : %H:%M:%S")
                    header = dt.strftime("[%d/%m/%Y]")
                except Exception:
                    header = None

            replaced = False
            if header:
                hidx = next((i for i in header_indices if lines[i].strip() == header), None)
                if hidx is not None:
                    next_idx = next((i for i in header_indices if i > hidx), len(lines))
                    for i in range(next_idx - 1, hidx, -1):
                        if lines[i].strip() == old_content:
                            lines[i] = f"{new_content}\n"
                            replaced = True
                            break

            if not replaced:
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip() == old_content:
                        lines[i] = f"{new_content}\n"
                        replaced = True
                        break

            if replaced:
                with open(self.journal_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            else:
                return f"Log {log_id} updated in logs.json. Entry not found in evove26."
        except Exception as e:
            return f"Log {log_id} updated in logs.json. Journal update failed: {e}"

        return f"Log {log_id} updated."

    def up_log_day(self, log_id):
        """Moves a log entry to the previous day (logs.json + evove26)."""
        self._load_logs_data()
        target = None
        for log in self.logs:
            try:
                if int(log.get("id")) == int(log_id):
                    target = log
                    break
            except (TypeError, ValueError):
                continue

        if not target:
            return f"Log id {log_id} not found."

        status = str(target.get("status", "")).upper()
        if "DELETED" in status:
            return f"Log {log_id} moved in evove26 (deleted log)."
        if "CLOUD" not in status:
            return f"Log {log_id} not moved. Only [CLOUD] logs can be upped."

        if not os.path.exists(self.journal_file):
            return f"Log {log_id} not moved. Journal file not found."

        content = target.get("content", "").strip()
        if not content:
            return f"Log {log_id} not moved. Empty content in journal."

        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Remove last matching line and capture its header position
            header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
            removed = False
            old_header_idx = None
            old_header_line = None
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == content:
                    # find nearest header above
                    for h in reversed(header_indices):
                        if h < i:
                            old_header_idx = h
                            old_header_line = lines[h].strip()
                            break
                    lines.pop(i)
                    removed = True
                    break

            if not removed or old_header_idx is None or not old_header_line:
                return f"Log {log_id} not moved. Entry not found in evove26."

            # Find previous day header (nearest header above the old one)
            prev_header_idx = None
            for h in reversed(header_indices):
                if h < old_header_idx:
                    prev_header_idx = h
                    break

            if prev_header_idx is None:
                return f"Log {log_id} not moved. No previous day header."

            insert_idx = self._insert_under_last_log(lines, prev_header_idx)
            lines.insert(insert_idx, f"{content}\n")

            with open(self.journal_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

        except Exception as e:
            return f"Log {log_id} not moved. Journal update failed: {e}"

        return f"Log {log_id} moved to previous day."

    def up_current_day(self):
        """Moves all today's [CLOUD] logs to the previous day in evove26 and shifts their coord day-1."""
        self._load_logs_data()
        today_day_num = self._day_number_for(datetime.now())
        candidates = {}
        moved_logs = []
        for log in self.logs:
            status = str(log.get("status", "")).upper()
            if "CLOUD" not in status:
                continue
            d, _o = self._coord_for_log(log)
            if d != today_day_num:
                continue
            content = str(log.get("content", "")).strip()
            if not content:
                continue
            candidates[content] = candidates.get(content, 0) + 1
            moved_logs.append(log)

        if not candidates:
            return "No [CLOUD] logs for today."

        if not os.path.exists(self.journal_file):
            return "Journal file not found."

        today_header = datetime.now().strftime("[%d/%m/%Y]")

        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
            today_idx = next((i for i in header_indices if lines[i].strip() == today_header), None)
            if today_idx is None:
                return "Today's header not found in evove26."

            prev_header_idx = None
            for h in reversed(header_indices):
                if h < today_idx:
                    prev_header_idx = h
                    break
            if prev_header_idx is None:
                return "No previous day header."

            next_header_idx = next((i for i in header_indices if i > today_idx), len(lines))

            moved_lines = []
            remove_indices = []
            for i in range(today_idx + 1, next_header_idx):
                line = lines[i].strip()
                if not line:
                    continue
                if line in candidates and candidates[line] > 0:
                    moved_lines.append(lines[i])
                    remove_indices.append(i)
                    candidates[line] -= 1

            if not moved_lines:
                return "No matching [CLOUD] logs found in evove26."

            for i in reversed(remove_indices):
                lines.pop(i)

            insert_idx = self._insert_under_last_log(lines, prev_header_idx)
            for offset, line in enumerate(moved_lines):
                lines.insert(insert_idx + offset, line)

            with open(self.journal_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

        except Exception as e:
            return f"Failed to move logs: {e}"

        # Reassign coord day for moved logs (today_day_num -1) and re-order within target day
        target_day = today_day_num - 1
        next_order = self._next_order_for_day(target_day)
        for log in moved_logs:
            log["coord"] = [target_day, next_order]
            next_order += 1
        self._save_logs_data()

        return f"Moved {len(moved_lines)} logs to previous day."

    def _git_push(self):
        """Commits and pushes changes to Git with enhanced error handling."""
        if not os.path.exists(self.journal_dir):
            return "Journal directory not found (subprocess)."
            
        try:
            # Check if it's a git repo
            if not os.path.exists(os.path.join(self.journal_dir, ".git")):
                return "Not a git repository."

            def run_git_cmd(args):
                result = subprocess.run(
                    args, 
                    cwd=self.journal_dir, 
                    capture_output=True, 
                    text=True, 
                    check=False # We handle return code manually
                )
                if result.returncode != 0:
                    return False, result.stderr.strip() or result.stdout.strip()
                return True, result.stdout.strip()

            # 0. Pull (to avoid conflicts)
            ok, msg = run_git_cmd(["git", "pull", "--no-rebase"])
            if not ok: 
                return f"Git Pull Error: {msg}"

            # 1. Add
            ok, msg = run_git_cmd(["git", "add", "."])
            if not ok: return f"Git Add Error: {msg}"

            # 2. Commit
            # Format: [evove dd/mm/yyyy - hh:mm:ss ]
            timestamp = datetime.now().strftime("%d/%m/%Y - %H:%M:%S")
            commit_msg = f"[evove {timestamp} ]"
            ok, msg = run_git_cmd(["git", "commit", "-m", commit_msg])
            
            # Allow "nothing to commit" as success
            if not ok:
                if "nothing to commit" in msg or "clean" in msg:
                    pass 
                else:
                    return f"Git Commit Error: {msg}"
            
            # 3. Push
            ok, msg = run_git_cmd(["git", "push"])
            if not ok:
                return f"Git Push Error: {msg}"
            
            return True
        except Exception as e:
            return f"Git Exception: {str(e)}"


journal_service = JournalService()
