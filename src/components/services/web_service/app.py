from flask import Flask, render_template, jsonify
import sys
import os

# Add project root to path to import components
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

from src.components.data.constants import user
from src.components.entitys.entity_manager import EntityManager
from src.components.services.UI.interface import ui, WebInputInterrupt
from src.components.services.dial_interaction.dial_digest import dial
from src.components.services.journal_service import journal_service
from src.components.services.web_service.web_menu_service import (
    get_settings,
    toggle_agent,
    cycle_mode,
    list_packages,
    import_package,
)
from src.components.services.fountain_service import fountain_service
from flask import request, send_from_directory

app = Flask(__name__)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('static', 'sw.js')

@app.route('/media/<path:filename>')
def serve_media(filename):
    media_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../assets/media"))
    return send_from_directory(media_dir, filename)

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    audio_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../assets/audio"))
    return send_from_directory(audio_dir, filename)

@app.route('/assets/audio/<path:filename>')
def serve_assets_audio(filename):
    audio_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../assets/audio"))
    return send_from_directory(audio_dir, filename)
em = EntityManager()
ui.web_mode = True

class SessionManager:
    def __init__(self):
        self.pending_input = None # { "prompt": "...", "type": "...", "context": "...", "action": func }
        self.last_buffer = ""

session = SessionManager()

def _handle_result(result):
    if result is None: return
    
    # Standard result handling
    current_him = em.get_entity()
    if current_him and current_him.messages:
        user.messages.extend(current_him.messages)
        current_him.clear_messages()

    if isinstance(result, (int, float)) and not isinstance(result, bool) and result > 0:
        if current_him:
            current_him.offer(result)
            if current_him.messages:
                user.messages.extend(current_him.messages)
                current_him.clear_messages()

@app.route('/')
def index():
    user.load_user()
    current_entity = em.get_entity()
    entity_info = {
        "name": current_entity.__class__.__name__ if current_entity else "None",
        "satisfaction": current_entity.satisfaction if current_entity else 0,
        "active": current_entity is not None
    }
    return render_template('index.html', user=user, entity=entity_info)

@app.route('/api/status')
def status():
    user.load_user()
    # Ensure daily refill also applies in web view
    user.refill_daily_tokens()
    current_entity = em.get_entity()
    
    # Add web buffer messages
    messages = list(user.messages)
    messages.extend(ui.web_buffer)
    ui.web_buffer = []
    user.clear_messages()
    
    resp = {
        "user": {
            "score": user.score,
            "value": user._value,
            "total_points": user.total_points,  # ← ADICIONADO
            "attributes": {k: {"name": v._name, "score": v.total_score} for k, v in user._attributes.items()},
            "actions": {k: {"name": v._name} for k, v in user._actions.items() if not getattr(v, "_deleted", False)},
            "parameters": {
                k: {
                    "name": v._name,
                    "value_type": v._value_type,
                    "logic_type": v._logic_type,
                    "value": v._value,
                }
                for k, v in user._parameters.items()
            },
            "tags": {k: {"name": v._name} for k, v in user._tags.items()},
            "metadata": user.metadata
        },
        "entity": {
            "name": current_entity.__class__.__name__ if current_entity else "None",
            "satisfaction": current_entity.satisfaction if current_entity else 0,
            "active": current_entity is not None
        },
        "messages": messages,
        "pending": session.pending_input,
        "is_sleeping": user.metadata.get("is_sleeping", False)
    }
    return jsonify(resp)

@app.route('/api/boot')
def boot():
    try:
        user.load_user()
        current_entity = em.get_entity()
        progress = 40
        message = "User loaded"
        if current_entity:
            progress = 80
            message = "Entity ready"
        if user._attributes is not None and user._actions is not None:
            progress = 100
            message = "Backend ready"
        return jsonify({ "progress": progress, "message": message, "ready": progress >= 100 })
    except Exception as e:
        return jsonify({ "progress": 0, "message": f"Backend error: {e}", "ready": False })

