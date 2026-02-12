import os
import json
import subprocess
from datetime import datetime, timedelta
from src.components.services.sleep_service import sleep_service
from src.components.services.sequence_service import sequence_service

class JournalService:
    def __init__(self):
        self.log_id_prefix = 73
        self.log_id_width = 4
        # Paths
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logs_data_path = os.path.join(base_dir, "data", "logs.json")
        
        # User journal directory (Git Repo)
        self.journal_dir = os.path.expanduser("~/journal")
        self.journal_file = os.path.join(self.journal_dir, "evove26")
        
        self.logs = []
        self._load_logs_data()

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

    def _load_logs_data(self):
        """Loads structured log data."""
        if os.path.exists(self.logs_data_path):
            try:
                with open(self.logs_data_path, 'r', encoding='utf-8') as f:
                    self.logs = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.logs = []
        else:
            self.logs = []

        # Normalize legacy statuses
        normalized = False
        for log in self.logs:
            status = log.get("status")
            if isinstance(status, str) and "TO PROCESS" in status and status != "[TO PROCESS]":
                log["status"] = "[TO PROCESS]"
                normalized = True
        if normalized:
            self._save_logs_data()

    def _save_logs_data(self):
        """Saves structured log data."""
        try:
            os.makedirs(os.path.dirname(self.logs_data_path), exist_ok=True)
            with open(self.logs_data_path, 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, indent=4)
            from src.components.services.backup_service import backup_json
            backup_json(self.logs_data_path)
        except IOError as e:
            print(f"Error saving logs data: {e}")

    def _get_last_file_date_header(self):
        """Reads the journal file backwards to find the last date header."""
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

    def add_log(self, text, manual_date=None, auto_confirm=False, custom_status=None):
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

        # Formats
        # New Header Format: [dd/mm/yyyy]
        current_date_header = target_date.strftime("[%d/%m/%Y]")
        timestamp_str = target_date.strftime("%d %m %Y : %H:%M:%S")
        
        status = custom_status if custom_status else "[IN WAIT]"
        if isinstance(status, str) and "TO PROCESS" in status:
            status = "[TO PROCESS]"
        
        # 1. Append to evove26 (Skip if it's a "TO PROCESS" system log)
        if status != "[TO PROCESS]":
            try:
                os.makedirs(self.journal_dir, exist_ok=True)
                
                # Check if we need to write the date header
                last_header = self._get_last_file_date_header()
                
                with open(self.journal_file, "a", encoding="utf-8") as f:
                    if last_header != current_date_header:
                        f.write(f"\n{current_date_header}\n")
                    
                    f.write(f"{text.strip()}\n")
            except IOError as e:
                return f"Error writing to file: {e}"

        # 2. Add to logs.json
        entry = {
            "id": self._next_log_id(),
            "timestamp": timestamp_str,
            "content": text.strip(),
            "status": status
        }
        self.logs.append(entry)
        self._save_logs_data()
        
        return True

    def process_daily_logs(self):
        """Aggregates [TO PROCESS] logs into [IN WAIT] entries."""
        if not self.logs:
            return "No logs to process."

        to_process_indices = [i for i, log in enumerate(self.logs) if log.get("status") == "[TO PROCESS]"]
        
        if not to_process_indices:
            return "No pending system logs."

        # Aggregation buckets
        actions_agg = {}   # "ACTION NAME": value
        purchases_agg = {} # "SHOP ITEM": qtd
        
        # Helper to parse log content
        # Expected formats: "value ACTION" or "qtd x ITEM"
        for idx in to_process_indices:
            content = self.logs[idx]["content"]
            try:
                if " x " in content:
                    # Purchase: "2 x VIDEOGAMES"
                    parts = content.split(" x ", 1)
                    qtd = int(parts[0])
                    name = parts[1].strip()
                    purchases_agg[name] = purchases_agg.get(name, 0) + qtd
                else:
                    # Action: "50 PUSHUPS"
                    parts = content.split(" ", 1)
                    val = int(parts[0])
                    name = parts[1].strip()
                    actions_agg[name] = actions_agg.get(name, 0) + val
            except (ValueError, IndexError):
                # Fallback: Just mark as processed but don't aggregate if format is weird? 
                # Or maybe just leave it? Let's assume strict format from User/Shop.
                pass

        # Create new aggregated logs
        for name, value in actions_agg.items():
            self.add_log(f"{value} {name}", auto_confirm=True, custom_status="[IN WAIT]")
            
        for name, qtd in purchases_agg.items():
            self.add_log(f"{qtd} x {name}", auto_confirm=True, custom_status="[IN WAIT]")

        # Mark originals as PROCESSED
        for idx in to_process_indices:
            self.logs[idx]["status"] = "[PROCESSED]"
            
        self._save_logs_data()
        return f"Processed {len(to_process_indices)} entries."

    def list_logs(self):
        """Returns last 15 active logs formatted."""
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

        recent = active_logs[-15:]
        formatted = []
        for log in recent:
            # Format: [dd mm yy : hh:mm:ss ] log 1 [STATUS]
            log_id = log.get("id")
            id_str = f"{log_id}" if log_id is not None else "----"
            line = f"[{id_str}] [{log['timestamp']} ] {log['content']} {log['status']}"
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
        """Smart delete: marks as [DELETED], removes from file, pushes if [CLOUD]."""
        if not self.logs:
            return "Log list is empty."
            
        # Find last non-deleted log
        target_index = -1
        for i in range(len(self.logs) - 1, -1, -1):
            if self.logs[i]["status"] != "[DELETED]":
                target_index = i
                break
        
        if target_index == -1:
            return "No active logs to delete."
            
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
        
        return f"Smart Delete: '{content_to_match}' -> [DELETED]. {file_msg}{git_msg}"

    def drop_last_day(self):
        """Alias for 007 - Drops last, same as 07 in this new single-file context."""
        return self.drop_last_buffer_entry()

    def delete_log_by_id(self, log_id):
        """Soft deletes a log by id and removes it from evove26."""
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
            return f"Log {log_id} already deleted."

        target["status"] = "[DELETED]"
        self._save_logs_data()

        if not os.path.exists(self.journal_file):
            return f"Log {log_id} deleted in logs.json. Journal file not found."

        content = str(target.get("content", "")).strip()
        if not content:
            return f"Log {log_id} deleted in logs.json. Empty content in journal."

        # If TO PROCESS, there's no evove26 entry
        if status == "[TO PROCESS]":
            return f"Log {log_id} deleted."

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
        if status == "[TO PROCESS]":
            return f"Log {log_id} moved to previous day."
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

            # Insert under the last day log (before first blank line in that day, if any)
            header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
            next_header_idx = next((i for i in header_indices if i > prev_header_idx), len(lines))
            insert_idx = next_header_idx
            for i in range(prev_header_idx + 1, next_header_idx):
                if lines[i].strip() == "":
                    insert_idx = i
                    break
            lines.insert(insert_idx, f"{content}\n")

            with open(self.journal_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

        except Exception as e:
            return f"Log {log_id} not moved. Journal update failed: {e}"

        return f"Log {log_id} moved to previous day."

    def up_current_day(self):
        """Moves all today's [CLOUD] logs to the previous day in evove26."""
        self._load_logs_data()
        today_str = datetime.now().strftime("%d %m %Y")
        candidates = {}
        for log in self.logs:
            status = str(log.get("status", "")).upper()
            if "CLOUD" not in status:
                continue
            ts = str(log.get("timestamp", ""))
            if not ts.startswith(today_str):
                continue
            content = str(log.get("content", "")).strip()
            if not content:
                continue
            candidates[content] = candidates.get(content, 0) + 1

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

            # Insert under the last day log (before first blank line in that day, if any)
            header_indices = [i for i, line in enumerate(lines) if self._is_date_header_line(line)]
            next_prev_header_idx = next((i for i in header_indices if i > prev_header_idx), len(lines))
            insert_idx = next_prev_header_idx
            for i in range(prev_header_idx + 1, next_prev_header_idx):
                if lines[i].strip() == "":
                    insert_idx = i
                    break

            for offset, line in enumerate(moved_lines):
                lines.insert(insert_idx + offset, line)

            with open(self.journal_file, "w", encoding="utf-8") as f:
                f.writelines(lines)

        except Exception as e:
            return f"Failed to move logs: {e}"

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

    def sleep(self):
        """Sleeps, pushes to git, updates status."""
        # 1. Push to Git
        git_res = self._git_push()
        
        msg = ""
        if git_res is True:
            msg = "Git push successful."
            # Update [IN WAIT] to [CLOUD]
            updated_count = 0
            for log in self.logs:
                if log["status"] == "[IN WAIT]":
                    log["status"] = "[CLOUD]"
                    updated_count += 1
            self._save_logs_data()
            if updated_count > 0:
                msg += f" Marked {updated_count} logs as [CLOUD]."
        else:
            msg = f"Git failed: {git_res}"
            
        # 2. Log sleep time (service)
        sleep_time = sleep_service.log_sleep()
        
        return f"Sleep at {sleep_time.strftime('%H:%M:%S')}. {msg}"

    def nap(self):                   
        # 2. Log sleep time (service)
        sleep_time = sleep_service.log_sleep()
        
        return f"Nap at {sleep_time.strftime('%H:%M:%S')}"

    def wake(self):
        wake_time, duration = sleep_service.log_wake()
        return f"Woke up at {wake_time.strftime('%H:%M:%S')}. Sleep duration: {duration}."

journal_service = JournalService()
