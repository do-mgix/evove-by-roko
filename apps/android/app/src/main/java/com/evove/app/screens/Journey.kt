package com.evove.app.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.Bus
import com.evove.app.Evove
import com.evove.app.api.Api
import com.evove.app.api.DungeonView
import com.evove.app.api.Equipment
import com.evove.app.api.EquipmentItem
import com.evove.app.api.FightEnd
import com.evove.app.api.FightSetup
import com.evove.app.api.JourneyStats
import com.evove.app.api.Recovery
import com.evove.app.fight.Fight
import com.evove.app.fight.FightEvent
import com.evove.app.fight.FightView
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
import com.evove.app.ui.drawGlyph
import com.evove.app.ui.hex
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import com.evove.app.ui.voiceInk
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// The journey as a mode: on top, the floor's map, which the figure explores by
// itself for as long as the checkpoints say, the opponent waiting at the end of
// it; under it, a line of the story. Below, the few things that can be done:
// start the fight when someone waits, answer a choice, buy hp back with
// tokens, wear equipment, see the stats, and, in the third act, choose the two
// entities carried. The fight takes the top over and plays itself in real
// time (com.evove.app.fight.Fight); the only input is the trick on offer.

private enum class Leg { MAP, FIGHT, STATUS, EQUIP, STATS, PAIR }

/** What each trick does, said where it is offered. */
private val TRICK_TEXT = mapOf(
    "atordoar" to "pausa as recargas do oponente",
    "furia" to "avança as suas recargas no tempo",
    "baque" to "para todos — depois, golpes ao mesmo tempo",
    "rasteira" to "devolve um ataque do oponente ao início",
    "escudo" to "segura a maior parte do próximo golpe",
    "eco" to "repete o seu último ataque, de graça",
)

