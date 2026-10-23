package com.evove.app.ui

/** What the server would answer, for Shots: a profile a few days in. */
object Fixtures {
    private val tiers = """[{"index":0,"label":"leve","marks":1},{"index":1,"label":"média","marks":2},{"index":2,"label":"forte","marks":3},
        {"index":3,"label":"longa","marks":4},{"index":4,"label":"dura","marks":5},{"index":5,"label":"máxima","marks":6}]"""

    private val actions = listOf("corrida", "flexões", "leitura técnica", "escrever narrativa", "meditação", "inglês", "piano", "alongamento", "natação")
        .mapIndexed { i, n -> """{"id":"50101${i}0","name":"${n.uppercase()}","type":3,"diff":2,"tiers":$tiers}""" }
        .joinToString(",", "[", "]")

    private val user = """{"username":"roko","day":40,"consecutive_days":6,"marks":120,"level":7,"rank_letter":"b","rank_name":"beta",
        "rank_symbol":"β","local_level_roman":"III","local_levels_total":5,"level_cost":8,"level_marks":5,"stage":2,"energy":18,
        "points":640,"build_points":640,"tokens":12,"max_tokens":40,"checkpoint_seconds_left":200000,"max_energy":25,
        "nickname":"vento-cinza","passcode":"K3J9","acts":42}"""

    private fun node(key: String, name: String, rank: String, marks: Int, need: Int, star: Int, children: String = "[]", claim: Boolean = false) =
        """{"key":"$key","name":"$name","degree":${4 - star},"star":$star,"is_leaf":${children == "[]"},"rank":"$rank","rank_index":1,
        "marks":$marks,"need":$need,"total_marks":${marks * 3},"children":$children${if (claim) ""","claim":{"ranks":1,"tokens":2,"points":40,"skill_points":1}""" else ""}}"""

    private val tree = """{"roots":[${node("fis", "Físico", "β", 4, 9, 3, "[${node("res", "Resistência", "γ", 2, 5, 1)},${node("for", "Força", "β", 1, 4, 1, claim = true)}]")},
        ${node("men", "Mental", "α", 1, 3, 3, "[${node("foc", "Foco", "α", 2, 3, 1)}]")}]}"""

    private val usage = """[${node("res", "Resistência", "γ", 2, 5, 1).dropLast(1)},"uses":9},${node("foc", "Foco", "α", 2, 3, 1).dropLast(1)},"uses":4}]"""

    private val shopActions = listOf("SPRINT" to 150, "REMO" to 300, "XADREZ" to 0, "YOGA" to 120, "ESCALADA" to 400, "CANTO" to 90, "DESENHO" to 0)
        .joinToString(",", "[", "]") { (n, c) -> """{"name":"$n","code":"5020101","type":3,"diff":2,"cost":$c,"package_attribute":"x","leaves":[{"key":"res","name":"Resistência","weight":0.6}],"author":"roko"}""" }

    private val day = """{"date":"2026-10-20","offset":0,"day":40,"logs":[
        {"id":1,"content":"corrida 5km","period":"mo","thought":{"id":1,"content":"foi leve, dá para mais"}},
        {"id":2,"content":"leitura técnica","period":"ev"},{"id":3,"content":"piano","period":"ni"}],
        "cycle":{"acted":true,"todo":false,"thoughts":1,"logs":3,"day_thought":false,"complete":false}}"""

