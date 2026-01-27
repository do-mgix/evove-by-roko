from flask import Flask, render_template, jsonify
import sys
import os

# Add project root to path to import components
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

from src.components.data.constants import user
from src.components.entitys.entity_manager import EntityManager
from src.components.services.UI.interface import ui, WebInputInterrupt
from src.components.services.dial_interaction.dial_digest import dial
from flask import request

app = Flask(__name__)
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
        "pending": session.pending_input
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
            if "payloads" in pi.get("options", {}): # Note: options might contain context
                user.create_attribute_by_id(pi["options"]["payloads"], name=buffer)
            else:
                user.create_attribute(name=buffer)
        
        elif p == "action name":
            user.create_action(pi.get("options", {}).get("buffer", ""), name=buffer)
            
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
                     result = journal_service.drop_last_day(confirmed=True)
                     user.add_message(result)
                 else:
                     user.add_message("Confirmed.")
             else:
                 user.add_message("Cancelled.")
        
        elif t == "numeric" and "action_id" in pi.get("options", {}):
            try:
                val = int(buffer)
                # action_id is like '526', payloads expects ['26']
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
        # 1. Handle Special Commands (Special prefix / or :)
        if buffer.startswith(':'):
            from src.components.services.journal_service import journal_service
            msg = buffer[1:].strip()
            if msg:
                journal_service.add_log(msg)
                user.add_message(f"Log buffered: {msg}")
            return jsonify({"completed": True, "clear": True})

        elif buffer == "/cloud":
            from src.components.services.journal_service import journal_service
            result = journal_service.sync_to_cloud()
            user.add_message(result)
            return jsonify({"completed": True, "clear": True})

        elif buffer == "/drop":
            from src.components.services.journal_service import journal_service
            result = journal_service.drop_last_day()
            user.add_message(result)
            return jsonify({"completed": True, "clear": True})

        # 2. Standard Dial Processing
        completed, result = dial.process(buffer)
        if completed:
            _handle_result(result)
            user.save_user()
            return jsonify({"completed": True, "clear": True})

    except WebInputInterrupt as e:
        session.pending_input = {"prompt": e.prompt, "type": e.type, "options": e.options, "context": {"buffer": buffer}}
        return jsonify({"completed": True, "clear": True})
    
    return jsonify({"completed": False, "clear": False})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
