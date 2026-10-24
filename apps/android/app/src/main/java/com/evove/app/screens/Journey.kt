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
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
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
import com.evove.app.api.FightEnd
import com.evove.app.api.FightSetup
import com.evove.app.api.JourneyStats
import com.evove.app.api.Recovery
import com.evove.app.fight.Fight
import com.evove.app.fight.FightEvent
import com.evove.app.fight.FightView
import com.evove.app.sound.Music
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

/** A message of the fight, the shape that goes with it, which side it came
 *  from, and — for an entity — who, for the camera to turn to; `second` says
 *  what it did, when that is not plain damage. */
private data class Beat(val n: Int, val text: String, val shape: String, val side: Int, val color: Color, val entity: String? = null,
                        val second: String? = null)

/** The color of the opponent's nameless entity. */
private val FOE_THEME = hex("#9b7bff")

private val TRICK_DID = mapOf(
    "atordoar" to "%o ficou atordoado: suas recargas param",
    "furia" to "as recargas de %w correm em dobro",
    "baque" to "tudo parou por um instante",
    "rasteira" to "um ataque de %o voltou ao começo",
    "escudo" to "%w segura o próximo golpe",
    "eco" to "%w repetiu o último ataque",
)
private val SKILL_DID = mapOf(
    "negar" to "o próximo golpe de %o será negado",
    "potencia" to "%w ficou mais forte",
    "truques" to "dois truques de uma vez",
)
private val ABILITY_DID = mapOf(
    "decreto" to "os ataques de %w subiram um rank",
    "pergunta" to "%o vai duvidar dos próximos golpes",
    "ficar" to "%w não se move: a defesa sobe",
    "pressa" to "%w recarrega em dobro",
    "troca" to "a cura de %o foi roubada",
    "amarra" to "%o foi amarrado: tudo volta ao começo",
    "chama" to "%o está queimando",
    "interferencia" to "algo mudou em %o",
)

private fun beatOf(n: Int, e: FightEvent, setup: FightSetup): Beat? {
    val who = if (e.side == 0) setup.you.name else setup.foe.name
    val other = if (e.side == 0) setup.foe.name else setup.you.name
    fun did(t: String?) = t?.replace("%w", who)?.replace("%o", other)
    val ally = e.name.substringBefore("|")
    val what = e.name.substringAfter("|")
    val color = if (e.side == 0) Ink.journey else Ink.enemy
    val theme = if (e.side == 0) voiceInk(entityOf(setup, ally)) else FOE_THEME
    val allies = (if (e.side == 0) setup.you.entities else setup.foe.entities).map { it.name }
    return when (e.kind) {
        "attack" -> Beat(n, "$who usou ${e.name}", "attack", e.side, color)
        // a heal from an entity is said as the entity's
        "heal" -> if (e.name in allies) Beat(n, "${e.name} agiu", "entity", e.side, theme, e.name, "${e.name} curou $who · +${e.value}")
            else Beat(n, "$who usou ${e.name}", "heal", e.side, Ink.act, second = "+${e.value} hp")
        "trick" -> Beat(n, "$who usou ${TRICK_NAME[e.name] ?: e.name}", "trick", e.side, color, second = did(TRICK_DID[e.name]))
        "skill" -> if (what == "atacar") Beat(n, "$ally atacou", "entity", e.side, theme, ally)
            else Beat(n, "$ally agiu", "entity", e.side, theme, ally, did(SKILL_DID[what]))
        "ability" -> Beat(n, "$ally usou ${ABILITY_NAME[what] ?: what}", "entity", e.side, theme, ally, did(ABILITY_DID[what]))
        "interfere" -> Beat(n, "$ally interferiu", "entity", e.side, theme, ally)
        "deny" -> Beat(n, "${e.name} foi negado", "none", e.side, color)
        "miss" -> Beat(n, "${e.name} falhou", "none", e.side, color)
        "level" -> Beat(n, "${e.name} subiu para o nível ${e.value}", "level", e.side, Ink.gold)
        else -> null
    }
}

/** A number that rises from the opponent: damage, or what it healed. */
private data class Pop(val id: Int, val text: String, val color: Color, val born: Long, val dx: Float)