@app.route('/api/command', methods=['POST'])
def command():
    data = request.json or {}
    buffer = data.get('buffer', '')
    
    user.load_user()
    
    # Handle pending input first
    if session.pending_input:
        pi = session.pending_input
        session.pending_input = None

        try:
            p = pi.get("prompt", "")
            t = pi.get("type", "")
            options = pi.get("options") or {}

            # 1. Attribute/Action Creation
            if p == "attribute name":
                if "payloads" in options:
                    user.create_attribute_by_id(options.get("payloads"), name=buffer)
                else:
                    user.create_attribute(name=buffer)
            
            elif p in ("unit type", "difficulty (1-5)", "action name"):
                step = options.get("create_step") if options else None
                data = options if options else {}
                try:
                    user.create_action(step=step, data=data, value=buffer)
                except WebInputInterrupt as e:
                    session.pending_input = {"prompt": e.prompt, "type": e.type, "options": e.options, "context": {"buffer": buffer}}
                    user.save_user()
                    return jsonify({"completed": True, "clear": True})

            elif p == "status name":
                user.create_status(options.get("buffer", ""), name=buffer)

            elif p == "tag name":
                user.create_tag(name=buffer)

            elif p.startswith("parameter value"):
                param_id = options.get("param_id")
                status_id = options.get("status_id")
                user._attach_status_to_param(param_id, status_id, buffer)

            elif p.startswith("parameter regen") or p.startswith("parameter start value"):
                step = options.get("param_step")
                data = options or {}
                next_step = user.parameter_init_next(step, data, buffer)
                if next_step:
                    session.pending_input = next_step
                    return jsonify({"completed": True, "clear": True})
            elif p.startswith("edit action") or p.startswith("edit attribute") or p.startswith("edit parameter") or p.startswith("edit status") or p.startswith("edit tag"):
                step = options.get("edit_step")
                data = options or {}
                if step and step.startswith("action_"):
                    next_step = user.action_edit_next(step, data, buffer)
                else:
                    next_step = user.misc_edit_next(step, data, buffer)
                if next_step:
                    session.pending_input = next_step
                    return jsonify({"completed": True, "clear": True})
            elif p.startswith("tag weight"):
                step = options.get("tag_step")
                data = options or {}
                next_step = user.tag_link_next(step, data, buffer)
                if next_step:
                    session.pending_input = next_step
                    return jsonify({"completed": True, "clear": True})

            elif p == "parameter name":
                step = options.get("create_step") if options else None
                data = options if options else {}
                try:
                    user.create_parameter(step=step, data=data, value=buffer)
                except WebInputInterrupt as e:
                    session.pending_input = {"prompt": e.prompt, "type": e.type, "options": e.options, "context": {"buffer": buffer}}
                    user.save_user()
                    return jsonify({"completed": True, "clear": True})
            elif p in (
                "parameter type (1 mark, 2 percentage)",
                "parameter logic (1 Emotional, 2 Ambiental, 3 Fisiologic)",
            ):
                step = options.get("create_step") if options else None
                data = options if options else {}
                try:
                    user.create_parameter(step=step, data=data, value=buffer)
                except WebInputInterrupt as e:
                    session.pending_input = {"prompt": e.prompt, "type": e.type, "options": e.options, "context": {"buffer": buffer}}
                    user.save_user()
                    return jsonify({"completed": True, "clear": True})
            
            elif p == "log message":
                user.log(buffer)

            elif p.startswith("agenda ") or "agenda_step" in options:
                step = options.get("agenda_step")
                data = options.get("agenda_data", {})
                next_step = user.agenda_wizard_next(step, data, buffer)
                if next_step:
                    session.pending_input = next_step
                    return jsonify({"completed": True, "clear": True})

            elif p == "sequence label":
                # This is first step of new_sequence
                session.pending_input = {
                    "prompt": "start value (integer)",
                    "type": "numeric",
                    "options": {"label": buffer}
                }
                return jsonify({"completed": True, "clear": True})

            elif p == "start value (integer)":
                label = options.get("label")
                user.new_sequence(label, buffer)
            
            elif p == "sequence index to delete":
                user.delete_sequence(buffer)

            # 2. General Confirmation
            elif t == "confirm":
                 if buffer == options.get("code"):
                     action_type = options.get("action")
                     payloads = options.get("payloads")
                     
                     if action_type == "delete_attribute":
                         user.delete_attribute(payloads, confirmed=True)
                     elif action_type == "delete_action":
                         user.delete_action(payloads, confirmed=True)
                     elif action_type == "delete_status":
                         user.delete_status(payloads, confirmed=True)
                     elif action_type == "delete_parameter":
                         user.delete_parameter(payloads, confirmed=True)
                     elif action_type == "delete_tag":
                         user.delete_tag(payloads, confirmed=True)
                     elif action_type == "journal_drop":
                         from src.components.services.journal_service import journal_service
                         result = journal_service.drop_last_day()
                         user.add_message(result)
                     else:
                         user.add_message("Confirmed.")
                 else:
                     user.add_message("Cancelled.")
            
            elif t == "confirm_day":
                log_text = options.get("text")
                from src.components.services.journal_service import journal_service
                if buffer == "1":
                    journal_service.add_log(log_text, auto_confirm=True)
                else:
                    # If 0, we could prompt for custom day, but let's simplify or handle it
                    # For now, if not 1, assume current day or handle as custom day input if it was a number > 1
                    try:
                        if int(buffer) > 1:
                            journal_service.add_log(log_text, manual_date=buffer)
                        else:
                            journal_service.add_log(log_text, auto_confirm=True)
                    except:
                        journal_service.add_log(log_text, auto_confirm=True)

            elif t == "numeric" and "action_id" in options:
                try:
                    val = int(buffer)
                    action_id = options["action_id"]
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
                    payloads = [payload]
                    result = user.act(payloads, value=val)
                    _handle_result(result)
                except ValueError:
                    user.add_message("Invalid numeric value.")

            user.save_user()
            return jsonify({"completed": True, "clear": True})
        except Exception as e:
            user.add_message(f"[ ERROR ] {str(e)}")
            user.save_user()
            return jsonify({"completed": True, "clear": True})

    # Process Command
    try:
        # Standard Dial Processing (Prefixes like : or / are no longer special-cased here)
        completed, result = dial.process(buffer, force=True)
        if completed:
            _handle_result(result)
            user.save_user()
            return jsonify({"completed": True, "clear": True})

    except WebInputInterrupt as e:
        session.pending_input = {"prompt": e.prompt, "type": e.type, "options": e.options, "context": {"buffer": buffer}}
        return jsonify({"completed": True, "clear": True})
    
    except Exception as e:
        print(f"Server Error: {e}")
        user.add_message(f"[ SERVER ERROR ] {str(e)}")
        return jsonify({"completed": True, "clear": True})
    
    return jsonify({"completed": False, "clear": False})

