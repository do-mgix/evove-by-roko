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

def _prompt_cli_input(message, autocomplete=None):
    if autocomplete:
        try:
            import readline
            matches = sorted(set(autocomplete))
            def completer(text, state):
                options = [m for m in matches if m.lower().startswith(text.lower())]
                if state < len(options):
                    return options[state]
                return None
            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass
    ui.clear_screen()
    print(message)
    value = input("> ")
    if autocomplete:
        try:
            import readline
            readline.set_completer(None)
        except Exception:
            pass
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
                    completed, result = dial.process(buffer, force=True)
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
                        autocomplete = None
                        if e.options and e.options.get("autocomplete") == "names":
                             autocomplete = user._collect_autocomplete_names()
                        cli_input = _prompt_cli_input(guide, autocomplete=autocomplete)
                        

                        if e.prompt == "log message":
                             user.add_log_entry(cli_input)
                             buffer = ""
                        elif e.prompt == "status name":
                             user.create_status(e.options.get("buffer", ""), name=cli_input)
                             buffer = ""
                        elif e.prompt == "tag name":
                             user.create_tag(name=cli_input)
                             buffer = ""
                        elif e.prompt in ("unit type", "difficulty (1-5)", "action name"):
                             current = e
                             current_input = cli_input
                             while True:
                                 step = current.options.get("create_step") if current.options else None
                                 data = current.options if current.options else {}
                                 try:
                                     user.create_action(step=step, data=data, value=current_input)
                                     buffer = ""
                                     break
                                 except WebInputInterrupt as next_e:
                                     prompt = next_e.prompt
                                     autocomplete = None
                                     if next_e.options and next_e.options.get("autocomplete") == "names":
                                         autocomplete = user._collect_autocomplete_names()
                                     current_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}", autocomplete=autocomplete)
                                     current = next_e
                        elif e.prompt in ("parameter type (1 mark, 2 percentage)", "parameter logic (1 Emotional, 2 Ambiental, 3 Fisiologic)", "parameter name"):
                             current = e
                             current_input = cli_input
                             while True:
                                 step = current.options.get("create_step") if current.options else None
                                 data = current.options if current.options else {}
                                 try:
                                     user.create_parameter(step=step, data=data, value=current_input)
                                     buffer = ""
                                     break
                                 except WebInputInterrupt as next_e:
                                     prompt = next_e.prompt
                                     autocomplete = None
                                     if next_e.options and next_e.options.get("autocomplete") == "names":
                                         autocomplete = user._collect_autocomplete_names()
                                     current_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}", autocomplete=autocomplete)
                                     current = next_e
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
                        elif e.prompt.startswith("tag weight"):
                             step = e.options.get("tag_step") if e.options else None
                             data = e.options if e.options else {}
                             next_step = user.tag_link_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("tag_step")
                                 data = next_step.get("options", {})
                                 next_step = user.tag_link_next(step, data, cli_input)
                             buffer = ""
                        elif e.prompt.startswith("edit action") or e.prompt.startswith("edit attribute") or e.prompt.startswith("edit parameter") or e.prompt.startswith("edit status"):
                             step = e.options.get("edit_step") if e.options else None
                             data = e.options if e.options else {}
                             if step and step.startswith("action_"):
                                 next_step = user.action_edit_next(step, data, cli_input)
                             else:
                                 next_step = user.misc_edit_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 autocomplete = None
                                 if next_step.get("options", {}).get("autocomplete") == "names":
                                     autocomplete = user._collect_autocomplete_names()
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}", autocomplete=autocomplete)
                                 step = next_step.get("options", {}).get("edit_step")
                                 data = next_step.get("options", {})
                                 if step and step.startswith("action_"):
                                     next_step = user.action_edit_next(step, data, cli_input)
                                 else:
                                     next_step = user.misc_edit_next(step, data, cli_input)
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
                                 payload = action_id[1:]
                                 action = user._actions.get(action_id)
                                 if action:
                                     lt = getattr(action, "_logic_type", None)
                                     st = getattr(action, "_sub_logic_type", None)
                                     if lt is not None:
                                         lt = str(lt).zfill(2) if str(lt).isdigit() else str(lt)
                                         if st is not None:
                                             st = str(st).zfill(2) if str(st).isdigit() else str(st)
                                             payload = f"{lt}{st}{payload}"
                                         else:
                                             payload = f"{lt}{payload}"
                                 user.act([payload], cli_input)
                                 buffer = ""
                             
                    else:
                        raise e

            else:
                # Add character to buffer (supporting letters and symbols now)
                if len(key) == 1 and (key.isalnum() or key in " :/._-+=()*&^%$#@!?,<>{}[]|\\~`'\""):
                    buffer += key
            

            if not buffer.startswith(':') and not buffer.startswith('/'):
                try:
                    completed, result = dial.process(buffer, force=False)
                    
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
                        autocomplete = None
                        if e.options and e.options.get("autocomplete") == "names":
                             autocomplete = user._collect_autocomplete_names()
                        cli_input = _prompt_cli_input(guide, autocomplete=autocomplete)
                        
                        if e.prompt == "log message":
                             user.add_log_entry(cli_input)
                             buffer = ""
                        elif e.prompt == "status name":
                             user.create_status(e.options.get("buffer", ""), name=cli_input)
                             buffer = ""
                        elif e.prompt == "tag name":
                             user.create_tag(name=cli_input)
                             buffer = ""
                        elif e.prompt in ("unit type", "difficulty (1-5)", "action name"):
                             current = e
                             current_input = cli_input
                             while True:
                                 step = current.options.get("create_step") if current.options else None
                                 data = current.options if current.options else {}
                                 try:
                                     user.create_action(step=step, data=data, value=current_input)
                                     buffer = ""
                                     break
                                 except WebInputInterrupt as next_e:
                                     prompt = next_e.prompt
                                     autocomplete = None
                                     if next_e.options and next_e.options.get("autocomplete") == "names":
                                         autocomplete = user._collect_autocomplete_names()
                                     current_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}", autocomplete=autocomplete)
                                     current = next_e
                        elif e.prompt in ("parameter type (1 mark, 2 percentage)", "parameter logic (1 Emotional, 2 Ambiental, 3 Fisiologic)", "parameter name"):
                             current = e
                             current_input = cli_input
                             while True:
                                 step = current.options.get("create_step") if current.options else None
                                 data = current.options if current.options else {}
                                 try:
                                     user.create_parameter(step=step, data=data, value=current_input)
                                     buffer = ""
                                     break
                                 except WebInputInterrupt as next_e:
                                     prompt = next_e.prompt
                                     autocomplete = None
                                     if next_e.options and next_e.options.get("autocomplete") == "names":
                                         autocomplete = user._collect_autocomplete_names()
                                     current_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}", autocomplete=autocomplete)
                                     current = next_e
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
                        elif e.prompt.startswith("tag weight"):
                             step = e.options.get("tag_step") if e.options else None
                             data = e.options if e.options else {}
                             next_step = user.tag_link_next(step, data, cli_input)
                             while next_step:
                                 prompt = next_step["prompt"]
                                 cli_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}")
                                 step = next_step.get("options", {}).get("tag_step")
                                 data = next_step.get("options", {})
                                 next_step = user.tag_link_next(step, data, cli_input)
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
