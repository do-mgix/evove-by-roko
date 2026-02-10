import json
import os


class TutorialService:
    def __init__(self, user_instance):
        self.user = user_instance
        self._shown_this_session = set()
        self.messages = self._load_messages()

    def _messages_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        return os.path.join(src_dir, "data", "tutorial_messages.json")

    def _load_messages(self):
        path = self._messages_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _state(self):
        return self.user.metadata.get("tutorial", {})

    def is_complete(self, key):
        return bool(self._state().get(key, {}).get("status"))

    def complete(self, key):
        tutorial = self._state()
        if key not in tutorial:
            return
        tutorial[key]["status"] = True
        self.user.metadata["tutorial"] = tutorial
        self.user.save_user()

    def show(self, key):
        if key in self._shown_this_session:
            return
        entry = self.messages.get(key, {})
        message = entry.get("message")
        if not message:
            return
        self.user.add_message(message)
        self._shown_this_session.add(key)

    def maybe_show_startup(self):
        if not self.is_complete("welcomed"):
            self.show("welcomed")
            self.complete("welcomed")

        if not self.is_complete("has_created_action") and not self.user._actions:
            self.show("has_created_action")
