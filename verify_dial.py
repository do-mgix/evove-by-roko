import sys
import os

# Ensure the src directory is in the path
sys.path.append(os.getcwd())

from src.components.services.UI.interface import ui
from src.components.services.dial_interaction.dial_digest import dial

def test_ui_rendering():
    test_buffers = [
        "98",         # list_attr (SINGLE_COMMAND)
        "1",          # him.cutucar (SINGLE_COMMAND)
        "8012",       # attr 01 add (dynamic command started)
        "80125011",   # attr 01 add action 01 act (dynamic command complete)
    ]
    
    print("Testing UI Rendering and Dial Parsing:")
    print("-" * 40)
    
    for buffer in test_buffers:
        print(f"Buffer: {buffer}")
        try:
            # Test dial parsing
            phrase, payloads, is_single = dial.parse_buffer(buffer)
            print(f"  Parsed: Phrase='{phrase}', Payloads={payloads}, Single={is_single}")
            
            # Test UI view processing
            view = ui.process_view(buffer)
            print(f"  UI View: {view}")
            
            # Test full render (simulated skip_clear)
            # ui.render(buffer, skip_clear=True)
            
        except Exception as e:
            print(f"  ERROR for buffer '{buffer}': {e}")
        print("-" * 40)

if __name__ == "__main__":
    test_ui_rendering()