@app.route('/api/cancel', methods=['POST'])
def cancel():
    session.pending_input = None
    user.add_message("Cancelled.")
    user.save_user()
    return jsonify({"ok": True})

@app.route('/api/preview', methods=['GET'])
def preview():
    """
    Retorna estado do parsing em tempo real sem executar.
    Frontend chama a cada keystroke: GET /api/preview?buffer=501
    Retorna:  { "preview": "⭐ (Push Ups) -> Add -> _", "remaining": 1, "complete": false }
    """
    buffer = request.args.get('buffer', '').strip()

    if not buffer:
        return jsonify({ "preview": "", "remaining": 0, "complete": False })

    try:
        user.load_user()
        state = dial.get_state(buffer)
        remaining = state.get("remaining", 0)
        phrase, payloads, is_single = dial.parse_buffer(buffer)

        tokens = []

        if is_single:
            # ── SINGLE_COMMAND (ex: :log, 71, 72…) ──
            for cmd_prefix, info in dial.SINGLE_COMMANDS.items():
                if buffer.startswith(cmd_prefix):
                    tokens.append(info.get("label", cmd_prefix))
                    # se tem payload parcial, mostra
                    payload_len = info["len"]
                    if payload_len > 0:
                        payload = buffer[len(cmd_prefix):]
                        if payload:
                            tokens.append(payload)
                    break
        else:
            # ── OBJECT + INTERACTION (ex: 5 01 2 …) ──
            ptr = 0
            while ptr < len(buffer):
                char = buffer[ptr]
                info = dial._get_info_for_char(buffer, ptr)
                if not info:
                    break

                ptr += 1
                label = info["label"]

                # resolve payload → nome da entidade
                if info["len"] > 0:
                    id_slice = buffer[ptr : ptr + info["len"]]
                    ptr += info["len"]
                    if id_slice:
                        name = _resolve_name(char, id_slice)
                        label = f"{label} ({name})" if name else f"{label} ({id_slice})"

                tokens.append(label)

        # monta string com arrows
        preview_str = " -> ".join(tokens)

        # cursor no final se ainda falta caracteres
        if remaining > 0:
            preview_str += " -> _"

        return jsonify({
            "preview": preview_str,
            "remaining": remaining,
            "complete": (remaining == 0 and len(buffer) > 0),
            "ambiguous": bool(state.get("ambiguous"))
        })

    except Exception as e:
        return jsonify({ "preview": f"[err] {e}", "remaining": -1, "complete": False })


