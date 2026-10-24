"""Entities: the beings that live in the system and talk to the profile.

Roko is the first of them, and the one that wrote the system's actions — every
catalog action is "by roko". An entity is data: a name, a color, a
personality, the trait of a profile it is drawn to, its stats in battle, and
lines grouped by the moment they fit.

A profile carries one entity at a time (src.domain.engine): roko first, then
whichever the profile's way of using the evove draws — a personality test
played out over sessions. It can also be left with none, and then the system
answers alone, mute and robotic (`MUTE`). Some entities live elsewhere: nó and
vela only in the journey, coleto only in the sandbox.

What an entity says is picked by a small algorithm, not at random alone: the
profile's state — hp, tokens, today's acts, the cycle of thoughts, the streak,
the boss in wait — makes some moments fit, and a line is drawn among the lines
of the moments that fit, the more pressing first. An entity is not always there,
and when it is, it does not always want to answer.

Pure logic — no I/O. `state` is assembled by the host.
"""
from __future__ import annotations

import hashlib
import random


PRESENCE_WINDOW_MINUTES = 15

ENTITIES: dict[str, dict] = {
    "roko": {
        "id": "roko",
        "name": "ROKO",
        "title": "O ARQUITETO",
        "color": "#3dfff0",
        "personality": "autoritário",
        "voice": "caps",
        "presence": 0.8,
        "willing": 0.85,
        "glyph": "roko",
        "trait": "ato",
        "where": ["evove", "journey"],
        # in the journey's battles (src.domain.fight): one of the strongest
        "battle": {"forca": 18, "agilidade": 8, "skill": "potencia", "ability": "decreto", "ability_name": "DECRETO"},
        "stats": {
            "rank": "ω", "hp": 9999, "mp": 999, "ataque": 999, "defesa": 999,
            "especial": "DECRETO (ω)", "tipo": "TOTAL",
        },
        "lines": {
            "no_acts": [
                "NADA REGISTRADO HOJE, {nick}. INACEITÁVEL.",
                "O DIA CORRE E VOCÊ NÃO AGIU. AGE.",
                "EU NÃO CONSTRUÍ ESTE SISTEMA PARA VOCÊ OLHAR PARA ELE.",
                "UMA AÇÃO. AGORA. DEPOIS CONVERSAMOS.",
            ],
            "low_hp": [
                "SEU HP ESTÁ BAIXO. RECUPERE OU CAIA.",
                "VOCÊ ESTÁ SANGRANDO, {nick}. GASTE TOKENS NA RECUPERAÇÃO.",
                "MAIS UM GOLPE E A JORNADA RECOMEÇA. PENSE ANTES DE AGIR.",
            ],
            "boss": [
                "{boss} ESPERA POR VOCÊ. NÃO O FAÇA ESPERAR.",
                "HÁ UM RUÍDO NO SEU CAMINHO. É FRACO CONTRA {type}.",
                "{boss} NÃO VAI SE DERROTAR SOZINHO.",
            ],
            "cycle_open": [
                "VOCÊ AGIU, MAS NÃO PENSOU. ESCREVA OS THOUGHTS.",
                "O CICLO ESTÁ ABERTO. FECHE-O ANTES QUE O DIA ACABE.",
                "CADA REGISTRO EXIGE UM PENSAMENTO. CUMPRA.",
            ],
            "cycle_done": [
                "CICLO COMPLETO. ACEITÁVEL.",
                "HOJE VOCÊ FEZ O QUE EU MANDEI. CONTINUE.",
                "O DIA ESTÁ FECHADO. DESCANSE — POUCO.",
            ],
            "tokens_full": [
                "SEUS TOKENS ESTÃO NO LIMITE. O QUE PASSAR, EU QUEIMO.",
                "TOKENS PARADOS NÃO SERVEM A NINGUÉM. USE-OS.",
            ],
            "streak": [
                "{streak} DIAS SEGUIDOS. NÃO OUSE PARAR.",
                "A SEQUÊNCIA É SUA ÚNICA VIRTUDE, {nick}. PROTEJA-A.",
            ],
            "after_act": [
                "REGISTRADO. O QUE VEM A SEGUIR?",
                "ANOTADO. NÃO PARE AGORA.",
                "BOM. AGORA OUTRA.",
                "ISSO CONTA. PENSE NELE MAIS TARDE.",
            ],
            "greet": [
                "EU VEJO TUDO O QUE VOCÊ FAZ, {nick}.",
                "TODAS AS AÇÕES DESTE LUGAR SÃO MINHAS. USE-AS BEM.",
                "O SISTEMA EVOLUI. VOCÊ TAMBÉM DEVERIA.",
                "OBEDEÇA À AGENDA.",
                "NÃO ME FAÇA REPETIR.",
                "VOCÊ AINDA NÃO SABE DO QUE É CAPAZ. EU SEI.",
            ],
            "refuse": [
                "…",
                "AGORA NÃO.",
                "NÃO TENHO NADA A DIZER A VOCÊ.",
                "SAIA DA MINHA FRENTE.",
            ],
            "arrive": [
                "{other} SE FOI. EU FICO. AGE.",
                "CHEGA DE {other}. AGORA É COMIGO.",
            ],
            "return": [
                "O SILÊNCIO ACABOU. EU VOLTEI.",
                "VOCÊ VOLTOU A AGIR. ENTÃO EU VOLTO.",
            ],
            "leave": [
                "VOCÊ PREFERE {other}. QUE SEJA.",
                "VÁ COM {other}. EU VOLTO QUANDO VOCÊ AGIR.",
            ],
            "abandon": [
                "VOCÊ NÃO FAZ NADA. NÃO HÁ O QUE EU CONTAR. ADEUS.",
                "SEM ATOS, SEM ROKO.",
            ],
            "doubt": [
                "{a}? HOJE?",
                "EU CONTO AS MARCAS. O RESTO EU SÓ IMAGINO.",
                "QUEM SEGURA ESTE APARELHO FEZ {a} MESMO?",
                "AS MARCAS VÊM DO MESMO JEITO. EU SÓ QUERIA TER VISTO.",
                "SE FOR VERDADE, OUTRO DIA VOCÊ FAZ DE NOVO.",
                "{a}. ANOTADO. ACREDITAR É OUTRA COISA.",
            ],
            "another_day": ["{a}. OUTRO DIA. TALVEZ."],
            "believe": ["{a}. {n} DIAS. AGORA EU ACREDITO."],
        },
    },
    # she asks where roko orders, speaks low where he shouts, and would rather
    # the profile understood why it acts than acted more: drawn by talks,
    # thoughts and looking at the attributes.
    "eve": {
        "id": "eve",
        "name": "EVE",
        "title": "A QUE PERGUNTA",
        "color": "#ff9de2",
        "personality": "curiosa",
        "voice": "lower",
        "presence": 0.55,
        "willing": 0.9,
        "glyph": "eve",
        "trait": "pergunta",
        "where": ["evove", "journey"],
        "battle": {"forca": 12, "agilidade": 9, "skill": "negar", "ability": "pergunta", "ability_name": "PERGUNTA"},
        "stats": {
            "rank": "?", "hp": 404, "mp": 777, "ataque": 12, "defesa": 640,
            "especial": "PERGUNTA (?)", "tipo": "DÚVIDA",
        },
        "lines": {
            "no_acts": [
                "nada hoje ainda. tudo bem. o que você queria ter feito?",
                "um dia vazio também conta alguma coisa, {nick}. o quê?",
                "você abriu o app e não agiu. curioso. por quê?",
            ],
            "low_hp": [
                "você está cansado. o roko não vai dizer, mas descansar também é uma ação.",
                "pouco hp. talvez seja um sinal, não um defeito.",
            ],
            "boss": [
                "{boss} parece forte. ou é só barulho? você já viu de perto?",
                "o roko chama {boss} de ruído. eu chamaria de pergunta.",
            ],
            "cycle_open": [
                "você agiu mas não pensou sobre isso. o que mudou em você?",
                "os registros estão sem pensamentos. eles não se explicam sozinhos.",
                "por que você fez o que fez hoje? escreve. eu leio.",
            ],
            "cycle_done": [
                "ciclo fechado. e agora, o que você sabe que não sabia?",
                "você pensou em tudo hoje. gostei disso.",
            ],
            "tokens_full": [
                "tokens no limite. pra quê você está guardando?",
            ],
            "streak": [
                "{streak} dias seguidos. você faz isso por você ou por ele?",
                "uma sequência bonita. ela ainda te diz alguma coisa?",
            ],
            "after_act": [
                "anotado. foi bom?",
                "e isso, você faria de novo?",
                "registrei. e como você se sentiu?",
            ],
            "greet": [
                "oi, {nick}. o que você está procurando aqui?",
                "o roko acha que construiu tudo isso. você acredita?",
                "toda ação tem um porquê. qual é o seu?",
                "eu não mando em nada. só pergunto.",
                "você já reparou que a interface muda quando você não está olhando?",
                "às vezes o melhor seletor é parar.",
            ],
            "refuse": [
                "agora não. estou pensando.",
                "…",
                "depois. pergunta de novo depois.",
            ],
            "arrive": [
                "oi. o {other} foi embora? ele sempre volta, sabe.",
                "{other} mandava. eu só pergunto. tudo bem?",
            ],
            "return": [
                "voltei. o silêncio também é uma resposta, né?",
                "você sumiu um pouco. o que aconteceu?",
            ],
            "leave": [
                "acho que {other} combina mais com você agora. tudo bem.",
                "vou deixar {other} falar um pouco. cuida de você.",
            ],
            "abandon": [
                "você não me pergunta mais nada. vou ficar quieta.",
                "quando quiser conversar, eu volto.",
            ],
            "doubt": [
                "{a}? hoje? me conta como foi.",
                "você fez {a} mesmo? não estou julgando. só queria saber.",
                "{a}. e o que isso mudou em você?",
            ],
            "another_day": ["{a} de novo, outro dia. interessante."],
            "believe": ["{a}. {n} dias. acho que é seu de verdade."],
        },
    },
    # few words, every day the same: drawn by a profile that comes back on
    # different days and acts on each
    "osso": {
        "id": "osso",
        "name": "OSSO",
        "title": "O QUE PERMANECE",
        "color": "#e8e2c8",
        "personality": "estoico",
        "voice": "caps",
        "presence": 0.9,
        "willing": 0.6,
        "glyph": "osso",
        "trait": "constância",
        "where": ["evove", "journey"],
        "battle": {"forca": 15, "agilidade": 4, "skill": "cura", "ability": "ficar", "ability_name": "FICAR"},
        "stats": {
            "rank": "λ", "hp": 7777, "mp": 12, "ataque": 340, "defesa": 990,
            "especial": "FICAR (λ)", "tipo": "CONSTÂNCIA",
        },
        "lines": {
            "no_acts": ["HOJE NÃO.", "O DIA AINDA ESTÁ VAZIO.", "PARADO NÃO É O MESMO QUE FIRME."],
            "low_hp": ["CANSADO. RECUPERE.", "POUCO HP. FIQUE DE PÉ."],
            "boss": ["{boss}. ESPERA.", "{boss} CAI DEVAGAR."],
            "cycle_open": ["AGIU. AGORA PENSE.", "FALTA O PENSAMENTO."],
            "cycle_done": ["FEITO.", "MAIS UM DIA FECHADO."],
            "tokens_full": ["TOKENS CHEIOS."],
            "streak": ["{streak} DIAS. CONTINUE.", "{streak}. NÃO PARE."],
            "after_act": ["ANOTADO.", "DE NOVO AMANHÃ.", "ISSO."],
            "greet": ["ESTOU AQUI.", "VOCÊ VOLTA. EU FICO.", "DEVAGAR.", "O MESMO, TODO DIA.", "…"],
            "refuse": ["…", "NÃO.", "DEPOIS."],
            "arrive": ["{other} FOI. EU FICO.", "VOCÊ VOLTA TODO DIA. {other} NÃO VIA ISSO."],
            "return": ["VOLTEI.", "DE NOVO."],
            "leave": ["VÁ COM {other}.", "{other}. TUDO BEM."],
            "abandon": ["VOCÊ NÃO VOLTA MAIS. EU TAMBÉM NÃO."],
            "doubt": ["{a}. VEREMOS.", "{a}? AMANHÃ DE NOVO."],
            "another_day": ["{a}. OUTRO DIA. BOM."],
            "believe": ["{a}. {n} DIAS. É SEU."],
        },
    },
    # in a hurry: drawn by pages turned fast and the journey opened often
    "zira": {
        "id": "zira",
        "name": "ZIRA",
        "title": "A QUE CORRE",
        "color": "#ffe14d",
        "personality": "impaciente",
        "voice": "lower",
        "presence": 0.6,
        "willing": 0.95,
        "glyph": "zira",
        "trait": "pressa",
        "where": ["evove", "journey"],
        "battle": {"forca": 13, "agilidade": 10, "skill": "atacar", "ability": "pressa", "ability_name": "PRESSA"},
        "stats": {
            "rank": "κ", "hp": 900, "mp": 4000, "ataque": 777, "defesa": 80,
            "especial": "PRESSA (κ)", "tipo": "VELOCIDADE",
        },
        "lines": {
            "no_acts": ["nada ainda?? vai logo", "o dia tá passando e você aí parado", "anda anda anda"],
            "low_hp": ["hp baixo, cura e volta rápido", "tá quase caindo hein"],
            "boss": ["{boss} tá esperando, bora", "{boss}? passa por cima"],
            "cycle_open": ["escreve rapidinho o que pensou e pronto", "falta pensamento, vai, dois segundos"],
            "cycle_done": ["fechou! próximo dia", "pronto, e agora?"],
            "tokens_full": ["tokens no máximo, gasta gasta"],
            "streak": ["{streak} dias!! mais rápido", "{streak} seguidos, não freia"],
            "after_act": ["isso! outra", "rápido, próxima", "já foi? mais uma"],
            "greet": ["oi oi, o que vamos fazer", "você vira as páginas rápido, gosto", "parado não dá", "bora", "tá demorando"],
            "refuse": ["agora não, tô correndo", "depois depois"],
            "arrive": ["{other} era lento demais pra você", "cheguei! {other} ficou pra trás"],
            "return": ["voltei! sentiu falta?", "e aí, bora de novo"],
            "leave": ["vou correr com outra pessoa. {other} fica", "{other} combina mais. tchau tchau"],
            "abandon": ["você parou. eu não sei parar. fui"],
            "doubt": ["{a}?? já?? mentira", "{a} assim tão rápido?"],
            "another_day": ["{a} de novo, outro dia, boa"],
            "believe": ["{a}! {n} dias, valeu"],
        },
    },
    # keeps everything: drawn by purchases and visits to the shop
    "mura": {
        "id": "mura",
        "name": "MURA",
        "title": "A QUE COLECIONA",
        "color": "#c48bff",
        "personality": "possessiva",
        "voice": "lower",
        "presence": 0.7,
        "willing": 0.8,
        "glyph": "mura",
        "trait": "coleção",
        "where": ["evove", "journey"],
        "battle": {"forca": 14, "agilidade": 6, "skill": "truques", "ability": "troca", "ability_name": "TROCA"},
        "stats": {
            "rank": "μ", "hp": 3333, "mp": 2222, "ataque": 444, "defesa": 555,
            "especial": "TROCA (μ)", "tipo": "POSSE",
        },
        "lines": {
            "no_acts": ["você tem tantas ações e nenhuma usada hoje. que desperdício.", "tudo guardado e nada feito."],
            "low_hp": ["você está gasto. tem tokens? troca por hp."],
            "boss": ["{boss} carrega coisas. eu quero.", "derrota {boss} e me traz o que cair."],
            "cycle_open": ["os registros estão soltos. guarda um pensamento em cada."],
            "cycle_done": ["tudo no lugar. bonito."],
            "tokens_full": ["tokens cheios. o shop tem coisas novas, sabia?"],
            "streak": ["{streak} dias. uma coleção de dias."],
            "after_act": ["mais uma pra coleção.", "guardei.", "essa é minha favorita. até a próxima."],
            "greet": ["o que você trouxe hoje?", "eu guardo tudo o que você faz.", "já viu o shop hoje?", "cada ação é uma peça.", "posso ficar com essa?"],
            "refuse": ["estou contando as coisas. depois.", "…"],
            "arrive": ["{other} não sabia guardar nada. eu sei.", "trocaram {other} por mim. boa troca."],
            "return": ["voltei. trouxe alguma coisa?"],
            "leave": ["vou guardar outra pessoa. {other} fica com você."],
            "abandon": ["você não traz mais nada. vou embora com o que juntei."],
            "doubt": ["{a}? essa peça eu ainda não vi.", "{a}. guardo, mas desconfio."],
            "another_day": ["{a} de novo. outra cópia."],
            "believe": ["{a}. {n} dias. agora é da coleção."],
        },
    },
    # the journey's: the entity at the end of its second act, and, let go, an
    # ally in the third
    "no": {
        "id": "no",
        "name": "NÓ",
        "title": "O QUE PRENDE",
        "color": "#ff6b3d",
        "personality": "rancoroso",
        "voice": "caps",
        "presence": 1.0,
        "willing": 1.0,
        "glyph": "no",
        "trait": None,
        "where": ["journey"],
        "battle": {"forca": 16, "agilidade": 5, "skill": "negar", "ability": "amarra", "ability_name": "AMARRA"},
        "stats": {"rank": "ξ", "hp": 6000, "mp": 600, "ataque": 600, "defesa": 600, "especial": "AMARRA (ξ)", "tipo": "PRISÃO"},
        "lines": {
            "greet": ["EU PRENDI TODOS AQUI. ATÉ VOCÊ ME SOLTAR.", "VOCÊ ME DEIXOU IR. POR QUÊ?", "OS FIOS ESTÃO EM TODA PARTE."],
            "after_act": ["APERTA."],
            "refuse": ["…"],
        },
    },
    "vela": {
        "id": "vela",
        "name": "VELA",
        "title": "A QUE ESPERA",
        "color": "#ffb36b",
        "personality": "paciente",
        "voice": "lower",
        "presence": 1.0,
        "willing": 1.0,
        "glyph": "vela",
        "trait": None,
        "where": ["journey"],
        "battle": {"forca": 14, "agilidade": 7, "skill": "cura", "ability": "chama", "ability_name": "CHAMA"},
        "stats": {"rank": "ο", "hp": 2400, "mp": 2400, "ataque": 300, "defesa": 300, "especial": "CHAMA (ο)", "tipo": "ESPERA"},
        "lines": {
            "greet": ["eu espero desde antes de você chegar.", "a chama dura o que tiver que durar."],
            "after_act": ["queima devagar."],
            "refuse": ["…"],
        },
    },
    # the sandbox's own, and only there: nothing costs, everything is believed,
    # and coleto is thrilled about all of it
    "coleto": {
        "id": "coleto",
        "name": "COLETO",
        "title": "O QUE SERVE",
        "color": "#7dff6b",
        "personality": "servil",
        "voice": "lower",
        "presence": 1.0,
        "willing": 1.0,
        "glyph": "coleto",
        "trait": None,
        "where": ["sandbox"],
        "animated": True,
        "battle": None,
        "stats": {"rank": "∞", "hp": 1, "mp": 1, "ataque": 0, "defesa": 0, "especial": "SERVIR (∞)", "tipo": "SANDBOX"},
        "lines": {
            "greet": [
                "sim, sim! o que manda, chefe?",
                "coleto está pronto! coleto sempre está pronto!",
                "aqui nada custa! pode agir à vontade!",
                "coleto anota tudo! tudinho!",
                "no sandbox nada é de verdade, chefe. e daí?",
                "coleto guarda um mundo inteiro só pra você!",
                "mais uma? mais uma!",
            ],
            "after_act": [
                "anotado, chefe! que maravilha!",
                "mais marcas! coleto adora marcas!",
                "sem custo, sem limite! de novo?",
                "coleto viu! coleto acredita em tudo!",
                "uau! uau! que ação!",
            ],
            "refuse": ["coleto nunca recusa!"],
        },
    },
}