    /** A profile with every module, met eve, the selector at its second level. */
    val engine = """{"passcode": "M9XWEGPX", "session": 2, "seed": 541472713, "tiles": [{"id": "act", "kind": "act", "label": "agir", "color": "#00f0ff", "glyph": "act", "tone": 1, "polygon": [[2.942, 0.0], [5.0, 0.0], [5.0, 7.0], [3.266, 7.0]], "delay": 220, "fresh": false, "code": "AGIR-7Q"}, {"id": "roko", "kind": "entity", "label": "roko", "color": "#3dfff0", "glyph": "roko", "tone": 3, "polygon": [[1.512, 4.776], [3.172, 4.962], [3.266, 7.0], [1.655, 7.0]], "delay": 304, "fresh": true, "code": "ROKO-9X"}, {"id": "shop", "kind": "shop", "label": "shop", "color": "#7af9ff", "glyph": "shop", "tone": 2, "polygon": [[1.435, 1.23], [2.994, 1.115], [3.102, 3.46], [1.554, 3.35]], "delay": 271, "fresh": true, "code": "LOJA-3K"}, {"id": "agenda", "kind": "agenda", "label": "agenda", "color": "#00a8e8", "glyph": "logs", "tone": 4, "polygon": [[0.0, 0.0], [2.942, 0.0], [2.994, 1.115], [0.0, 1.335]], "delay": 58, "fresh": true, "code": "AGND-4M"}, {"id": "attributes", "kind": "attributes", "label": "atributos", "color": "#00c8ff", "glyph": "attributes", "tone": 5, "polygon": [[0.0, 4.607], [1.512, 4.776], [1.655, 7.0], [0.0, 7.0]], "delay": 345, "fresh": true, "code": "ATRB-6P"}, {"id": "journey", "kind": "journey", "label": "jornada", "color": "#00ffd0", "glyph": "journey", "tone": 6, "polygon": [[0.0, 3.239], [3.102, 3.46], [3.172, 4.962], [0.0, 4.607]], "delay": 334, "fresh": true, "code": "JRND-8T"}, {"id": "build", "kind": "build", "label": "construir", "color": "#00e0ff", "glyph": "build", "tone": 7, "polygon": [[0.0, 1.335], [1.435, 1.23], [1.554, 3.35], [0.0, 3.239]], "delay": 38, "fresh": true, "code": "CNST-2W"}], "hint": "act", "modules": [{"id": "act", "label": "agir", "code": "AGIR-7Q", "on": true}, {"id": "shop", "label": "shop", "code": "LOJA-3K", "on": true}, {"id": "roko", "label": "roko", "code": "ROKO-9X", "on": true}, {"id": "agenda", "label": "agenda", "code": "AGND-4M", "on": true}, {"id": "attributes", "label": "atributos", "code": "ATRB-6P", "on": true}, {"id": "journey", "label": "jornada", "code": "JRND-8T", "on": true}, {"id": "build", "label": "construir", "code": "CNST-2W", "on": true}], "entities": ["roko", "eve"], "story": {"step": "start", "at": 0, "of": 7, "done": false}, "line": {"entity": "eve", "text": "oi. ele fala alto, né? eu só pergunto coisas."}, "selector": {"level": 2, "turns": 0, "next_at": null, "chance": 0.12}, "counters": {"visits": 2, "acts": 0, "opens": 0, "turns": 0, "talks": 0, "buys": 0, "plans": 0}, "lines": [], "doubted": []}"""

    /** A profile on the story's first step: agir alone, and actions it does not own. */
    val engineFresh = """{"passcode": "M9XWEGPX", "session": 1, "seed": 300083833, "tiles": [{"id": "act", "kind": "act", "label": "agir", "color": "#00f0ff", "glyph": "act", "tone": 1, "polygon": [[2.912, 0.0], [5.0, 0.0], [5.0, 7.0], [3.551, 7.0]], "delay": 185, "fresh": false, "code": "AGIR-7Q"}], "hint": "act", "modules": [{"id": "act", "label": "agir", "code": "AGIR-7Q", "on": true}, {"id": "shop", "label": "shop", "code": null, "on": false}, {"id": "roko", "label": "roko", "code": null, "on": false}, {"id": "agenda", "label": "agenda", "code": null, "on": false}, {"id": "attributes", "label": "atributos", "code": null, "on": false}, {"id": "journey", "label": "jornada", "code": null, "on": false}, {"id": "build", "label": "construir", "code": null, "on": false}], "entities": [], "story": {"step": "start", "at": 0, "of": 7, "done": false}, "line": {"entity": "roko", "text": "AGE."}, "selector": {"level": 1, "turns": 0, "next_at": 1000, "chance": null}, "counters": {"visits": 1, "acts": 0, "opens": 0, "turns": 0, "talks": 0, "buys": 0, "plans": 0}, "lines": [], "doubted": ["CORRIDA", "PIANO"]}"""

