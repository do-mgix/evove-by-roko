package com.evove.app.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
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
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.IntOffset
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
import com.evove.app.ui.Static
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
import kotlin.math.pow

// The journey as a mode: a corridor seen from inside, walked by itself for as
// long as the checkpoints say, someone waiting — a frame of static — at the end
// of it. Below, the few things that can be done: start the fight, answer a
// choice, buy hp back with tokens, wear equipment, see the stats, and, in the
// third act, choose the two entities carried. No one talks here.
//
// The fight is drawn as an old console's: one message at a time in a box on
// top, the opponent as static in the middle, the hp at the bottom as a counter
// that rolls down, and the four attacks recharging beside it. Each action is a
// message and one shape — a blow shrinks toward the opponent, the opponent's
// blows wash over the screen — and while a message is read the fight waits.
// It plays itself, tricks included (com.evove.app.fight.Fight).

private enum class Leg { MAP, FIGHT, STATUS, EQUIP, STATS, PAIR }

/** How long a message of the fight stays, the fight waiting under it. */
private const val BEAT_MS = 1100L

private val TRICK_NAME = mapOf("atordoar" to "atordoar", "furia" to "fúria", "baque" to "baque", "rasteira" to "rasteira", "escudo" to "escudo", "eco" to "eco")
private val ABILITY_NAME = mapOf("decreto" to "decreto", "pergunta" to "pergunta", "ficar" to "ficar", "pressa" to "pressa", "troca" to "troca",
    "amarra" to "amarra", "chama" to "chama", "interferencia" to "interferência")

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

/** A message of the fight and the shape that goes with it. */
private data class Beat(val n: Int, val text: String, val shape: String, val side: Int, val color: Color)

private fun beatOf(n: Int, e: FightEvent, setup: FightSetup): Beat? {
    val who = if (e.side == 0) setup.you.name else setup.foe.name
    val ally = e.name.substringBefore("|")
    val color = if (e.side == 0) Ink.journey else Ink.enemy
    return when (e.kind) {
        "attack" -> Beat(n, "$who usou ${e.name}", if (e.side == 0) "attack" else "hurt", e.side, color)
        "heal" -> Beat(n, "$who usou ${e.name}", "heal", e.side, Ink.act)
        "trick" -> Beat(n, "$who usou ${TRICK_NAME[e.name] ?: e.name}", "trick", e.side, color)
        "skill" -> Beat(n, "$ally agiu", "entity", e.side, if (e.side == 0) voiceInk(entityOf(setup, ally)) else Ink.enemy)
        "ability" -> Beat(n, "$ally usou ${ABILITY_NAME[e.name.substringAfter("|")] ?: e.name.substringAfter("|")}", "entity", e.side,
            if (e.side == 0) voiceInk(entityOf(setup, ally)) else Ink.enemy)
        "interfere" -> Beat(n, "$ally interferiu", "entity", e.side, if (e.side == 0) voiceInk(entityOf(setup, ally)) else Ink.enemy)
        "deny" -> Beat(n, "${e.name} foi negado", "none", e.side, color)
        "miss" -> Beat(n, "${e.name} falhou", "none", e.side, color)
        else -> null
    }
}

