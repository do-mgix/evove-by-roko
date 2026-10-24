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


    private val sandboxTiles = """[{"id":"act","kind":"sandbox_act","label":"agir","color":"#7dff6b","glyph":"act","tone":1,"polygon":[[2.9,0.0],[5.0,0.0],[5.0,7.0],[3.3,7.0]],"delay":120},
        {"id":"attributes","kind":"sandbox_attributes","label":"atributos","color":"#5cffb0","glyph":"attributes","tone":5,"polygon":[[0.0,0.0],[2.9,0.0],[3.0,2.6],[0.0,2.4]],"delay":40},
        {"id":"entities","kind":"sandbox_entities","label":"entidades","color":"#b0ff5c","glyph":"roko","tone":3,"polygon":[[0.0,2.4],[3.0,2.6],[3.15,4.9],[0.0,4.7]],"delay":260},
        {"id":"coleto","kind":"coleto","label":"coleto","color":"#7dff6b","glyph":"coleto","tone":7,"polygon":[[0.0,4.7],[3.15,4.9],[3.3,7.0],[0.0,7.0]],"delay":330}]"""

    /** What /entity answers: roko, or none when `mute`. */
    var mute = false

    /** Which dungeon /dungeon answers: walk, wait, choice, ending, act3. */
    var dungeon = "walk"

    private val map = """{"size":13,"tiles":["#############","#...#.D...D.#","#.###.#...#.#","#.#.#.#...#.#","#.#.###...###","#.....D...#.#",
        "#.#####D#D#.#","#.......#.#.#","#.#######D#D#","#.D...D.D...#","#.#...#.#...#","#.#...#.D...#","#############"],
        "start":[1,3],"boss":[10,10],"chests":[[8,3],[4,10]],"rooms":[[3,0,2,3],[1,4,2,2],[4,4,2,2]],"need":15}"""

    /** What was seen of the maze: its upper two thirds. */
    private val seen = "1".repeat(13 * 9) + "0".repeat(13 * 4)

    private val recover = """[{"kind":"small","cost":3,"heal":5,"ready":true},{"kind":"large","cost":8,"heal":15,"ready":false,"blocked":"cooldown","seconds_left":5000}]"""

    private fun dungeonView(): String {
        val wait = dungeon == "wait" || dungeon == "act3"
        val act = if (dungeon == "act3") 3 else if (dungeon == "choice") 1 else 1
        val pending = if (dungeon == "choice") """{"kind":"door","text":"UMA PORTA. DO OUTRO LADO, O MUNDO DE ANTES.","options":[{"id":"leave","label":"ir embora"},{"id":"stay","label":"ficar"}]}""" else "null"
        val ending = if (dungeon == "ending") "\"left\"" else "null"
        val act3 = if (dungeon == "act3") ""","act3":{"pair":["no","eve"],"unlocked":["no","eve","osso"],"done":["no"],"fragments":0,"objectives":[
            {"entity":"no","text":"vença 3 lutas com nó ao seu lado","need":3,"have":3,"done":true,"unlocked":true},
            {"entity":"eve","text":"vença uma luta sem curar","need":1,"have":0,"unlocked":true},
            {"entity":"osso","text":"vença com menos de 25% da barra","need":1,"have":0,"unlocked":true},
            {"entity":"zira","text":"vença em menos de 25 segundos","need":1},{"entity":"mura","text":"junte 3 fragmentos","need":3},
            {"entity":"vela","text":"vença jogando 8 truques numa luta","need":1}]}""" else ""
        val partners = if (dungeon == "act3") """[{"id":"no","name":"NÓ","color":"#ff6b3d","glyph":"no","ability":"AMARRA"},{"id":"eve","name":"EVE","color":"#ff9de2","glyph":"eve","ability":"PERGUNTA"}]"""
            else """[{"id":"roko","name":"ROKO","color":"#3dfff0","glyph":"roko","ability":"DECRETO"}]"""
        return """{"act":$act,"floor":${if (act == 3) 15 else 3},"floor_in_act":3,"of":${if (act == 3) "null" else "6"},"map":$map,
            "pos":${if (wait) "[9,10]" else "[1,7]"},"face":1,"seen":"$seen","theme":${if (act == 3) 2 else 0},"walk_seconds":4200,
            "steps":{"left":${if (wait) 0 else 6},"came":14,"spent":8,"need":15,"every":280.0,"next_in":141},"waiting":$wait,
            "opponent":{"name":"KIROCUME","title":"PRESO COMO VOCÊ","kind":"person"},"pending":$pending,"ending":$ending,
            "ending_lines":${if (dungeon == "ending") """["VOCÊ SAIU.","AQUI DENTRO, SÓ FICOU UM CÓDIGO."]""" else "[]"},
            "intro":["O CORREDOR CONTINUA."],"waiting_line":"KIROCUME ESTÁ PARADO NA SUA FRENTE. ELE TAMBÉM QUER SAIR.",
            "wins":2,"losses":1,"level":3,"xp":4,"xp_need":10,"stats":{"hp":112,"resist":110,"defense":4,"absorb":80,"bonus":8},
            "ally_levels":{"roko":2},"companions":$partners,"energy":18,"max_energy":25,"tokens":12,"recover":$recover,
            "code":${if (dungeon == "ending") "\"EVS1 SWIZ 455M JGTJ 6UQA PDNG 3E67 N3ND AFGG L4S7 FNML TTYE Q2KD 7XWB A4HD P9ZK ME3R\"" else "null"}$act3}"""
    }

    val fightSetup = """{"seed":123456789,"max_ticks":1200,"tick_ms":100,
        "you":{"name":"LUME","hp":112,"max_hp":112,"resist":110,"defense":4,"absorb":80,
            "moves":[{"name":"CORRIDA (α)","dmg":24,"decree":66,"cd":80,"multiplier":2.0,"crit":20},{"name":"LEITURA (α)","dmg":6,"decree":33,"cd":60}],
            "heal":{"name":"FILME","amount":16,"cd":150},
            "entities":[{"id":"roko","name":"ROKO","forca":60,"agilidade":8,"skill":"potencia","ability":"decreto","level":2}],
            "level":3,"xp":4,"xp_need":10,"per_level":{"hp":6,"resist":5,"defense":1,"bonus":4}},
        "foe":{"name":"KIROCUME","hp":268,"max_hp":268,"resist":110,"defense":10,"absorb":80,
            "moves":[{"name":"PULSO","dmg":1,"cd":60},{"name":"ESCREVER (α)","dmg":3,"cd":110}],
            "heal":{"name":"RECOMPOR","amount":32,"cd":180},
            "entities":[{"id":"foe","name":"O QUE NÃO TEM NOME","forca":42,"agilidade":3,"skill":"cura","ability":"interferencia"}],"tricks":true,
            "level":3,"xp_need":10,"per_level":{"hp":6,"resist":5,"defense":1,"bonus":4}},
        "opponent":{"name":"KIROCUME","title":"PRESO COMO VOCÊ","kind":"person"}}"""

    /** A profile with every module, met eve, the selector at its second level. */
    val engine = """{"passcode": "M9XWEGPX", "session": 2, "seed": 541472713, "tiles": [{"id": "act", "kind": "act", "label": "agir", "color": "#00f0ff", "glyph": "act", "tone": 1, "polygon": [[2.942, 0.0], [5.0, 0.0], [5.0, 7.0], [3.266, 7.0]], "delay": 220, "fresh": false, "code": "AGIR-7Q"}, {"id": "roko", "kind": "entity", "label": "roko", "color": "#3dfff0", "glyph": "roko", "tone": 3, "polygon": [[1.512, 4.776], [3.172, 4.962], [3.266, 7.0], [1.655, 7.0]], "delay": 304, "fresh": true, "code": "ROKO-9X"}, {"id": "shop", "kind": "shop", "label": "shop", "color": "#7af9ff", "glyph": "shop", "tone": 2, "polygon": [[1.435, 1.23], [2.994, 1.115], [3.102, 3.46], [1.554, 3.35]], "delay": 271, "fresh": true, "code": "LOJA-3K"}, {"id": "agenda", "kind": "agenda", "label": "agenda", "color": "#00a8e8", "glyph": "logs", "tone": 4, "polygon": [[0.0, 0.0], [2.942, 0.0], [2.994, 1.115], [0.0, 1.335]], "delay": 58, "fresh": true, "code": "AGND-4M"}, {"id": "attributes", "kind": "attributes", "label": "atributos", "color": "#00c8ff", "glyph": "attributes", "tone": 5, "polygon": [[0.0, 4.607], [1.512, 4.776], [1.655, 7.0], [0.0, 7.0]], "delay": 345, "fresh": true, "code": "ATRB-6P"}, {"id": "journey", "kind": "journey", "label": "jornada", "color": "#00ffd0", "glyph": "journey", "tone": 6, "polygon": [[0.0, 3.239], [3.102, 3.46], [3.172, 4.962], [0.0, 4.607]], "delay": 334, "fresh": true, "code": "JRND-8T", "alert": true}, {"id": "build", "kind": "build", "label": "construir", "color": "#00e0ff", "glyph": "build", "tone": 7, "polygon": [[0.0, 1.335], [1.435, 1.23], [1.554, 3.35], [0.0, 3.239]], "delay": 38, "fresh": true, "code": "CNST-2W"}], "hint": "act", "modules": [{"id": "act", "label": "agir", "code": "AGIR-7Q", "on": true}, {"id": "shop", "label": "shop", "code": "LOJA-3K", "on": true}, {"id": "roko", "label": "roko", "code": "ROKO-9X", "on": true}, {"id": "agenda", "label": "agenda", "code": "AGND-4M", "on": true}, {"id": "attributes", "label": "atributos", "code": "ATRB-6P", "on": true}, {"id": "journey", "label": "jornada", "code": "JRND-8T", "on": true}, {"id": "build", "label": "construir", "code": "CNST-2W", "on": true}], "entities": ["roko", "eve"], "story": {"step": "start", "at": 0, "of": 7, "done": false}, "line": {"entity": "eve", "text": "oi. ele fala alto, né? eu só pergunto coisas."}, "selector": {"level": 2, "turns": 0, "next_at": null, "chance": 0.12}, "counters": {"visits": 2, "acts": 0, "opens": 0, "turns": 0, "talks": 0, "buys": 0, "plans": 0}, "lines": [], "doubted": [],
        "entity": {"id": "roko", "name": "ROKO", "title": "O ARQUITETO", "color": "#3dfff0", "glyph": "roko"},
        "modes": {"evove": true, "sandbox": true, "journey": true, "journey_alert": true}}"""

    /** A profile on the story's first step: agir alone, and actions it does not own. */
    val engineFresh = """{"passcode": "M9XWEGPX", "session": 1, "seed": 300083833, "tiles": [{"id": "act", "kind": "act", "label": "agir", "color": "#00f0ff", "glyph": "act", "tone": 1, "polygon": [[2.912, 0.0], [5.0, 0.0], [5.0, 7.0], [3.551, 7.0]], "delay": 185, "fresh": false, "code": "AGIR-7Q"}], "hint": "act", "modules": [{"id": "act", "label": "agir", "code": "AGIR-7Q", "on": true}, {"id": "shop", "label": "shop", "code": null, "on": false}, {"id": "roko", "label": "roko", "code": null, "on": false}, {"id": "agenda", "label": "agenda", "code": null, "on": false}, {"id": "attributes", "label": "atributos", "code": null, "on": false}, {"id": "journey", "label": "jornada", "code": null, "on": false}, {"id": "build", "label": "construir", "code": null, "on": false}], "entities": [], "story": {"step": "start", "at": 0, "of": 7, "done": false}, "line": {"entity": "roko", "text": "AGE."}, "selector": {"level": 1, "turns": 0, "next_at": 1000, "chance": null}, "counters": {"visits": 1, "acts": 0, "opens": 0, "turns": 0, "talks": 0, "buys": 0, "plans": 0}, "lines": [], "doubted": ["CORRIDA", "PIANO"],
        "entity": {"id": "roko", "name": "ROKO", "title": "O ARQUITETO", "color": "#3dfff0", "glyph": "roko"},
        "modes": {"evove": true, "sandbox": false, "journey": false}}"""

    fun answer(method: String, path: String): String = when {
        path.startsWith("/engine") -> engine
        path.startsWith("/save") -> """{"code":"EVS1SWIZ455MJGTJ6UQAPDNG3E67","grouped":"EVS1 SWIZ 455M JGTJ 6UQA PDNG 3E67 N3ND AFGG L4S7 FNML TTYE Q2KD 7XWB A4HD","length":806,"actions":3,"attributes":13}"""
        path.startsWith("/dungeon/fight") -> fightSetup
        path.startsWith("/dungeon/items") -> """{"level":3,"attacks":["CORRIDA","LEITURA"],"bonuses":{"damage":14,"defense":3,"hp":17},"items":[
            {"id":"a1","name":"FERRAMENTA DE CORRIDA","slot":"arma","action":"CORRIDA","level":3,"value":9,"synergy":1.6,"count":2,"worn":true,"effective":14,"synergy_on":true},
            {"id":"a2","name":"MARCA DE PIANO","slot":"acessorio","action":"PIANO","level":2,"value":3,"synergy":1.8,"worn":true,"effective":3},
            {"id":"a3","name":"FAIXA DE SALTO","slot":"cabeca","action":"SALTO","level":3,"value":17,"synergy":1.5,"worn":true,"effective":17}]}"""
        path.startsWith("/dungeon/walk") -> """{"lines":[],"view":${dungeonView()}}"""
        path.startsWith("/dungeon") -> dungeonView()
        path.startsWith("/entity/talk") -> if (mute) """{"entity":null,"present":false,"answered":false,"line":"CANAL ABERTO. NENHUMA VOZ."}"""
            else """{"entity":"roko","present":true,"answered":true,"line":"VOCÊ VOLTOU. AJA ANTES DE PENSAR DEMAIS."}"""
        path.startsWith("/entity") -> if (mute) """{"id":"","name":"","none":true,"affinity":{"roko":1.2,"eve":0.4}}"""
            else """{"id":"roko","name":"ROKO","title":"O ARQUITETO","color":"#3dfff0","personality":"autoritário","presence":0.8,"glyph":"roko","trait":"ato",
            "battle":{"forca":18,"agilidade":8,"skill":"potencia","ability":"decreto","ability_name":"DECRETO"},"affinity":{"roko":6.1,"eve":2.3,"osso":1.5}}"""
        path.startsWith("/sandbox/entities") && path.endsWith("/talk") -> """{"entity":"coleto","present":true,"answered":true,"line":"sim, sim! o que manda, chefe?"}"""
        path.startsWith("/sandbox/entities") -> """[{"id":"coleto","name":"COLETO","title":"O QUE SERVE","color":"#7dff6b","personality":"servil","voice":"lower","glyph":"coleto","animated":true},
            {"id":"roko","name":"ROKO","title":"O ARQUITETO","color":"#3dfff0","glyph":"roko"}]"""
        path.startsWith("/sandbox/actions") -> actions
        path.startsWith("/sandbox/attributes") -> usage
        path.startsWith("/sandbox") -> """{"tiles":$sandboxTiles,"acts":12,"actions":4,"talks":3,"entities":["roko"]}"""
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
