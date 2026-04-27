import random
from datetime import datetime, timedelta

try:
    from wordtriepy import WordTrie
except ImportError:
    WordTrie = None

from src.application.services.roko_message_service import PortugueseDictionary

class BossService:
    MASC_ARTICLES = ["O"]
    FEM_ARTICLES = ["A"]
    
    MASC_NOUNS = ["Caminho", "Tempo", "Foco", "Vento", "Código", "Sistema", "Gesto", "Desafio", "Ritmo", "Espelho", "Chef", "Lobo", "Capitão", "Macaco"]
    MASC_ADJS = ["Longo", "Rápido", "Firme", "Claro", "Vasto", "Atento", "Novo", "Antigo", "Sutil", "Pleno", "Fanfarrão", "Pirado", "Poderoso"]
    
    FEM_NOUNS = ["Ação", "Pausa", "Meta", "Visão", "Prática", "Escolha", "Forma", "Vida", "Tarefa", "Jornada", "Chef", "Loba", "Capitã", "Macaca"]
    FEM_ADJS = ["Longa", "Rápida", "Firme", "Clara", "Vasta", "Atenta", "Nova", "Antiga", "Sutil", "Plena", "Fanfarrona", "Pirada", "Poderosa"]

    MASC_ENTITIES = MASC_NOUNS
    FEM_ENTITIES = FEM_NOUNS

    def __init__(self, user):
        self.user = user
        self.dictionary = PortugueseDictionary()
        self.trie = self.dictionary.trie

    def _get_trie_word(self, gender="m"):
        if not self.trie:
            return None
        
        for _ in range(5):
            prefix = random.choice("abcdefghijklmnopqrstuvwxyz")
            try:
                words = self.trie.get_words_by_prefix(prefix)
                if words:
                    if gender == "m":
                        filtered = [w for w in words if w.endswith(('o', 'r', 'l', 'm', 'i', 'u', 's')) and len(w) > 3]
                    else:
                        filtered = [w for w in words if w.endswith(('a', 'ã', 'e')) and len(w) > 3]
                    
                    res = random.choice(filtered) if filtered else random.choice(words)
                    return res.capitalize()
            except:
                continue
        return None

    def _generate_attack_name(self, gender="m"):
        verb = self._get_trie_word(gender) or random.choice(self.MASC_NOUNS if gender == "m" else self.FEM_NOUNS)
        adj = self._get_trie_word(gender) or random.choice(self.MASC_ADJS if gender == "m" else self.FEM_ADJS)
        return f"{verb} {adj}"

    def generate_name(self):
        gender = random.choice(["m", "f"])
        if gender == "m":
            article = random.choice(self.MASC_ARTICLES)
            noun = self._get_trie_word("m") or random.choice(self.MASC_NOUNS)
            adj = self._get_trie_word("m") or random.choice(self.MASC_ADJS)
        else:
            article = random.choice(self.FEM_ARTICLES)
            noun = self._get_trie_word("f") or random.choice(self.FEM_NOUNS)
            adj = self._get_trie_word("f") or random.choice(self.FEM_ADJS)
        return f"{article} {noun} {adj}"

    def get_encounter(self):
        return self.user.metadata.get("enemy_encounter")

    def check_and_generate(self, now=None):
        if now is None:
            now = datetime.now()
        encounter = self.get_encounter()
        today_str = now.strftime("%Y-%m-%d")
        if not encounter:
            self.generate_new_encounter(today_str)
            return True
        last_day_check = self.user.metadata.get("encounter_day_check")
        if last_day_check != today_str:
            encounter["days_remaining"] = max(0, encounter["days_remaining"] - 1)
            self.user.metadata["encounter_day_check"] = today_str
            if encounter["days_remaining"] <= 0:
                self.handle_loss()
                self.generate_new_encounter(today_str)
                return True
            else:
                self.user.save_user()
        return False

    def handle_loss(self):
        current_xp = self.user.total_points
        penalty = int(current_xp * 0.1) + 100
        self.user.metadata["score"] = max(0, float(self.user.metadata.get("score", 0)) - penalty)
        self.user.add_message(f"BOSS ESCAPOU! Penalidade: -{penalty} XP.")

    def handle_win(self):
        encounter = self.get_encounter()
        if not encounter: return
        
        # Calcula recompensa baseada no total atual
        current_total = float(self.user.total_points)
        reward_xp = int(current_total * 0.015) + 1000
        
        # Incrementa o score global diretamente
        current_score = float(self.user.metadata.get("score", 0))
        self.user.metadata["score"] = current_score + reward_xp
        
        self.user.metadata["action_xp"] = 0
        self.user.add_message(f"BOSS DERROTADO! Recompensa: +{reward_xp} XP.")

        # Equipamento
        boss_attr = random.choice(encounter["attributes"])
        user_attr = next((a for a in self.user._attributes.values() if a._name == boss_attr["name"]), None)
        user_pwr = user_attr.power if user_attr else 1000
        absolute_boost = max(1000, int(user_pwr * (random.randint(1, 6) / 100)))
        
        item_name = self._get_trie_word(random.choice(["m", "f"])) or random.choice(self.MASC_NOUNS + self.FEM_NOUNS)
        new_item = {"name": item_name, "attribute": boss_attr["name"], "boost_val": absolute_boost}
        
        self.equip_item(new_item)
        # generate_new_encounter já chama self.user.save_user()
        self.generate_new_encounter(datetime.now().strftime("%Y-%m-%d"))

    def equip_item(self, new_item):
        equipped = self.user.metadata.get("equipment", [])
        better_exists = False
        for i, item in enumerate(equipped):
            if item["attribute"] == new_item["attribute"]:
                if new_item["boost_val"] > item.get("boost_val", 0):
                    old_name = item["name"]
                    equipped[i] = new_item
                    self.user.add_message(f"{old_name} -> {new_item['name']} !")
                else:
                    self.user.add_message(f"{new_item['name']} -> {item['name']} !")
                better_exists = True
                break
        if not better_exists:
            if len(equipped) < 4:
                equipped.append(new_item)
                self.user.add_message(f"Novo item: {new_item['name']} !")
            else:
                self.user.add_message("Slots cheios!")
        self.user.metadata["equipment"] = equipped
        self.user.save_user()

    def generate_new_encounter(self, today_str):
        name = self.generate_name()
        attrs = list(self.user._attributes.values())
        if len(attrs) < 2:
            selected_attrs = []
            for i, attr in enumerate(attrs):
                pwr = max(1, attr.power // 1000)
                selected_attrs.append({"name": attr._name, "value": int(pwr * 1.2) + 1, "user_val": pwr})
            while len(selected_attrs) < 2:
                selected_attrs.append({"name": "???", "value": 10, "user_val": 0})
        else:
            chosen = random.sample(attrs, 2)
            selected_attrs = []
            for attr in chosen:
                pwr = max(1, attr.power // 1000)
                selected_attrs.append({"name": attr._name, "value": int(pwr * 1.2) + 1, "user_val": pwr})
        
        greek_symbols = ["α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "ι", "κ", "λ", "μ", "ν", "ξ", "ο", "π", "ρ", "σ", "τ", "υ", "φ", "χ", "ψ", "ω"]
        try:
            prog = self.user.get_progression_state()
            user_rank_idx = prog.get("rank_index", 0)
        except:
            user_rank_idx = 0
        attack_rank_idx = max(1, user_rank_idx // 2)
        attack_rank_idx = min(attack_rank_idx, len(greek_symbols) - 1)
        greek_symbol = greek_symbols[attack_rank_idx]
        attacks = [
            f"{self._generate_attack_name(random.choice(['m', 'f']))} [{greek_symbol}]",
            f"{self._generate_attack_name(random.choice(['m', 'f']))} [{greek_symbol}]"
        ]
        encounter = {"name": name, "attributes": selected_attrs, "attacks": attacks, "days_remaining": 7}
        self.user.metadata["enemy_encounter"] = encounter
        self.user.metadata["encounter_last_marked"] = today_str
        self.user.metadata["encounter_day_check"] = today_str
        self.user.save_user()

boss_service = None
def get_boss_service(user):
    global boss_service
    if boss_service is None: boss_service = BossService(user)
    return boss_service