def _resolve_name(prefix_char, id_value):
    """Map an ID to a name based on its prefix to avoid cross-type collisions."""
    try:
        if prefix_char == "5":
            raw = str(id_value)
            if len(raw) >= 2:
                action_id = f"5{raw[-2:]}"
                if action_id in user._actions:
                    return user._actions[action_id]._name
        elif prefix_char == "8":
            attr_id = f"8{id_value}"
            if attr_id in user._attributes:
                return user._attributes[attr_id]._name
        elif prefix_char == "4":
            status_id = f"4{id_value}"
            if status_id in user._statuses:
                return user._statuses[status_id]._name
        elif prefix_char == "1":
            tag_id = f"1{id_value}"
            if tag_id in user._tags:
                return user._tags[tag_id]._name
        elif prefix_char == "6":
            param_id = f"6{id_value}"
            if param_id in user._parameters:
                return user._parameters[param_id]._name
    except:
        pass
    return None

@app.route('/api/log_suggestions', methods=['GET'])
def log_suggestions():
    """Return recent log contents for autocomplete."""
    try:
        journal_service._load_logs_data()
        suggestions = []
        base = ""
        today = None
        try:
            from datetime import datetime
            today = datetime.now().strftime("%d %m %Y")
        except Exception:
            today = None

        if today:
            for entry in journal_service.logs:
                if not isinstance(entry, dict):
                    continue
                ts = entry.get("timestamp", "")
                content = entry.get("content")
                if not ts or not content:
                    continue
                if ts.startswith(today):
                    base = str(content).strip()
                    break

        for entry in reversed(journal_service.logs):
            content = entry.get("content") if isinstance(entry, dict) else None
            if not content:
                continue
            content = str(content).strip()
            if content and content not in suggestions:
                suggestions.append(content)
            if len(suggestions) >= 60:
                break
        return jsonify({ "suggestions": suggestions, "base": base })
    except Exception:
        return jsonify({ "suggestions": [], "base": "" })

@app.route('/api/menu/settings', methods=['GET', 'POST'])
def menu_settings():
    if request.method == 'GET':
        return jsonify(get_settings())
    data = request.json or {}
    action = data.get("action")
    if action == "toggle_agent":
        return jsonify(toggle_agent())
    if action == "cycle_mode":
        return jsonify(cycle_mode())
    return jsonify(get_settings())

@app.route('/api/menu/packages', methods=['GET'])
def menu_packages():
    return jsonify({ "packages": list_packages() })

@app.route('/api/menu/packages/import', methods=['POST'])
def menu_packages_import():
    data = request.json or {}
    key = data.get("key")
    return jsonify(import_package(key))

@app.route('/api/fountain/offer', methods=['POST'])
def fountain_offer():
    data = request.json or {}
    try:
        value = int(data.get("value", 0))
    except Exception:
        value = 0
    spent = fountain_service.offer(value)
    remaining = user.metadata.get("score", 0) if not user._attributes else user.score
    return jsonify({ "spent": spent, "total": fountain_service.total_offer, "remaining": remaining })
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
