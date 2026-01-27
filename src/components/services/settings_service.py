from src.components.services.UI.interface import ui
from src.components.data.constants import user, MODES

class SettingsService:
    def start(self):
        while True:
            options = {
                "1": f"Virtual Agent: {'[ENABLED]' if user.metadata.get('virtual_agent_active', True) else '[DISABLED]'}",
                "2": f"Current Mode: {user.metadata.get('mode', 'progressive').upper()}",
                "0": "Back"
            }
            
            choice = ui.show_menu("SETTINGS", options)
            
            if choice == "1":
                current = user.metadata.get("virtual_agent_active", True)
                user.metadata["virtual_agent_active"] = not current
                user.add_message(f"Agent {'enabled' if not current else 'disabled'}.")
                user.save_user()
            elif choice == "2":
                self._change_mode()
            elif choice == "0":
                break

    def _change_mode(self):
        mode_options = {str(i+1): mode.upper() for i, mode in enumerate(MODES.values())}
        mode_options["0"] = "Cancel"
        
        choice = ui.show_menu("SELECT MODE", mode_options)
        
        if choice in mode_options and choice != "0":
            index = int(choice) - 1
            new_mode = list(MODES.values())[index]
            user.metadata["mode"] = new_mode
            user.add_message(f"Mode changed to {new_mode.upper()}.")
            user.save_user()

settings_service = SettingsService()
