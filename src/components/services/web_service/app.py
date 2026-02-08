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
from flask import request, send_from_directory

app = Flask(__name__)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('static', 'sw.js')
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
            "actions": {k: {"name": v._name} for k, v in user._actions.items()},
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

@app.route('/api/command', methods=['POST'])
def command():
    data = request.json
    buffer = data.get('buffer', '')
    
    user.load_user()
    
    # Handle pending input first
    if session.pending_input:
        pi = session.pending_input
        session.pending_input = None
        
        p = pi.get("prompt", "")
        t = pi.get("type", "")

        # 1. Attribute/Action Creation
        if p == "attribute name":
            if "payloads" in pi.get("options", {}):
                user.create_attribute_by_id(pi["options"]["payloads"], name=buffer)
            else:
                user.create_attribute(name=buffer)
        
        elif p == "action name":
            user.create_action(pi.get("options", {}).get("buffer", ""), name=buffer)
        
        elif p == "log message":
            user.log(buffer)

        elif p.startswith("agenda ") or "agenda_step" in pi.get("options", {}):
            step = pi.get("options", {}).get("agenda_step")
            data = pi.get("options", {}).get("agenda_data", {})
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
            label = pi.get("options", {}).get("label")
            user.new_sequence(label, buffer)
        
        elif p == "sequence index to delete":
            user.delete_sequence(buffer)

        # 2. General Confirmation
        elif t == "confirm":
             if buffer == pi.get("options", {}).get("code"):
                 action_type = pi.get("options", {}).get("action")
                 payloads = pi.get("options", {}).get("payloads")
                 
                 if action_type == "delete_attribute":
                     user.delete_attribute(payloads, confirmed=True)
                 elif action_type == "delete_action":
                     user.delete_action(payloads, confirmed=True)
                 elif action_type == "journal_drop":
                     from src.components.services.journal_service import journal_service
                     result = journal_service.drop_last_day()
                     user.add_message(result)
                 else:
                     user.add_message("Confirmed.")
             else:
                 user.add_message("Cancelled.")
        
        elif t == "confirm_day":
            log_text = pi.get("options", {}).get("text")
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

        elif t == "numeric" and "action_id" in pi.get("options", {}):
            try:
                val = int(buffer)
                action_id = pi["options"]["action_id"]
                payloads = [action_id[1:]]
                result = user.act(payloads, value=val)
                _handle_result(result)
            except ValueError:
                user.add_message("Invalid numeric value.")

        user.save_user()
        return jsonify({"completed": True, "clear": True})

    # Process Command
    try:
        # Standard Dial Processing (Prefixes like : or / are no longer special-cased here)
        completed, result = dial.process(buffer)
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
        remaining = dial.get_length(buffer)
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
                info = dial.OBJECTS.get(char) or dial.INTERACTIONS.get(char)
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
            "complete": (remaining == 0 and len(buffer) > 0)
        })

    except Exception as e:
        return jsonify({ "preview": f"[err] {e}", "remaining": -1, "complete": False })


def _resolve_name(prefix_char, id_value):
    """Tenta mapear um ID extraído para o nome da entidade correspondente."""
    try:
        # Action  → prefixo 5
        action_id = f"5{id_value}"
        if action_id in user._actions:
            return user._actions[action_id]._name

        # Attribute → prefixo 8
        attr_id = f"8{id_value}"
        if attr_id in user._attributes:
            return user._attributes[attr_id]._name
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
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
