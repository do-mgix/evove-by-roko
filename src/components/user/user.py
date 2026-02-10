# ==================== USER.PY ====================
import json, os, time
from datetime import datetime, timedelta
from src.components.entitys.entity_manager import EntityManager
from src.components.user.attributes.attribute import Attribute
from src.components.user.actions.action import Action
from src.components.user.parameters.parameter import Parameter
from src.components.user.statuses.status import Status
from src.components.user.tags.tag import Tag
from src.components.services.journal_service import journal_service
from src.components.services.agenda_service import agenda_service
from src.components.services.tutorial_service import TutorialService

class User:
    def __init__(self):
        him = EntityManager().get_entity()
        self._attributes = {} 
        self._actions = {} 
        self._parameters = {}
        self._statuses = {}
        self._shop_action_links = {}
        self._shop_entitlements = {}
        self._shop_item_entitlements = {}
        self._tags = {}
        self._action_tags = {}
        self._param_tags = {}
        self.logic_types = {}
        self.sublogic_types = {}
        self._value = 0
        self.messages = []  # Buffer de mensagens para o render
        self.metadata = {
            "mode": "progressive",
            "virtual_agent_active": True,
            "unlocked_packages": ["basics"],
            "tokens": 0,
            "max_tokens": 50,
            "daily_refill": 10,
            "refill_cooldown": 12,
            "refill_cooldown": 12,
            "last_token_refill": datetime.now().strftime("%Y-%m-%d"),
            "tutorial": {
                "has_created_action": {"status": False, "priority": 10},
                "welcomed": {"status": False, "priority": 11}
            }
        }
        self.load_user()
        self._ensure_tutorial_state()
        self.tutorial = TutorialService(self)
        self.tutorial.maybe_show_startup()

    def refill_daily_tokens(self, now=None):
        """Refill once per day based on date (ignores time)."""
        # Always reload to reduce duplicate refills across processes
        self.load_user()

        if now is None:
            now = datetime.now()

        # Try to acquire a simple inter-process lock (best-effort)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        data_dir = os.path.join(src_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        lock_path = os.path.join(data_dir, "user.json.lock")

        lock_fd = None
        start = time.time()
        while lock_fd is None and (time.time() - start) < 2.0:
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                time.sleep(0.05)

        if lock_fd is None:
            # Another process is updating; avoid duplicate refill
            return False

        try:
            today_str = now.strftime("%Y-%m-%d")
            last_str = self.metadata.get("last_token_refill")

            if not last_str:
                self.metadata["last_token_refill"] = today_str
                self.save_user()
                return False

            # Accept both date-only and full ISO strings
            try:
                last_date = datetime.fromisoformat(last_str).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                self.metadata["last_token_refill"] = today_str
                self.save_user()
                return False

            if last_date == today_str:
                return False

            amount = self.metadata.get("daily_refill", self.metadata["daily_refill"])
            # Set date first so add_tokens save includes it
            self.metadata["last_token_refill"] = today_str
            self.add_tokens(amount)
            return True
        finally:
            try:
                if lock_fd is not None:
                    os.close(lock_fd)
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception:
                # If cleanup fails, avoid crashing caller
                pass

    def regenerate_tokens(self):

        now = datetime.now()
        
        last_str = self.metadata.get("last_token_refill")
        if not last_str:
            # Se nunca foi definido, inicializa agora
            self.metadata["last_token_refill"] = now.strftime("%Y-%m-%d")
            self.save_user()
            return
        
        # Garante que last é datetime (suporta ambos formatos para retrocompatibilidade)
        try:
            if isinstance(last_str, str):
                last = datetime.fromisoformat(last_str)
            else:
                last = last_str
        except (ValueError, TypeError):
            # Se formato inválido, reinicializa
            self.metadata["last_token_refill"] = now.strftime("%Y-%m-%d")
            self.save_user()
            return
        
        time_passed = (now - last).total_seconds() / 3600  # horas
        refill_cooldown = self.metadata.get("refill_cooldown", 12)
        daily_refill = self.metadata.get("daily_refill", 20)
        
        tokens_to_add = int(time_passed / refill_cooldown * daily_refill)
        
        if tokens_to_add > 0:
            # Usa add_tokens() que já faz:
            #   - limite ao max_tokens
            #   - adiciona mensagem ao buffer
            #   - chama save_user()
            self.add_tokens(tokens_to_add)
            
            # Atualiza last_token_refill com formato consistente (string YYYY-MM-DD)
            self.metadata["last_token_refill"] = now.strftime("%Y-%m-%d")
            self.save_user()  

    def add_tokens(self, amount):
        """Adds tokens up to max_tokens limit"""
        max_t = self.metadata.get("max_tokens", 50)
        current = self.metadata.get("tokens", 0)
        new_total = min(max_t, current + amount)
        self.metadata["tokens"] = new_total
        self.add_message(f"Tokens added: {amount}. Current balance: {new_total}/{max_t}")
        self.save_user()

    def spend_tokens(self, amount):
        """Spends tokens if possible. Returns True if successful."""
        current = self.metadata.get("tokens", 0)                       
        if current >= amount:
            self.metadata["tokens"] = current - amount
            self.add_message(f"Tokens spent: {amount}. Current balance: {self.metadata['tokens']}")
            self.save_user()
            return True
        else:
            self.add_message(f"Insufficient tokens! Needed: {amount}, Current: {current}")
            return False
            
    def clear_messages(self):
        """Limpa o buffer de mensagens"""
        self.messages = []
    
    def add_message(self, msg): 
        """Adiciona mensagem ao buffer""" 
        self.messages.append(msg)
    
    @property
    def next_attr_id(self):        
        if self._attributes:
            higher = max(self._attributes)
            higher = higher[1:3]
            return int(higher) + 1
        else:
            return 1
    
    @property
    def next_action_id(self):
        if self._actions:
            higher = max(self._actions)
            higher = higher[1:3]
            return int(higher) + 1
        else:
            return 1

    @property
    def next_param_id(self):
        if self._parameters:
            higher = max(self._parameters)
            higher = higher[1:3]
            return int(higher) + 1
        else:
            return 1

    @property
    def next_tag_id(self):
        if self._tags:
            higher = max(self._tags)
            higher = higher[1:3]
            return int(higher) + 1
        else:
            return 1

    @property
    def next_status_id(self):
        if self._statuses:
            higher = max(self._statuses)
            higher = higher[1:3]
            return int(higher) + 1
        else:
            return 1
    
    @property
    def score(self):
        if self._attributes:
            total = sum(attr.total_score for attr in self._attributes.values())
            return total / len(self._attributes)
        else:
            return self.metadata.get("score", 0)
 
    @property
    def total_points(self):
        """Soma total de pontos de todas as actions."""
        if self._actions:
            return sum(action.score for action in self._actions.values())
        return 0

    def sleep(self):
        if self._check_sleep():
            return

        # 1. Process Daily Logs (TO PROCESS -> IN WAIT)
        # Aggregates granular logs into daily summary logs in evove26
        process_msg = journal_service.process_daily_logs()
        self.add_message(process_msg)

        # 2. Proceed to Sleep (Git Sync)
        result = journal_service.sleep()
        self.metadata["is_sleeping"] = True
        self.add_message(result)
        self.save_user()

    def nap(self):
        if self._check_sleep():
            return

        #Sleep without git sync
        result = journal_service.nap()
        self.metadata["is_sleeping"] = True
        self.add_message(result)
        self.log("NAP")
        self.save_user()

    def wake(self):
        result = journal_service.wake()
        self.metadata["is_sleeping"] = False
        self.add_message(result)
        self.save_user()
    
    def _check_sleep(self):
        if self.metadata.get("is_sleeping"):
            self.add_message("You are sleeping! Remember to wake up (71) before any operation.")
            return True
        return False

    def act(self, payloads, value=None):
        if self._check_sleep():
            return

        if not payloads or not payloads[0]:
            self.add_message("Invalid action ID.")
            return None

        action_id, action = self._resolve_action_payload(payloads[0])
        if not action:
            return None
        if getattr(action, "_deleted", False):
            self.add_message(f"Action {action_id} is deleted.")
            return None

        if not self._check_shop_access(action_id):
            return None

        original_value = action.value
        score_difference, action_messages = action.execution(manual_value=value)
        value_difference = action.value - original_value

        if value_difference:
            self._apply_tag_effects(action, value_difference)
        
        # Daily Aggregation Logic -> Immediate Log (TO PROCESS)
        action_name = action.name
        executed_value = value if value else 1
        
        try:
            val_int = int(executed_value)
        except:
            val_int = 1 
            
        # Log to logs.json only (TO PROCESS)
        journal_service.add_log(f"{val_int} {action_name.upper()}", auto_confirm=True, custom_status="[TO PROCESS]")

        # Adiciona mensagens da action
        for msg in action_messages:
            self.add_message(msg)

        # Cálculo de Boost por Satisfação
        him = EntityManager().get_entity()
        current_sat = him.satisfaction
        
        boost_multiplier = 1
        if current_sat > 40:
            boost_factor = min(0.5, (current_sat - 40) / 60 * 0.5)
            boost_factor = max(0, boost_factor)
            boost_multiplier = 1 + boost_factor

        final_score_difference = score_difference * boost_multiplier
        if not self._attributes:
            current_score = self.metadata.get("score", 0) or 0
            self.metadata["score"] = current_score + action.score
        self.save_user()
        return final_score_difference

    def _format_logic_id(self, value):
        if value is None:
            return None
        s = str(value)
        if s.isdigit():
            return s.zfill(2)
        return s

    def _resolve_action_payload(self, payload):
        raw = str(payload or "").strip()
        if not raw:
            self.add_message("Invalid action ID.")
            return None, None

        if len(raw) == 2:
            logic_type = None
            sub_logic_type = None
            action_part = raw
        elif len(raw) == 4:
            logic_type = raw[:2]
            sub_logic_type = None
            action_part = raw[2:]
        elif len(raw) == 6:
            logic_type = raw[:2]
            sub_logic_type = raw[2:4]
            action_part = raw[4:]
        else:
            self.add_message("Invalid action ID format.")
            return None, None

        action_id = f"5{action_part}"
        action = self._actions.get(action_id)
        if not action:
            self.add_message(f"\n [ ERROR ] Action ID {action_id} not found. (Loaded Actions: {len(self._actions)})")
            return None, None

        action_logic = self._format_logic_id(getattr(action, "_logic_type", None))
        action_sublogic = self._format_logic_id(getattr(action, "_sub_logic_type", None))

        if logic_type is None:
            if action_logic or action_sublogic:
                self.add_message("Action requires logic type. Use id5/id7.")
                return None, None
        else:
            if logic_type not in self.logic_types:
                self.add_message(f"Logic type {logic_type} not found.")
                return None, None
            if action_logic != logic_type:
                self.add_message(f"Action {action_id} not in logic type {logic_type}.")
                return None, None
            if action_sublogic:
                if sub_logic_type is None:
                    self.add_message(f"Action {action_id} requires sub logic type.")
                    return None, None
                if sub_logic_type != action_sublogic:
                    self.add_message(f"Action {action_id} not in sub logic type {sub_logic_type}.")
                    return None, None
            else:
                if sub_logic_type is not None:
                    self.add_message(f"Action {action_id} has no sub logic type.")
                    return None, None
            if sub_logic_type is not None:
                if sub_logic_type not in self.sublogic_types:
                    self.add_message(f"Sub logic type {sub_logic_type} not found.")
                    return None, None
                subs = self.logic_types.get(logic_type, {}).get("subs", [])
                if sub_logic_type not in subs:
                    self.add_message(f"Sub logic type {sub_logic_type} not allowed for logic {logic_type}.")
                    return None, None

        return action_id, action

    def log(self, text):
        if journal_service.add_log(text):
            self.add_message(f"Log buffered: {text}")
        self.save_user()

    def add_log_entry(self, text=None):
        if self._check_sleep():
            return
        if text is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("log message", type="text")
        self.log(text)

    def agenda_item(self, text):
        return self.add_agenda_item(text)

    def _add_agenda_payload(self, payload):
        if not isinstance(payload, dict):
            self.add_message("Agenda payload must be a JSON object.")
            return

        label = payload.get("label")
        item_type = payload.get("type") or payload.get("item_type")
        related_action = payload.get("related_action")
        schedule = payload.get("schedule")
        max_value = payload.get("max_value", 1)
        current_value = payload.get("current_value", 0)
        first_date = payload.get("first_date")
        last_execution = payload.get("last_execution")

        result = agenda_service.add_item(
            label=label,
            item_type=item_type,
            related_action=related_action,
            schedule=schedule,
            max_value=max_value,
            current_value=current_value,
            first_date=first_date,
            last_execution=last_execution,
        )

        if isinstance(result, dict):
            self.add_message(f"Agenda item added: {result.get('label')}")
        else:
            self.add_message(f"Agenda error: {result}")
        self.save_user()

    def agenda_wizard_next(self, step, data, value):
        data = dict(data or {})
        val = (value or "").strip()

        if step == "label":
            if not val:
                self.add_message("Label is required.")
                return {"prompt": "agenda label", "type": "text", "options": {"agenda_step": "label", "agenda_data": data}}
            data["label"] = val
            return {"prompt": "agenda type (1- Daily, 2- Weekly)", "type": "numeric", "options": {"agenda_step": "type", "agenda_data": data}}

        if step == "type":
            normalized = val.lower()
            if normalized == "everyday":
                normalized = "daily"
            if normalized == "1":
                normalized = "daily"
            if normalized == "2":
                normalized = "weekly"
            if normalized not in {"daily", "weekly"}:
                self.add_message("Type must be 1 (Daily) or 2 (Weekly).")
                return {"prompt": "agenda type (1- Daily, 2- Weekly)", "type": "numeric", "options": {"agenda_step": "type", "agenda_data": data}}
            data["type"] = normalized
            if normalized == "daily":
                return {"prompt": "agenda start time (HH:MM)", "type": "text", "options": {"agenda_step": "daily_start", "agenda_data": data}}
            return {"prompt": "agenda occurrences (1-6)", "type": "numeric", "options": {"agenda_step": "weekly_count", "agenda_data": data}}

        if step == "daily_start":
            if not val:
                self.add_message("Start time is required.")
                return {"prompt": "agenda start time (HH:MM)", "type": "text", "options": {"agenda_step": "daily_start", "agenda_data": data}}
            data["start_time"] = val
            return {"prompt": "agenda end time (HH:MM)", "type": "text", "options": {"agenda_step": "daily_end", "agenda_data": data}}

        if step == "daily_end":
            if not val:
                self.add_message("End time is required.")
                return {"prompt": "agenda end time (HH:MM)", "type": "text", "options": {"agenda_step": "daily_end", "agenda_data": data}}
            data["end_time"] = val
            return {"prompt": "agenda day (optional, monday-friday)", "type": "text", "options": {"agenda_step": "daily_day", "agenda_data": data}}

        if step == "daily_day":
            schedule = {
                "start_time": data.get("start_time"),
                "end_time": data.get("end_time"),
            }
            if val:
                schedule["day"] = val.lower()
            payload = {
                "label": data.get("label"),
                "type": data.get("type"),
                "schedule": schedule,
            }
            self._add_agenda_payload(payload)
            return None

        if step == "weekly_count":
            try:
                count = int(val)
            except Exception:
                count = 0
            if count < 1 or count > 6:
                self.add_message("Weekly occurrences must be between 1 and 6.")
                return {"prompt": "agenda occurrences (1-6)", "type": "numeric", "options": {"agenda_step": "weekly_count", "agenda_data": data}}
            data["week_count"] = count
            data["week_index"] = 1
            data["week_entries"] = []
            return {"prompt": "agenda day 1", "type": "text", "options": {"agenda_step": "weekly_day", "agenda_data": data}}

        if step == "weekly_day":
            if not val:
                self.add_message("Day is required.")
                return {"prompt": f"agenda day {data.get('week_index', 1)}", "type": "text", "options": {"agenda_step": "weekly_day", "agenda_data": data}}
            data["week_current"] = {"day": val.lower()}
            return {"prompt": f"agenda start time {data.get('week_index', 1)} (HH:MM)", "type": "text", "options": {"agenda_step": "weekly_start", "agenda_data": data}}

        if step == "weekly_start":
            if not val:
                self.add_message("Start time is required.")
                return {"prompt": f"agenda start time {data.get('week_index', 1)} (HH:MM)", "type": "text", "options": {"agenda_step": "weekly_start", "agenda_data": data}}
            data["week_current"]["start_time"] = val
            return {"prompt": f"agenda end time {data.get('week_index', 1)} (HH:MM)", "type": "text", "options": {"agenda_step": "weekly_end", "agenda_data": data}}

        if step == "weekly_end":
            if not val:
                self.add_message("End time is required.")
                return {"prompt": f"agenda end time {data.get('week_index', 1)} (HH:MM)", "type": "text", "options": {"agenda_step": "weekly_end", "agenda_data": data}}
            data["week_current"]["end_time"] = val
            data["week_entries"].append(data["week_current"])
            data["week_current"] = {}
            if data["week_index"] < data["week_count"]:
                data["week_index"] += 1
                idx = data["week_index"]
                return {"prompt": f"agenda day {idx}", "type": "text", "options": {"agenda_step": "weekly_day", "agenda_data": data}}

            payload = {
                "label": data.get("label"),
                "type": data.get("type"),
                "schedule": data.get("week_entries", []),
            }
            self._add_agenda_payload(payload)
            return None

        self.add_message("Agenda wizard error: invalid step.")
        return None

    def add_agenda_item(self, text=None):
        if self._check_sleep():
            return
        if text is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("agenda label", type="text", options={"agenda_step": "label", "agenda_data": {}})

        try:
            payload = json.loads(text)
        except Exception:
            self.add_message("Invalid agenda payload. Provide JSON.")
            self.add_message("Example: {\"label\":\"Study\",\"type\":\"daily\",\"schedule\":{\"start_time\":\"09:00\",\"end_time\":\"10:00\"}}")
            return

        self._add_agenda_payload(payload)

    def list_logs(self):
        if self._check_sleep():
            return
        logs = journal_service.list_logs()
        from src.components.services.UI.interface import ui
        ui.show_list(logs, "CURRENT LOG BUFFER")

    def drop_last_log_buffer(self):
        if self._check_sleep():
            return
        result = journal_service.drop_last_buffer_entry()
        self.add_message(result)
        self.save_user()

    def drop_last_day(self):
        if self._check_sleep():
            return
        result = journal_service.drop_last_day()
        self.add_message(result)
        self.save_user()

    def list_sequences(self):
        if self._check_sleep():
            return
        from src.components.services.sequence_service import sequence_service
        info = sequence_service.get_current_sequences_str()
        self.add_message(f"Sequences: {info}")

    def list_days(self):
        if self._check_sleep():
            return
        logs = journal_service.list_days()
        from src.components.services.UI.interface import ui
        # Using show_list to display the file content
        ui.show_list(logs, "EVOVE26 FILE CONTENT")

    def delete_sequence(self, index=None):
        if self._check_sleep():
            return
        if index is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("sequence index to delete", type="numeric")
        try:
            from src.components.services.sequence_service import sequence_service
            msg = sequence_service.delete_sequence(int(index))
            self.add_message(msg)
            self.save_user()
        except ValueError:
            self.add_message("Invalid index.")

    def new_sequence(self, label=None, start_value=None):
        if self._check_sleep():
            return
        if label is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("sequence label", type="text")
        
        if start_value is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("start value (integer)", type="numeric", options={"label": label})

        try:
            val = int(start_value)
            from src.components.services.sequence_service import sequence_service
            msg = sequence_service.create_sequence(label, val)
            self.add_message(msg)
            self.save_user()
        except ValueError:
            self.add_message("Invalid start value. Must be an integer.")
    
    def save_user(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Sobe 2 níveis: user/ -> components/ -> src/
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        data_dir = os.path.join(src_dir, "data")    
        data_file = os.path.join(data_dir, "user.json")

        # Cria o diretório se não existir
        os.makedirs(data_dir, exist_ok=True)

        # Keep score mirrored in metadata for UI consumers
        self.metadata["score"] = self.score
            
        data = {
            "score": self.score,
            "value": self._value,
            "attributes": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._attributes.items()
            },
            "actions": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._actions.items()
            },
            "parameters": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._parameters.items()
            },
            "statuses": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._statuses.items()
            },
            "shop_action_links": self._shop_action_links,
            "shop_entitlements": self._shop_entitlements,
            "shop_item_entitlements": self._shop_item_entitlements,
            "tags": {
                k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self._tags.items()
            },
            "action_tags": self._action_tags,
            "param_tags": self._param_tags,
            "logic_types": self.logic_types,
            "sublogic_types": self.sublogic_types,
            "metadata": self.metadata
        }
    
        try:
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            from src.components.services.backup_service import backup_json
            backup_json(data_file)
            # self.add_message(f"file saved.")
            self.load_user()
        except Exception as e:
            self.add_message(f"Error saving {e}")

    def load_user(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Sobe 2 níveis: user/ -> components/ -> src/
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        data_dir = os.path.join(src_dir, "data")
        data_file = os.path.join(data_dir, "user.json")

        if not os.path.exists(data_file):
            # self.add_message(f"new save file created.")
            self.save_user() 
            return
        
        if os.path.getsize(data_file) == 0:
            self.add_message("empty save file.")
            return
        
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.add_message("corrupted save file.")
            return
        
        self._value = data.get("value", 0)
        self.metadata.update(data.get("metadata", {}))
        self._ensure_tutorial_state()
        self.logic_types = data.get("logic_types", {}) or {}
        self.sublogic_types = data.get("sublogic_types", {}) or {}
        
        self._attributes.clear()
        for attr_id, attr_data in data.get("attributes", {}).items():
            new_attr = Attribute.from_dict(attr_data)
            self._attributes[attr_id] = new_attr
        
        self._actions.clear()
        for action_id, action_data in data.get("actions", {}).items():
            logic_type = self._format_logic_id(action_data.get("logic_type"))
            logic_label = action_data.get("logic_label")
            if logic_type:
                label = logic_label or logic_type
                entry = self.logic_types.get(logic_type) or {"id": logic_type, "label": label, "subs": []}
                entry["label"] = label
                entry.setdefault("subs", [])
                self.logic_types[logic_type] = entry
            sub_logic_type = self._format_logic_id(action_data.get("sub_logic_type"))
            sub_logic_label = action_data.get("sub_logic_label")
            if sub_logic_type:
                self.sublogic_types[sub_logic_type] = {"id": sub_logic_type, "label": sub_logic_label or sub_logic_type}
                if logic_type:
                    entry = self.logic_types.get(logic_type) or {"id": logic_type, "label": logic_label or logic_type, "subs": []}
                    subs = entry.setdefault("subs", [])
                    if sub_logic_type not in subs:
                        subs.append(sub_logic_type)
                    self.logic_types[logic_type] = entry
            new_act = Action.from_dict(action_data)
            self._actions[action_id] = new_act

        self._parameters.clear()
        for param_id, param_data in data.get("parameters", {}).items():
            new_param = Parameter.from_dict(param_data)
            self._parameters[param_id] = new_param

        self._shop_action_links = data.get("shop_action_links", {}) or {}
        self._shop_entitlements = data.get("shop_entitlements", {}) or {}
        self._shop_item_entitlements = data.get("shop_item_entitlements", {}) or {}

        self._statuses.clear()
        for status_id, status_data in data.get("statuses", {}).items():
            new_status = Status.from_dict(status_data)
            self._statuses[status_id] = new_status

        self._tags.clear()
        for tag_id, tag_data in data.get("tags", {}).items():
            new_tag = Tag.from_dict(tag_data)
            self._tags[tag_id] = new_tag
        self._action_tags = data.get("action_tags", {}) or {}
        self._param_tags = data.get("param_tags", {}) or {}
        
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_related_actions'):
                attr.resolve_related_actions(self._actions)
        
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_children'):
                attr.resolve_children(self._attributes)
        
        for attr in self._attributes.values():
            if hasattr(attr, 'resolve_parent'):
                attr.resolve_parent(self._attributes)

        for param in self._parameters.values():
            if param.update_value():
                self._update_statuses_for_param(param)
        if hasattr(self, "tutorial"):
            self.tutorial.maybe_show_startup()

    def _ensure_tutorial_state(self):
        tutorial = self.metadata.get("tutorial")
        if not isinstance(tutorial, dict):
            tutorial = {}
        if "has_created_action" not in tutorial:
            tutorial["has_created_action"] = {"status": False, "priority": 10}
        if "welcomed" not in tutorial:
            tutorial["welcomed"] = {"status": False, "priority": 11}
        self.metadata["tutorial"] = tutorial
    
    

    def open_shop(self):
        """Displays shop items"""
        from src.components.services.shop_service import ShopService
        
        shop = ShopService(self)
        shop.show_items()


    def buy_shop_item(self, item_id=None):
        """Buys a shop item. item_id can be passed from dial or buffer."""
        from src.components.services.shop_service import ShopService
        
        shop = ShopService(self)
        
        # If called from list_actions/dial, it might be a list
        target_id = item_id
        if isinstance(item_id, list) and item_id:
            target_id = "".join(str(part) for part in item_id)
            
        if shop.buy_item(target_id):
            self._grant_shop_entitlement(target_id)
            self.save_user()

    def _normalize_shop_item_id(self, shop_item_id):
        if isinstance(shop_item_id, str):
            return shop_item_id.lstrip("0") or "0"
        return str(shop_item_id).lstrip("0") or "0"

    def _is_entitlement_active(self, expiry_str, now=None):
        if not expiry_str:
            return False
        from datetime import datetime
        if now is None:
            now = datetime.now()
        try:
            expiry = datetime.fromisoformat(expiry_str)
        except Exception:
            return False
        return now <= expiry

    def _grant_shop_entitlement(self, shop_item_id):
        from datetime import datetime, timedelta
        norm_item_id = self._normalize_shop_item_id(shop_item_id)
        expiry = datetime.now() + timedelta(hours=12)
        expiry_str = expiry.isoformat()
        # Track entitlement by item for consistent access checks and UI
        self._shop_item_entitlements[norm_item_id] = expiry_str
        for action_id, linked_item in self._shop_action_links.items():
            linked = self._normalize_shop_item_id(linked_item)
            if linked == norm_item_id:
                self._shop_entitlements[action_id] = expiry_str

    def _get_item_entitlement_from_actions(self, norm_item_id, now=None):
        """Fallback for legacy data where only action entitlements exist."""
        for action_id, linked_item in self._shop_action_links.items():
            linked = self._normalize_shop_item_id(linked_item)
            if linked != norm_item_id:
                continue
            expiry_str = self._shop_entitlements.get(action_id)
            if self._is_entitlement_active(expiry_str, now=now):
                return expiry_str
        return None

    def is_shop_item_purchased(self, shop_item_id):
        norm_item_id = self._normalize_shop_item_id(shop_item_id)
        now = datetime.now()
        expiry_str = self._shop_item_entitlements.get(norm_item_id)
        if self._is_entitlement_active(expiry_str, now=now):
            return True
        # Legacy fallback: derive from action entitlements
        expiry_str = self._get_item_entitlement_from_actions(norm_item_id, now=now)
        if self._is_entitlement_active(expiry_str, now=now):
            # Upgrade to item entitlement for future checks
            self._shop_item_entitlements[norm_item_id] = expiry_str
            return True
        return False

    def _check_shop_access(self, action_id):
        if action_id not in self._shop_action_links:
            return True
        item_id = self._shop_action_links.get(action_id)
        norm_item_id = self._normalize_shop_item_id(item_id)
        now = datetime.now()
        expiry_str = self._shop_entitlements.get(action_id)
        if self._is_entitlement_active(expiry_str, now=now):
            return True

        # Fall back to item entitlement (purchase) if action entitlement is missing/expired
        item_expiry = self._shop_item_entitlements.get(norm_item_id)
        if not self._is_entitlement_active(item_expiry, now=now):
            item_expiry = self._get_item_entitlement_from_actions(norm_item_id, now=now)

        if self._is_entitlement_active(item_expiry, now=now):
            # Repair/refresh action entitlement for this action
            self._shop_entitlements[action_id] = item_expiry
            return True

        self.add_message(f"Action {action_id} requires shop item {item_id}. Buy it in the shop first.")
        return False

    def create_attribute(self, name=None):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        if name is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("attribute name", type="text", options={"autocomplete": "names"})

        nextid = self.next_attr_id
        new_id = f"80{nextid}" if nextid < 10 else f"8{nextid}"           
        new_attribute = Attribute(new_id, name, None, None, None)
        self._attributes[new_id] = new_attribute
        
        self.add_message(f"attribute '{name}' created with ID {new_id}")
        self.save_user()
    
    def create_attribute_by_id(self, payloads, name=None):
        if not payloads or not payloads[0]:
            self.add_message("Invalid attribute ID.")
            return
        new_id = f"8{payloads[0]}"        
        
        if new_id not in self._attributes:
            if name is None:
                from src.components.services.UI.interface import WebInputInterrupt
                raise WebInputInterrupt("attribute name", type="text", options={"payloads": payloads, "autocomplete": "names"})
            new_attribute = Attribute(new_id, name, None, None, None)
            self._attributes[new_id] = new_attribute
            self.add_message(f"attribute '{name}' created with ID {new_attribute._id}")
            self.save_user()
        else:
            self.add_message(f"ID ({new_id}) already exists.")
    
    def create_action(self, step=None, data=None, value=None):    
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt

        data = data or {}
        clean_data = {k: v for k, v in data.items() if k != "create_step"}
        step = step or "action_type"

        if step == "action_type":
            try:
                tipo = int(value)
            except Exception:
                ui.show_list(
                    ["1 - Repetition", "2 - Seconds", "3 - Minutes", "4 - Hours", "5 - Letters", "6 - Lines"],
                    "UNIT TYPE",
                )
                raise WebInputInterrupt("unit type", type="numeric", options={"create_step": "action_type"})
            if tipo < 1 or tipo > 6:
                self.add_message("Invalid unit type. Use 1-6.")
                raise WebInputInterrupt("unit type", type="numeric", options={"create_step": "action_type"})
            clean_data["action_type"] = tipo
            ui.show_list(
                ["1", "2", "3", "4", "5"],
                "DIFFICULTY (1-5)",
            )
            raise WebInputInterrupt(
                "difficulty (1-5)",
                type="numeric",
                options={**clean_data, "create_step": "action_diff"},
            )

        if step == "action_diff":
            try:
                diff = int(value)
            except Exception:
                raise WebInputInterrupt(
                    "difficulty (1-5)",
                    type="numeric",
                    options={"create_step": "action_diff", **data},
                )
            if diff < 1 or diff > 5:
                self.add_message("Invalid difficulty. Use 1-5.")
                raise WebInputInterrupt(
                    "difficulty (1-5)",
                    type="numeric",
                    options={"create_step": "action_diff", **data},
                )
            clean_data["action_diff"] = diff
            ui.show_messages_animated(["Type a name"])
            raise WebInputInterrupt(
                "action name",
                type="text",
                options={**clean_data, "create_step": "action_name", "autocomplete": "names"},
            )

        if step == "action_name":
            name = str(value or "").strip()
            if not name:
                raise WebInputInterrupt(
                    "action name",
                    type="text",
                    options={**clean_data, "create_step": "action_name", "autocomplete": "names"},
                )
            tipo = clean_data.get("action_type")
            diff = clean_data.get("action_diff")
            if tipo is None or diff is None:
                raise WebInputInterrupt("unit type", type="numeric", options={"create_step": "action_type"})

            nextid = self.next_action_id
            new_id = f"50{nextid}" if nextid < 10 else f"5{nextid}"           
            starter_value = 0
            
            action = Action(new_id, name, tipo, diff, starter_value)
            self._actions[new_id] = action
            
            self.add_message(f"action '{name}' created with ID {new_id}")
            if hasattr(self, "tutorial"):
                self.tutorial.complete("has_created_action")
            self.save_user()
            return

        # Unknown step: restart flow
        raise WebInputInterrupt("unit type", type="numeric", options={"create_step": "action_type"})

    def create_tag(self, name=None):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        if name is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("tag name", type="text", options={"autocomplete": "names"})

        nextid = self.next_tag_id
        new_id = f"10{nextid}" if nextid < 10 else f"1{nextid}"
        new_tag = Tag(new_id, name)
        self._tags[new_id] = new_tag
        self.add_message(f"tag '{name}' created with ID {new_id}")
        self.save_user()

    def create_status(self, buffer: str, name=None):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        if name is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt("status name", type="text", options={"buffer": buffer, "autocomplete": "names"})

        try:
            duration_type = int(buffer[0])
            nextid = self.next_status_id
            new_id = f"40{nextid}" if nextid < 10 else f"4{nextid}"
            status = Status(new_id, name, duration_type)
            self._statuses[new_id] = status
            self.add_message(f"status '{name}' created with ID {new_id}")
            self.save_user()
        except Exception as e:
            self.add_message(f"{e}")

    def create_parameter(self, step=None, data=None, value=None):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt

        data = data or {}
        clean_data = {k: v for k, v in data.items() if k != "create_step"}
        step = step or "param_type"

        if step == "param_type":
            try:
                value_type = int(value)
            except Exception:
                ui.show_list(["1 - Mark", "2 - Percentage"], "PARAMETER TYPE")
                raise WebInputInterrupt(
                    "parameter type (1 mark, 2 percentage)",
                    type="numeric",
                    options={"create_step": "param_type"},
                )
            if value_type not in (1, 2):
                self.add_message("Parameter type must be 1 (mark) or 2 (percentage).")
                raise WebInputInterrupt(
                    "parameter type (1 mark, 2 percentage)",
                    type="numeric",
                    options={"create_step": "param_type"},
                )
            clean_data["value_type"] = value_type
            ui.show_list(
                ["1 - Emotional", "2 - Ambiental", "3 - Fisiologic"],
                "PARAMETER LOGIC",
            )
            raise WebInputInterrupt(
                "parameter logic (1 Emotional, 2 Ambiental, 3 Fisiologic)",
                type="numeric",
                options={**clean_data, "create_step": "param_logic"},
            )

        if step == "param_logic":
            try:
                logic_type = int(value)
            except Exception:
                raise WebInputInterrupt(
                    "parameter logic (1 Emotional, 2 Ambiental, 3 Fisiologic)",
                    type="numeric",
                    options={**clean_data, "create_step": "param_logic"},
                )
            if logic_type not in (1, 2, 3):
                self.add_message("Parameter logic must be 1, 2, or 3.")
                raise WebInputInterrupt(
                    "parameter logic (1 Emotional, 2 Ambiental, 3 Fisiologic)",
                    type="numeric",
                    options={**clean_data, "create_step": "param_logic"},
                )
            clean_data["logic_type"] = logic_type
            ui.show_list(["Type a name"], "PARAMETER NAME")
            raise WebInputInterrupt(
                "parameter name",
                type="text",
                options={**clean_data, "create_step": "param_name", "autocomplete": "names"},
            )

        if step == "param_name":
            name = str(value or "").strip()
            if not name:
                ui.show_messages_animated(["Type a name"])
                raise WebInputInterrupt(
                    "parameter name",
                    type="text",
                    options={**clean_data, "create_step": "param_name", "autocomplete": "names"},
                )
            value_type = clean_data.get("value_type")
            logic_type = clean_data.get("logic_type")
            if value_type is None or logic_type is None:
                raise WebInputInterrupt(
                    "parameter type (1 mark, 2 percentage)",
                    type="numeric",
                    options={"create_step": "param_type"},
                )

        try:
            nextid = self.next_param_id
            new_id = f"60{nextid}" if nextid < 10 else f"6{nextid}"
            param = Parameter(new_id, name, value_type, logic_type, 0)
            self._parameters[new_id] = param
            self.add_message(f"parameter '{name}' created with ID {new_id}")
            self.save_user()
        except Exception as e:
            self.add_message(f"{e}")
        return

        # Unknown step: restart flow
        raise WebInputInterrupt(
            "parameter type (1 mark, 2 percentage)",
            type="numeric",
            options={"create_step": "param_type"},
        )

    def activate_status(self, payloads):
        status_id = f"4{payloads[0]}"
        status = self._statuses.get(status_id)
        if not status:
            self.add_message(f"Status ID ({status_id}) not found")
            return
        status.activate()
        self.add_message(f"Status {status._name} ({status._id}) activated.")
        self.save_user()

    def clean_status(self, payloads):
        status_id = f"4{payloads[0]}"
        status = self._statuses.get(status_id)
        if not status:
            self.add_message(f"Status ID ({status_id}) not found")
            return
        status.clean()
        self.add_message(f"Status {status._name} ({status._id}) cleaned.")
        self.save_user()

    def _attach_status_to_param(self, param_id, status_id, value):
        param = self._parameters.get(param_id)
        status = self._statuses.get(status_id)
        if not param or not status:
            self.add_message("parameter or status not found.")
            return

        if param._value_type == 1:
            try:
                value = float(value)
            except Exception:
                value = 0.0
            value = max(-3.0, min(3.0, value))
        else:
            try:
                value = float(value)
            except Exception:
                value = 0.0
            value = max(0.0, min(100.0, value))

        status.add_param_link(param_id, value)
        self.add_message(f"{status._name} -> {param._name} ({value})")
        self.save_user()

    def parameter_add_status(self, payloads, value=None):
        if len(payloads) < 2:
            self.add_message("Invalid parameter/status IDs.")
            return
        param_id = f"6{payloads[0]}"
        status_id = f"4{payloads[1]}"
        param = self._parameters.get(param_id)
        status = self._statuses.get(status_id)
        if not param or not status:
            self.add_message("parameter or status not found.")
            return

        if value is None:
            from src.components.services.UI.interface import WebInputInterrupt
            if param._value_type == 1:
                prompt = "parameter value (mark -3 to 3)"
            else:
                prompt = "parameter value (percentage 0-100)"
            raise WebInputInterrupt(
                prompt,
                type="numeric",
                options={
                    "param_id": param_id,
                    "status_id": status_id,
                    "value_type": param._value_type,
                },
            )

        self._attach_status_to_param(param_id, status_id, value)

    def init_parameter(self, payloads):
        if not payloads or not payloads[0]:
            self.add_message("Invalid parameter ID.")
            return
        param_id = f"6{payloads[0]}"
        if param_id not in self._parameters:
            self.add_message(f"Parameter ID ({param_id}) not found")
            return
        from src.components.services.UI.interface import WebInputInterrupt
        raise WebInputInterrupt(
            "parameter regen type (1 regen, 2 decay)",
            type="numeric",
            options={"param_step": "regen_type", "param_id": param_id},
        )

    def parameter_init_next(self, step, data, value):
        data = dict(data or {})
        val = (value or "").strip()

        if step == "regen_type":
            if val not in {"1", "2"}:
                self.add_message("Regen type must be 1 (regen) or 2 (decay).")
                return {"prompt": "parameter regen type (1 regen, 2 decay)", "type": "numeric", "options": {"param_step": "regen_type", "param_id": data.get("param_id")}}
            data["regen_type"] = int(val)
            param_id = data.get("param_id")
            param = self._parameters.get(param_id)
            if not param:
                self.add_message("Parameter not found.")
                return None
            if param._value_type == 1:
                prompt = "parameter regen factor (mark 1-6: 1/24h, 1/12h, 1/6h, 1/3h, 1/1.5h, 1/45min)"
            else:
                prompt = "parameter regen factor (percentage 1-5: 5/10/15/20/25% per h)"
            return {"prompt": prompt, "type": "numeric", "options": {"param_step": "regen_factor", "param_id": param_id, "regen_type": data["regen_type"]}}

        if step == "regen_factor":
            param_id = data.get("param_id")
            param = self._parameters.get(param_id)
            if not param:
                self.add_message("Parameter not found.")
                return None
            try:
                factor = int(val)
            except Exception:
                factor = 0
            if param._value_type == 1:
                if factor < 1 or factor > 6:
                    self.add_message("Mark regen factor must be between 1 and 6.")
                    return {"prompt": "parameter regen factor (mark 1-6: 1/24h, 1/12h, 1/6h, 1/3h, 1/1.5h, 1/45min)", "type": "numeric", "options": {"param_step": "regen_factor", "param_id": param_id, "regen_type": data.get("regen_type")}}
            else:
                if factor < 1 or factor > 5:
                    self.add_message("Percentage regen factor must be between 1 and 5.")
                    return {"prompt": "parameter regen factor (percentage 1-5: 5/10/15/20/25% per h)", "type": "numeric", "options": {"param_step": "regen_factor", "param_id": param_id, "regen_type": data.get("regen_type")}}
            data["regen_factor"] = factor
            return {"prompt": "parameter start value", "type": "numeric", "options": {"param_step": "start_value", "param_id": param_id, "regen_type": data.get("regen_type"), "regen_factor": factor}}

        if step == "start_value":
            param_id = data.get("param_id")
            param = self._parameters.get(param_id)
            if not param:
                self.add_message("Parameter not found.")
                return None
            try:
                start_value = float(val)
            except Exception:
                self.add_message("Invalid start value.")
                return {"prompt": "parameter start value", "type": "numeric", "options": {"param_step": "start_value", "param_id": param_id, "regen_type": data.get("regen_type"), "regen_factor": data.get("regen_factor")}}
            param.set_regen(data.get("regen_type"), data.get("regen_factor"), start_value)
            self.add_message(f"Parameter {param._name} ({param._id}) initialized.")
            self.save_user()
            return None

        self.add_message("Parameter init error: invalid step.")
        return None

    def edit_action(self, payloads):
        if not payloads or not payloads[0]:
            self.add_message("Invalid action ID.")
            return
        action_id, action = self._resolve_action_payload(payloads[0])
        if not action:
            return
        from src.components.services.UI.interface import WebInputInterrupt
        raise WebInputInterrupt(
            "edit action name (blank keep)",
            type="text",
            options={"edit_step": "action_name", "action_id": action_id, "autocomplete": "names"},
        )

    def action_edit_next(self, step, data, value):
        data = dict(data or {})
        val = value if value is not None else ""

        if step == "action_name":
            data["name"] = val.strip()
            return {"prompt": "edit action type (0-6, blank keep)", "type": "numeric", "options": {"edit_step": "action_type", "action_id": data.get("action_id"), "name": data["name"]}}

        if step == "action_type":
            data["type"] = val.strip()
            return {"prompt": "edit action diff (0-5, blank keep)", "type": "numeric", "options": {"edit_step": "action_diff", "action_id": data.get("action_id"), "name": data.get("name"), "type": data.get("type")}}

        if step == "action_diff":
            action_id = data.get("action_id")
            action = self._actions.get(action_id)
            if not action:
                self.add_message("Action not found.")
                return None
            name = data.get("name")
            tipo_raw = data.get("type")
            diff_raw = val.strip()
            if name:
                action._name = name
            if tipo_raw:
                try:
                    tipo = int(tipo_raw)
                    if tipo in Action._TYPE_MAP:
                        action._tipo = tipo
                except Exception:
                    pass
            if diff_raw:
                try:
                    diff = int(diff_raw)
                    if 0 <= diff <= 5:
                        action._diff = diff
                        action._diff_multiplier = action._DIFFICULTY_MULTIPLIER_MAP[diff]
                except Exception:
                    pass
            self.add_message(f"Action {action._name} ({action._id}) updated.")
            self.save_user()
            return None

        self.add_message("Action edit error: invalid step.")
        return None

    def edit_attribute(self, payloads):
        if not payloads or not payloads[0]:
            self.add_message("Invalid attribute ID.")
            return
        attr_id = f"8{payloads[0]}"
        attr = self._attributes.get(attr_id)
        if not attr:
            self.add_message(f"Attribute ID ({attr_id}) not found")
            return
        from src.components.services.UI.interface import WebInputInterrupt
        raise WebInputInterrupt(
            "edit attribute name (blank keep)",
            type="text",
            options={"edit_step": "attr_name", "attr_id": attr_id, "autocomplete": "names"},
        )

    def edit_parameter(self, payloads):
        if not payloads or not payloads[0]:
            self.add_message("Invalid parameter ID.")
            return
        param_id = f"6{payloads[0]}"
        param = self._parameters.get(param_id)
        if not param:
            self.add_message(f"Parameter ID ({param_id}) not found")
            return
        from src.components.services.UI.interface import WebInputInterrupt
        raise WebInputInterrupt(
            "edit parameter name (blank keep)",
            type="text",
            options={"edit_step": "param_name", "param_id": param_id, "autocomplete": "names"},
        )

    def edit_status(self, payloads):
        if not payloads or not payloads[0]:
            self.add_message("Invalid status ID.")
            return
        status_id = f"4{payloads[0]}"
        status = self._statuses.get(status_id)
        if not status:
            self.add_message(f"Status ID ({status_id}) not found")
            return
        from src.components.services.UI.interface import WebInputInterrupt
        raise WebInputInterrupt(
            "edit status name (blank keep)",
            type="text",
            options={"edit_step": "status_name", "status_id": status_id, "autocomplete": "names"},
        )

    def misc_edit_next(self, step, data, value):
        data = dict(data or {})
        val = value if value is not None else ""

        if step == "attr_name":
            attr = self._attributes.get(data.get("attr_id"))
            if not attr:
                self.add_message("Attribute not found.")
                return None
            if val.strip():
                attr._name = val.strip()
            self.add_message(f"Attribute {attr._name} ({attr._id}) updated.")
            self.save_user()
            return None

        if step == "param_name":
            param = self._parameters.get(data.get("param_id"))
            if not param:
                self.add_message("Parameter not found.")
                return None
            data["name"] = val.strip()
            return {"prompt": "edit parameter type (1 mark, 2 percentage, blank keep)", "type": "numeric", "options": {"edit_step": "param_type", "param_id": data.get("param_id"), "name": data.get("name")}}

        if step == "param_type":
            param = self._parameters.get(data.get("param_id"))
            if not param:
                self.add_message("Parameter not found.")
                return None
            data["type"] = val.strip()
            return {"prompt": "edit parameter logic (1 Emotional, 2 Ambiental, 3 Fisiologic, blank keep)", "type": "numeric", "options": {"edit_step": "param_logic", "param_id": data.get("param_id"), "name": data.get("name"), "type": data.get("type")}}

        if step == "param_logic":
            param = self._parameters.get(data.get("param_id"))
            if not param:
                self.add_message("Parameter not found.")
                return None
            name = data.get("name")
            type_raw = data.get("type")
            logic_raw = val.strip()
            if name:
                param._name = name
            if type_raw:
                try:
                    tval = int(type_raw)
                    if tval in Parameter.VALUE_TYPES:
                        param._value_type = tval
                        param.set_value(param._value)
                except Exception:
                    pass
            if logic_raw:
                try:
                    lval = int(logic_raw)
                    if lval in Parameter.LOGIC_TYPES:
                        param._logic_type = lval
                except Exception:
                    pass
            self.add_message(f"Parameter {param._name} ({param._id}) updated.")
            self.save_user()
            return None

        if step == "status_name":
            status = self._statuses.get(data.get("status_id"))
            if not status:
                self.add_message("Status not found.")
                return None
            data["name"] = val.strip()
            return {"prompt": "edit status duration (0-3, blank keep)", "type": "numeric", "options": {"edit_step": "status_duration", "status_id": data.get("status_id"), "name": data.get("name")}}

        if step == "status_duration":
            status = self._statuses.get(data.get("status_id"))
            if not status:
                self.add_message("Status not found.")
                return None
            name = data.get("name")
            if name:
                status._name = name
            dur_raw = val.strip()
            if dur_raw:
                try:
                    dval = int(dur_raw)
                    if dval in Status.DURATION_MAP:
                        status._duration_type = dval
                except Exception:
                    pass
            self.add_message(f"Status {status._name} ({status._id}) updated.")
            self.save_user()
            return None

        self.add_message("Edit error: invalid step.")
        return None

    def shop_item_add_action(self, payloads):
        if len(payloads) < 2:
            self.add_message("Invalid shop item/action IDs.")
            return
        shop_item_id = payloads[0]
        action_id, action = self._resolve_action_payload(payloads[1])
        if not action:
            self.add_message("action not found.")
            return
        self._shop_action_links[action_id] = shop_item_id
        self.add_message(f"Shop item {shop_item_id} linked to Action {action_id}.")
        self.save_user()

    def action_add_tag(self, payloads, value=None):
        if len(payloads) < 2:
            self.add_message("Invalid action/tag IDs.")
            return
        action_id, action = self._resolve_action_payload(payloads[0])
        tag_id = f"1{payloads[1]}"
        tag = self._tags.get(tag_id)
        if not action or not tag:
            self.add_message("action or tag not found.")
            return
        if value is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt(
                "tag weight (-3 to 3)",
                type="numeric",
                options={"tag_step": "action_weight", "action_id": action_id, "tag_id": tag_id},
            )
        self._add_action_tag(action_id, tag_id, value)

    def parameter_add_tag(self, payloads, value=None):
        if len(payloads) < 2:
            self.add_message("Invalid parameter/tag IDs.")
            return
        param_id = f"6{payloads[0]}"
        tag_id = f"1{payloads[1]}"
        param = self._parameters.get(param_id)
        tag = self._tags.get(tag_id)
        if not param or not tag:
            self.add_message("parameter or tag not found.")
            return
        if value is None:
            from src.components.services.UI.interface import WebInputInterrupt
            raise WebInputInterrupt(
                "tag weight (-3 to 3)",
                type="numeric",
                options={"tag_step": "param_weight", "param_id": param_id, "tag_id": tag_id},
            )
        self._add_param_tag(param_id, tag_id, value)

    def tag_link_next(self, step, data, value):
        data = dict(data or {})
        try:
            text = str(value).strip()
            if len(text) > 1 and text.startswith("0"):
                weight = -int(text[1:])
            else:
                weight = int(text)
        except Exception:
            weight = 0
        if weight < -3 or weight > 3 or weight == 0:
            self.add_message("Tag weight must be between -3 and 3 (non-zero). Use 0 prefix for negative (e.g., 03 = -3).")
            return {"prompt": "tag weight (0x = negative, e.g., 03 = -3)", "type": "numeric", "options": data}

        if step == "action_weight":
            self._add_action_tag(data.get("action_id"), data.get("tag_id"), weight)
            return None
        if step == "param_weight":
            self._add_param_tag(data.get("param_id"), data.get("tag_id"), weight)
            return None

        self.add_message("Tag link error: invalid step.")
        return None

    def _add_action_tag(self, action_id, tag_id, weight):
        tags = [t for t in self._action_tags.get(action_id, []) if t.get("tag_id") != tag_id]
        tags.append({"tag_id": tag_id, "weight": weight})
        self._action_tags[action_id] = tags
        self.add_message(f"Tag {tag_id} linked to Action {action_id} ({weight}).")
        self.save_user()

    def _add_param_tag(self, param_id, tag_id, weight):
        tags = [t for t in self._param_tags.get(param_id, []) if t.get("tag_id") != tag_id]
        tags.append({"tag_id": tag_id, "weight": weight})
        self._param_tags[param_id] = tags
        self.add_message(f"Tag {tag_id} linked to Param {param_id} ({weight}).")
        self.save_user()

    def _apply_tag_effects(self, action, value_difference):
        action_tags = self._action_tags.get(action.id, [])
        if not action_tags:
            return
        unit_map = {
            0: 3.0,  # session
            1: 1.0,  # repetitions
            2: 0.1,  # seconds
            3: 0.5,  # minutes
            4: 3.0,  # hours
            5: 1.0,  # letters
            6: 1.0,  # lines
        }
        unit_factor = unit_map.get(action.type, 1.0)
        base_percent = 3.0
        base_mark = 1.5

        # Preindex action tag weights by tag_id
        action_tag_map = {}
        for t in action_tags:
            tid = t.get("tag_id")
            try:
                w = int(t.get("weight"))
            except Exception:
                w = 0
            if tid:
                action_tag_map[tid] = action_tag_map.get(tid, 0) + w

        for param_id, param in self._parameters.items():
            param_tags = self._param_tags.get(param_id, [])
            if not param_tags:
                continue
            delta_total = 0.0
            for pt in param_tags:
                tid = pt.get("tag_id")
                if tid not in action_tag_map:
                    continue
                try:
                    pw = int(pt.get("weight"))
                except Exception:
                    pw = 0
                aw = action_tag_map.get(tid, 0)
                if aw == 0 or pw == 0:
                    continue
                base_value = base_mark if param._value_type == 1 else base_percent
                delta_total += value_difference * unit_factor * aw * pw * base_value
            if delta_total != 0:
                param.set_value(param._value + delta_total)
                self._update_statuses_for_param(param)
        self.save_user()

    def _update_statuses_for_param(self, param):
        from datetime import datetime
        now = datetime.now()
        for status in self._statuses.values():
            links = getattr(status, "_param_links", [])
            for link in links:
                if link.get("param_id") != param._id:
                    continue
                try:
                    target = float(link.get("value"))
                except Exception:
                    continue
                if param._value >= target:
                    if not status.is_active(now):
                        status.activate(now)
    
    def list_attributes(self):
        if self._attributes:
            from src.components.services.UI.interface import ui
            items = [f"({attr._id}) - {attr._name}" for attr in self._attributes.values()]
            ui.show_list(items, "CURRENT ATTRIBUTES")
        else:
            self.add_message("no attributes available. try creating one with 28...")
    
    def list_actions(self):
        if self._actions:
            from src.components.services.UI.interface import ui
            items = [f"({action._id}) - {action._name}" for action in self._actions.values() if not getattr(action, "_deleted", False)]
            ui.show_list(items, "CURRENT ACTIONS")
        else:
            self.add_message("no actions available. try creating one with 25...")

    def list_statuses(self):
        if not self._statuses:
            self.add_message("no statuses available. try creating one with 24...")
            return
        from datetime import datetime
        from src.components.services.UI.interface import ui
        now = datetime.now()
        items = []
        for status in self._statuses.values():
            is_active = status.is_active(now)
            state = "active" if is_active else "inactive"
            if is_active:
                remaining = status.remaining_str(now)
            elif status.active_until:
                remaining = "expired"
            else:
                remaining = "-"
            items.append(f"({status._id}) - {status._name} [{state} | {remaining}]")
        ui.show_list(items, "STATUSES")

    def list_active_statuses(self):
        from datetime import datetime
        now = datetime.now()
        expired = []
        items = []
        for status in self._statuses.values():
            if status.is_active(now):
                items.append(f"({status._id}) - {status._name} [{status.remaining_str(now)}]")
            elif status.active_until and not status.is_active(now):
                expired.append(status)

        for st in expired:
            st.clean()

        if items:
            from src.components.services.UI.interface import ui
            ui.show_list(items, "ACTIVE STATUSES")
        else:
            self.add_message("no active statuses.")
        self.save_user()

    def list_tags(self):
        if self._tags:
            from src.components.services.UI.interface import ui
            items = [f"({tag._id}) - {tag._name}" for tag in self._tags.values()]
            ui.show_list(items, "CURRENT TAGS")
        else:
            self.add_message("no tags available. try creating one with 21...")

    def list_actions_detailed(self):
        from src.components.services.UI.interface import ui
        items = []
        for action in self._actions.values():
            if getattr(action, "_deleted", False):
                continue
            tag_list = []
            for tag_link in self._action_tags.get(action._id, []):
                tid = tag_link.get("tag_id")
                weight = tag_link.get("weight")
                name = self._tags.get(tid)._name if tid in self._tags else tid
                tag_list.append(f"{name}({weight})")
            tags_str = ", ".join(tag_list) if tag_list else "-"
            items.append(f"({action._id}) {action._name} | score {action.score:.2f} | tags: {tags_str}")
        if items:
            ui.show_list(items, "ACTIONS (DETAILED)")
        else:
            self.add_message("no actions available.")

    def list_params_full(self):
        from src.components.services.UI.interface import ui
        items = []
        for param in self._parameters.values():
            tag_list = []
            for tag_link in self._param_tags.get(param._id, []):
                tid = tag_link.get("tag_id")
                weight = tag_link.get("weight")
                name = self._tags.get(tid)._name if tid in self._tags else tid
                tag_list.append(f"{name}({weight})")
            tags_str = ", ".join(tag_list) if tag_list else "-"
            val = param._value
            items.append(
                f"({param._id}) {param._name} | "
                f"{Parameter.VALUE_TYPES.get(param._value_type)} / {Parameter.LOGIC_TYPES.get(param._logic_type)} | "
                f"value {val:.4f} | tags: {tags_str}"
            )
        if items:
            ui.show_list(items, "PARAMS (FULL)")
        else:
            self.add_message("no parameters available.")

    def list_attributes_detailed(self):
        from src.components.services.UI.interface import ui
        items = []
        for attr in self._attributes.values():
            rel_actions = [a._name for a in getattr(attr, "_related_actions", [])]
            children = [c._name for c in getattr(attr, "_children", [])]
            parents = [p._name for p in getattr(attr, "_parent", [])]
            items.append(
                f"({attr._id}) {attr._name} | score {attr.total_score:.2f} | "
                f"actions: {', '.join(rel_actions) if rel_actions else '-'} | "
                f"children: {', '.join(children) if children else '-'} | "
                f"parent: {', '.join(parents) if parents else '-'}"
            )
        if items:
            ui.show_list(items, "ATTRIBUTES (DETAILED)")
        else:
            self.add_message("no attributes available.")

    def list_tags_detailed(self):
        from src.components.services.UI.interface import ui
        items = []
        for tag in self._tags.values():
            action_links = []
            for action_id, links in self._action_tags.items():
                for link in links:
                    if link.get("tag_id") == tag._id:
                        action = self._actions.get(action_id)
                        if action and not getattr(action, "_deleted", False):
                            action_links.append(f"{action._name}({link.get('weight')})")
            param_links = []
            for param_id, links in self._param_tags.items():
                for link in links:
                    if link.get("tag_id") == tag._id:
                        param = self._parameters.get(param_id)
                        if param:
                            param_links.append(f"{param._name}({link.get('weight')})")
            items.append(
                f"({tag._id}) {tag._name} | actions: {', '.join(action_links) if action_links else '-'} | "
                f"params: {', '.join(param_links) if param_links else '-'}"
            )
        if items:
            ui.show_list(items, "TAGS (DETAILED)")
        else:
            self.add_message("no tags available.")

    def show_user_info(self):
        from src.components.services.UI.interface import ui
        meta = self.metadata
        items = [
            f"score: {self.score:.2f}",
            f"total_points: {self.total_points:.2f}",
            f"mode: {meta.get('mode')}",
            f"tokens: {meta.get('tokens')}/{meta.get('max_tokens')}",
            f"daily_refill: {meta.get('daily_refill')}",
            f"refill_cooldown: {meta.get('refill_cooldown')}",
            f"last_token_refill: {meta.get('last_token_refill')}",
            f"attributes: {len(self._attributes)}",
            f"actions: {len([a for a in self._actions.values() if not getattr(a, '_deleted', False)])}",
            f"parameters: {len(self._parameters)}",
            f"statuses: {len(self._statuses)}",
            f"tags: {len(self._tags)}",
        ]
        ui.show_list(items, "USER INFO")


    def _collect_autocomplete_names(self):
        import json
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        data_dir = os.path.join(src_dir, "data")
        results = set()

        for root, _, files in os.walk(data_dir):
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue

                def _walk(obj):
                    if isinstance(obj, dict):
                        name = obj.get("name")
                        if isinstance(name, str) and name.strip():
                            results.add(name.strip())
                        for v in obj.values():
                            _walk(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            _walk(v)

                _walk(data)

        return sorted(results)

    def list_parameters(self):
        if self._parameters:
            from src.components.services.UI.interface import ui
            for param in self._parameters.values():
                if param.update_value():
                    self._update_statuses_for_param(param)
            items = []
            for param in self._parameters.values():
                val = int(round(param._value))
                if param._value_type == 2:
                    items.append(f"({param._id}) - {param._name} = {val}%")
                else:
                    items.append(f"({param._id}) - {param._name} = {val}")
            ui.show_list(items, "CURRENT PARAMETERS")
            self.save_user()
        else:
            self.add_message("no parameters available. try creating one with 26...")
    
    def drop_attributes(self):
        from src.components.services.UI.interface import ui
        if ui.ask_confirmation("This will PERMANENTLY DELETE ALL ATTRIBUTES."):
            self._attributes.clear()
            self.add_message("attributes deleted.")
            self.save_user()
        else:
            self.add_message("the attributes are safe.")
    
    def drop_actions(self):
        from src.components.services.UI.interface import ui
        if ui.ask_confirmation("This will PERMANENTLY DELETE ALL ACTIONS."):
            self._actions.clear()
            self.add_message("actions deleted.")
            self.save_user()
        else:
            self.add_message("the actions are safe.")

    def drop_parameters(self):
        from src.components.services.UI.interface import ui
        if ui.ask_confirmation("This will PERMANENTLY DELETE ALL PARAMETERS."):
            self._parameters.clear()
            self.add_message("parameters deleted.")
            self.save_user()
        else:
            self.add_message("the parameters are safe.")
    
    def delete_attribute(self, payloads, confirmed=None):
        payload_id = f"8{payloads[0]}"   
        attr = self._attributes.get(payload_id)
        
        if not attr:
            self.add_message(f"Attribute ID ({payload_id}) not found")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt
        if confirmed is True:
            pass
        elif ui.web_mode:
            import random
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.add_message(f"Delete {attr._name} ({attr._id})?")
            self.add_message(f"Type the code: {code}")
            raise WebInputInterrupt(f"Confirm code: {code}", type="confirm", options={"code": code, "payloads": payloads, "action": "delete_attribute"})
        elif not ui.ask_confirmation(f"Delete attribute {attr._name} ({attr._id})?"):
            return

        self._attributes.pop(payload_id, None)
        self.add_message(f"Attribute {attr._name} ({attr._id}) deleted.")
        self.save_user()

    def delete_action(self, payloads, confirmed=None):
        if not payloads or not payloads[0]:
            self.add_message("Invalid action ID.")
            return
        payload_id, action = self._resolve_action_payload(payloads[0])
        if not action:
            return
        if getattr(action, "_deleted", False):
            self.add_message(f"Action {action._name} ({action._id}) already deleted.")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt
        if confirmed is True:
            pass
        elif ui.web_mode:
            import random
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.add_message(f"Delete {action._name} ({action._id})?")
            self.add_message(f"Type the code: {code}")
            raise WebInputInterrupt(f"Confirm code: {code}", type="confirm", options={"code": code, "payloads": payloads, "action": "delete_action"})
        elif not ui.ask_confirmation(f"Delete action {action._name} ({action._id})?"):
            return

        action.set_deleted(True)
        self.add_message(f"Action {action._name} ({action._id}) deleted.")
        self.save_user()

    def delete_status(self, payloads, confirmed=None):
        payload_id = f"4{payloads[0]}"
        status = self._statuses.get(payload_id)

        if not status:
            self.add_message(f"Status ID ({payload_id}) not found")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt
        if confirmed is True:
            pass
        elif ui.web_mode:
            import random
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.add_message(f"Delete {status._name} ({status._id})?")
            self.add_message(f"Type the code: {code}")
            raise WebInputInterrupt(
                f"Confirm code: {code}",
                type="confirm",
                options={"code": code, "payloads": payloads, "action": "delete_status"},
            )
        elif not ui.ask_confirmation(f"Delete status {status._name} ({status._id})?"):
            return

        self._statuses.pop(payload_id, None)
        self.add_message(f"Status {status._name} ({status._id}) deleted.")
        self.save_user()

    def delete_parameter(self, payloads, confirmed=None):
        payload_id = f"6{payloads[0]}"
        param = self._parameters.get(payload_id)

        if not param:
            self.add_message(f"Parameter ID ({payload_id}) not found")
            return

        from src.components.services.UI.interface import ui, WebInputInterrupt
        if confirmed is True:
            pass
        elif ui.web_mode:
            import random
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.add_message(f"Delete {param._name} ({param._id})?")
            self.add_message(f"Type the code: {code}")
            raise WebInputInterrupt(
                f"Confirm code: {code}",
                type="confirm",
                options={"code": code, "payloads": payloads, "action": "delete_parameter"},
            )
        elif not ui.ask_confirmation(f"Delete parameter {param._name} ({param._id})?"):
            return

        self._parameters.pop(payload_id, None)
        self.add_message(f"Parameter {param._name} ({param._id}) deleted.")
        self.save_user()

    def attribute_add_action(self, payloads):
        attr_id = f"8{payloads[0]}"   
        action_id, action = self._resolve_action_payload(payloads[1])
        
        attribute = self._attributes.get(attr_id)
        
        if attribute and action:
            attribute.add_related_action(action)
            self.add_message(f"{action._name} -> {attribute._name}")
            self.save_user()
        else:
            self.add_message(f"some of IDs {attr_id} {action_id} not found.")
    
    def attribute_add_child(self, payloads):
        attr_id = f"8{payloads[0]}"   
        child_id = f"8{payloads[1]}"
        
        attribute = self._attributes.get(attr_id)
        child = self._attributes.get(child_id)
        
        if attribute and child:
            if not attribute == child:
                attribute.add_child(child)
                self.add_message(f"{child._name} -> {attribute._name}")
                self.save_user()
            else:        
                self.add_message(f"{attr_id} {child_id} are the same.")   
        else:
            self.add_message(f"some of IDs {attr_id} {child_id} not found.")

user = User()
