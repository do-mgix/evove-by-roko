import os
import sys
import time 
import readchar

from src.components.services.UI.interface import ui
from src.components.services.dial_interaction.dial_digest import dial
from src.components.entitys.entity_manager import EntityManager
from src.components.services.challenge_service import ChallengeManager

from src.components.data.constants import (
    user,
    OBJECTS,
    INTERACTIONS,
    SINGLE_COMMANDS,
    COMMANDS
)

def _prompt_cli_input(message):
    ui.clear_screen()
    print(message)
    value = input("> ")
    ui.clear_screen()
    return value

def dial_start():
    user.load_user()
    em = EntityManager()
    cm = ChallengeManager(user, em)
    
    try:
        buffer = ""
        while True:
            # Process any existing messages from entities BEFORE waiting for input
            current_him = em.get_entity()
            if current_him and current_him.messages:
                ui.show_messages_animated(current_him.messages)
                current_him.clear_messages()
            
            if user.messages:
                ui.show_messages_animated(user.messages)
                user.clear_messages()

            # Render interface
            ui.render(buffer)
            
            # Background checks (will run after each user interaction)
            em.check_and_spawn()
            cm.update()

            # Blocking key read - much better for performance
            key = readchar.readkey()
            
            if key in (readchar.key.BACKSPACE, '\x7f', '\x08'):
                buffer = buffer[:-1]
            elif key == readchar.key.ENTER or key == '\r' or key == '\n':
                # If Enter is pressed, process buffer
                try:
                    completed, result = dial.process(buffer)
                    if completed:
                        buffer = ""
                        _handle_result(result, em, ui)
                except Exception as e:
                    # In case of WebInputInterrupt, we need to import it inside to avoid circular imports if possible
                    # or assume it's the one. Common pattern: check class name or import.
                    from src.components.services.UI.interface import WebInputInterrupt
                    if isinstance(e, WebInputInterrupt):
                        ui.render(buffer, force_print=True) # Ensure render doesn't wipe immediately
                        guide = f"[ INPUT REQUIRED ] {e.prompt}"
                        if e.type:
                            guide += f" ({e.type})"
                        cli_input = _prompt_cli_input(guide)
                        

                        if e.prompt == "log message":
                             user.add_log_entry(cli_input)
                             buffer = ""
                        elif e.prompt == "status name":
                             user.create_status(e.options.get("buffer", ""), name=cli_input)
                             buffer = ""
                        elif e.prompt == "parameter name":
                             user.create_parameter(e.options.get("buffer", ""), name=cli_input)
                             buffer = ""
                        elif e.prompt.startswith("parameter value"):
                             user._attach_status_to_param(
                                 e.options.get("param_id"),
                                 e.options.get("status_id"),
                                 cli_input,
                             )
                             buffer = ""
                        elif e.prompt.startswith("parameter regen") or e.prompt.startswith("parameter start value"):
                             step = e.options.get("param_step") if e.options else None
                             data = e.options if e.options else {}
                             next_step = user.parameter_init_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("param_step")
                                 data = next_step.get("options", {})
                                 next_step = user.parameter_init_next(step, data, cli_input)
                             buffer = ""
                        elif e.prompt.startswith("param-action"):
                             step = e.options.get("pa_step") if e.options else None
                             data = e.options if e.options else {}
                             next_step = user.param_action_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("pa_step")
                                 data = next_step.get("options", {})
                                 next_step = user.param_action_next(step, data, cli_input)
                             buffer = ""
                        elif e.prompt.startswith("agenda "):
                             step = e.options.get("agenda_step") if e.options else None
                             data = e.options.get("agenda_data") if e.options else {}
                             next_step = user.agenda_wizard_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("agenda_step")
                                 data = next_step.get("options", {}).get("agenda_data", {})
                                 next_step = user.agenda_wizard_next(step, data, cli_input)
                             buffer = ""
                        elif e.prompt == "sequence label":

                             print("Complex input incomplete. (Not fully supported in CLI for multi-step yet)")
                             buffer = ""
                        elif e.prompt == "sequence start value (integer)":
                             # This implies label was somehow passed? unlikely via dial.
                             pass
                        elif "value" in e.prompt:
                             # action value
                             action_id = e.options.get("action_id")
                             if action_id:
                                 user.act(list(action_id), cli_input) # Approximate reconstruction
                                 buffer = ""
                             
                    else:
                        raise e

            else:
                # Add character to buffer (supporting letters and symbols now)
                if len(key) == 1 and (key.isalnum() or key in " :/._-+=()*&^%$#@!?,<>{}[]|\\~`'\""):
                    buffer += key
            

            if not buffer.startswith(':') and not buffer.startswith('/'):
                try:
                    completed, result = dial.process(buffer)
                    
                    if completed:
                        buffer = ""
                        _handle_result(result, em, ui)
                except Exception as e:
                     from src.components.services.UI.interface import WebInputInterrupt
                     if isinstance(e, WebInputInterrupt):
                        # CLI Interrupt Handling duplicated logic
                        guide = f"[ INPUT REQUIRED ] {e.prompt}"
                        if e.type:
                            guide += f" ({e.type})"
                        cli_input = _prompt_cli_input(guide)
                        
                        if e.prompt == "log message":
                             user.add_log_entry(cli_input)
                             buffer = ""
                        elif e.prompt == "status name":
                             user.create_status(e.options.get("buffer", ""), name=cli_input)
                             buffer = ""
                        elif e.prompt == "parameter name":
                             user.create_parameter(e.options.get("buffer", ""), name=cli_input)
                             buffer = ""
                        elif e.prompt.startswith("parameter value"):
                             user._attach_status_to_param(
                                 e.options.get("param_id"),
                                 e.options.get("status_id"),
                                 cli_input,
                             )
                             buffer = ""
                        elif e.prompt.startswith("parameter regen") or e.prompt.startswith("parameter start value"):
                             step = e.options.get("param_step") if e.options else None
                             data = e.options if e.options else {}
                             next_step = user.parameter_init_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("param_step")
                                 data = next_step.get("options", {})
                                 next_step = user.parameter_init_next(step, data, cli_input)
                             buffer = ""
                        elif e.prompt.startswith("param-action"):
                             step = e.options.get("pa_step") if e.options else None
                             data = e.options if e.options else {}
                             next_step = user.param_action_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("pa_step")
                                 data = next_step.get("options", {})
                                 next_step = user.param_action_next(step, data, cli_input)
                             buffer = ""
                        elif e.prompt.startswith("agenda "):
                             step = e.options.get("agenda_step") if e.options else None
                             data = e.options.get("agenda_data") if e.options else {}
                             next_step = user.agenda_wizard_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("agenda_step")
                                 data = next_step.get("options", {}).get("agenda_data", {})
                                 next_step = user.agenda_wizard_next(step, data, cli_input)
                             buffer = ""
                        elif "numeric value" in e.prompt or "value" in e.prompt:
                             action_id = e.options.get("action_id")
                             if action_id:

                                 user.act(list(action_id), cli_input)
                                 buffer = ""
                        elif e.prompt == "sequence index to delete":
                            user.delete_sequence(cli_input)
                            buffer = ""
                
    except KeyboardInterrupt:
        print("\nBYE")
        sys.exit(0)

def _handle_result(result, em, ui):
    from src.components.data.constants import user
    # Handle result and messages immediately after command completion
    current_him = em.get_entity()
    if current_him and current_him.messages:
        ui.show_messages_animated(current_him.messages)
        current_him.clear_messages()

    if isinstance(result, (int, float)) and not isinstance(result, bool) and result > 0:
        if current_him:
            current_him.offer(result)
            if current_him.messages:
                ui.show_messages_animated(current_him.messages)
                current_him.clear_messages()            

    if user.messages:
        ui.show_messages_animated(user.messages)
        user.clear_messages()