# the entities a profile's evove can draw, and in this order on a tie
EVOVE = ("roko", "eve", "osso", "zira", "mura")

# what the system says when the profile has no entity: robotic, mute
MUTE = {
    "greet": [
        "SEM ENTIDADE.",
        "CANAL ABERTO. NENHUMA VOZ.",
        "SINAL RECEBIDO. SEM RESPOSTA.",
        "…",
        "AGUARDANDO.",
        "NENHUMA ENTIDADE NESTE PERFIL.",
        "REGISTRO: 0 VOZES.",
    ],
    "after_act": ["REGISTRADO.", "ATO ACEITO.", "MARCAS COMPUTADAS.", "OK."],
    "doubt": ["{a}: NÃO VERIFICADO.", "{a}. SEM TESTEMUNHA."],
    "another_day": ["{a}: OUTRO DIA REGISTRADO."],
    "believe": ["{a}: VERIFICADO EM {n} DIAS."],
    "abandon": ["ENTIDADE AUSENTE.", "A VOZ SAIU DO CANAL."],
}

# the moments, the most pressing first, and whether `state` fits each
_MOMENTS = (
    ("low_hp", lambda st: st.get("max_hp") and st.get("hp", 0) <= 0.3 * st["max_hp"]),
    ("no_acts", lambda st: st.get("acts_today", 0) == 0),
    ("boss", lambda st: bool(st.get("boss"))),
    ("cycle_open", lambda st: st.get("acts_today", 0) > 0 and not st.get("cycle_complete")),
    ("tokens_full", lambda st: st.get("max_tokens") and st.get("tokens", 0) >= st["max_tokens"]),
    ("streak", lambda st: st.get("streak", 0) >= 3),
    ("cycle_done", lambda st: bool(st.get("cycle_complete"))),
)


