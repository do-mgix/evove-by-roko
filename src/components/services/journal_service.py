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

    def sync_to_cloud(self):
        """Syncs buffered logs to the journal file and pushes to GitHub."""
        if not self.buffer:
            return "Buffer is empty. Nothing to sync."

        now = datetime.now()
        date_header = now.strftime("%Y-%m-%d %H:%M:%S")
        commit_date = now.strftime("%d/%m/%Y")
        
        log_content = f"\n--- {date_header} ---\n"
        log_content += "\n".join(self.buffer) + "\n"

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
            # This handles the case where the user deleted something on GitHub
            subprocess.run(["git", "reset", "--hard", f"origin/{branch}"], cwd=self.journal_dir, check=True)

            # 3. APPEND NEW LOGS
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
                subprocess.run(
                    cmd, 
                    cwd=self.journal_dir, 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
            
            self.buffer = [] # Clear memory buffer
            self.save_buffer() # Clear file buffer
            return f"Successfully synced to cloud and pushed to GitHub with commit [evove ({commit_date})]."
            
        except subprocess.CalledProcessError as e:
            return f"Git Error: {e.stderr}"
        except Exception as e:
            return f"Error: {str(e)}"

journal_service = JournalService()
