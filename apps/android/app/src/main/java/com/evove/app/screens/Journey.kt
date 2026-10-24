package com.evove.app.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.setValue
import androidx.compose.runtime.getValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.Bus
import com.evove.app.Evove
import com.evove.app.api.Api
import com.evove.app.api.DungeonView
import com.evove.app.api.FightEnd
import com.evove.app.api.FightSetup
import com.evove.app.api.JourneyStats
import com.evove.app.api.Recovery
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Display
import com.evove.app.ui.Empty
import com.evove.app.ui.Glyphs
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.IconView
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.KeyText
import com.evove.app.ui.Label
import com.evove.app.ui.ListRow
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Message
import com.evove.app.ui.Mono
import com.evove.app.ui.Small
import com.evove.app.ui.Stats
import com.evove.app.ui.Tag
import com.evove.app.ui.Ticker
import com.evove.app.ui.Type
import com.evove.app.ui.caps
import com.evove.app.ui.hex
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import com.evove.app.ui.voiceInk
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.floor

// The journey as a mode: a maze seen from inside (Maze.kt), walked a step at
// a time with the steps time brings, its rooms keeping chests and, in the
// farthest, someone waiting — a frame of static. Below, the few things that
// can be done: walk, start the fight, answer a choice, buy hp back with
// tokens, wear equipment, see the stats, and, in the third act, choose the
// two entities carried. No one talks here. The fight is JourneyFight.kt's.

private enum class Leg { MAP, FIGHT, STATUS, EQUIP, STATS, PAIR }

/** "2d 05h", "3h 07m", "4m 09s". */
fun clock(total: Long): String {
    val d = total / 86400
    val h = (total % 86400) / 3600
    val m = (total % 3600) / 60
    val s = total % 60
    fun p(n: Long) = n.toString().padStart(2, '0')
    return if (d > 0) "${d}d ${p(h)}h" else if (h > 0) "${h}h ${p(m)}m" else "${m}m ${p(s)}s"
}

/** 1.5 as "1.5", 2.0 as "2". */
fun trim(d: Double): String = if (d == Math.floor(d)) d.toLong().toString() else d.toString()