    fun answer(method: String, path: String): String = when {
        path.startsWith("/engine") -> engine
        path.startsWith("/auth/me") -> """{"user_id":1,"username":"roko","created_at":"2026-09-10T10:00:00","email":"a@b.c",
            "session":{"created_at":"2026-10-20T08:00:00","expires_at":"2026-11-20T08:00:00"},"active_sessions":2}"""
        path.startsWith("/allies") -> """{"passcode":"K3J9","items":[{"nickname":"lobo-azul","marks":300,"stage":3}]}"""
        path.startsWith("/emblems") -> "[]"
        path.startsWith("/logs") -> """{"day":40,"offset":0,"date":"2026-10-20","logs":[{"id":1,"content":"corrida: 5km","marks":3,"tokens":2,"order":1,"period":"mo"},
            {"id":2,"content":"leitura técnica","marks":2,"order":2,"period":"ev"}]}"""
        path.startsWith("/calendar") -> """{"year":2026,"month":10,"days":{"2026-10-03":{"log_count":2},"2026-10-25":{"events":[{"id":"e","label":"prova"}]}}}"""
        path.startsWith("/user-attributes") -> """[{"id":1,"name":"escrita","is_leaf":true,"rank":"α","marks":1,"need":3}]"""
        path.startsWith("/attributes/recent") -> usage
        path.startsWith("/actions") && path.contains("/window") -> """{"window_marks":2,"limit":5,"hours":6}"""
        path.startsWith("/actions") -> actions
        path.startsWith("/user") -> user
        path.startsWith("/attributes/tree") -> tree
        path.startsWith("/attributes/usage") -> usage
        path.startsWith("/attributes") -> "[]"
        path.startsWith("/shop") -> """{"phase":"frames","left":3,"found":12,"catalog":80,"points":640,"new":[],
            "groups":[{"key":"fis","name":"Físico","actions":$shopActions}]}"""
        path.startsWith("/journey/boss") -> """{"boss":{"name":"Golem de Areia","rank":"β","type":"terra","hp":120,"types":[{"key":"fis","name":"Físico"}],
            "abilities":[{"name":"Tremor","power":12}]},"beaten":false,"lineup":[{"action_id":"1","name":"CORRIDA (β)","damage":14,"multiplier":1.5,"kinship":"físico"}],"hp":18,"reward":80}"""
        path.startsWith("/journey") -> """{"stage":2,"stage_days":7,"seconds_left":300000,"seconds_to_next_point":40000,"energy":18,"max_energy":25,
            "tokens":12,"resets":1,"points":[{"day":2,"reached":true},{"day":4,"reached":false},{"day":6,"reached":false}],
            "recover":[{"kind":"small","cost":3,"heal":5,"ready":true},{"kind":"large","cost":8,"heal":15,"ready":false,"blocked":"cooldown","seconds_left":5000}]}"""
        path.startsWith("/agenda/day") -> day
        path.startsWith("/todos") -> """{"items":[{"id":1,"title":"terminar capítulo","actions":[{"id":"1","name":"ESCREVER","acted":true}]}]}"""
        path.startsWith("/projects") -> """{"items":[{"id":"p","name":"livro","active":true,"stats":{"todos":3,"todos_done":1}}]}"""
        path.startsWith("/entities") && path.endsWith("/talk") -> """{"entity":"roko","present":true,"line":"VOCÊ VOLTOU. AJA ANTES DE PENSAR DEMAIS."}"""
        path.startsWith("/entities") -> """[{"id":"roko","name":"ROKO","title":"o autor","color":"#3dfff0","personality":"autoritário","presence":0.8,"stats":{"humor":"seco"}},
            {"id":"eve","name":"EVE","title":"A QUE PERGUNTA","color":"#ff9de2","personality":"curiosa","voice":"lower","presence":0.55,"stats":{"tipo":"DÚVIDA"}}]"""
        else -> "{}"
    }
}