private val TRICK_NAME = mapOf("furia" to "fúria")

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
    var gear by remember { mutableStateOf<Equipment?>(null) }
    var slotAt by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var loadedAt by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    // the fight going on: its setup, the rules running it, the ticks the tricks were played at
    var setup by remember { mutableStateOf<FightSetup?>(null) }
    var fight by remember { mutableStateOf<Fight?>(null) }
    // what the screen shows of it, copied at every tick
    var shown by remember { mutableStateOf<FightView?>(null) }
    var wantPlay by remember { mutableStateOf(false) }
    val plays = remember { mutableListOf<Int>() }
    var ended by remember { mutableStateOf<FightEnd?>(null) }
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
    val left = v?.let { maxOf(0, it.secondsLeft - elapsed) } ?: 0
    val progress = v?.let {
        if (it.walkSeconds <= 0) 1f else (it.progress + elapsed / it.walkSeconds.toDouble()).coerceIn(0.0, 1.0).toFloat()
    } ?: 0f
    val arrived = v != null && v.ending == null && v.pending == null && (v.waiting || progress >= 1f)

    fun go(l: Leg) {
        Sfx.tap(if (l == Leg.MAP) 0 else 4)
        leg = l
        message = emptyList()
        if (l == Leg.STATS) scope.launch { runCatching { Api.journeyStats() }.onSuccess { stats = it } }
        if (l == Leg.EQUIP) scope.launch { runCatching { Api.equipment() }.onSuccess { gear = it } }
        Sfx.powerOn()
    }

    /** The fight is over, here or because the person left: the server replays
     *  it with the tricks played so far, the rest playing itself. */
    fun finish(leaving: Boolean = false) {
        val f = fight ?: return
        val ticks = plays.toList()
        fight = null
        if (leaving) {
            Evove.later { runCatching { Api.endFight(ticks) } }
            return
        }
        scope.launch {
            try {
                val r = Api.endFight(ticks)
                ended = r
                view = r.view
                loadedAt = System.currentTimeMillis()
                now = loadedAt
                if (r.won) Sfx.gains() else Sfx.buzz(0, 120, 80, 120)
                message = listOf(if (r.won) "vitória" else "derrota") + r.lines.map { it.lowercase() }
                Bus.bumpUser()
                Evove.refresh()
                if (r.close) {
                    // the evove undone: the ending told, the app closes by itself
                    delay(6000)
                    onClose()
                }
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            }
        }
    }

    fun startFight() {
        if (busy) return
        busy = true
        Sfx.tap(9)
        scope.launch {
            try {
                val s = Api.startFight()
                setup = s
                plays.clear()
                wantPlay = false
                ended = null
                fight = Fight(s).also { shown = it.view() }
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
                val r = Api.choose(option)
                view = r.view
                loadedAt = System.currentTimeMillis()
                message = r.lines.map { it.lowercase() }
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

    fun useItem(item: EquipmentItem) {
        if (busy) return
        busy = true
        scope.launch {
            try {
                gear = if (item.owned) Api.wearEquipment(item.id, !item.worn) else Api.buyEquipment(item.id)
                Sfx.tap(if (item.owned) 5 else 8)
                if (!item.owned) Sfx.gains()
                Bus.bumpUser()
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
    Ticker(1000) {
        now = System.currentTimeMillis()
        // the figure got there while the screen was open: the server confirms it
        val cur = view
        if (fight == null && cur != null && !cur.waiting && cur.ending == null && left == 0L && now - loadedAt > 1500) scope.launch { load() }
    }
    // the fight's clock: a tick every tenth of a second, a trick played at the start of one
    LaunchedEffect(fight) {
        val f = fight ?: return@LaunchedEffect
        val ms = (setup?.tickMs ?: 100).toLong()
        while (!f.over) {
            delay(ms)
            val play = wantPlay && f.sides[0].ready
            wantPlay = false
            if (play) plays += f.tick
            val before = f.events.size
            f.step(play)
            for (e in f.events.drop(before)) when (e.kind) {
                "attack" -> Sfx.tick(if (e.side == 0) 3 else 1)
                "interfere", "ability" -> Sfx.powerOn()
                "trick" -> Sfx.tick(9)
                "heal" -> Sfx.tick(8)
            }
            shown = f.view()
        }
        finish()
    }

    BackHandler(enabled = leg != Leg.MAP && leg != Leg.FIGHT) { go(Leg.MAP) }
    BackHandler(enabled = leg == Leg.FIGHT && fight == null) { ended = null; go(Leg.MAP) }

    val f = fight
    val ink = Ink.journey
    DarkScreen(
        ink, display = 0.42f,
        displayContent = {
            if (leg == Leg.FIGHT && (shown != null || ended != null)) {
                FightPanel(shown, f == null, setup, ended)
            } else if (v != null) MapPanel(v, progress, left, arrived, message)
            else Small("…")
        },
        bar = {
            when (leg) {
                Leg.MAP -> {
                    Key({ startFight() }, Modifier.at(1).testTag("fight"), enabled = arrived && !busy, on = arrived) { KeyIcon(Icon.BOLT) }
                    Key({ go(Leg.STATUS) }, Modifier.at(2), enabled = v?.ending == null) { KeyIcon(Icon.HEART) }
                    Key({ go(Leg.EQUIP) }, Modifier.at(3), enabled = v?.ending == null) { KeyIcon(Icon.TRIANGLE) }
                    Key({ go(Leg.STATS) }, Modifier.at(4)) { KeyIcon(Icon.BARS) }
                    if (v?.act3 != null && v.ending == null) Key({ go(Leg.PAIR) }, Modifier.at(5)) { KeyIcon(Icon.DOTS) }
                }
                Leg.FIGHT -> if (f == null) Key({ Sfx.tap(0); ended = null; go(Leg.MAP) }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
                else -> {
                    Key({ go(Leg.MAP) }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
                    if (leg == Leg.EQUIP) Key({ Sfx.tap(2); slotAt++; Sfx.powerOn() }, Modifier.at(3)) { KeyIcon(Icon.DOWN) }
                }
            }
            HomeKey {
                Sfx.tap(0)
                if (fight != null) finish(leaving = true)
                onHome()
            }
        },
    ) {
        when {
            leg == Leg.FIGHT -> FightBody(if (f == null) null else shown, ended, wantPlay) { if (f?.sides?.get(0)?.ready == true) { wantPlay = true; Sfx.tap(9) } }
            v == null -> Empty("…")
            v.ending != null -> Ending(v) { code ->
                (context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager)?.setPrimaryClip(ClipData.newPlainText("evove", code.replace(" ", "")))
                Sfx.gains()
                message = listOf("copiado")
            }
            leg == Leg.MAP -> MapBody(v, arrived, busy, left, ::startFight, ::choose)
            leg == Leg.STATUS -> StatusBody(v, busy, elapsed, ::heal)
            leg == Leg.EQUIP -> EquipBody(gear, slotAt, busy, ::useItem)
            leg == Leg.STATS -> {
                val s = stats
                Stats(listOfNotNull(
                    "ato" to "${v.act}", "andar" to "${v.floor}", "vitórias" to "${v.wins}", "derrotas" to "${v.losses}",
                    v.act3?.let { "fragmentos" to "${it.fragments}" },
                    s?.let { "checkpoint" to "estágio ${it.stage}" }, s?.let { "reinícios" to "${it.resets}" },
                    s?.let { "recuperações" to "${it.recoverUses}" },
                ))
            }
            leg == Leg.PAIR -> PairBody(v, pair, ::toggle)
        }
    }
}

// ---------------------------------------------------------------- the map

@Composable
private fun ColumnScope.MapPanel(v: DungeonView, progress: Float, left: Long, arrived: Boolean, message: List<String>) {
    val ink = LocalInk.current
    val head = TextStyle(fontFamily = Mono, fontSize = 0.68.rem, letterSpacing = 0.1.em, color = ink.copy(alpha = 0.85f))
    Row(Modifier.fillMaxWidth()) {
        BasicText(caps("ato ${v.act} · andar ${v.floorInAct}" + (v.of?.let { "/$it" } ?: "")), Modifier.weight(1f), style = head)
        BasicText(
            caps(when {
                v.ending != null -> "fim"
                v.pending != null -> "escolha"
                arrived -> "esperando você"
                else -> clock(left)
            }),
            style = head,
        )
    }
    if (v.ending == null) DungeonMap(v, progress, arrived, Modifier.fillMaxWidth().weight(1f))
    else Box(Modifier.fillMaxWidth().weight(1f))
    // a line of the story: what happened, the choice, who waits, or the floor's own
    val story = when {
        message.isNotEmpty() -> message
        v.ending != null -> v.endingLines
        v.pending != null -> listOf(v.pending.text)
        arrived -> listOf(v.waitingLine)
        else -> v.intro
    }
    StoryLine(story)
}

/** The lines of the story, typed out one after the other, and again. */
@Composable
private fun StoryLine(lines: List<String>) {
    var at by remember(lines) { mutableIntStateOf(0) }
    var typed by remember(lines, at) { mutableStateOf("") }
    LaunchedEffect(lines, at) {
        val text = lines.getOrNull(at) ?: return@LaunchedEffect
        for (i in 1..text.length) {
            delay(26)
            typed = text.take(i)
            if (i % 4 == 0) Sfx.tap(i % 10)
        }
        if (lines.size > 1) {
            delay(2600)
            at = (at + 1) % lines.size
        }
    }
    BasicText(
        caps(typed) + "▍",
        Modifier.fillMaxWidth().heightIn(min = 2.6.remDp),
        style = TextStyle(fontFamily = Display, fontSize = 0.82.rem, fontWeight = FontWeight.Medium, lineHeight = 1.4.em,
            letterSpacing = 0.05.em, color = Color.White, textAlign = TextAlign.End),
    )
}

/** The floor: rooms on a grid, the corridors between them, the part walked lit,
 *  the figure on its way, the opponent at the end. */
@Composable
private fun DungeonMap(v: DungeonView, progress: Float, arrived: Boolean, modifier: Modifier) {
    val ink = LocalInk.current
    val pulse = rememberInfiniteTransition(label = "pulse")
    val beat by pulse.animateFloat(0.35f, 1f, infiniteRepeatable(tween(650, easing = LinearEasing), RepeatMode.Reverse), label = "b")
    val m = v.map
    val foe = if (v.opponent.kind == "entity" || v.opponent.kind == "roko") Glyphs.byName(if (v.opponent.kind == "roko") "roko" else "no") else Glyphs.zira
    Canvas(modifier.padding(vertical = 6.dp)) {
        if (m.path.isEmpty()) return@Canvas
        val cell = minOf(size.width / m.w, size.height / m.h)
        val ox = size.width - cell * m.w
        val oy = (size.height - cell * m.h) / 2
        fun center(x: Int, y: Int) = Offset(ox + (x + 0.5f) * cell, oy + (y + 0.5f) * cell)
        val room = cell * 0.46f
        val stroke = 1.5.dp.toPx()
        val n = m.path.size
        val pos = progress * (n - 1)
        // the rooms off the path, and their corridors: faint, they lead nowhere
        for (r in m.rooms) {
            val c = center(r[0], r[1])
            drawLine(ink.copy(alpha = 0.18f), center(r[2], r[3]), c, stroke)
            drawRect(ink.copy(alpha = 0.22f), Offset(c.x - room / 2, c.y - room / 2), Size(room, room), style = Stroke(stroke))
        }
        for (i in 0 until n - 1) {
            val a = center(m.path[i][0], m.path[i][1])
            val b = center(m.path[i + 1][0], m.path[i + 1][1])
            drawLine(ink.copy(alpha = if (i < pos) 0.9f else 0.25f), a, b, stroke)
        }
        for ((i, p) in m.path.withIndex()) {
            val c = center(p[0], p[1])
            val lit = i <= pos
            drawRect(ink.copy(alpha = if (lit) 0.16f else 0.04f), Offset(c.x - room / 2, c.y - room / 2), Size(room, room))
            drawRect(ink.copy(alpha = if (lit) 0.95f else 0.3f), Offset(c.x - room / 2, c.y - room / 2), Size(room, room), style = Stroke(stroke))
        }
        // who waits at the end
        val end = center(m.path[n - 1][0], m.path[n - 1][1])
        val side = room * 0.8f
        drawGlyph(foe, Offset(end.x - side / 2, end.y - side / 2), side, Ink.enemy.copy(alpha = if (arrived) beat else 0.55f), stroke = 1.6.dp.toPx())
        // the figure, between two rooms
        val i = pos.toInt().coerceIn(0, n - 1)
        val j = minOf(n - 1, i + 1)
        val t = pos - i
        val a = center(m.path[i][0], m.path[i][1])
        val b = center(m.path[j][0], m.path[j][1])
        val at = if (arrived) Offset(end.x - room * 0.95f, end.y) else Offset(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
        val dot = room * 0.32f
        drawRect(Color.White.copy(alpha = if (arrived) 1f else beat), Offset(at.x - dot / 2, at.y - dot / 2), Size(dot, dot))
    }
}

@Composable
private fun ColumnScope.MapBody(v: DungeonView, arrived: Boolean, busy: Boolean, left: Long, onFight: () -> Unit, onChoose: (String) -> Unit) {
    val ink = LocalInk.current
    HpBar(v.energy, v.maxEnergy)
    Partners(v)
    v.act3?.let { a3 ->
        Label("objetivos · ${a3.done.size}/${a3.objectives.size}")
        for (o in a3.objectives.filter { it.unlocked && !it.done }.take(2)) {
            BasicText(buildAnnotatedString {
                withStyle(SpanStyle(color = voiceInk(o.entity))) { append(caps(o.entity)) }
                append(" · ${o.text} (${o.have}/${o.need})")
            }, style = Type.row.copy(fontSize = 0.72.rem), maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
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
        else -> Label("explorando · alguém no fim do andar em ${clock(left)}")
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

/** The entities at the profile's side — or none, and the system goes along, mute. */
@Composable
private fun Partners(v: DungeonView) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        if (v.companions.isEmpty()) {
            IconView(Icon.DOTS, Ink.mute, 16.dp)
            BasicText(caps(if (v.act == 2) "roko sumiu · sem entidade" else "sem entidade · só o sistema, mudo"), style = Type.row.copy(fontSize = 0.72.rem, color = Ink.mute))
        }
        for (c in v.companions) {
            val ink = runCatching { hex(c.color) }.getOrDefault(Color.White)
            com.evove.app.ui.GlyphView(Glyphs.byName(c.glyph), ink, 18.dp)
            BasicText(buildAnnotatedString {
                withStyle(SpanStyle(color = ink)) { append(c.name) }
                c.ability?.let { withStyle(SpanStyle(color = Color.White.copy(alpha = 0.55f))) { append(" · $it") } }
            }, style = Type.row.copy(fontSize = 0.72.rem))
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

@Composable
private fun ColumnScope.EquipBody(g: Equipment?, slotAt: Int, busy: Boolean, onUse: (EquipmentItem) -> Unit) {
    val ink = LocalInk.current
    if (g == null || g.slots.isEmpty()) {
        Empty("…")
        return
    }
    val slot = g.slots[slotAt % g.slots.size]
    Label("$slot · ${slotAt % g.slots.size + 1}/${g.slots.size} · ${g.points} pontos")
    // no blades and no amulets: a shape for each slot, a word for each item
    val icon = when (slot) { "vetor" -> Icon.TRIANGLE; "filtro" -> Icon.SQUARE; else -> Icon.CIRCLE }
    for (item in g.items.filter { it.slot == slot }) {
        ListRow({ onUse(item) }, enabled = !busy && (item.owned || g.points >= item.price), background = if (item.worn) ink.copy(alpha = 0.22f) else null) {
            IconView(icon, Color.White, 16.dp)
            BasicText(
                buildAnnotatedString {
                    append(item.name)
                    withStyle(SpanStyle(color = Color.White.copy(alpha = 0.55f), fontSize = 0.68.rem)) { append(" · ${item.text}") }
                },
                Modifier.weight(1f), style = Type.row, maxLines = 1, overflow = TextOverflow.Ellipsis,
            )
            Tag(if (item.worn) "em uso" else if (item.owned) "vestir" else "${item.price} pts")
        }
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
            com.evove.app.ui.GlyphView(Glyphs.byName(o.entity), c, 16.dp)
            BasicText(
                buildAnnotatedString {
                    withStyle(SpanStyle(color = c)) { append(caps(if (o.unlocked) o.entity else "?")) }
                    withStyle(SpanStyle(color = Color.White.copy(alpha = 0.6f), fontSize = 0.66.rem)) {
                        append(if (o.unlocked) " · ${o.text}" else " · ainda não apareceu")
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
    val code = v.code
    if (code == null) {
        Empty("livre. não há código.")
        return
    }
    Label("o que ficou")
    BasicText(
        code,
        Modifier.fillMaxWidth().weight(1f, fill = false).border(1.5.dp, LocalInk.current).padding(0.7.remDp),
        style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, color = Color.White, lineHeight = 0.95.rem),
    )
    Key({ onCopy(code) }, Modifier.fillMaxWidth().heightIn(min = 2.8.remDp)) { KeyIcon(Icon.LINK); KeyText("copiar") }
}

// ---------------------------------------------------------------- the fight

/** The top of the fight: both bars, the entities on each side, the last blows. */
@Composable
private fun ColumnScope.FightPanel(v: FightView?, done: Boolean, setup: FightSetup?, ended: FightEnd?) {
    val ink = LocalInk.current
    val font = TextStyle(fontFamily = Display, fontSize = 0.7.rem, letterSpacing = 0.08.em)
    val s = setup ?: return
    val you = v?.sides?.get(0)
    val foe = v?.sides?.get(1)
    val youHp = ended?.result?.hp?.getOrNull(0) ?: you?.hp ?: 0L
    val foeHp = ended?.result?.hp?.getOrNull(1) ?: foe?.hp ?: 0L
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            BasicText(caps("${s.you.name} ${maxOf(0, youHp)}"), style = font.copy(color = Color.White), maxLines = 1)
            Bar(youHp, s.you.maxHp, ink)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp), horizontalAlignment = Alignment.End) {
            BasicText(caps("${s.foe.name} ${maxOf(0, foeHp)}"), style = font.copy(color = Ink.enemy), maxLines = 1)
            Bar(foeHp, s.foe.maxHp, Ink.enemy)
        }
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            if (you != null) for (a in you.allies) AllyRow(a.name, voiceInk(a.id), a.skill, a.ability)
            if (you != null && you.allies.isEmpty()) BasicText(caps("sem entidade"), style = font.copy(fontSize = 0.6.rem, color = Ink.mute))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp), horizontalAlignment = Alignment.End) {
            if (foe != null) for (a in foe.allies) AllyRow(a.name, Ink.enemy, a.skill, a.ability)
        }
    }
    Column(Modifier.fillMaxWidth().weight(1f), verticalArrangement = Arrangement.spacedBy(0.3.remDp, Alignment.Bottom)) {
        val names = s.you.name to s.foe.name
        for (e in v?.events.orEmpty()) BasicText(eventText(e, names), style = font.copy(fontSize = 0.72.rem, color = if (e.side == 0) Color.White else Ink.enemy), maxLines = 1, overflow = TextOverflow.Ellipsis)
        if (done && ended != null) BasicText(
            caps(if (ended.won) "${s.foe.name} caiu." else "o sinal caiu."),
            style = font.copy(fontSize = 1.rem, fontWeight = FontWeight.SemiBold, color = ink),
        )
        else if (done) BasicText("…", style = font.copy(color = ink))
    }
}

@Composable
private fun Bar(hp: Long, max: Long, color: Color) {
    BoxWithConstraints(Modifier.fillMaxWidth().height(8.dp).border(1.dp, color)) {
        Box(Modifier.width(maxWidth * (maxOf(0L, hp).toFloat() / maxOf(1L, max)).coerceIn(0f, 1f)).fillMaxHeight().background(color))
    }
}

/** An entity in the fight: its name, and how close its skill and its ability are. */
@Composable
private fun AllyRow(name: String, color: Color, skill: Float, ability: Float) {
    Row(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
        BasicText(caps(name), style = TextStyle(fontFamily = Mono, fontSize = 0.58.rem, color = color), maxLines = 1)
        Charge(skill, color, 22.dp)
        Charge(ability, color, 34.dp)
    }
}

@Composable
private fun Charge(p: Float, color: Color, w: androidx.compose.ui.unit.Dp) {
    Box(Modifier.width(w).height(4.dp).border(0.5.dp, color.copy(alpha = 0.7f))) {
        Box(Modifier.fillMaxHeight().width(w * p.coerceIn(0f, 1f)).background(color))
    }
}

private fun eventText(e: FightEvent, names: Pair<String, String>): String {
    val who = if (e.side == 0) names.first else names.second
    return caps(when (e.kind) {
        "attack" -> "${e.name} −${e.value}"
        "heal" -> "${e.name} +${e.value}"
        "trick" -> "$who: ${TRICK_NAME[e.name] ?: e.name}"
        "skill" -> "${e.name} age"
        "ability" -> "${e.name}!"
        "interfere" -> "${e.name} interfere −${e.value}"
        "deny" -> "${e.name} negado"
        "miss" -> "${e.name} falhou"
        "burn" -> "chama −${e.value}"
        else -> e.kind
    })
}

/** The bottom of the fight: the attacks recharging, the heal, and the trick —
 *  the one thing to do. */
@Composable
private fun ColumnScope.FightBody(v: FightView?, ended: FightEnd?, queued: Boolean, onTrick: () -> Unit) {
    val ink = LocalInk.current
    if (v == null) {
        val r = ended
        if (r == null) { Empty("…"); return }
        Stats(listOf(
            "resultado" to (if (r.won) "vitória" else "derrota"),
            "tempo" to "${r.result.ticks / 10}s",
            "dano causado" to "${r.result.dealt.getOrNull(0) ?: 0}",
            "truques" to "${r.result.tricks.getOrNull(0) ?: 0}",
            "pontos" to "+${r.points}",
        ))
        return
    }
    val you = v.sides[0]
    for ((name, p) in you.moves) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            BasicText(caps(name), Modifier.weight(1f), style = Type.row.copy(fontSize = 0.72.rem), maxLines = 1, overflow = TextOverflow.Ellipsis)
            Charge(p, ink, 72.dp)
        }
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        BasicText(caps("${you.heal.first} · cura"), Modifier.weight(1f), style = Type.row.copy(fontSize = 0.72.rem, color = Ink.act), maxLines = 1)
        Charge(you.heal.second, Ink.act, 72.dp)
    }
    val trick = you.trick ?: ""
    val ready = you.ready
    Key(onTrick, Modifier.fillMaxWidth().heightIn(min = 5.remDp).testTag("trick"), enabled = true, on = ready || queued) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(0.25.remDp)) {
            BasicText(caps(TRICK_NAME[trick] ?: trick), style = Type.key.copy(fontSize = 1.1.rem, color = if (ready) Color.White else ink))
            BasicText(TRICK_TEXT[trick] ?: "", Modifier.alpha(0.7f), style = Type.small.copy(fontSize = 0.66.rem))
            Charge(you.charge, if (ready) Color.White else ink, 140.dp)
        }
        Column(horizontalAlignment = Alignment.End) {
            BasicText(caps("depois"), Modifier.alpha(0.6f), style = Type.label.copy(color = ink))
            BasicText(caps(TRICK_NAME[you.next ?: ""] ?: you.next ?: ""), style = Type.key.copy(color = ink))
        }
    }
}
