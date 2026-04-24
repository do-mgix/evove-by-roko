import random


class PortugueseDictionary:
    def __init__(self):
        self.words = {
            "nouns": [
                "caminho",
                "ritmo",
                "foco",
                "pausa",
                "vento",
                "chama",
                "maré",
                "fôlego",
                "silêncio",
                "passo",
                "mapa",
                "eco",
                "fluxo",
                "porta",
                "trilha",
                "brisa",
            ],
            "verbs": [
                "alinha",
                "abre",
                "acalma",
                "desperta",
                "molda",
                "sustenta",
                "guia",
                "corta",
                "move",
                "ilumina",
                "costura",
                "ergue",
            ],
            "adjectives": [
                "leve",
                "claro",
                "sereno",
                "forte",
                "vivo",
                "limpo",
                "preciso",
                "calmo",
                "breve",
                "pleno",
            ],
            "adverbs": [
                "agora",
                "devagar",
                "em frente",
                "sem pressa",
                "com calma",
                "em silêncio",
                "com foco",
                "de leve",
            ],
            "connectives": [
                "e",
                "mas",
                "porque",
                "então",
                "quando",
            ],
        }

    def pick(self, category):
        return random.choice(self.words[category])


class RokoMessageService:
    def __init__(self):
        self.dictionary = PortugueseDictionary()
        self.templates = [
            "ROKO: {verb} o {noun} {adverb}.",
            "ROKO: {adjective} {noun} {connective} {verb} o dia.",
            "ROKO: o {noun} fica {adjective} quando você {verb}.",
            "ROKO: {adjective} e {adjective}, o {noun} segue {adverb}.",
            "ROKO: {verb} o {noun} {connective} mantém o passo.",
            "ROKO: {adverb}, o {noun} encontra {adjective}.",
        ]

    def generate(self):
        template = random.choice(self.templates)
        phrase = template.format(
            noun=self.dictionary.pick("nouns"),
            verb=self.dictionary.pick("verbs"),
            adjective=self.dictionary.pick("adjectives"),
            adverb=self.dictionary.pick("adverbs"),
            connective=self.dictionary.pick("connectives"),
        )
        return self._normalize(phrase)

    def _normalize(self, message):
        prefix, body = "ROKO:", message.split("ROKO:", 1)[1].strip()
        if not body:
            return prefix
        return f"{prefix} {body.upper()}"


roko_message_service = RokoMessageService()
