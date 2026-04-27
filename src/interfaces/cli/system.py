import os
import sys
import time 
import select
import readchar

from src.interfaces.cli.ui.interface import ui
from src.application.dial_interaction.dial_digest import dial
from src.domain.entities.entity_manager import EntityManager
from src.application.services.challenge_service import ChallengeManager
from src.application.services.journal_service import journal_service

from src.domain.constants import (
    user,
    OBJECTS,
    INTERACTIONS,
    SINGLE_COMMANDS,
    COMMANDS
)

class PromptCancelled(Exception):
    pass

ESC_SEQ_TIMEOUT = 0.4

def _read_cli_key():
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                deadline = time.monotonic() + ESC_SEQ_TIMEOUT
                seq = ""
                while time.monotonic() < deadline:
                    timeout = max(0, deadline - time.monotonic())
                    if not select.select([sys.stdin], [], [], timeout)[0]:
                        break
                    seq += sys.stdin.read(1)
                    if len(seq) >= 2:
                        if seq[0] in ("[", "O") and seq[1] in ("A", "B", "C", "D", "H", "F"):
                            return f"\x1b{seq[0]}{seq[1]}"
                        if len(seq) >= 3 and seq[0] == "[" and seq[1] in ("1", "2", "3", "4", "5", "6", "7", "8") and seq[2] in ("A", "B", "C", "D", "H", "F"):
                            return f"\x1b{seq}"
                        break
                return "\x1b"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        return readchar.readkey()

def _prompt_cli_input(message, autocomplete=None, history=None):
    ui.clear_screen()
    print(f"{message} [Esc cancela]")
    matches = sorted({
        str(item).strip().lower()
        for item in (autocomplete or [])
        if str(item).strip()
    })
    history_items = []
    seen_history = set()
    for item in (history or []):
        value = str(item).strip().lower()
        if value and value not in seen_history:
            seen_history.add(value)
            history_items.append(value)
    typed = ""
    nav_mode = None
    nav_base = ""
    nav_options = []
    nav_index = -1

    def redraw():
        sys.stdout.write("\r\033[K")
        sys.stdout.write(f"> {typed}")
        sys.stdout.flush()

    def reset_navigation():
        nonlocal nav_mode, nav_base, nav_options, nav_index
        nav_mode = None
        nav_base = ""
        nav_options = []
        nav_index = -1

    def current_options():
        if nav_mode == "completion":
            return [m for m in matches if m.startswith(nav_base)]
        if nav_mode == "history":
            return history_items
        prefix = typed.strip().lower()
        if prefix:
            return [m for m in matches if m.startswith(prefix)]
        return history_items

    def step_options(direction):
        nonlocal typed, nav_mode, nav_base, nav_options, nav_index
        options = current_options()
        if not options:
            return

        if nav_mode in ("completion", "history"):
            mode = nav_mode
            prefix = nav_base if nav_mode == "completion" else ""
        else:
            prefix = typed.strip().lower()
            mode = "completion" if prefix else "history"

        if nav_mode != mode or nav_base != prefix or nav_options != options:
            nav_mode = mode
            nav_base = prefix
            nav_options = options
            nav_index = -1

        if direction == "up":
            if nav_index < len(options) - 1:
                nav_index += 1
            else:
                return
        else:
            if nav_index > 0:
                nav_index -= 1
            else:
                nav_index = -1
                typed = nav_base if nav_mode == "completion" else ""
                redraw()
                return

        typed = nav_options[nav_index]
        redraw()

    redraw()
    while True:
        key = _read_cli_key()
        if key == "\x1b":
            sys.stdout.write("\r\033[K\n")
            sys.stdout.flush()
            ui.clear_screen()
            raise PromptCancelled()
        if key in ("\r", "\n"):
            sys.stdout.write("\r\033[K\n")
            sys.stdout.flush()
            break
        if key in ("\b", "\x7f", "\x08"):
            if typed:
                typed = typed[:-1]
                reset_navigation()
                redraw()
            continue
        if key in ("\t", "\x1b[A", "\x1b[B"):
            if key == "\t" or key == "\x1b[A":
                step_options("up")
            else:
                step_options("down")
            continue
        if len(key) == 1:
            typed += key.lower() if key.isalpha() else key
            reset_navigation()
            redraw()

    ui.clear_screen()
    return typed