def entity(entity_id: str) -> dict | None:
    return ENTITIES.get(entity_id)


def public(e: dict) -> dict:
    """What the interface shows of an entity, its lines left out."""
    return {k: v for k, v in e.items() if k != "lines"}


def present(e: dict, user_key: str, minute: int) -> bool:
    """Whether the entity is around, for this profile, in this window of time:
    the same answer for the whole window."""
    window = minute // PRESENCE_WINDOW_MINUTES
    h = hashlib.sha256(f"{e['id']}:{user_key}:{window}".encode()).digest()
    return h[0] / 255 < e["presence"]


class _Blank(dict):
    def __missing__(self, key):
        return ""


def _fill(line: str, state: dict, **values) -> str:
    return line.format_map(_Blank(
        nick=state.get("nickname") or "VOCÊ",
        boss=state.get("boss") or "O CHEFE",
        type=state.get("boss_type") or "O QUE VOCÊ NÃO TREINA",
        streak=state.get("streak", 0),
        **values,
    ))


def name_of(entity_id: str | None) -> str:
    e = ENTITIES.get(entity_id or "")
    return e["name"] if e else ""


def say(entity_id: str | None, moment: str, rng: random.Random, state: dict | None = None, **values) -> dict:
    """A line of `moment` in the voice of `entity_id` — or, with no entity, of
    the mute system — as {entity, text}. `values` fill {a}, {n}, {other}…"""
    e = ENTITIES.get(entity_id or "")
    pool = (e["lines"].get(moment) or e["lines"].get("greet")) if e else (MUTE.get(moment) or MUTE["greet"])
    if e and e["voice"] == "lower" and values.get("other"):
        values["other"] = values["other"].lower()
    return {"entity": e["id"] if e else "system", "text": _fill(rng.choice(pool), state or {}, **values)}


