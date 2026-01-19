import os
import sys
import time 
import readchar

from src.components.services.UI.interface import ui
from src.components.services.dial_interaction.dial_digest import dial

from src.components.data.constants import (
    user,
    him,
    OBJECTS,
    INTERACTIONS,
    SINGLE_COMMANDS,
    COMMANDS
)

def dial_start():
    user.load_user()
    try:
        buffer = ""
        while True:
            
            ui.render(buffer)
        
            completed, result = dial.process(buffer)
            
            if completed:
                buffer = ""

                if him.messages:
                    ui.show_messages_animated(him.messages)
                    him.clear_messages()

                if isinstance(result, (int, float)) and result > 0:
                    him.offer(result)
                    
                    if him.messages:
                        ui.show_messages_animated(him.messages)
                        him.clear_messages()            

                if user.messages:
                    ui.show_messages_animated(user.messages)
                    user.clear_messages()
                
                continue 
            
            key = readchar.readkey()
            if key in (readchar.key.BACKSPACE, '\x7f'):
                buffer = buffer[:-1]
            elif key.isdigit():
                buffer += key
    except KeyboardInterrupt:
        print("BYE")
        sys.exit(0)