@Composable
fun JourneyScreen(onHome: () -> Unit, onClose: () -> Unit = {}) {
    var leg by remember { mutableStateOf(Leg.MAP) }
    var view by remember { mutableStateOf<DungeonView?>(null) }
    var stats by remember { mutableStateOf<JourneyStats?>(null) }
    var inventory by remember { mutableStateOf<com.evove.app.api.Inventory?>(null) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var loadedAt by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    // the fight going on, and what the server decided of it
    var setup by remember { mutableStateOf<FightSetup?>(null) }
    var ended by remember { mutableStateOf<FightEnd?>(null) }
    // the moves made here the server has not answered yet, and the ones on their way
    var queued by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf("") }
    // what the box under the maze tells, one line at a time
    var notices by remember { mutableStateOf<List<String>>(emptyList()) }
    var pair by remember { mutableStateOf<List<String>>(emptyList()) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    suspend fun load() {
        try {
            view = Api.dungeon()
            loadedAt = System.currentTimeMillis()
            now = loadedAt
            view?.act3?.let { pair = it.pair }
        } catch (e: Exception) {
            message = listOf(e.message ?: "erro")
        }
    }

    val v = view
    val elapsed = (now - loadedAt) / 1000
    // where the profile is, its moves on their way counted in; the steps that came since the view did too
    val here = v?.let { walked(it.map, it.pos, it.face, sending + queued) }
    val came = v?.steps?.let { s -> if (elapsed >= s.nextIn) 1 + ((elapsed - s.nextIn) / maxOf(1.0, s.every)).toInt() else 0 } ?: 0
    val steps = v?.let { maxOf(0, it.steps.left + came - (here?.third ?: 0)) } ?: 0
    val nextIn = v?.steps?.let { s -> val e = maxOf(1.0, s.every); val past = elapsed - s.nextIn
        if (past < 0) s.nextIn - elapsed else (e - (past % e)).toLong() } ?: 0L
    val settled = queued.isEmpty() && sending.isEmpty()
    val arrived = v != null && v.ending == null && v.pending == null && v.waiting && settled

    fun go(l: Leg) {
        Sfx.tap(if (l == Leg.MAP) 0 else 4)
        leg = l
        message = emptyList()
        if (l == Leg.STATS) scope.launch { runCatching { Api.journeyStats() }.onSuccess { stats = it } }
        if (l == Leg.EQUIP) scope.launch { runCatching { Api.inventory() }.onSuccess { inventory = it } }
        Sfx.powerOn()
    }

    /** Sends the moves made, a batch at a time; the server's answer is where
     *  the profile really is, and what it found on the way. */
    fun flush() {
        if (sending.isNotEmpty() || queued.isEmpty()) return
        sending = queued
        queued = ""
        scope.launch {
            try {
                val r = Api.walk(sending)
                view = r.view
                loadedAt = System.currentTimeMillis()
                now = loadedAt
                if (r.lines.isNotEmpty()) {
                    notices = r.lines.map { it.lowercase() }
                    Sfx.gains()
                }
            } catch (e: Exception) {
                queued = ""
                message = listOf(e.message ?: "erro")
            } finally {
                sending = ""
            }
            if (queued.isNotEmpty()) flush()
            else view?.let { cur ->
                // next to whoever waits: turn to face them
                val (p, f, _) = walked(cur.map, cur.pos, cur.face, "")
                val turn = turnsToBoss(cur.map, p.first, p.second, f)
                if (turn.isNotEmpty() && cur.ending == null && cur.pending == null) { queued = turn; flush() }
            }
        }
    }

    fun move(m: Char) {
        val cur = view ?: return
        if (cur.ending != null || cur.pending != null || leg != Leg.MAP) return
        val (p, f, _) = here ?: return
        if (m == 'F') {
            val (dx, dy) = DIRS[f]
            if (!cur.map.passable(p.first + dx, p.second + dy)) { Sfx.buzz(0, 30); return }
            if (steps <= 0) { Sfx.buzz(0, 30, 60, 30); notices = listOf("sem passos: o próximo em ${clock(nextIn)}"); return }
            Sfx.tap(2)
        } else Sfx.tap(6)
        if (notices.isNotEmpty() && m == 'F') notices = emptyList()
        queued += m
        flush()
    }

    /** The fight is over, or the person left it: the server replays it — the
     *  rest of it plays itself — and decides what it pays. */
    fun finish(leaving: Boolean = false) {
        if (leaving) {
            Evove.later { runCatching { Api.endFight(emptyList(), left = true) } }
            return
        }
        scope.launch {
            try {
                val r = Api.endFight(emptyList())
                ended = r
                view = r.view
                loadedAt = System.currentTimeMillis()
                now = loadedAt
                if (r.won) Sfx.gains() else Sfx.buzz(0, 120, 80, 120)
                notices = r.lines.map { it.lowercase() }
                Bus.bumpUser()
                Evove.refresh()
                if (r.close) {
                    // the evove undone: the app closes by itself
                    delay(4000)
                    onClose()
                }
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            }
        }
    }

    fun startFight() {
        if (busy || !arrived) return
        busy = true
        Sfx.tap(9)
        scope.launch {
            try {
                setup = Api.startFight()
                ended = null
                leg = Leg.FIGHT
                message = emptyList()
                Sfx.powerOn()
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    fun choose(option: String) {
        if (busy) return
        busy = true
        Sfx.tap(7)
        scope.launch {
            try {
                view = Api.choose(option).view
                loadedAt = System.currentTimeMillis()
                Evove.refresh()
                Sfx.powerOn()
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    fun heal(r: Recovery) {
        if (busy || !r.ready) return
        busy = true
        scope.launch {
            try {
                val res = Api.recover(r.kind)
                Sfx.gains()
                message = listOf("+${res.healed} hp", "−${r.cost} tokens")
                Bus.bumpUser()
                load()
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    fun wear(item: com.evove.app.api.Item?) {
        if (busy) return
        busy = true
        scope.launch {
            try {
                inventory = if (item == null) Api.wearBest() else Api.wearItem(item.id)
                Sfx.tap(5)
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    fun toggle(e: String) {
        val next = if (e in pair) pair - e else (pair + e).takeLast(2)
        pair = next
        Sfx.tap(6)
        if (next.size == 2) scope.launch {
            try { view = Api.pair(next) } catch (x: Exception) { message = listOf(x.message ?: "erro") }
        }
    }

    LaunchedEffect(Unit) {
        load()
        Sfx.powerOn()
    }
    Ticker(1000) { now = System.currentTimeMillis() }

    BackHandler(enabled = leg != Leg.MAP && leg != Leg.FIGHT) { go(Leg.MAP) }
    BackHandler(enabled = leg == Leg.FIGHT && ended != null) { ended = null; setup = null; go(Leg.MAP) }

    val look = LOOKS[(v?.theme ?: 0).mod(LOOKS.size)]
    val s = setup
    if (leg == Leg.FIGHT && s != null) {
        FightScreen(s, look, ended, onOver = { finish() }, onBack = { ended = null; setup = null; go(Leg.MAP) }) { leaving ->
            if (leaving) finish(leaving = true)
            onHome()
        }
        return
    }

    val ink = Ink.journey
    DarkScreen(
        ink, display = 0.56f,
        displayContent = {
            when {
                message.isNotEmpty() -> Message(message)
                v == null -> Small("…")
                v.ending != null -> Big(if (v.ending == "free") "livre" else "fim")
                else -> {
                    Row(Modifier.fillMaxWidth()) {
                        val head = TextStyle(fontFamily = Mono, fontSize = 0.68.rem, letterSpacing = 0.1.em, color = ink.copy(alpha = 0.85f))
                        BasicText(caps("ato ${v.act} · andar ${v.floorInAct}" + (v.of?.let { "/$it" } ?: "")), Modifier.weight(1f), style = head)
                        BasicText(caps(when {
                            v.pending != null -> "escolha"
                            arrived -> ""
                            steps <= 0 -> "+1 passo em ${clock(nextIn)}"
                            else -> "passos $steps"
                        }), Modifier.padding(start = 8.dp).testTag("steps"), style = head)
                    }
                    MazeView(v.map, here?.first ?: (1 to 1), here?.second ?: 1, look, v.seen, Modifier.fillMaxWidth().weight(1f), ::move)
                    Notices(
                        when {
                            notices.isNotEmpty() -> notices
                            v.pending != null -> listOf(v.pending.text.lowercase())
                            arrived -> listOf("inimigo encontrado: ${v.opponent.name}")
                            steps <= 0 -> listOf("sem passos: o próximo em ${clock(nextIn)}")
                            else -> listOf("explorando o andar ${v.floorInAct} · $steps ${if (steps == 1) "passo" else "passos"}")
                        },
                    ) { notices = emptyList() }
                }
            }
        },
        bar = {
            when (leg) {
                Leg.MAP -> {
                    Key({ startFight() }, Modifier.at(1).testTag("fight"), enabled = arrived && !busy, on = arrived) { KeyIcon(Icon.BOLT) }
                    Key({ go(Leg.STATUS) }, Modifier.at(2), enabled = v?.ending == null) { KeyIcon(Icon.HEART) }
                    Key({ go(Leg.EQUIP) }, Modifier.at(3).testTag("items"), enabled = v?.ending == null) { KeyIcon(Icon.TRIANGLE) }
                    Key({ go(Leg.STATS) }, Modifier.at(4)) { KeyIcon(Icon.BARS) }
                    if (v?.act3 != null && v.ending == null) Key({ go(Leg.PAIR) }, Modifier.at(5)) { KeyIcon(Icon.DOTS) }
                }
                else -> {
                    Key({ go(Leg.MAP) }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
                    if (leg == Leg.EQUIP) Key({ wear(null) }, Modifier.at(3, 3), enabled = !busy) { KeyIcon(Icon.STAR, 16.dp); KeyText("equipar melhores") }
                }
            }
            HomeKey { Sfx.tap(0); onHome() }
        },
    ) {
        when {
            v == null -> Empty("…")
            v.ending != null -> Ending(v) { code ->
                (context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager)?.setPrimaryClip(ClipData.newPlainText("evove", code.replace(" ", "")))
                Sfx.gains()
                message = listOf("copiado")
            }
            leg == Leg.MAP -> MapBody(v, arrived, busy, steps > 0, ::startFight, ::choose, ::move)
            leg == Leg.STATUS -> StatusBody(v, busy, elapsed, ::heal)
            leg == Leg.EQUIP -> InventoryBody(inventory, busy) { wear(it) }
            leg == Leg.STATS -> StatsBody(v)
            leg == Leg.PAIR -> PairBody(v, pair, ::toggle)
        }
    }
}

/** Under the maze: the hp and the entities carried; the answer to a choice,
 *  the fight with whoever waits, or the keys to walk — a quarter turn either
 *  way, a step forward, a half turn. Swiping the maze walks it too. */
@Composable
private fun ColumnScope.MapBody(v: DungeonView, arrived: Boolean, busy: Boolean, canStep: Boolean, onFight: () -> Unit, onChoose: (String) -> Unit,
                                onMove: (Char) -> Unit) {
    val ink = LocalInk.current
    HpBar(v.energy, v.maxEnergy)
    Partners(v)
    v.act3?.let { Label("objetivos · ${it.done.size}/${it.objectives.size}") }
    val p = v.pending
    when {
        p != null -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((k, o) in p.options.withIndex()) {
                CompositionLocalProvider(LocalInk provides if (k == 0) Ink.danger else ink) {
                    Key({ onChoose(o.id) }, Modifier.weight(1f).heightIn(min = 3.4.remDp).testTag("choice-${o.id}"), enabled = !busy) { KeyText(o.label) }
                }
            }
        }
        arrived -> Key(onFight, Modifier.fillMaxWidth().heightIn(min = 3.4.remDp).testTag("fight-now"), enabled = !busy && v.energy > 0) {
            KeyIcon(Icon.BOLT)
            KeyText(if (v.energy > 0) "lutar com ${v.opponent.name}" else "sem hp — recupere", Type.key.copy(fontSize = 0.9.rem))
        }
        else -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            val keys = listOf('L' to Icon.LEFT, 'F' to Icon.UP, 'R' to Icon.RIGHT, 'B' to Icon.DOWN)
            for ((m, icon) in keys) {
                Key({ onMove(m) }, Modifier.weight(1f).heightIn(min = 3.4.remDp).testTag("move-$m"), on = m == 'F' && canStep) { KeyIcon(icon) }
            }
        }
    }
}

@Composable
private fun HpBar(energy: Int, max: Int) {
    val ink = LocalInk.current
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Label("hp $energy/$max")
        val low = energy <= max * 0.3
        Row(Modifier.fillMaxWidth().height(14.dp), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
            repeat(maxOf(1, max)) { i ->
                val on = i < energy
                val c = if (on && low) Ink.danger else ink
                Box(Modifier.weight(1f).fillMaxHeight().alpha(if (on) 1f else 0.35f).border(1.dp, c).background(if (on) c else Color.Transparent))
            }
        }
    }
}

/** The entities at the profile's side — one mark, each in its color — or none. */
@Composable
private fun Partners(v: DungeonView) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        if (v.companions.isEmpty()) {
            com.evove.app.ui.GlyphView(Glyphs.roko, Ink.mute, 18.dp)
            BasicText(caps("sem entidade"), style = Type.row.copy(fontSize = 0.72.rem, color = Ink.mute))
        }
        for (c in v.companions) {
            val ink = runCatching { hex(c.color) }.getOrDefault(Color.White)
            com.evove.app.ui.GlyphView(Glyphs.roko, ink, 18.dp)
            BasicText(c.name, style = Type.row.copy(fontSize = 0.72.rem, color = ink))
        }
    }
}

@Composable
private fun ColumnScope.StatusBody(v: DungeonView, busy: Boolean, elapsed: Long, onHeal: (Recovery) -> Unit) {
    val ink = LocalInk.current
    HpBar(v.energy, v.maxEnergy)
    v.checkpoint?.let { c ->
        Label("checkpoint · estágio ${c.stage} em ${clock(maxOf(0, c.secondsLeft - elapsed))}" + if (c.resets > 0) " · ${c.resets} reinícios" else "")
    }
    Label("recuperar · ${v.tokens} tokens")
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        val labels = mapOf("small" to "pequena", "large" to "grande")
        for (r in v.recover) {
            Key({ onHeal(r) }, Modifier.weight(1f).heightIn(min = 4.remDp), enabled = !busy && r.ready) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(0.2.remDp)) {
                    KeyIcon(Icon.HEART, 16.dp)
                    KeyText("+${r.heal} · ${r.cost}t")
                    BasicText(
                        caps(when (r.blocked) {
                            "cooldown" -> clock(maxOf(0, r.secondsLeft - elapsed))
                            "full" -> "cheio"
                            "tokens" -> "sem tokens"
                            else -> labels[r.kind] ?: r.kind
                        }),
                        Modifier.alpha(0.7f), style = Type.key.copy(fontSize = 0.62.rem, color = ink),
                    )
                }
            }
        }
    }
}

private val SLOT_NAME = mapOf("arma" to "arma", "acessorio" to "acessório", "cabeca" to "cabeça")
private val SLOT_WHAT = mapOf("arma" to "% de dano", "acessorio" to " de defesa", "cabeca" to " de hp")

/** The inventory: what the people beaten left, by slot, each with what it
 *  adds now — more when its action is one of the two attacks. A tap wears it,
 *  or takes it off; the bar's key wears the best of each slot. */
@Composable
private fun ColumnScope.InventoryBody(inv: com.evove.app.api.Inventory?, busy: Boolean, onWear: (com.evove.app.api.Item) -> Unit) {
    val ink = LocalInk.current
    if (inv == null) { Empty("…"); return }
    val b = inv.bonuses
    Label("nível ${inv.level} · +${b.damage}% dano · +${b.defense} defesa · +${b.hp} hp")
    if (inv.items.isEmpty()) Empty("nada ainda — os vencidos deixam itens")
    for (item in inv.items.sortedWith(compareByDescending<com.evove.app.api.Item> { it.worn }.thenByDescending { it.effective }).take(7)) {
        val icon = when (item.slot) { "arma" -> Icon.TRIANGLE; "acessorio" -> Icon.DIAMOND; else -> Icon.CIRCLE }
        ListRow({ onWear(item) }, enabled = !busy, background = if (item.worn) ink.copy(alpha = 0.22f) else null) {
            IconView(icon, if (item.synergyOn) Ink.gold else Color.White, 16.dp)
            BasicText(
                buildAnnotatedString {
                    append(item.name)
                    withStyle(SpanStyle(color = Color.White.copy(alpha = 0.55f), fontSize = 0.66.rem)) {
                        append(" · nv ${item.level} · +${item.effective}${SLOT_WHAT[item.slot] ?: ""}")
                        if (item.synergyOn) append(" ×${item.synergy}")
                        if (item.count > 1) append(" · ${item.count}×")
                    }
                },
                Modifier.weight(1f), style = Type.row.copy(fontSize = 0.74.rem), maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
            Tag(if (item.worn) "em uso" else SLOT_NAME[item.slot] ?: item.slot)
        }
    }
}

/** The journey's level and what it gives, with the items worn and the levels
 *  of the entities. */
@Composable
private fun ColumnScope.StatsBody(v: DungeonView) {
    val ink = LocalInk.current
    Label("nível ${v.level} · ${v.xp}/${v.xpNeed} de experiência")
    Box(Modifier.fillMaxWidth().height(8.dp).border(1.dp, ink)) {
        Box(Modifier.fillMaxHeight().fillMaxWidth((v.xp / maxOf(1, v.xpNeed).toFloat()).coerceIn(0f, 1f)).background(ink))
    }
    val st = v.stats
    Stats(listOf(
        "hp máximo" to "${st.hp}", "resistência" to "${st.resist}", "defesa" to "${st.defense}", "absorção" to "${st.absorb}%",
        "dano" to "+${st.bonus}%", "vitórias" to "${v.wins}", "derrotas" to "${v.losses}",
    ) + v.allyLevels.map { (e, lv) -> e to "nível $lv" })
}

/** The box under the corridor: what happened, one line at a time, the next
 *  at a tap; the last stays. */
@Composable
private fun Notices(lines: List<String>, onDone: () -> Unit) {
    var at by remember(lines) { mutableIntStateOf(0) }
    val ink = LocalInk.current
    Box(
        Modifier.fillMaxWidth().heightIn(min = 3.4.remDp).border(1.5.dp, ink).background(Color.Black)
            .clickable(remember { MutableInteractionSource() }, null) {
                if (at < lines.size - 1) at++ else if (lines.size > 1) onDone()
            }
            .padding(horizontal = 0.8.remDp, vertical = 0.6.remDp).testTag("notice"),
        contentAlignment = Alignment.CenterStart,
    ) {
        BasicText("• ${caps(lines.getOrNull(at) ?: "")}", style = TextStyle(fontFamily = Display, fontSize = 0.8.rem, fontWeight = FontWeight.Medium,
            lineHeight = 1.35.em, letterSpacing = 0.05.em, color = Color.White), maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun ColumnScope.PairBody(v: DungeonView, pair: List<String>, onToggle: (String) -> Unit) {
    val a3 = v.act3 ?: return
    Label("duas entidades ao seu lado · ${pair.size}/2")
    for (o in a3.objectives) {
        val c = voiceInk(o.entity)
        ListRow(if (o.unlocked) ({ onToggle(o.entity) }) else null, enabled = o.unlocked,
            background = if (o.entity in pair) c.copy(alpha = 0.22f) else null) {
            com.evove.app.ui.GlyphView(Glyphs.roko, c, 16.dp)
            BasicText(
                buildAnnotatedString {
                    withStyle(SpanStyle(color = c)) { append(caps(if (o.unlocked) o.entity else "?")) }
                    withStyle(SpanStyle(color = Color.White.copy(alpha = 0.6f), fontSize = 0.66.rem)) {
                        append(if (o.unlocked) " · ${o.text}" else "")
                    }
                },
                Modifier.weight(1f), style = Type.row.copy(fontSize = 0.74.rem), maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
            Tag(if (o.done) "feito" else if (o.unlocked) "${o.have}/${o.need}" else "")
        }
    }
}

@Composable
private fun ColumnScope.Ending(v: DungeonView, onCopy: (String) -> Unit) {
    val code = v.code ?: return
    BasicText(
        code,
        Modifier.fillMaxWidth().weight(1f, fill = false).border(1.5.dp, LocalInk.current).padding(0.7.remDp),
        style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, color = Color.White, lineHeight = 0.95.rem),
    )
    Key({ onCopy(code) }, Modifier.fillMaxWidth().heightIn(min = 2.8.remDp)) { KeyIcon(Icon.LINK); KeyText("copiar") }
}