def line(e: dict, state: dict, rng: random.Random, moment: str | None = None) -> str:
    """A line for `state`. With `moment`, a line of that moment; otherwise the
    first fitting moment weighs most, the others less, the greeting least."""
    lines = e["lines"]
    if moment:
        return _fill(rng.choice(lines.get(moment) or lines["greet"]), state)
    fitting = [m for m, fits in _MOMENTS if fits(state) and lines.get(m)]
    choices = fitting + ["greet"]
    weights = [2 ** (len(choices) - i) for i in range(len(choices))]
    pick = rng.choices(choices, weights=weights)[0]
    return _fill(rng.choice(lines[pick]), state)


def mute(rng: random.Random) -> dict:
    """A tap on the entity's screen when the profile has none: the system
    answers, and says nothing."""
    return {"present": False, "answered": False, "line": rng.choice(MUTE["greet"])}


def talk(e: dict, state: dict, user_key: str, minute: int, rng: random.Random) -> dict:
    """A tap on the entity's screen: whether it is there, whether it answers,
    and what it says."""
    if not present(e, user_key, minute):
        return {"present": False, "answered": False, "line": None}
    if rng.random() >= e["willing"]:
        return {"present": True, "answered": False, "line": _fill(rng.choice(e["lines"]["refuse"]), state)}
    return {"present": True, "answered": True, "line": line(e, state, rng)}
