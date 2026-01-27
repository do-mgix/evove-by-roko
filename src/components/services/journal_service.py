import os
import json
import subprocess
from datetime import datetime

class JournalService:
    def __init__(self):
        self.buffer = []
        # Relative to project root: src/data/logs.json
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logs_json_path = os.path.join(base_dir, "data", "logs.json")
        self.journal_path = os.path.expanduser("~/journal/evove26")
        self.journal_dir = os.path.expanduser("~/journal")
        self.load_buffer()

    def load_buffer(self):
        """Loads logs from JSON file if it exists."""
        if os.path.exists(self.logs_json_path):
            try:
                with open(self.logs_json_path, 'r', encoding='utf-8') as f:
                    self.buffer = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.buffer = []

    def save_buffer(self):
        """Saves current buffer to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.logs_json_path), exist_ok=True)
            with open(self.logs_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.buffer, f, indent=4)
        except IOError as e:
            print(f"Error saving log buffer: {e}")

    def add_log(self, text):
        """Adds text to the log buffer and persists it."""
        if text.strip():
            self.buffer.append(text.strip())
            self.save_buffer()
            return True
        return False

    def _robust_git_sync(self, commit_msg):
        """Unified Git sync logic: fetch, reset to origin, apply changes, and push."""
        try:
            # Detect branch
            branch = "main"
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.journal_dir, capture_output=True, text=True, check=True
                )
                detected = res.stdout.strip()
                if detected and detected != "HEAD":
                    branch = detected
            except:
                pass

            # 1. CLEAN STATE: Abort any pending rebase/merge and fetch
            subprocess.run(["git", "rebase", "--abort"], cwd=self.journal_dir, capture_output=True)
            subprocess.run(["git", "merge", "--abort"], cwd=self.journal_dir, capture_output=True)
            subprocess.run(["git", "fetch", "origin", branch], cwd=self.journal_dir, check=True)
            
            # 2. SYNC WITH REMOTE: Reset local to match remote exactly
            subprocess.run(["git", "reset", "--hard", f"origin/{branch}"], cwd=self.journal_dir, check=True)

            # 3. YIELD TO CALLER FOR FILE MODIFICATION
            # The caller handles the actual 'with open... write' logic after this point.
            return True, branch
        except Exception as e:
            return False, str(e)

    def sync_to_cloud(self):
        """Syncs buffered logs to the journal file and pushes to GitHub."""
        if not self.buffer:
            return "Buffer is empty. Nothing to sync."

        success, result = self._robust_git_sync("Syncing...")
        if not success:
            return f"Git Error during sync: {result}"
        
        branch = result
        now = datetime.now()
        date_header = now.strftime("%Y-%m-%d %H:%M:%S")
        commit_date = now.strftime("%d/%m/%Y")
        
        log_content = f"\n--- {date_header} ---\n"
        log_content += "\n".join(self.buffer) + "\n"

        try:
            # 3. APPEND NEW LOGS (After reset)
            os.makedirs(self.journal_dir, exist_ok=True)
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(log_content)
            
            # 4. COMMIT AND PUSH
            commands = [
                ["git", "add", "evove26"],
                ["git", "commit", "-m", f"[evove ({commit_date})]"],
                ["git", "push", "origin", branch]
            ]
            
            for cmd in commands:
                subprocess.run(cmd, cwd=self.journal_dir, check=True, capture_output=True)
            
            self.buffer = [] # Clear memory buffer
            self.save_buffer() # Clear file buffer
            return f"Successfully synced to cloud and pushed to GitHub with commit [evove ({commit_date})]."
        except Exception as e:
            return f"Error applying changes: {str(e)}"

    def drop_last_day(self, confirmed=False):
        """Removes the last entry block from the journal file with confirmation and sync."""
        if not os.path.exists(self.journal_path):
            return "Journal file not found."

        try:
            # 1. READ LOCAL TO GET HEADER INFO (For confirmation)
            with open(self.journal_path, "r", encoding="utf-8") as f:
                content = f.read()

            marker = "\n--- "
            last_index = content.rfind(marker)
            if last_index == -1 and content.startswith("--- "): last_index = 0
            
            if last_index == -1: return "No entry markers found in journal."

            header_end = content.find(" ---\n", last_index)
            if header_end == -1: header_end = content.find("\n", last_index + len(marker))
            header_info = content[last_index:header_end].strip("- \n")

            if not confirmed:
                from src.components.services.UI.interface import ui, WebInputInterrupt
                if ui.web_mode:
                    import random
                    code = "".join([str(random.randint(0, 9)) for _ in range(3)])
                    from src.components.data.constants import user
                    user.add_message(f"Drop entry: {header_info}?")
                    user.add_message(f"Type the code: {code}")
                    raise WebInputInterrupt(f"Confirm code: {code}?", type="confirm", options={"code": code, "action": "journal_drop"})
                else:
                    if not ui.ask_confirmation(f"Drop entry: {header_info}?"):
                        return "Drop cancelled."
                    confirmed = True

            # 2. SYNC WITH REMOTE FIRST (To avoid Divergence)
            success, result = self._robust_git_sync("Dropping...")
            if not success: return f"Sync Error: {result}"
            branch = result

            # 3. RE-APPLY TRUNCATION ON THE SYNCED CONTENT
            with open(self.journal_path, "r", encoding="utf-8") as f:
                synced_content = f.read()
            
            # Find index in synced content
            new_last_index = synced_content.rfind(marker)
            if new_last_index == -1 and synced_content.startswith("--- "): new_last_index = 0
            
            if new_last_index != -1:
                truncated_content = synced_content[:new_last_index]
                with open(self.journal_path, "w", encoding="utf-8") as f:
                    f.write(truncated_content)

                # 4. COMMIT AND PUSH
                commit_date = datetime.now().strftime("%d/%m/%Y")
                subprocess.run(["git", "add", "evove26"], cwd=self.journal_dir, check=True)
                subprocess.run(["git", "commit", "-m", f"[evove (DROP {commit_date})]"], cwd=self.journal_dir, check=True)
                subprocess.run(["git", "push", "origin", branch], cwd=self.journal_dir, check=True)
                
                return f"Successfully dropped and synced: {header_info}"
            else:
                return "Could not find entry to drop after sync."

        except Exception as e:
            if "WebInputInterrupt" in str(type(e)): raise e
            return f"Error during drop: {str(e)}"

journal_service = JournalService()