private fun entityOf(setup: FightSetup, name: String) = setup.you.entities.find { it.name == name }?.id

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
    // the fight going on: its setup, the rules running it, what the screen shows of it
    var setup by remember { mutableStateOf<FightSetup?>(null) }
    var fight by remember { mutableStateOf<Fight?>(null) }
    var shown by remember { mutableStateOf<FightView?>(null) }
    var beat by remember { mutableStateOf<Beat?>(null) }
    var ended by remember { mutableStateOf<FightEnd?>(null) }
    var pops by remember { mutableStateOf<List<Pop>>(emptyList()) }
    // what the box under the corridor tells, one line at a time
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
    val left = v?.let { maxOf(0, it.secondsLeft - elapsed) } ?: 0
    val arrived = v != null && v.ending == null && v.pending == null && (v.waiting || left == 0L)

    fun go(l: Leg) {
        Sfx.tap(if (l == Leg.MAP) 0 else 4)
        leg = l
        message = emptyList()
        if (l == Leg.STATS) scope.launch { runCatching { Api.journeyStats() }.onSuccess { stats = it } }
        if (l == Leg.EQUIP) scope.launch { runCatching { Api.inventory() }.onSuccess { inventory = it } }
        Sfx.powerOn()
    }

    /** The fight is over, or the person left it: the server replays it — the
     *  rest of it plays itself — and decides what it pays. */
    fun finish(leaving: Boolean = false) {
        fight ?: return
        fight = null
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
        var p = 0
        while (!f.over) {
            delay(ms)
            val before = f.events.size
            f.step()
            val now = f.view()
            shown = now
            if (f.tick % 10 == 0) {
                val you = now.sides[0]
                Music.mix(f.tick / 10f, you.hp * 100 < you.maxHp * 35, you.hasted, you.allies.maxOfOrNull { it.chance } ?: 0f)
            }
            for (e in f.events.drop(before)) {
                // what reaches the opponent rises from it as a number
                val onFoe = e.side == 0 && e.kind in setOf("attack", "interfere", "skill", "burn") && (e.kind != "skill" || e.name.endsWith("|atacar"))
                val foeHeal = e.side == 1 && e.kind == "heal"
                if (onFoe || foeHeal) {
                    pops = pops.filter { System.currentTimeMillis() - it.born < 1600 } +
                        Pop(++p, if (foeHeal) "+${e.value}" else "−${e.value}", if (foeHeal) Ink.act else Color.White,
                            System.currentTimeMillis(), ((p * 37) % 60 - 30) / 100f)
                }
                val b = beatOf(++n, e, s) ?: continue
                beat = b
                when (b.shape) {
                    "attack" -> Sfx.hit()
                    "heal" -> Sfx.heal()
                    "trick" -> Sfx.entity()
                    "entity" -> Sfx.boom()
                    "level" -> Sfx.levelUp()
                }
                delay(BEAT_MS)
                b.second?.let {
                    beat = b.copy(n = ++n, text = it, shape = "none")
                    delay(BEAT_MS)
                }
            }
        }
        beat = null
        finish()
    }

    BackHandler(enabled = leg != Leg.MAP && leg != Leg.FIGHT) { go(Leg.MAP) }
    BackHandler(enabled = leg == Leg.FIGHT && fight == null) { ended = null; go(Leg.MAP) }

    if (leg == Leg.FIGHT && setup != null) {
        FightScreen(setup!!, shown, beat, pops, fight == null, ended, onBack = { ended = null; go(Leg.MAP) }) {
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
                    Notices(
                        when {
                            notices.isNotEmpty() -> notices
                            v.pending != null -> listOf(v.pending.text.lowercase())
                            arrived -> listOf("inimigo encontrado: ${v.opponent.name}")
                            else -> listOf("explorando o andar ${v.floorInAct}")
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
            leg == Leg.MAP -> MapBody(v, arrived, busy, ::startFight, ::choose)
            leg == Leg.STATUS -> StatusBody(v, busy, elapsed, ::heal)
            leg == Leg.EQUIP -> InventoryBody(inventory, busy) { wear(it) }
            leg == Leg.STATS -> StatsBody(v)
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

// ---------------------------------------------------------------- the fight

/** The fight: the message box; the stage — the opponent as unstable frames of
 *  static over a floor in perspective, its shadow under it, its energy bar —
 *  or, while an entity acts, the camera on that entity; the hp rolling down,
 *  the two attacks, the heal and the trick, and the entities' chance to step in. */
@Composable
private fun FightScreen(setup: FightSetup, v: FightView?, beat: Beat?, pops: List<Pop>, done: Boolean, ended: FightEnd?, onBack: () -> Unit, onHome: () -> Unit) {
    val ink = Ink.journey
    // the fight's own music while it lasts, the menus' after
    androidx.compose.runtime.DisposableEffect(Unit) {
        Music.battle()
        Evove.fighting = true
        onDispose {
            Music.menus()
            Evove.fighting = false
        }
    }
    val you = v?.sides?.get(0)
    val foe = v?.sides?.get(1)
    val frozen = v?.frozen == true
    // blows that come at the screen shake it
    val shake = remember { Animatable(0f) }
    LaunchedEffect(beat?.n) {
        val b = beat ?: return@LaunchedEffect
        if ((b.shape == "attack" && b.side == 1) || b.shape == "entity" || (b.shape == "attack" && b.side == 0)) {
            shake.snapTo(1f)
            shake.animateTo(0f, tween(if (b.shape == "entity") 650 else 450, easing = LinearEasing))
        }
    }
    CompositionLocalProvider(LocalInk provides ink) {
        Box(Modifier.fillMaxSize().padding(10.dp)) {
            val jitter = with(LocalDensity.current) { (shake.value * 7.dp.toPx() * if ((beat?.n ?: 0) % 2 == 0) 1 else -1).toInt() }
            Column(Modifier.fillMaxSize().offset { IntOffset(jitter, -jitter / 2) }, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                MessageBox(
                    when {
                        done && ended != null -> endText(ended)
                        done -> "…"
                        beat != null -> beat.text
                        else -> "${setup.foe.name} está na sua frente"
                    },
                )
                Box(Modifier.fillMaxWidth().weight(1f).clipToBounds()) {
                    val camera = beat?.takeIf { it.shape == "entity" }
                    if (camera != null) EntityCamera(camera, Modifier.fillMaxSize())
                    else Stage(setup, foe, frozen, done && ended?.won == true, Modifier.fillMaxSize())
                    Shapes(beat, Modifier.fillMaxSize())
                    Pops(pops, Modifier.fillMaxSize())
                    LevelBadge(beat?.takeIf { it.shape == "level" && it.side == 1 }, Modifier.align(Alignment.TopCenter).padding(top = 44.dp))
                }
                if (done && ended != null) EndSummary(ended)
                Box(Modifier.fillMaxWidth()) {
                    LevelBadge(beat?.takeIf { it.shape == "level" && it.side == 0 }, Modifier.align(Alignment.TopCenter))
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically) {
                    HpCard(setup.you.name, you?.hp ?: ended?.result?.hp?.getOrNull(0) ?: setup.you.hp, if (frozen || you?.stunned == true) Ink.mute else ink, you,
                        you?.level ?: setup.you.level)
                    Skills(you, if (frozen || you?.stunned == true) Ink.mute else ink)
                    Chances(you)
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

/** Where the opponent stands: a floor in perspective to a horizon, the
 *  opponent's frames over their shadow, and its energy bar above. */
@Composable
private fun Stage(setup: FightSetup, foe: com.evove.app.fight.SideView?, frozen: Boolean, beaten: Boolean, modifier: Modifier) {
    val ink = LocalInk.current
    val grey = frozen || foe?.stunned == true
    BoxWithConstraints(modifier) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val horizon = h * 0.42f
        val feet = h * 0.72f
        Canvas(Modifier.fillMaxSize()) {
            val stroke = 1.dp.toPx()
            drawLine(ink.copy(alpha = 0.35f), Offset(0f, horizon), Offset(w, horizon), stroke)
            // the floor: lines to a vanishing point, and rows nearing the eye
            val vx = w / 2
            for (k in -6..6) drawLine(ink.copy(alpha = 0.16f), Offset(vx + k * w * 0.02f, horizon), Offset(vx + k * w * 0.32f, h), stroke)
            for (r in 1..7) {
                val y = horizon + (h - horizon) * (r / 7f).pow(1.8f)
                drawLine(ink.copy(alpha = 0.06f + 0.03f * r), Offset(0f, y), Offset(w, y), stroke)
            }
            // the shadow at the opponent's feet
            val sw = w * 0.34f
            drawOval(Color.Black.copy(alpha = 0.85f), Offset(vx - sw / 2, feet - sw * 0.09f), Size(sw, sw * 0.18f))
            drawOval(ink.copy(alpha = 0.22f), Offset(vx - sw / 2, feet - sw * 0.09f), Size(sw, sw * 0.18f), style = Stroke(stroke))
        }
        val density = LocalDensity.current
        val side = with(density) { (minOf(w * 0.34f, (feet - horizon) * 1.6f)).toDp() }
        val top = with(density) { feet.toDp() } - side * 1.05f
        Column(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            BasicText(caps(setup.foe.name), style = TextStyle(fontFamily = Display, fontSize = 0.72.rem, letterSpacing = 0.15.em, color = if (grey) Ink.mute else Ink.enemy))
            val hp = foe?.hp ?: 0L
            val c = if (grey) Ink.mute else if (foe?.burning == true) Ink.late else Ink.enemy
            Box(Modifier.width(side * 1.6f).height(7.dp).border(1.dp, c)) {
                Box(Modifier.fillMaxHeight().width(side * 1.6f * (maxOf(0L, hp).toFloat() / maxOf(1L, setup.foe.maxHp)).coerceIn(0f, 1f)).background(c))
            }
        }
        if (!beaten) StaticFigure(
            if (grey) Ink.mute else Color.White, if (grey) Ink.mute else Ink.enemy,
            Modifier.offset(with(density) { (w / 2).toDp() } - side / 2, top).size(side).testTag("foe"),
            shield = foe?.shielded == true,
        )
    }
}

/** The camera turned to an entity: its own frames, in its color, close. */
@Composable
private fun EntityCamera(b: Beat, modifier: Modifier) {
    BoxWithConstraints(modifier, contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            // a burst of lines behind it, in its color
            val c = Offset(size.width / 2, size.height / 2)
            for (k in 0 until 24) {
                val a = Math.toRadians(k * 15.0)
                val r = size.maxDimension
                drawLine(b.color.copy(alpha = 0.18f), c, Offset(c.x + (Math.cos(a) * r).toFloat(), c.y + (Math.sin(a) * r).toFloat()), 1.dp.toPx())
            }
        }
        val side = minOf(maxWidth, maxHeight) * 0.66f
        UnstableFrames(b.color, b.color, Modifier.size(side), count = 9)
        BasicText(caps(b.entity ?: ""), Modifier.align(Alignment.BottomCenter).padding(bottom = 6.dp),
            style = TextStyle(fontFamily = Display, fontSize = 1.rem, letterSpacing = 0.25.em, color = b.color))
    }
}

/** Frames of static that will not hold still: a few of them, overlapping,
 *  thrown a little each moment, tinted `tint`. */
@Composable
private fun UnstableFrames(tint: Color, edge: Color, modifier: Modifier, count: Int = 6, shield: Boolean = false) {
    var tick by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) { delay(90); tick++ }
    }
    Canvas(modifier) {
        val rnd = java.util.Random(tick.toLong() * 31 + 17)
        val cells = 7
        for (f in 0 until count) {
            val fw = size.width * (0.42f + rnd.nextFloat() * 0.36f)
            val fh = size.height * (0.42f + rnd.nextFloat() * 0.36f)
            val x = (size.width - fw) * rnd.nextFloat()
            val y = (size.height - fh) * rnd.nextFloat()
            val cw = fw / cells
            val ch = fh / cells
            for (i in 0 until cells) for (j in 0 until cells) {
                val v = rnd.nextFloat()
                drawRect(tint.copy(alpha = 0.08f + v * 0.32f), Offset(x + i * cw, y + j * ch), Size(cw, ch))
            }
            drawRect(edge.copy(alpha = 0.75f), Offset(x, y), Size(fw, fh), style = Stroke(1.2.dp.toPx()))
        }
        if (shield) drawCircle(Ink.journey.copy(alpha = 0.7f), size.minDimension * 0.62f, style = Stroke(2.dp.toPx()))
    }
}

/** Whoever waits, as a few frames of static that hold their places, stacked
 *  taller than wide; only the static inside them moves, even when everything
 *  else has stopped. */
@Composable
private fun StaticFigure(tint: Color, edge: Color, modifier: Modifier, shield: Boolean = false) {
    var tick by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) { delay(90); tick++ }
    }
    // where each frame stands, in parts of the figure's box: fixed
    val frames = remember { listOf(floatArrayOf(0.32f, 0.0f, 0.36f, 0.24f), floatArrayOf(0.24f, 0.22f, 0.52f, 0.34f),
        floatArrayOf(0.3f, 0.54f, 0.18f, 0.44f), floatArrayOf(0.52f, 0.54f, 0.18f, 0.44f)) }
    Canvas(modifier) {
        val rnd = java.util.Random(tick.toLong() * 131 + 7)
        val cells = 6
        for (f in frames) {
            val x = size.width * f[0]
            val y = size.height * f[1]
            val fw = size.width * f[2]
            val fh = size.height * f[3]
            val cw = fw / cells
            val ch = fh / (cells * 1.5f)
            var j = 0f
            while (j * ch < fh - 0.5f) {
                for (i in 0 until cells) drawRect(tint.copy(alpha = 0.1f + rnd.nextFloat() * 0.45f), Offset(x + i * cw, y + j * ch), Size(cw, minOf(ch, fh - j * ch)))
                j += 1f
            }
            drawRect(edge.copy(alpha = 0.85f), Offset(x, y), Size(fw, fh), style = Stroke(1.5.dp.toPx()))
        }
        if (shield) drawOval(Ink.journey.copy(alpha = 0.75f), Offset(size.width * 0.12f, -size.height * 0.05f), Size(size.width * 0.76f, size.height * 1.1f), style = Stroke(2.5.dp.toPx()))
    }
}

/** The numbers that rise from the opponent — damage in white, what it healed
 *  in green — and fade. */
@Composable
private fun Pops(pops: List<Pop>, modifier: Modifier) {
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(pops) {
        while (pops.any { System.currentTimeMillis() - it.born < 1400 }) {
            withFrameMillis { }
            now = System.currentTimeMillis()
        }
        now = System.currentTimeMillis()
    }
    BoxWithConstraints(modifier) {
        val w = maxWidth
        val h = maxHeight
        for (p in pops) {
            val age = (now - p.born) / 1400f
            if (age < 0f || age >= 1f) continue
            BasicText(
                p.text,
                Modifier.offset(w * (0.5f + p.dx) - 20.dp, h * (0.42f - 0.2f * age)).alpha(1f - age * age),
                style = TextStyle(fontFamily = Mono, fontSize = 1.25.rem, fontWeight = FontWeight.Bold, color = p.color),
            )
        }
    }
}

/** LEVEL UP, over whoever went up. */
@Composable
private fun LevelBadge(beat: Beat?, modifier: Modifier) {
    val b = beat ?: return
    val pulse = remember(b.n) { Animatable(0f) }
    LaunchedEffect(b.n) { pulse.animateTo(1f, tween(500)) }
    BasicText(
        "LEVEL UP",
        modifier.alpha(0.4f + 0.6f * pulse.value).border(1.5.dp, Ink.gold).background(Color.Black).padding(horizontal = 10.dp, vertical = 3.dp),
        style = TextStyle(fontFamily = Display, fontSize = (0.7f + 0.15f * pulse.value).rem, letterSpacing = 0.2.em, color = Ink.gold),
    )
}

/** The end of the fight, said in the box. */
private fun endText(r: FightEnd): String = when {
    r.won -> "vitória · +${r.points} pontos"
    else -> "derrota · o ato recomeça"
}

/** What the fight gave, at its end: the levels and what they brought, the item. */
@Composable
private fun EndSummary(r: FightEnd) {
    val l = r.levels
    val lines = buildList {
        if (l.left) add("você saiu: os níveis desta luta se perderam")
        else if (l.gained > 0) add("+${l.gained} ${if (l.gained == 1) "nível" else "níveis"} · nível ${l.to} · hp +${l.hp} · resistência +${l.resist} · defesa +${l.defense} · dano +${l.damage}%")
        r.item?.let { add("item: ${it.name} · nível ${it.level}") }
    }
    if (lines.isEmpty()) return
    Column(Modifier.fillMaxWidth().border(1.5.dp, Ink.gold).padding(0.7.remDp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        for (t in lines) BasicText(caps(t), style = TextStyle(fontFamily = Mono, fontSize = 0.66.rem, color = Ink.gold, lineHeight = 1.3.em))
    }
}

/** The shape of the action read, one per kind — square for a blow, diamond for
 *  a trick, triangle for an entity, circle for a heal. The profile's come from
 *  behind the screen, as big as it, and shrink into the opponent; the
 *  opponent's are the exact opposite, born at its center and growing until
 *  they fill the screen. */
@Composable
private fun Shapes(beat: Beat?, modifier: Modifier) {
    val t = remember { Animatable(1f) }
    LaunchedEffect(beat?.n) {
        if (beat == null) return@LaunchedEffect
        t.snapTo(0f)
        t.animateTo(1f, tween(750, easing = LinearEasing))
    }
    val b = beat ?: return
    if (b.shape == "none") return
    Canvas(modifier) {
        val p = t.value
        if (p >= 1f) return@Canvas
        val foe = Offset(size.width / 2, size.height * 0.55f)
        val eye = Offset(size.width / 2, size.height / 2)
        val stroke = (if (b.shape == "entity") 5 else 4).dp.toPx()
        val full = size.maxDimension * 1.5f
        val small = 10.dp.toPx()
        // toward the opponent when it is the profile's; out at the screen when it is the opponent's
        val k = if (b.side == 0) p else 1f - p
        val s = small + (full - small) * (1f - k).pow(2f)
        val c = Offset(eye.x + (foe.x - eye.x) * k, eye.y + (foe.y - eye.y) * k)
        val color = b.color.copy(alpha = if (b.side == 0) 0.4f + 0.6f * p else 1f - p * 0.7f)
        val fill = color.copy(alpha = color.alpha * 0.18f)
        when (b.shape) {
            "attack" -> {
                drawRect(fill, Offset(c.x - s / 2, c.y - s / 2), Size(s, s))
                drawRect(color, Offset(c.x - s / 2, c.y - s / 2), Size(s, s), style = Stroke(stroke))
            }
            "trick" -> rotate(p * 90f, c) { diamond(c, s, color, stroke) }
            "entity" -> { triangle(c, s * 1.04f, fill, stroke * 3); triangle(c, s, color, stroke) }
            // a heal stays where it lands: it opens at the profile's feet, or closes on the opponent
            "heal" -> if (b.side == 0) drawCircle(b.color.copy(alpha = 1f - p), small + size.minDimension * 0.6f * p,
                Offset(size.width / 2, size.height), style = Stroke(stroke))
            else drawCircle(b.color.copy(alpha = 1f - p * 0.5f), small + size.minDimension * 0.4f * (1f - p), foe, style = Stroke(stroke))
        }
        // the blow lands: a flash
        if (b.shape != "heal" && b.shape != "level") {
            val flash = if (b.side == 1) (1f - p) * 0.22f else (if (p > 0.85f) (1f - p) / 0.15f * 0.18f else 0f)
            if (flash > 0f) drawRect(b.color.copy(alpha = flash))
        }
        if (b.shape == "level") drawCircle(Ink.gold.copy(alpha = 1f - p), size.minDimension * (0.1f + 0.5f * p), Offset(size.width / 2, size.height), style = Stroke(stroke))
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
 *  roll down toward the hp left, never jumping. What a trick or an entity
 *  did to the profile shows on the card: grey when it cannot act, a second
 *  border with a shield, gold while strengthened. */
@Composable
private fun HpCard(name: String, hp: Long, ink: Color, you: com.evove.app.fight.SideView?, level: Int) {
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
    val edge = if (you?.boosted == true) Ink.gold else ink
    Column(
        Modifier.then(if (you?.shielded == true) Modifier.border(1.5.dp, ink).padding(3.dp) else Modifier)
            .border(1.5.dp, edge).background(Color.Black).padding(horizontal = 0.9.remDp, vertical = 0.55.remDp).testTag("hp"),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(0.25.remDp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.5.remDp)) {
            BasicText(caps(name), style = TextStyle(fontFamily = Display, fontSize = 0.74.rem, letterSpacing = 0.12.em, color = if (ink == Ink.mute) Ink.mute else Color.White), maxLines = 1)
            BasicText("NV $level", style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, color = Ink.gold))
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.4.remDp)) {
            BasicText("HP", style = TextStyle(fontFamily = Mono, fontSize = 0.7.rem, color = ink))
            Odometer(shownHp, digits = maxOf(3, target.toLong().toString().length), color = if (target <= 0f) Ink.danger else if (ink == Ink.mute) Ink.mute else Color.White)
        }
        val marks = listOfNotNull(
            if (you?.stunned == true) "atordoado" else null, if (you?.shielded == true) "escudo" else null,
            if (you?.boosted == true) "forte" else null, if (you?.hasted == true) "veloz" else null, if (you?.denying == true) "nega" else null,
        )
        if (marks.isNotEmpty()) BasicText(caps(marks.joinToString(" · ")), style = TextStyle(fontFamily = Mono, fontSize = 0.5.rem, color = edge), maxLines = 1)
    }
}

/** Digits that roll like an odometer's: each one moves on as the one to its
 *  right passes from 9 to 0. */
@Composable
private fun Odometer(value: Float, digits: Int, color: Color) {
    val style = TextStyle(fontFamily = Mono, fontSize = 1.5.rem, lineHeight = 1.8.rem, fontWeight = FontWeight.SemiBold, color = color)
    val h = 1.8.remDp
    Row(Modifier.clipToBounds()) {
        for (place in digits - 1 downTo 0) {
            val unit = 10f.pow(place)
            val d = (value / unit) % 10f
            // the digit turns only while the places to its right roll over
            val lower = value % unit
            val turn = if (place == 0) d - floor(d) else ((lower - (unit - 1f)).coerceIn(0f, 1f))
            val digit = floor(d).toInt() % 10
            Box(Modifier.width(1.0.remDp).height(h).clipToBounds()) {
                val off = with(LocalDensity.current) { (h.toPx() * turn).toInt() }
                BasicText("$digit", Modifier.offset { IntOffset(0, -off) }, style = style)
                BasicText("${(digit + 1) % 10}", Modifier.offset { IntOffset(0, h.roundToPx() - off) }, style = style)
            }
        }
    }
}

/** Two by two: the two attacks, the heal and the trick, each a ring that
 *  closes as it recharges; the trick's carries the name of the one on offer. */
@Composable
private fun Skills(you: com.evove.app.fight.SideView?, ink: Color) {
    val grey = ink == Ink.mute
    val slots = you?.moves.orEmpty().take(2).map { Triple(it.first.substringBefore(" ("), it.second, ink) } +
        listOfNotNull(you?.heal?.let { Triple(it.first.substringBefore(" ("), it.second, if (grey) ink else Ink.act) }) +
        listOfNotNull(you?.let { Triple(TRICK_NAME[it.trick ?: ""] ?: (it.trick ?: "truque"), it.charge, if (grey) ink else if (it.ready) Color.White else Ink.gold) })
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        for (row in slots.chunked(2)) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((name, p, c) in row) Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Canvas(Modifier.size(2.0.remDp)) {
                        val s = 2.5.dp.toPx()
                        drawCircle(c.copy(alpha = 0.25f), size.minDimension / 2 - s, style = Stroke(s))
                        drawArc(c, -90f, 360f * p.coerceIn(0f, 1f), false, Offset(s, s), Size(size.width - 2 * s, size.height - 2 * s),
                            style = Stroke(s, cap = StrokeCap.Round))
                    }
                    // fúria: everything recharges twice as fast
                    if (you?.hasted == true && !grey) BasicText("x2", style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, fontWeight = FontWeight.Bold, color = Ink.gold))
                }
                BasicText(caps(name.take(7)), style = TextStyle(fontFamily = Mono, fontSize = 0.5.rem, color = c), maxLines = 1)
            }
        }
    }
}

/** How likely each entity at the profile's side is to step in within the next
 *  second: it grows the longer the fight lasts. */
@Composable
private fun Chances(you: com.evove.app.fight.SideView?) {
    val allies = you?.allies.orEmpty()
    if (allies.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        for (a in allies) Column(horizontalAlignment = Alignment.CenterHorizontally) {
            val c = voiceInk(a.id)
            BasicText(caps(a.name), style = TextStyle(fontFamily = Mono, fontSize = 0.5.rem, color = c), maxLines = 1)
            BasicText("${(a.chance * 100).toInt()}%", style = TextStyle(fontFamily = Mono, fontSize = 0.9.rem, fontWeight = FontWeight.SemiBold, color = c))
        }
    }
}