private fun entityOf(setup: FightSetup, name: String) = setup.you.entities.find { it.name == name }?.id

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
    // the fight going on: its setup, the rules running it, what the screen shows of it
    var setup by remember { mutableStateOf<FightSetup?>(null) }
    var fight by remember { mutableStateOf<Fight?>(null) }
    var shown by remember { mutableStateOf<FightView?>(null) }
    var beat by remember { mutableStateOf<Beat?>(null) }
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
    val arrived = v != null && v.ending == null && v.pending == null && (v.waiting || left == 0L)

    fun go(l: Leg) {
        Sfx.tap(if (l == Leg.MAP) 0 else 4)
        leg = l
        message = emptyList()
        if (l == Leg.STATS) scope.launch { runCatching { Api.journeyStats() }.onSuccess { stats = it } }
        if (l == Leg.EQUIP) scope.launch { runCatching { Api.equipment() }.onSuccess { gear = it } }
        Sfx.powerOn()
    }

    /** The fight is over, or the person left it: the server replays it — the
     *  rest of it plays itself — and decides what it pays. */
    fun finish(leaving: Boolean = false) {
        fight ?: return
        fight = null
        if (leaving) {
            Evove.later { runCatching { Api.endFight(emptyList()) } }
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
        if (busy) return
        busy = true
        Sfx.tap(9)
        scope.launch {
            try {
                val s = Api.startFight()
                setup = s
                ended = null
                beat = null
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
    // the fight's clock: a tick every tenth of a second, and every message read
    // before the next one, the fight waiting under it
    LaunchedEffect(fight) {
        val f = fight ?: return@LaunchedEffect
        val s = setup ?: return@LaunchedEffect
        val ms = s.tickMs.toLong()
        var n = 0
        while (!f.over) {
            delay(ms)
            val before = f.events.size
            f.step()
            shown = f.view()
            for (e in f.events.drop(before)) {
                val b = beatOf(++n, e, s) ?: continue
                beat = b
                when (b.shape) {
                    "attack", "hurt" -> Sfx.hit()
                    "heal" -> Sfx.heal()
                    "entity", "trick" -> Sfx.entity()
                }
                delay(BEAT_MS)
            }
        }
        beat = null
        finish()
    }

    BackHandler(enabled = leg != Leg.MAP && leg != Leg.FIGHT) { go(Leg.MAP) }
    BackHandler(enabled = leg == Leg.FIGHT && fight == null) { ended = null; go(Leg.MAP) }

    if (leg == Leg.FIGHT && setup != null) {
        FightScreen(setup!!, shown, beat, fight == null, ended, onBack = { ended = null; go(Leg.MAP) }) {
            Sfx.tap(0)
            if (fight != null) finish(leaving = true)
            onHome()
        }
        return
    }

    val ink = Ink.journey
    DarkScreen(
        ink, display = 0.46f,
        displayContent = {
            when {
                message.isNotEmpty() -> Message(message)
                v == null -> Small("…")
                v.ending != null -> Big(if (v.ending == "free") "livre" else "fim")
                else -> {
                    Row(Modifier.fillMaxWidth()) {
                        val head = TextStyle(fontFamily = Mono, fontSize = 0.68.rem, letterSpacing = 0.1.em, color = ink.copy(alpha = 0.85f))
                        BasicText(caps("ato ${v.act} · andar ${v.floorInAct}" + (v.of?.let { "/$it" } ?: "")), Modifier.weight(1f), style = head)
                        BasicText(caps(if (v.pending != null) "escolha" else if (arrived) "" else clock(left)), style = head)
                    }
                    Corridor(walking = !arrived && v.pending == null, waiting = arrived, Modifier.fillMaxWidth().weight(1f))
                }
            }
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
                else -> {
                    Key({ go(Leg.MAP) }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
                    if (leg == Leg.EQUIP) Key({ Sfx.tap(2); slotAt++; Sfx.powerOn() }, Modifier.at(3)) { KeyIcon(Icon.DOWN) }
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
            leg == Leg.MAP -> MapBody(v, arrived, busy, ::startFight, ::choose)
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

// ---------------------------------------------------------------- the corridor

/** The corridor seen from inside: frames receding to a vanishing point, the
 *  walls' edges joining them, doors opening on either side now and then. While
 *  walking the frames come toward the eye; at the end of the floor a wall
 *  stands ahead, and on it whoever waits, as static. */
@Composable
private fun Corridor(walking: Boolean, waiting: Boolean, modifier: Modifier) {
    val ink = LocalInk.current
    // the distance walked, in frames: it grows while walking, stops when not
    var walked by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(walking) {
        if (!walking) return@LaunchedEffect
        var last = withFrameMillis { it }
        while (true) {
            val t = withFrameMillis { it }
            walked += (t - last) / 1400f
            last = t
        }
    }
    BoxWithConstraints(modifier.clipToBounds()) {
        val density = LocalDensity.current
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val farDepth = 3.2f
        fun scaleAt(z: Float) = 1f / (1f + z * 0.55f)
        Canvas(Modifier.fillMaxSize()) {
            val cx = w / 2
            val cy = h * 0.48f
            val stroke = 1.5.dp.toPx()
            fun rect(z: Float): Pair<Offset, Size> {
                val k = scaleAt(z)
                val rw = w * 0.96f * k
                val rh = h * 0.96f * k
                return Offset(cx - rw / 2, cy - rh / 2) to Size(rw, rh)
            }
            val frac = walked - floor(walked)
            val base = floor(walked).toInt()
            val depths = if (waiting) (0..3).map { it.toFloat() } else (1..9).map { it - frac }
            val maxZ = if (waiting) farDepth else 9f
            // the walls' four edges, from the eye to the farthest frame
            val (fo, fs) = rect(maxZ)
            val alphaFar = 0.25f
            for ((a, b) in listOf(Offset(0f, 0f) to fo, Offset(w, 0f) to Offset(fo.x + fs.width, fo.y),
                    Offset(0f, h) to Offset(fo.x, fo.y + fs.height), Offset(w, h) to Offset(fo.x + fs.width, fo.y + fs.height))) {
                drawLine(ink.copy(alpha = 0.55f), a, b, stroke)
            }
            for (z in depths) {
                if (z <= 0.05f || z > maxZ) continue
                val (o, s) = rect(z)
                val alpha = (1f - z / (maxZ + 1)).coerceIn(alphaFar, 0.9f)
                drawRect(ink.copy(alpha = alpha), o, s, style = Stroke(stroke))
                // a door on the left or right wall of some frames, the same each time it comes by
                val k = (base + z.toInt()) * 7919 % 5
                if (!waiting && (k == 1 || k == 3)) {
                    val (o2, s2) = rect(z + 0.55f)
                    val left = k == 1
                    val x1 = if (left) o.x else o.x + s.width
                    val x2 = if (left) o2.x else o2.x + s2.width
                    val top1 = o.y + s.height * 0.28f
                    val top2 = o2.y + s2.height * 0.28f
                    val p = Path().apply {
                        moveTo(x1, o.y + s.height); lineTo(x1, top1); lineTo(x2, top2); lineTo(x2, o2.y + s2.height)
                    }
                    drawPath(p, ink.copy(alpha = alpha * 0.8f), style = Stroke(stroke))
                }
            }
            if (waiting) {
                // the wall at the end of the floor
                drawRect(ink.copy(alpha = 0.06f), fo, fs)
                drawRect(ink.copy(alpha = 0.6f), fo, fs, style = Stroke(stroke))
            }
            // the floor's line at the eye's feet
            drawLine(ink.copy(alpha = 0.2f), Offset(0f, h * 0.98f), Offset(w, h * 0.98f), stroke)
        }
        if (waiting) {
            val k = scaleAt(farDepth)
            val side = with(density) { (minOf(w, h) * 0.96f * k * 0.62f).toDp() }
            val cxDp = with(density) { (w / 2).toDp() }
            val cyDp = with(density) { (h * 0.48f).toDp() }
            Static(Modifier.offset(cxDp - side / 2, cyDp - side / 2).size(side).border(1.5.dp, Ink.enemy).testTag("waiting"), opacity = 0.6f)
        }
    }
}

@Composable
private fun ColumnScope.MapBody(v: DungeonView, arrived: Boolean, busy: Boolean, onFight: () -> Unit, onChoose: (String) -> Unit) {
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

// ---------------------------------------------------------------- the fight

/** The fight: the message box, the opponent as static, the shape of the action
 *  read, the hp rolling down and the four attacks recharging. */
@Composable
private fun FightScreen(setup: FightSetup, v: FightView?, beat: Beat?, done: Boolean, ended: FightEnd?, onBack: () -> Unit, onHome: () -> Unit) {
    val ink = Ink.journey
    val you = v?.sides?.get(0)
    // the opponent's blows shake the screen a little
    val shake = remember { Animatable(0f) }
    LaunchedEffect(beat?.n) {
        if (beat?.shape == "hurt") {
            shake.snapTo(1f)
            shake.animateTo(0f, tween(450, easing = LinearEasing))
        }
    }
    CompositionLocalProvider(LocalInk provides ink) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
            val jitter = with(LocalDensity.current) { (shake.value * 6.dp.toPx() * if ((beat?.n ?: 0) % 2 == 0) 1 else -1).toInt() }
            Column(Modifier.fillMaxSize().offset { IntOffset(jitter, 0) }, verticalArrangement = Arrangement.spacedBy(14.dp)) {
                MessageBox(
                    when {
                        done && ended != null -> if (ended.won) "vitória · +${ended.points} pontos" else "derrota"
                        done -> "…"
                        beat != null -> beat.text
                        else -> "${setup.foe.name} está na sua frente"
                    },
                )
                // the opponent, and the shapes flying to it or from it
                Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                    BoxWithConstraints(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        val side = minOf(maxWidth, maxHeight) * 0.62f
                        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Static(Modifier.size(side).border(1.5.dp, Ink.enemy).testTag("foe"), opacity = if (done && ended?.won == true) 0.12f else 0.6f)
                            BasicText(caps(setup.foe.name), style = TextStyle(fontFamily = Display, fontSize = 0.8.rem, letterSpacing = 0.15.em, color = Ink.enemy))
                        }
                    }
                    Shapes(beat, Modifier.fillMaxSize())
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically) {
                    HpCard(setup.you.name, you?.hp ?: ended?.result?.hp?.getOrNull(0) ?: setup.you.hp, ink)
                    Skills(you, ink)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    if (done) Key({ Sfx.tap(0); onBack() }, Modifier.weight(1f).height(3.remDp)) { KeyIcon(Icon.LEFT) } else Box(Modifier.weight(1f))
                    Box(Modifier.weight(3f))
                    Key(onHome, Modifier.weight(1f).height(3.remDp)) { KeyIcon(Icon.CIRCLE, 16.dp) }
                }
            }
        }
    }
}

/** One message at a time, in a box. */
@Composable
private fun MessageBox(text: String) {
    val ink = LocalInk.current
    Box(Modifier.fillMaxWidth().heightIn(min = 4.2.remDp).border(1.5.dp, ink).background(Color.Black).padding(horizontal = 0.9.remDp, vertical = 0.8.remDp),
        contentAlignment = Alignment.CenterStart) {
        BasicText("• ${caps(text)}", style = TextStyle(fontFamily = Display, fontSize = 0.92.rem, fontWeight = FontWeight.Medium, lineHeight = 1.4.em,
            letterSpacing = 0.05.em, color = Color.White), maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

/** The shape of the action being read: one per kind. A blow, a trick or an
 *  entity of the profile's side shrinks from below toward the opponent; the
 *  opponent's blows come at the screen as rings; a heal opens where it lands. */
@Composable
private fun Shapes(beat: Beat?, modifier: Modifier) {
    val t = remember { Animatable(1f) }
    LaunchedEffect(beat?.n) {
        if (beat == null) return@LaunchedEffect
        t.snapTo(0f)
        t.animateTo(1f, tween(700, easing = LinearEasing))
    }
    val b = beat ?: return
    if (b.shape == "none") return
    Canvas(modifier) {
        val p = t.value
        if (p >= 1f) return@Canvas
        val foe = Offset(size.width / 2, size.height * 0.45f)
        val self = Offset(size.width / 2, size.height * 1.05f)
        val stroke = 2.dp.toPx()
        val from = if (b.side == 0) self else foe
        val to = if (b.side == 0) foe else self
        fun at(k: Float) = Offset(from.x + (to.x - from.x) * k, from.y + (to.y - from.y) * k)
        val big = size.minDimension * 0.5f
        when (b.shape) {
            "attack" -> {
                val s = big * (1f - p).pow(1.4f) + 6.dp.toPx()
                val c = at(p)
                drawRect(b.color.copy(alpha = 1f - p * 0.4f), Offset(c.x - s / 2, c.y - s / 2), Size(s, s), style = Stroke(stroke))
            }
            "trick" -> {
                val s = big * 0.8f * (1f - p) + 6.dp.toPx()
                rotate(p * 180f, at(p)) { diamond(at(p), s, b.color.copy(alpha = 1f - p * 0.4f), stroke) }
            }
            "entity" -> {
                val s = big * 0.9f * (1f - p).pow(1.2f) + 6.dp.toPx()
                triangle(at(p), s, b.color.copy(alpha = 1f - p * 0.3f), stroke)
            }
            "heal" -> {
                val c = if (b.side == 0) Offset(size.width / 2, size.height * 0.95f) else foe
                drawCircle(b.color.copy(alpha = 1f - p), big * 0.15f + big * 0.6f * p, c, style = Stroke(stroke))
            }
            "hurt" -> {
                // rings from the opponent washing over the screen
                for (k in 0..2) {
                    val q = (p - k * 0.15f).coerceIn(0f, 1f)
                    if (q <= 0f) continue
                    drawCircle(b.color.copy(alpha = (1f - q) * 0.8f), size.maxDimension * q, foe, style = Stroke(stroke * (1 + k)))
                }
                drawRect(b.color.copy(alpha = (1f - p) * 0.12f))
            }
        }
    }
}

private fun DrawScope.diamond(c: Offset, s: Float, color: Color, stroke: Float) {
    val p = Path().apply { moveTo(c.x, c.y - s / 2); lineTo(c.x + s / 2, c.y); lineTo(c.x, c.y + s / 2); lineTo(c.x - s / 2, c.y); close() }
    drawPath(p, color, style = Stroke(stroke))
}

private fun DrawScope.triangle(c: Offset, s: Float, color: Color, stroke: Float) {
    val p = Path().apply { moveTo(c.x, c.y - s / 2); lineTo(c.x + s / 2, c.y + s / 2); lineTo(c.x - s / 2, c.y + s / 2); close() }
    drawPath(p, color, style = Stroke(stroke))
}

/** The hp as the old consoles kept it: the name, and a counter whose digits
 *  roll down toward the hp left, never jumping. */
@Composable
private fun HpCard(name: String, hp: Long, ink: Color) {
    val target = maxOf(0L, hp).toFloat()
    var shownHp by remember { mutableFloatStateOf(target) }
    val goalNow by rememberUpdatedState(target)
    LaunchedEffect(Unit) {
        var last = withFrameMillis { it }
        while (true) {
            val t = withFrameMillis { it }
            val dt = (t - last) / 1000f
            last = t
            val goal = goalNow
            // a few points a second, faster the farther it has to go
            val speed = maxOf(12f, kotlin.math.abs(goal - shownHp) * 1.2f)
            shownHp = if (shownHp > goal) maxOf(goal, shownHp - speed * dt) else minOf(goal, shownHp + speed * dt)
        }
    }
    Column(
        Modifier.border(1.5.dp, ink).background(Color.Black).padding(horizontal = 1.remDp, vertical = 0.6.remDp).testTag("hp"),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(0.3.remDp),
    ) {
        BasicText(caps(name), style = TextStyle(fontFamily = Display, fontSize = 0.78.rem, letterSpacing = 0.12.em, color = Color.White), maxLines = 1)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.4.remDp)) {
            BasicText("HP", style = TextStyle(fontFamily = Mono, fontSize = 0.7.rem, color = ink))
            Odometer(shownHp, digits = maxOf(3, target.toLong().toString().length), color = if (target <= 0f) Ink.danger else Color.White)
        }
    }
}

/** Digits that roll like an odometer's: each one moves on as the one to its
 *  right passes from 9 to 0. */
@Composable
private fun Odometer(value: Float, digits: Int, color: Color) {
    val style = TextStyle(fontFamily = Mono, fontSize = 1.6.rem, fontWeight = FontWeight.SemiBold, color = color)
    val h = 1.9.remDp
    Row(Modifier.clipToBounds()) {
        for (place in digits - 1 downTo 0) {
            val unit = 10f.pow(place)
            val d = (value / unit) % 10f
            // the digit turns only while the places to its right roll over
            val lower = value % unit
            val turn = if (place == 0) d - floor(d) else ((lower - (unit - 1f)).coerceIn(0f, 1f))
            val digit = floor(d).toInt() % 10
            Box(Modifier.width(1.05.remDp).height(h).clipToBounds()) {
                val off = with(LocalDensity.current) { (h.toPx() * turn).toInt() }
                BasicText("$digit", Modifier.offset { IntOffset(0, -off) }, style = style)
                BasicText("${(digit + 1) % 10}", Modifier.offset { IntOffset(0, h.roundToPx() - off) }, style = style)
            }
        }
    }
}

/** The four attacks, two by two, each a ring that closes as it recharges. */
@Composable
private fun Skills(you: com.evove.app.fight.SideView?, ink: Color) {
    // the attacks, and the heal in the slot one of them leaves free
    val slots = (you?.moves.orEmpty().map { Triple(it.first, it.second, false) } +
        listOfNotNull(you?.heal?.let { Triple(it.first, it.second, true) })).take(4)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        for (row in slots.chunked(2)) Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            for ((name, p, heal) in row) Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                val c = if (heal) Ink.act else ink
                Canvas(Modifier.size(2.2.remDp)) {
                    val s = 2.5.dp.toPx()
                    drawCircle(c.copy(alpha = 0.25f), size.minDimension / 2 - s, style = Stroke(s))
                    drawArc(c, -90f, 360f * p.coerceIn(0f, 1f), false, Offset(s, s), Size(size.width - 2 * s, size.height - 2 * s),
                        style = Stroke(s, cap = StrokeCap.Round))
                }
                BasicText(caps(name.substringBefore(" (").take(7)), style = TextStyle(fontFamily = Mono, fontSize = 0.52.rem, color = c), maxLines = 1)
            }
        }
    }
}