def _handle_web_input_interrupt(e, current_buffer, clear_command_buffer):
    from src.interfaces.cli.ui.interface import WebInputInterrupt
    try:
        if e.prompt == "group confirm":
             with open("/tmp/group_debug.log", "a") as _f:
                 _f.write(f"GROUP CONFIRM HIT: parent={e.options.get('parent')} children={e.options.get('children')}\n")
             parent = e.options.get("parent", "")
             children = e.options.get("children", [])
             sys.stdout.write("\033[2J\033[H")
             sys.stdout.write(f"\n  GROUP: {parent}\n\n")
             if not children:
                 sys.stdout.write("  (no matching child actions found)\n\n")
             for v, name, _cid in children:
                 sys.stdout.write(f"    {v} x {name}\n")
             sys.stdout.write("\n  [y] confirmar  [outro] cancelar\n\n")
             sys.stdout.flush()
             key = _read_cli_key()
             if key and key.lower() == 'y' and children:
                 for child_value, child_name, child_id in children:
                     try:
                         user.act([child_id[1:]], value=str(child_value), _group_depth=1)
                     except WebInputInterrupt as next_e:
                         _handle_web_input_interrupt(next_e, current_buffer, clear_command_buffer)
             clear_command_buffer()
             return True

        ui.render(current_buffer, force_print=True)
        guide = f"[ INPUT REQUIRED ] {e.prompt}"
        if e.type:
            guide += f" ({e.type})"
        autocomplete = None
        if e.prompt == "log message":
             journal_service._load_logs_data()
             autocomplete = [
                 entry.get("content", "")
                 for entry in reversed(journal_service.logs)
                 if isinstance(entry, dict) and str(entry.get("content", "")).strip()
             ]
             history = autocomplete
        elif e.options and e.options.get("autocomplete") == "names":
             autocomplete = user._collect_autocomplete_names()
        else:
             history = None
        cli_input = _prompt_cli_input(guide, autocomplete=autocomplete, history=history if e.prompt == "log message" else None)

        if e.prompt == "log message":
             user.add_log_entry(cli_input)
             clear_command_buffer()
        elif e.prompt == "status name":
             user.create_status(e.options.get("buffer", ""), name=cli_input)
             clear_command_buffer()
        elif e.prompt == "tag name":
             user.create_tag(name=cli_input)
             clear_command_buffer()
        elif e.prompt == "attribute name":
             user.create_attribute(name=cli_input)
             clear_command_buffer()
        elif e.prompt in ("unit type", "difficulty (1-5)", "action name"):
             current = e
             current_input = cli_input
             while True:
                 step = current.options.get("create_step") if current.options else None
                 data = current.options if current.options else {}
                 try:
                     user.create_action(step=step, data=data, value=current_input)
                     clear_command_buffer()
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
                     clear_command_buffer()
                     break
                 except WebInputInterrupt as next_e:
                     prompt = next_e.prompt
                     autocomplete = None
                     if next_e.options and next_e.options.get("autocomplete") == "names":
                         autocomplete = user._collect_autocomplete_names()
                     current_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {prompt}", autocomplete=autocomplete)
                     current = next_e
        elif e.prompt in ("shop item name", "shop item cost"):
             current = e
             current_input = cli_input
             while True:
                 step = current.options.get("create_step") if current.options else None
                 data = current.options if current.options else {}
                 try:
                     user.create_shop_item(step=step, data=data, value=current_input)
                     clear_command_buffer()
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
             clear_command_buffer()
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
             clear_command_buffer()
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
             clear_command_buffer()
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
             clear_command_buffer()
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
             clear_command_buffer()
        elif e.prompt == "sequence label":
             label_input = cli_input
             try:
                 user.new_sequence(label=label_input)
             except WebInputInterrupt as next_e:
                 sv_input = _prompt_cli_input(f"[ INPUT REQUIRED ] {next_e.prompt}")
                 user.new_sequence(label=label_input, start_value=sv_input)
             clear_command_buffer()
        elif e.prompt == "start value (integer)":
             pass
        elif e.prompt == "sequence index for action link":
             user.sequence_add_action(
                 e.options.get("action_id_suffix"),
                 sequence_index=cli_input,
             )
             clear_command_buffer()
        elif e.prompt == "sequence id to delete":
             user.delete_sequence(cli_input)
             clear_command_buffer()
        elif e.prompt == "action note":
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
                 clear_command_buffer()
        return True
    except PromptCancelled:
        user.add_message("Cancelled.")
        user.save_user()
        clear_command_buffer()
        return False

def dial_start():
    user.load_user()
    em = EntityManager()
    cm = ChallengeManager(user, em)
    
    try:
        buffer = ""
        ui.home_input_armed = True

        def clear_command_buffer():
            nonlocal buffer
            buffer = ""
            ui.home_input_armed = True

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

            key = _read_cli_key()
            
            if key == '\x1b':
                buffer = ""
                ui.home_input_armed = False
            if key in ('\b', '\x7f', '\x08'):
                if buffer:
                    buffer = buffer[:-1]
            elif key in ('\r', '\n'):
                if buffer:
                    try:
                        submitted_command = buffer
                        completed, result = dial.process(buffer, force=True)
                        if completed:
                            clear_command_buffer()
                            ui.add_command_history(submitted_command)
                            _handle_result(result, em, ui)
                    except Exception as e:
                        # In case of WebInputInterrupt, we need to import it inside to avoid circular imports if possible
                        # or assume it's the one. Common pattern: check class name or import.
                        from src.interfaces.cli.ui.interface import WebInputInterrupt
                        if isinstance(e, WebInputInterrupt):
                            if not _handle_web_input_interrupt(e, buffer, clear_command_buffer):
                                continue
                        else:
                            raise e
            elif buffer == "" and not ui.home_input_armed:
                ui.handle_idle_navigation(key)
            elif key in ("\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"):
                continue
            elif len(key) == 1 and (key.isdigit() or key in " :/._-+=()*&^%$#@!?,<>{}[]|\\~`'\""):
                buffer += key
            

            if buffer and not buffer.startswith(':') and not buffer.startswith('/'):
                try:
                    submitted_command = buffer
                    completed, result = dial.process(buffer, force=False)
                    
                    if completed:
                        clear_command_buffer()
                        ui.add_command_history(submitted_command)
                        _handle_result(result, em, ui)
                except Exception as e:
                     from src.interfaces.cli.ui.interface import WebInputInterrupt
                     if isinstance(e, WebInputInterrupt):
                        if not _handle_web_input_interrupt(e, buffer, clear_command_buffer):
                            continue
                
    except KeyboardInterrupt:
        print("\nBYE")
        sys.exit(0)

def _handle_result(result, em, ui):
    from src.domain.constants import user
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
