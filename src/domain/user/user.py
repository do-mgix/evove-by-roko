# ==================== USER.PY ====================
import json, os, time, math
import roman
from datetime import datetime, timedelta

_GREEK = ['α','β','γ','δ','ε','ζ','η','θ','ι','κ','λ','μ','ν','ξ','ο','π','ρ','σ','τ','υ','φ','χ','ψ','ω']
from src.domain.entities.entity_manager import EntityManager
from src.domain.user.attributes.attribute import Attribute
from src.domain.user.actions.action import Action
from src.domain.user.parameters.parameter import Parameter
from src.domain.user.statuses.status import Status
from src.domain.user.tags.tag import Tag
from src.application.services.journal_service import journal_service
from src.application.services.roko_message_service import roko_message_service
from src.application.services.tutorial_service import TutorialService
from src.infrastructure.storage import get_current_username, get_evove_data_dir

class User:
    def __init__(self):
        him = EntityManager().get_entity()
        self._attributes = {} 
        self._actions = {} 
        self._parameters = {}
        self._statuses = {}
        self._shop_items = {}
        self._shop_action_links = {}
        self._active_items = []
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
            "username": get_current_username(),
            "energy": 1000,
            "max_score": 0,
            "max_xp": 0,
            "skill_points": 0,
            "stage": 1,
            "days_until_next_checkpoint": 20,
            "last_checkpoint_check": datetime.now().strftime("%Y-%m-%d"),
            "tokens": 0,
            "max_tokens": 50,
            "daily_refill": 20,
            "refill_cooldown": 12,
            "last_token_refill": datetime.now().strftime("%Y-%m-%d"),
            "interaction_count": 0,
            "log_xp": 0,
            "xp_deducted": 0,
            "tutorial": {
                "has_created_action": {"status": False, "priority": 10},
                "welcomed": {"status": False, "priority": 11}
            }
        }
        self.load_user()
        self._ensure_tutorial_state()
        self._update_max_progress_metrics()
        self.tutorial = TutorialService(self)
        self.tutorial.maybe_show_startup()

    def refill_daily_tokens(self, now=None):
        """Refill once per day based on date (ignores time)."""
        # Always reload to reduce duplicate refills across processes
        self.load_user()

        if now is None:
            now = datetime.now()

        # Try to acquire a simple inter-process lock (best-effort)
        data_dir = get_evove_data_dir()
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
            self._active_items = []
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
        """Spends tokens, allowing negative balance."""
        current = self.metadata.get("tokens", 0)
        self.metadata["tokens"] = current - amount
        self.add_message(f"Tokens spent: {amount}. Current balance: {self.metadata['tokens']}")
        self.save_user()
        return True

    def _today_agenda_attributes(self, now=None):
        from src.application.services.evove_agenda_service import get_today_schedule, parse_agenda
        _day, items, _idx = get_today_schedule(
            agenda=parse_agenda(),
            now=now or datetime.now(),
        )
        labels = {
            " ".join(str(label or "").strip().upper().split())
            for _s, _e, label in items
        }
        labels.discard("")
        if not labels:
            return []
        result = []
        for attr in self._attributes.values():
            name_norm = " ".join(str(getattr(attr, "_name", "") or "").strip().upper().split())
            if name_norm and name_norm in labels:
                result.append(attr)
        return result

    def _action_belongs_to_today_attribute(self, action_id, now=None):
        attrs = self._today_agenda_attributes(now=now)
        if not attrs:
            return None
        aid = str(action_id)
        for attr in attrs:
            if any(str(a.id) == aid for a in getattr(attr, "_related_actions", [])):
                return True
        return False

    def _is_negative_numeric_note(self, note_info):
        if not isinstance(note_info, dict) or not note_info.get("is_numeric"):
            return False
        try:
            return int(note_info.get("value")) < 0
        except (TypeError, ValueError):
            return False

    def _apply_energy_penalty(self, action_id, note_info=None, now=None):
        current_energy = self.metadata.get("energy", 1000)
        try:
            current_energy = int(current_energy)
        except (TypeError, ValueError):
            current_energy = 1000
        current_energy = max(0, current_energy)
        self.metadata["energy"] = current_energy

        penalty = 0
        reasons = []

        belongs = self._action_belongs_to_today_attribute(action_id, now=now)
        if belongs is False:
            penalty += 10
            reasons.append("outside today's attribute")

        if self._is_negative_numeric_note(note_info):
            penalty += 25
            reasons.append("negative token")

        if penalty <= 0:
            return False

        new_energy = max(0, current_energy - penalty)
        spent = current_energy - new_energy
        self.metadata["energy"] = new_energy
        self.add_message(
            f"Energy spent: {spent}. Reason: {', '.join(reasons)}. "
            f"Current balance: {new_energy}/1000"
        )
        depleted = current_energy > 0 and new_energy == 0
        if depleted:
            self._reset_progression_for_energy_depletion()
        return depleted

    def _reset_progression_for_energy_depletion(self):
        self.metadata["score"] = 0
        self.metadata["log_xp"] = 0
        self.metadata["xp_deducted"] = 0
        for action in self._actions.values():
            if hasattr(action, "reset_value"):
                action.reset_value()
        self._progression_tiers_cache = None
        self.add_message("Energy depleted: score, XP and action values reset to 0.")

    def _current_xp_total(self):
        score = float(self.metadata.get("score", 0) or 0)
        log_xp = float(self.metadata.get("log_xp", 0) or 0)
        return score + log_xp

    def _update_max_progress_metrics(self):
        current_score = float(self.metadata.get("score", 0) or 0)
        current_xp = self._current_xp_total()
        max_score = float(self.metadata.get("max_score", 0) or 0)
        max_xp = float(self.metadata.get("max_xp", 0) or 0)
        self.metadata["max_score"] = max(max_score, current_score)
        self.metadata["max_xp"] = max(max_xp, current_xp)

    def _checkpoint_interval_for_stage(self, stage):
        return 19 + max(1, int(stage or 1))

    def get_days_until_next_checkpoint(self, now=None):
        days_until = int(
            self.metadata.get(
                "days_until_next_checkpoint",
                self._checkpoint_interval_for_stage(self.metadata.get("stage", 1)),
            ) or 0
        )
        if days_until <= 0:
            days_until = self._checkpoint_interval_for_stage(self.metadata.get("stage", 1))
        return days_until

    def process_daily_checkpoint(self, now=None):
        if now is None:
            now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        stage = int(self.metadata.get("stage", 1) or 1)
        days_until = self.get_days_until_next_checkpoint(now=now)
        last_check_str = self.metadata.get("last_checkpoint_check")
        try:
            last_check = datetime.fromisoformat(str(last_check_str)).date() if last_check_str else now.date()
        except (TypeError, ValueError):
            last_check = now.date()

        elapsed_days = max(0, (now.date() - last_check).days)
        if elapsed_days <= 0:
            return 0

        days_until = max(0, days_until - elapsed_days)
        completed = 0
        if days_until <= 0:
            stage += 1
            reward = 1 + int(math.ceil(stage / 4))
            self.metadata["energy"] = 1000
            self.metadata["stage"] = stage
            self.metadata["skill_points"] = int(self.metadata.get("skill_points", 0) or 0) + reward
            days_until = self._checkpoint_interval_for_stage(stage)
            completed = 1
            self.add_message(
                f"Checkpoint reached: energy restored, stage {stage}, +{reward} skill points."
            )

        self.metadata["days_until_next_checkpoint"] = days_until
        self.metadata["last_checkpoint_check"] = today_str
        self.save_user()
        return completed

    def _award_skill_points_for_rank_progress(self, previous_rank_index):
        current_rank_index = int(self.get_progression_state().get("rank_index", 0) or 0)
        highest_rank_rewarded = int(self.metadata.get("highest_rank_rewarded", current_rank_index) or 0)
        previous_rank_index = int(previous_rank_index or 0)
        baseline = max(highest_rank_rewarded, previous_rank_index)
        if current_rank_index <= baseline:
            return 0

        gained = current_rank_index - baseline
        self.metadata["skill_points"] = int(self.metadata.get("skill_points", 0) or 0) + gained
        self.metadata["highest_rank_rewarded"] = current_rank_index
        self.add_message(f"Rank up reward: +{gained} skill point{'s' if gained != 1 else ''}.")
        return gained
            
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
    def next_shop_item_id(self):
        from src.application.services.shop_service import ShopService

        items = ShopService.get_items_for_user(self)
        if not items:
            return 1
        return max(int(item_id) for item_id in items.keys()) + 1
    
    @property
    def attribute_average(self):
        if self._attributes:
            total = sum(attr.total_score for attr in self._attributes.values())
            return total / len(self._attributes)
        return 0

    @property
    def total_points(self):
        """XP Global: Unificado no campo 'score' do metadata."""
        return float(self.metadata.get("score", 0))

    def act(self, payloads, value=None, _group_depth=0):
        if not payloads or not payloads[0]:
            self.add_message("Invalid action ID.")
            return None

        action_id, action = self._resolve_action_payload(payloads[0])
        if not action:
            return None
        if getattr(action, "_deleted", False):
            self.add_message(f"Action {action_id} is deleted.")
            return None

        linked_item = self._shop_action_links.get(action_id)
        if linked_item:
            norm_item = self._normalize_shop_item_id(linked_item)
            if norm_item not in self._active_items:
                from src.application.services.shop_service import ShopService
                item = ShopService(self).get_item(linked_item)
                if item:
                    self._active_items.append(norm_item)
                    self.spend_tokens(int(item.get("cost", 0)))

        with open("/tmp/group_debug.log", "a") as _f:
            _f.write(f"ACT CALLED: action={getattr(action, 'name', '?')} tipo={getattr(action, '_tipo', '?')} depth={_group_depth}\n")
        if getattr(action, '_tipo', None) == 8:
            with open("/tmp/group_debug.log", "a") as _f:
                _f.write(f"  TIPO 8 DETECTED for {action.name}\n")
            action_name = action.name
            from src.application.services.evove_groups_service import get_group_children
            resolved = []
            for child_value, child_name in get_group_children(action_name):
                child_id = next(
                    (aid for aid, a in self._actions.items()
                     if not getattr(a, "_deleted", False) and a.name.upper() == child_name),
                    None,
                )
                if child_id:
                    resolved.append((child_value, child_name, child_id))
            if _group_depth == 0:
                from src.interfaces.cli.ui.interface import WebInputInterrupt
                raise WebInputInterrupt(
                    "group confirm",
                    options={"parent": action_name, "children": resolved},
                )
            for child_value, child_name, child_id in resolved:
                self.act([child_id[1:]], value=str(child_value), _group_depth=_group_depth + 1)
            return None

        if self._action_connection_color(action_id) == "blue":
            self.add_message(f"[ {action.name} ] no object connections (unlinked).")

        previous_rank_index = self.get_progression_state().get("rank_index", 0)
        original_value = action.value
        score_difference, action_messages, note_info = action.execution(manual_value=value)
        value_difference = action.value - original_value

        if value_difference:
            self._apply_tag_effects(action, value_difference)
        
        action_name = action.name
        note_text = ""
        note_value = None
        note_is_numeric = False
        if isinstance(note_info, dict):
            note_text = str(note_info.get("text", "")).strip()
            note_value = note_info.get("value")
            note_is_numeric = bool(note_info.get("is_numeric"))

        if not note_text:
            note_text = str(value if value is not None else "").strip()
            try:
                note_value = int(note_text)
                note_is_numeric = True
            except (TypeError, ValueError):
                note_is_numeric = False

        energy_note_info = {
            "text": note_text,
            "value": note_value,
            "is_numeric": note_is_numeric,
        }

        if note_is_numeric:
            log_text = self._format_action_note_log(action_name, note_text, note_value=note_value, is_numeric=True)
        else:
            log_text = self._format_action_note_log(action_name, note_text)

        energy_depleted = self._apply_energy_penalty(action_id, note_info=energy_note_info)

        # Cálculo de Boost por Satisfação
        him = EntityManager().get_entity()
        current_sat = him.satisfaction
        boost_multiplier = 1
        if current_sat > 40:
            boost_factor = min(0.5, (current_sat - 40) / 60 * 0.5)
            boost_factor = max(0, boost_factor)
            boost_multiplier = 1 + boost_factor

        final_score_difference = score_difference * boost_multiplier

        # Add directly to global score (XP)
        xp_gained = int(round(final_score_difference))
        if not energy_depleted:
            current_score = float(self.metadata.get("score", 0))
            self.metadata["score"] = current_score + final_score_difference
            self._award_skill_points_for_rank_progress(previous_rank_index)
        else:
            xp_gained = 0

        action_status = "[CLOUD/TO PROCESS]" if note_is_numeric else "[CLOUD]"
        journal_service.add_log(log_text, auto_confirm=True, custom_status=action_status,
                                xp=xp_gained)

        for msg in action_messages:
            self.add_message(msg)

        self._register_interaction()
        self.add_message(roko_message_service.generate())
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

    def _format_log_text(self, text):
        return " ".join(
            part[:1].upper() + part[1:].lower()
            for part in str(text or "").strip().split()
            if part
        )

    def _build_progression_tiers(self):
        if hasattr(self, "_progression_tiers_cache") and self._progression_tiers_cache:
            return self._progression_tiers_cache

        tiers = []
        cumulative_xp = 0
        global_level = 1
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        total_ranks = len(letters)

        for rank_index, letter in enumerate(letters):
            levels_in_rank = max(1, total_ranks - rank_index)
            rank_symbol = _GREEK[rank_index % len(_GREEK)]
            for local_level in range(1, levels_in_rank + 1):
                xp_cost = int(round(200 * (1.06 ** (global_level - 1)) * (1.28 ** rank_index)))
                xp_cost = max(1, xp_cost)
                cumulative_xp += xp_cost
                tiers.append({
                    "level": global_level,
                    "rank_index": rank_index,
                    "rank_letter": letter,
                    "rank_symbol": rank_symbol,
                    "rank_name": letter,
                    "local_level": local_level,
                    "local_level_roman": roman.toRoman(local_level),
                    "local_levels_total": levels_in_rank,
                    "xp_cost": xp_cost,
                    "threshold": cumulative_xp,
                })
                global_level += 1

        self._progression_tiers_cache = tiers
        return tiers

    def get_progression_state(self):
        xp = max(0, int(round(self.total_points)))
        tiers = self._build_progression_tiers()
        if not tiers:
            return {
                "level": 1,
                "rank_index": 0,
                "rank_symbol": "α",
                "rank_name": "A",
                "rank_letter": "A",
                "local_level": 1,
                "local_level_roman": "I",
                "local_levels_total": 1,
                "next_xp": 0,
                "xp": xp,
            }

        current_tier = tiers[0]
        for tier in tiers:
            current_tier = tier
            if xp < tier["threshold"]:
                break
        else:
            current_tier = tiers[-1]

        next_xp = max(0, current_tier["threshold"] - xp)
        if xp >= tiers[-1]["threshold"]:
            next_xp = 0

        return {
            "level": current_tier["level"],
            "rank_index": current_tier["rank_index"],
            "rank_symbol": current_tier["rank_symbol"],
            "rank_name": current_tier["rank_name"],
            "rank_letter": current_tier["rank_letter"],
            "local_level": current_tier["local_level"],
            "local_level_roman": current_tier["local_level_roman"],
            "local_levels_total": current_tier["local_levels_total"],
            "next_xp": next_xp,
            "xp_cost": current_tier["xp_cost"],
            "xp": xp,
        }

    def get_user_felicity(self):
        interaction_count = int(self.metadata.get("interaction_count", 0) or 0)
        xp = max(0, int(round(self.total_points)))
        felicity = 35 + min(35, xp / 30) + min(30, interaction_count * 1.4)
        return max(0, min(100, felicity))

    def _get_roko_adjective(self):
        adjectives = [
            "sereno",
            "vivo",
            "ácido",
            "calmo",
            "ácustico",
            "firme",
            "breve",
            "luminoso",
            "silencioso",
            "preciso",
            "vibrante",
            "quieto",
        ]
        seed = f"{int(self.total_points)}:{int(self.get_user_felicity())}:{self.metadata.get('interaction_count', 0)}"
        import random
        return random.Random(seed).choice(adjectives).upper()

    def _register_interaction(self):
        self.metadata["interaction_count"] = int(self.metadata.get("interaction_count", 0) or 0) + 1

    def _format_action_note_log(self, action_name, note_text, note_value=None, is_numeric=False):
        action_label = self._format_log_text(action_name)
        note_label = self._format_log_text(note_text)
        if is_numeric:
            return f"{int(note_value)} X {action_label}"
        return f"{str(action_name or '').strip().upper()} : {note_label}"

    def _compute_log_xp(self, text):
        import random
        t = str(text or "").strip()
        words = t.split()
        base = max(3, min(30, len(words) * 3 + len(t) // 8))
        spread = max(1, min(15, len(words) + 2))
        return base + random.Random(t).randint(0, spread)

    def log(self, text):
        formatted = self._format_log_text(text)
        linked_action = journal_service.resolve_note_action(formatted)
        if linked_action:
            formatted = self._format_action_note_log(linked_action, formatted)
        xp = self._compute_log_xp(formatted)
        if journal_service.add_log(formatted, xp=xp):
            self.metadata["log_xp"] = int(self.metadata.get("log_xp", 0)) + xp
            self.add_message(roko_message_service.generate())
            self._register_interaction()
        self.save_user()

    def add_log_entry(self, text=None):
        if text is None:
            from src.interfaces.cli.ui.interface import WebInputInterrupt
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
        if text is None:
            from src.interfaces.cli.ui.interface import WebInputInterrupt
            raise WebInputInterrupt("agenda label", type="text", options={"agenda_step": "label", "agenda_data": {}})

        try:
            payload = json.loads(text)
        except Exception:
            self.add_message("Invalid agenda payload. Provide JSON.")
            self.add_message("Example: {\"label\":\"Study\",\"type\":\"daily\",\"schedule\":{\"start_time\":\"09:00\",\"end_time\":\"10:00\"}}")
            return

        self._add_agenda_payload(payload)

    def list_logs(self):
        from src.interfaces.cli.ui.interface import ui
        table_rows = self._build_log_rows(include_xp=False)
        ui.show_vertical_list(
            table_rows,
            "CURRENT LOG BUFFER",
            mode="table",
            columns=[("id", "ID"), ("label", "HISTÓRICO")],
        )

    def _build_log_rows(self, include_xp=False):
        journal_service._load_logs_data()
        rows = []
        for log in journal_service.logs:
            status = str(log.get("status", "")).upper()
            if "DELETED" in status or "PROCESSED" in status:
                continue

            log_id = log.get("id")
            id_str = f"{log_id}" if log_id is not None else "----"
            raw_status = str(log.get("status", ""))
            display_status = "[CLOUD]" if raw_status == "[CLOUD/TO PROCESS]" else raw_status
            label = f"[{log['timestamp']} ] {log['content']} {display_status}"
            row = {"id": id_str, "label": label}
            if include_xp:
                row["xp"] = str(int(log.get("xp", 0) or 0))
            rows.append(row)
        return rows

    def up_log_day(self, payloads=None):
        payload = payloads[0] if payloads else ""
        raw = str(payload).strip()
        if not raw.isdigit():
            self.add_message("Invalid log id payload.")
            return
        # Accept either 4-digit payload (appends prefix) or 5-digit payload (full id without leading "7")
        if len(raw) == journal_service.log_id_width:
            raw = raw.zfill(journal_service.log_id_width)
            full_id = int(f"{journal_service.log_id_prefix}{raw}")
        elif len(raw) == journal_service.log_id_width + 1:
            full_id = int(f"7{raw}")
        else:
            self.add_message("Invalid log id payload length.")
            return
        result = journal_service.up_log_day(full_id)
        self.add_message(result)
        self.save_user()

    def up_current_day(self):
        result = journal_service.up_current_day()
        self.add_message(result)
        self.save_user()

    def delete_log(self, payloads=None):
        payload = payloads[0] if payloads else ""
        raw = str(payload).strip()
        if not raw.isdigit():
            self.add_message("Invalid log id payload.")
            return
        if len(raw) == journal_service.log_id_width:
            raw = raw.zfill(journal_service.log_id_width)
            full_id = int(f"{journal_service.log_id_prefix}{raw}")
        elif len(raw) == journal_service.log_id_width + 1:
            full_id = int(f"7{raw}")
        else:
            self.add_message("Invalid log id payload length.")
            return
        result = journal_service.delete_log_by_id(full_id)
        self.add_message(result)
        self.save_user()

    def drop_last_log_buffer(self):
        message, xp = journal_service.drop_last_buffer_entry()
        self.metadata["xp_deducted"] = int(self.metadata.get("xp_deducted", 0)) + xp
        self.add_message(message)
        self.save_user()

    def drop_last_day(self):
        message, xp = journal_service.drop_last_day()
        self.metadata["xp_deducted"] = int(self.metadata.get("xp_deducted", 0)) + xp
        self.add_message(message)
        self.save_user()

    def list_sequences(self):
        from src.application.services.sequence_service import sequence_service
        from src.interfaces.cli.ui.interface import ui
        rows = sequence_service.get_sequences_rows(include_actions=False)
        if not rows:
            self.add_message("No sequences.")
            return
        ui.show_vertical_list(
            rows,
            "SEQUENCES",
            mode="table",
            columns=[("id", "ID"), ("label", "LABEL"), ("value", "DAY")],
        )

    def list_sequences_detailed(self):
        from src.application.services.sequence_service import sequence_service
        from src.interfaces.cli.ui.interface import ui
        rows = sequence_service.get_sequences_rows(include_actions=True)
        if not rows:
            self.add_message("No sequences.")
            return
        for row in rows:
            ids = [a for a in (row["actions"].split(", ") if row["actions"] != "—" else [])]
            names = []
            for aid in ids:
                a = self._actions.get(aid)
                label = getattr(a, "_name", None) if a else None
                names.append(f"{aid} ({label})" if label else aid)
            row["actions"] = ", ".join(names) if names else "—"
        ui.show_vertical_list(
            rows,
            "SEQUENCES + ACTIONS",
            mode="table",
            columns=[("id", "ID"), ("label", "LABEL"), ("value", "DAY"), ("actions", "ACTIONS")],
        )

    def list_days(self):
        from src.interfaces.cli.ui.interface import ui
        from src.application.services.journal_service import journal_service

        path = journal_service.journal_file
        if not os.path.exists(path):
            ui.show_vertical_list([f"(empty) {path}"], "JOURNAL/EVOVE26")
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f]

        ui.show_vertical_list(lines or ["(empty)"], "JOURNAL/EVOVE26")

    def delete_sequence(self, payloads=None):
        seq_id = None
        if isinstance(payloads, list) and payloads:
            seq_id = str(payloads[0]).strip()
        elif payloads is not None:
            seq_id = str(payloads).strip()

        if not seq_id:
            from src.interfaces.cli.ui.interface import WebInputInterrupt
            raise WebInputInterrupt("sequence id to delete", type="numeric")

        from src.application.services.sequence_service import sequence_service
        msg = sequence_service.delete_sequence(seq_id)
        self.add_message(msg)
        self.save_user()

    def new_sequence(self, label=None, start_value=None):
        if label is None:
            from src.interfaces.cli.ui.interface import WebInputInterrupt
            raise WebInputInterrupt("sequence label", type="text")
        
        if start_value is None:
            from src.interfaces.cli.ui.interface import WebInputInterrupt
            raise WebInputInterrupt("start value (integer)", type="numeric", options={"label": label})

        try:
            val = int(start_value)
            from src.application.services.sequence_service import sequence_service
            msg = sequence_service.create_sequence(label, val)
            self.add_message(msg)
            self.save_user()
        except ValueError:
            self.add_message("Invalid start value. Must be an integer.")

    def sequence_add_action(self, payloads=None, sequence_index=None):
        if isinstance(payloads, list):
            seq_id = str(payloads[0]).strip() if len(payloads) > 0 else None
            raw = str(payloads[1]).strip() if len(payloads) > 1 else ""
        else:
            raw = str(payloads or "").strip()
            seq_id = str(sequence_index).strip() if sequence_index is not None else None

        if not raw.isdigit() or len(raw) != 2:
            self.add_message(f"Invalid action id '{raw}'. Need 2 digits.")
            return
        full_action_id = f"5{raw}"
        if full_action_id not in self._actions:
            self.add_message(f"Action {full_action_id} not found.")
            return

        from src.application.services.sequence_service import sequence_service
        seqs = sequence_service.sequences.get("sequences", [])
        if not seqs:
            self.add_message("No sequences available. Create one first (24).")
            return

        if not seq_id:
            if len(seqs) == 1:
                seq_id = str(seqs[0].get("id", ""))
            else:
                from src.interfaces.cli.ui.interface import WebInputInterrupt
                raise WebInputInterrupt(
                    "sequence index for action link",
                    type="numeric",
                    options={"action_id_suffix": raw},
                )

        msg = sequence_service.add_action_to_sequence(seq_id, full_action_id)
        self.add_message(msg)
        self.save_user()

    def save_user(self):
        data_dir = get_evove_data_dir()
        data_file = os.path.join(data_dir, "user.json")

        # Cria o diretório se não existir
        os.makedirs(data_dir, exist_ok=True)

        # Usamos total_points (que lê do metadata['score']) como valor de score para o JSON
        current_score = self.total_points
        self._update_max_progress_metrics()
            
        data = {
            "username": self.metadata.get("username") or get_current_username(),
            "score": current_score,
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
            "shop_items": self._shop_items,
            "shop_action_links": self._shop_action_links,
            "active_items": self._active_items,
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
            from src.infrastructure.backup_service import backup_json
            backup_json(data_file)
            # self.add_message(f"file saved.")
            self.load_user()
        except Exception as e:
            self.add_message(f"Error saving {e}")

    def load_user(self):
        self._progression_tiers_cache = None
        data_dir = get_evove_data_dir()
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
        if data.get("username"):
            self.metadata["username"] = data.get("username")
            
        self._ensure_tutorial_state()
        self._update_max_progress_metrics()
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
        self._shop_items = data.get("shop_items", {}) or {}
        self._active_items = list(data.get("active_items", []) or [])

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
        self.metadata["username"] = get_current_username()
        if "energy" not in self.metadata:
            self.metadata["energy"] = 1000
        self.metadata["max_score"] = float(self.metadata.get("max_score", 0) or 0)
        self.metadata["max_xp"] = float(self.metadata.get("max_xp", 0) or 0)
        self.metadata["skill_points"] = int(self.metadata.get("skill_points", 0) or 0)
        self.metadata["stage"] = max(1, int(self.metadata.get("stage", 1) or 1))
        days_until_checkpoint = self.metadata.get("days_until_next_checkpoint")
        if days_until_checkpoint is None:
            legacy_next_checkpoint_day = int(self.metadata.get("next_checkpoint_day", 0) or 0)
            if legacy_next_checkpoint_day > 0:
                from src.application.services.sequence_service import sequence_service
                current_day = sequence_service.days_since_first_activity()
                if current_day > 0:
                    days_until_checkpoint = max(0, legacy_next_checkpoint_day - current_day)
                else:
                    days_until_checkpoint = legacy_next_checkpoint_day
            else:
                days_until_checkpoint = self._checkpoint_interval_for_stage(self.metadata["stage"])
        self.metadata["days_until_next_checkpoint"] = int(days_until_checkpoint or 0)
        self.metadata["last_checkpoint_check"] = self.metadata.get("last_checkpoint_check") or datetime.now().strftime("%Y-%m-%d")
        if "highest_rank_rewarded" not in self.metadata:
            self.metadata["highest_rank_rewarded"] = int(self.get_progression_state().get("rank_index", 0))
        else:
            self.metadata["highest_rank_rewarded"] = int(self.metadata.get("highest_rank_rewarded", 0) or 0)
    
    

    def open_shop(self):
        """Displays shop items"""
        from src.application.services.shop_service import ShopService
        
        shop = ShopService(self)
        shop.show_items()


    def buy_shop_item(self, item_id=None):
        """Buys a shop item. item_id can be passed from dial or buffer."""
        from src.application.services.shop_service import ShopService

        shop = ShopService(self)

        target_id = item_id
        if isinstance(item_id, list) and item_id:
            target_id = "".join(str(part) for part in item_id)

        norm_id = self._normalize_shop_item_id(target_id)

        if norm_id in self._active_items:
            item = shop.get_item(target_id)
            name = item["name"] if item else target_id
            self.add_message(f"{name} já ativo hoje.")
            return

        self._active_items.append(norm_id)

        if shop.buy_item(target_id):
            self.save_user()
        else:
            self._active_items.remove(norm_id)

    def create_shop_item(self, step=None, data=None, value=None):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        from src.interfaces.cli.ui.interface import WebInputInterrupt

        data = data or {}
        clean_data = {k: v for k, v in data.items() if k != "create_step"}
        step = step or "shop_item_name"

        if step == "shop_item_name":
            name = str(value or "").strip()
            if not name:
                raise WebInputInterrupt(
                    "shop item name",
                    type="text",
                    options={"create_step": "shop_item_name", "autocomplete": "names"},
                )
            clean_data["name"] = name
            raise WebInputInterrupt(
                "shop item cost",
                type="numeric",
                options={**clean_data, "create_step": "shop_item_cost"},
            )

        if step == "shop_item_cost":
            name = str(clean_data.get("name", "")).strip()
            if not name:
                raise WebInputInterrupt(
                    "shop item name",
                    type="text",
                    options={"create_step": "shop_item_name", "autocomplete": "names"},
                )
            try:
                cost = int(value)
            except Exception:
                self.add_message("Invalid shop item cost.")
                raise WebInputInterrupt(
                    "shop item cost",
                    type="numeric",
                    options={**clean_data, "create_step": "shop_item_cost"},
                )
            if cost < 0:
                self.add_message("Shop item cost must be 0 or greater.")
                raise WebInputInterrupt(
                    "shop item cost",
                    type="numeric",
                    options={**clean_data, "create_step": "shop_item_cost"},
                )

            nextid = self.next_shop_item_id
            if nextid > 99:
                self.add_message("Shop item limit reached (max ID 99).")
                return

            new_id = str(nextid)
            self._shop_items[new_id] = {"name": name, "cost": cost}
            self.add_message(f"shop item '{name}' created with ID {new_id}")
            self.save_user()
            return

        raise WebInputInterrupt(
            "shop item name",
            type="text",
            options={"create_step": "shop_item_name", "autocomplete": "names"},
        )

    def _normalize_shop_item_id(self, shop_item_id):
        if isinstance(shop_item_id, str):
            return shop_item_id.lstrip("0") or "0"
        return str(shop_item_id).lstrip("0") or "0"

    def is_shop_item_purchased(self, shop_item_id):
        return self._normalize_shop_item_id(shop_item_id) in self._active_items

    def create_attribute(self, name=None):
        mode = self.metadata.get("mode", "progressive")
        if mode == "semi-progressive":
            self.add_message("[ MODE ] Manual creation disabled in semi-progressive mode.")
            return

        if name is None:
            from src.interfaces.cli.ui.interface import WebInputInterrupt
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
                from src.interfaces.cli.ui.interface import WebInputInterrupt
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

        from src.interfaces.cli.ui.interface import ui, WebInputInterrupt

        data = data or {}
        clean_data = {k: v for k, v in data.items() if k != "create_step"}
        step = step or "action_type"

        if step == "action_type":
            try:
                tipo = int(value)
            except Exception:
                ui.show_list(
                    [
                        "1 - Repetition",
                        "2 - Seconds",
                        "3 - Minutes",
                        "4 - Hours",
                        "5 - Letters",
                        "6 - Lines",
                        "7 - Words",
                        "8 - Group",
                    ],
                    "UNIT TYPE",
                )
                raise WebInputInterrupt("unit type", type="numeric", options={"create_step": "action_type"})
            if tipo < 1 or tipo > 8:
                self.add_message("Invalid unit type. Use 1-7.")
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

            self.add_message(f"action '{action.name}' created with ID {new_id}")
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
            from src.interfaces.cli.ui.interface import WebInputInterrupt
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
            from src.interfaces.cli.ui.interface import WebInputInterrupt
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

        from src.interfaces.cli.ui.interface import ui, WebInputInterrupt

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
            from src.interfaces.cli.ui.interface import WebInputInterrupt
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
        from src.interfaces.cli.ui.interface import WebInputInterrupt
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
        from src.interfaces.cli.ui.interface import WebInputInterrupt
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
            return {"prompt": "edit action type (0-7, blank keep)", "type": "numeric", "options": {"edit_step": "action_type", "action_id": data.get("action_id"), "name": data["name"]}}

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
        from src.interfaces.cli.ui.interface import WebInputInterrupt
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
        from src.interfaces.cli.ui.interface import WebInputInterrupt
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
        from src.interfaces.cli.ui.interface import WebInputInterrupt
        raise WebInputInterrupt(
            "edit status name (blank keep)",
            type="text",
            options={"edit_step": "status_name", "status_id": status_id, "autocomplete": "names"},
        )

    def edit_tag(self, payloads):
        if not payloads or not payloads[0]:
            self.add_message("Invalid tag ID.")
            return
        tag_id = f"1{payloads[0]}"
        tag = self._tags.get(tag_id)
        if not tag:
            self.add_message(f"Tag ID ({tag_id}) not found")
            return
        from src.interfaces.cli.ui.interface import WebInputInterrupt
        raise WebInputInterrupt(
            "edit tag name (blank keep)",
            type="text",
            options={"edit_step": "tag_name", "tag_id": tag_id, "autocomplete": "names"},
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

        if step == "tag_name":
            tag = self._tags.get(data.get("tag_id"))
            if not tag:
                self.add_message("Tag not found.")
                return None
            if val.strip():
                tag._name = val.strip()
            self.add_message(f"Tag {tag._name} ({tag._id}) updated.")
            self.save_user()
            return None

        self.add_message("Edit error: invalid step.")
        return None

    def shop_item_add_action(self, payloads):
        if len(payloads) < 2:
            self.add_message("Invalid shop item/action IDs.")
            return
        from src.application.services.shop_service import ShopService

        shop_item_id = self._normalize_shop_item_id(payloads[0])
        if not ShopService(self).get_item(shop_item_id):
            self.add_message(f"Shop item {shop_item_id} not found.")
            return
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
            from src.interfaces.cli.ui.interface import WebInputInterrupt
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
            from src.interfaces.cli.ui.interface import WebInputInterrupt
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
            7: 1.0,  # words
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
            from src.interfaces.cli.ui.interface import ui
            items = [f"({attr._id}) - {attr._name} - {attr.power_display}" for attr in self._attributes.values()]
            ui.show_vertical_list(items, "CURRENT ATTRIBUTES")
        else:
            self.add_message("no attributes available. try creating one with 28...")
    
    def list_actions(self):
        if self._actions:
            from src.interfaces.cli.ui.interface import ui
            items = [f"({action._id}) - {action._name}" for action in self._actions.values() if not getattr(action, "_deleted", False)]
            ui.show_list(items, "CURRENT ACTIONS")
        else:
            self.add_message("no actions available. try creating one with 25...")

    def list_statuses(self):
        if not self._statuses:
            self.add_message("no statuses available. try creating one with 24...")
            return
        from datetime import datetime
        from src.interfaces.cli.ui.interface import ui
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
            from src.interfaces.cli.ui.interface import ui
            ui.show_list(items, "ACTIVE STATUSES")
        else:
            self.add_message("no active statuses.")
        self.save_user()

    def list_tags(self):
        if self._tags:
            from src.interfaces.cli.ui.interface import ui
            items = [f"({tag._id}) - {tag._name}" for tag in self._tags.values()]
            ui.show_list(items, "CURRENT TAGS")
        else:
            self.add_message("no tags available. try creating one with 21...")

    def list_actions_detailed(self):
        from src.interfaces.cli.ui.interface import ui
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
            items.append(
                f"({action._id}) {action._name} | value {action.value}/{action.max_value} | "
                f"score {action.score:.2f} | tags: {tags_str}"
            )
        if items:
            ui.show_list(items, "ACTIONS (DETAILED)")
        else:
            self.add_message("no actions available.")

    def list_params_full(self):
        from src.interfaces.cli.ui.interface import ui
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
        from src.interfaces.cli.ui.interface import ui
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
        from src.interfaces.cli.ui.interface import ui
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
        from src.interfaces.cli.ui.interface import ui
        from src.application.services.sleep_service import sleep_service
        from src.application.services.sequence_service import sequence_service
        current_entity = EntityManager().get_entity()
        meta = self.metadata

        progress = self.get_progression_state()
        sleep_info = sleep_service.get_last_sleep()
        if sleep_info:
            sleep_text = f"{sleep_info.get('duration', '-')}"
        else:
            sleep_text = "no data"

        days = sequence_service.days_since_first_activity()
        day_text = str(days)
        checkpoint_days = self.get_days_until_next_checkpoint()
        roko_satisfaction = 0
        roko_mood = "none"
        roko_name = "ROKO"
        if current_entity:
            try:
                roko_satisfaction = int(round(current_entity.satisfaction))
            except Exception:
                roko_satisfaction = 0
            roko_name = f"ROKO ({self._get_roko_adjective()})"
            if hasattr(current_entity, "_get_mood"):
                roko_mood = str(current_entity._get_mood()).upper()

        items = [
            "USER",
            f"SLEEP: {sleep_text}",
            f"DAY: {day_text}",
            f"CHECKPOINT: {checkpoint_days} days",
            f"LEVEL: {progress['level']}",
            f"RANK: {progress['rank_symbol']}",
            f"NEXT: {progress['next_xp']} XP",
            f"SATISFACTION: {self.get_user_felicity():.0f}%",
            "",
            "ATTRIBUTES",
        ]

        if self._attributes:
            for attr in self._attributes.values():
                items.append(f"({attr._id}) {attr._name} :: {attr.power_display}")
        else:
            items.append("No attributes yet.")

        items.extend([
            "",
            roko_name,
            f"SATISFACTION: {roko_satisfaction}%",
            f"MOOD: {roko_mood}",
        ])

        ui.show_vertical_list(items, "USER / ROKO")

    def _action_connection_color(self, action_id):
        """Returns 'white', 'yellow', or 'blue' based on transitive object connectivity."""
        aid = str(action_id)

        has_attr = any(
            any(str(a.id) == aid for a in attr._related_actions)
            for attr in self._attributes.values()
        )

        tag_links = self._action_tags.get(aid, [])
        has_tag = bool(tag_links)

        tag_ids = {str(tl.get("tag_id", "")) for tl in tag_links}
        param_ids = set()
        for pid, pt_list in self._param_tags.items():
            for pt in pt_list:
                if str(pt.get("tag_id", "")) in tag_ids:
                    param_ids.add(pid)
        has_param = bool(param_ids)

        has_status = any(
            any(str(pl.get("param_id", "")) in param_ids for pl in status._param_links)
            for status in self._statuses.values()
        )

        if has_attr and has_tag and has_param and has_status:
            return "white"
        if has_attr or has_tag or has_param or has_status:
            return "yellow"
        return "blue"

    def show_object_tree(self):
        from src.interfaces.cli.ui.interface import ui

        W   = "\033[97m"   # bright white
        Y   = "\033[33m"   # yellow
        BL  = "\033[94m"   # bright blue
        C   = "\033[36m"   # cyan — attributes
        DIM = "\033[2m"
        R   = "\033[0m"

        # tag_id → set of param_ids
        tag_to_params = {}
        for pid, pt_list in self._param_tags.items():
            for pt in pt_list:
                tid = str(pt.get("tag_id", ""))
                tag_to_params.setdefault(tid, set()).add(pid)

        # param_id → set of status_ids
        param_to_statuses = {}
        for sid, status in self._statuses.items():
            for pl in status._param_links:
                pid = str(pl.get("param_id", ""))
                param_to_statuses.setdefault(pid, set()).add(sid)

        # action_id → has attribute link
        action_to_attrs = {}
        for attr in self._attributes.values():
            for action in attr._related_actions:
                action_to_attrs.setdefault(str(action.id), set()).add(attr._id)

        def col(action_id):
            c = self._action_connection_color(action_id)
            return W if c == "white" else (Y if c == "yellow" else BL)

        def tag_chain(tid):
            tag = self._tags.get(str(tid))
            name = tag._name if tag else str(tid)
            params = tag_to_params.get(str(tid), set())
            pnames = [self._parameters[p]._name for p in params if p in self._parameters]
            snames = []
            for p in params:
                for s in param_to_statuses.get(p, set()):
                    if s in self._statuses:
                        snames.append(self._statuses[s]._name)
            parts = [f"{DIM}{tid}{R} {name}"]
            if pnames:
                parts.append(f"{DIM}→{R} {', '.join(pnames)}")
            if snames:
                parts.append(f"{DIM}→{R} {', '.join(snames)}")
            return "  ".join(parts)

        lines = []

        def append_action(action, prefix, is_last):
            aid = str(action.id)
            conn = "└── " if is_last else "├── "
            lines.append(f"{prefix}{conn}{col(aid)}{action.id} {action.name}{R}")
            tag_ids = [str(tl.get("tag_id", "")) for tl in self._action_tags.get(aid, []) if tl.get("tag_id")]
            sub = prefix + ("    " if is_last else "│   ")
            for j, tid in enumerate(tag_ids):
                tconn = "└── " if j == len(tag_ids) - 1 else "├── "
                lines.append(f"{sub}{tconn}{tag_chain(tid)}")

        def append_attr(attr, prefix, is_last):
            conn = "└── " if is_last else "├── "
            lines.append(f"{prefix}{conn}{C}{attr._id} {attr._name}{R}")
            sub = prefix + ("    " if is_last else "│   ")
            children = attr._children
            actions = [a for a in attr._related_actions if not getattr(a, "_deleted", False)]
            total = len(children) + len(actions)
            for j, child in enumerate(children):
                append_attr(child, sub, j == len(children) - 1 and not actions)
            for j, action in enumerate(actions):
                append_action(action, sub, j == len(actions) - 1)

        root_attrs = [a for a in self._attributes.values() if not a._parent]
        unlinked = [a for a in self._actions.values()
                    if not getattr(a, "_deleted", False) and str(a.id) not in action_to_attrs]

        for i, attr in enumerate(root_attrs):
            append_attr(attr, "", i == len(root_attrs) - 1 and not unlinked)

        if unlinked:
            lines.append(f"└── {DIM}UNLINKED{R}")
            for i, action in enumerate(unlinked):
                append_action(action, "    ", i == len(unlinked) - 1)

        ui.show_tree_scroll(lines, "OBJECTS")

    def _collect_autocomplete_names(self):
        import json
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(os.path.dirname(base_dir))
        data_dir = os.path.join(src_dir, "infrastructure", "data")
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
            from src.interfaces.cli.ui.interface import ui
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
        from src.interfaces.cli.ui.interface import ui
        if ui.ask_confirmation("This will PERMANENTLY DELETE ALL ATTRIBUTES."):
            self._attributes.clear()
            self.add_message("attributes deleted.")
            self.save_user()
        else:
            self.add_message("the attributes are safe.")
    
    def drop_actions(self):
        from src.interfaces.cli.ui.interface import ui
        if ui.ask_confirmation("This will PERMANENTLY DELETE ALL ACTIONS."):
            self._actions.clear()
            self.add_message("actions deleted.")
            self.save_user()
        else:
            self.add_message("the actions are safe.")

    def drop_parameters(self):
        from src.interfaces.cli.ui.interface import ui
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

        from src.interfaces.cli.ui.interface import ui, WebInputInterrupt
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

        from src.interfaces.cli.ui.interface import ui, WebInputInterrupt
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

        from src.interfaces.cli.ui.interface import ui, WebInputInterrupt
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

        from src.interfaces.cli.ui.interface import ui, WebInputInterrupt
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

    def delete_tag(self, payloads, confirmed=None):
        payload_id = f"1{payloads[0]}"
        tag = self._tags.get(payload_id)

        if not tag:
            self.add_message(f"Tag ID ({payload_id}) not found")
            return

        from src.interfaces.cli.ui.interface import ui, WebInputInterrupt
        if confirmed is True:
            pass
        elif ui.web_mode:
            import random
            code = "".join([str(random.randint(0, 9)) for _ in range(3)])
            self.add_message(f"Delete {tag._name} ({tag._id})?")
            self.add_message(f"Type the code: {code}")
            raise WebInputInterrupt(
                f"Confirm code: {code}",
                type="confirm",
                options={"code": code, "payloads": payloads, "action": "delete_tag"},
            )
        elif not ui.ask_confirmation(f"Delete tag {tag._name} ({tag._id})?"):
            return

        self._tags.pop(payload_id, None)
        for action_id, links in list(self._action_tags.items()):
            new_links = [link for link in links if link.get("tag_id") != payload_id]
            if new_links:
                self._action_tags[action_id] = new_links
            else:
                self._action_tags.pop(action_id, None)
        for param_id, links in list(self._param_tags.items()):
            new_links = [link for link in links if link.get("tag_id") != payload_id]
            if new_links:
                self._param_tags[param_id] = new_links
            else:
                self._param_tags.pop(param_id, None)

        self.add_message(f"Tag {tag._name} ({tag._id}) deleted.")
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
