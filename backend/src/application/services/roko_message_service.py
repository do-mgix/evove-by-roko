import random
try:
    from wordtriepy import WordTrie
except ImportError:
    WordTrie = None


class PortugueseDictionary:
    _WORD_BANK = {
        "nouns": {
            "words": [
                "caminho", "ritmo", "foco", "pausa", "vento", "chama", "maré", "fôlego",
                "silêncio", "passo", "mapa", "eco", "fluxo", "porta", "trilha", "brisa",
                "horizonte", "impulso", "abrigo", "centelha", "memória", "travessia",
                "pulso", "gesto", "clareza", "cuidado", "origem", "ponte", "presença",
                "contorno", "rumo", "compasso", "raiz", "textura", "vigília", "respiro",
            ],
        },
        "verbs": {
            "words": [
                "alinha", "abre", "acalma", "desperta", "molda", "sustenta", "guia", "corta",
                "move", "ilumina", "costura", "ergue", "respira", "cuida", "observa",
                "mantém", "fortalece", "organiza", "ajusta", "reconstrói", "protege",
                "acolhe", "prepara", "clareia", "transforma", "preserva", "desata", "firma",
            ],
        },
        "adjectives": {
            "words": [
                "leve", "claro", "sereno", "forte", "vivo", "limpo", "preciso", "calmo",
                "breve", "pleno", "firme", "sutil", "vasto", "inteiro", "nítido",
                "seguro", "atento", "estável", "gentil", "profundo", "luminoso", "contido",
            ],
        },
        "adverbs": {
            "words": [
                "agora", "devagar", "em frente", "sem pressa", "com calma", "em silêncio", "com foco", "de leve",
                "adiante", "cedo", "sempre", "aos poucos", "por inteiro", "com cuidado", "suavemente",
            ],
        },
        "connectives": {
            "words": ["e", "mas", "porque", "então", "quando", "enquanto", "assim", "por isso"],
        },
    }

    def __init__(self):
        self.random = random.SystemRandom()
        self.trie = WordTrie(language="pt") if WordTrie else None
        self.words = self._build_word_bank()

    def pick(self, category):
        return self.random.choice(self.words[category])

    def _build_word_bank(self):
        bank = {}
        for category, config in self._WORD_BANK.items():
            fallback_words = list(config["words"])
            if self.trie is None or category in {"adverbs", "connectives"}:
                bank[category] = fallback_words
                continue
            validated = [word for word in fallback_words if self.trie.exists(word)]
            bank[category] = validated or fallback_words
        return bank


class RokoMessageService:
    def __init__(self):
        self.dictionary = PortugueseDictionary()
        self.random = random.SystemRandom()
        self.templates = [
            "ROKO: {verb} {noun} {adverb}.",
            "ROKO: {noun} fica {adjective} quando você {verb}.",
            "ROKO: {adverb}, {noun} encontra {adjective}.",
            "ROKO: {verb} com {noun} {adverb}.",
            "ROKO: {noun} e {noun2}, movimento {adverb}.",
            "ROKO: {verb} {noun} {connective} mantém o passo.",
            "ROKO: {noun} pede {adjective} e {adjective2}.",
            "ROKO: {verb} {noun} antes de seguir {adverb}.",
        ]

    def generate(self):
        template = self.random.choice(self.templates)
        adjective = self.dictionary.pick("adjectives")
        adjective2 = self._pick_distinct("adjectives", adjective)
        noun = self.dictionary.pick("nouns")
        noun2 = self._pick_distinct("nouns", noun)
        phrase = template.format(
            noun=noun,
            noun2=noun2,
            verb=self.dictionary.pick("verbs"),
            adjective=adjective,
            adjective2=adjective2,
            adverb=self.dictionary.pick("adverbs"),
            connective=self.dictionary.pick("connectives"),
        )
        return self._normalize(phrase)

    def _pick_distinct(self, category, current):
        for _ in range(6):
            candidate = self.dictionary.pick(category)
            if candidate != current:
                return candidate
        return current

    def _normalize(self, message):
        prefix, body = "ROKO:", message.split("ROKO:", 1)[1].strip()
        if not body:
            return prefix
        return f"{prefix} {body.upper()}"


roko_message_service = RokoMessageService()
