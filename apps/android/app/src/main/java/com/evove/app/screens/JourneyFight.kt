package com.evove.app.screens

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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.setValue
import androidx.compose.runtime.getValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.snapshotFlow
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
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.Evove
import com.evove.app.api.FightEnd
import com.evove.app.api.FightSetup
import com.evove.app.fight.Fight
import com.evove.app.fight.FightEvent
import com.evove.app.fight.SideView
import com.evove.app.sound.Music
import com.evove.app.sound.Sfx
import com.evove.app.ui.Display
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Mono
import com.evove.app.ui.Static
import com.evove.app.ui.caps
import com.evove.app.ui.hex
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import com.evove.app.ui.voiceInk
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.pow

// The journey's fight, drawn as an old console's: one message at a time in a
// box on top, the opponent as a frame of static in the middle, the hp at the
// bottom as a counter that rolls, and the four attacks recharging beside it.
//
// It does not run in real time: the rules (com.evove.app.fight.Fight) run
// tick by tick underneath, but the screen jumps — the recharges run fast up to
// the next thing that happens, the floor taking a step toward the eye — and
// then stops on it: its message, read at leisure, and its shape — a blow
// shrinks toward the opponent, the opponent's wash over the screen. The hp is
// the only thing that does not jump: it counts at its own pace, and the next
// jump waits until it is done. It plays itself, tricks included.

/** How many ticks a frame of the jump runs. */
private const val JUMP_TICKS = 4

/** How long a message stays: a moment, and a little for each letter. */
private fun readMs(text: String) = (1500L + 26L * text.length).coerceAtMost(3200L)

private val TRICK_NAME = mapOf("atordoar" to "atordoar", "furia" to "fúria", "baque" to "baque", "rasteira" to "rasteira", "escudo" to "escudo", "eco" to "eco")
private val ABILITY_NAME = mapOf("decreto" to "decreto", "pergunta" to "pergunta", "ficar" to "ficar", "pressa" to "pressa", "troca" to "troca",
    "amarra" to "amarra", "chama" to "chama", "interferencia" to "interferência")

/** A message of the fight, the shape that goes with it, which side it came
 *  from, and — for an entity — who, for the camera to turn to; `second` says
 *  what it did, when that is not plain damage; `crit` how many times a
 *  critical multiplied the blow. */
private data class Beat(val n: Int, val text: String, val shape: String, val side: Int, val color: Color, val entity: String? = null,
                        val second: String? = null, val crit: Int = 0)

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

private fun entityOf(setup: FightSetup, name: String) = setup.you.entities.find { it.name == name }?.id

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

/** The fight, from its setup to its end: it plays itself, jump by jump, and
 *  says when it is over — `onOver` — for the server to replay it; `ended` is
 *  what the server decided. Leaving it halfway is `onHome(true)`. */
@Composable
internal fun FightScreen(setup: FightSetup, look: Look, ended: FightEnd?, onOver: () -> Unit, onBack: () -> Unit, onHome: (leaving: Boolean) -> Unit) {
    val ink = Ink.journey
    val fight = remember(setup) { Fight(setup) }
    var shown by remember(setup) { mutableStateOf(fight.view()) }
    var beat by remember(setup) { mutableStateOf<Beat?>(null) }
    var pops by remember(setup) { mutableStateOf<List<Pop>>(emptyList()) }
    var over by remember(setup) { mutableStateOf(false) }
    // the hp as the counter shows it, rolling toward the hp at its own pace
    var counted by remember(setup) { mutableFloatStateOf(setup.you.hp.toFloat()) }
    val goal by rememberUpdatedState(maxOf(0L, shown.sides[0].hp).toFloat())
    // the floor's steps toward the eye, one a jump
    val walked = remember(setup) { Animatable(0f) }
    val onOverNow by rememberUpdatedState(onOver)

    // the fight's own music while it lasts, the menus' after
    DisposableEffect(Unit) {
        Music.battle()
        Evove.fighting = true
        onDispose {
            Music.menus()
            Evove.fighting = false
        }
    }
    LaunchedEffect(setup) {
        var last = withFrameMillis { it }
        while (true) {
            val t = withFrameMillis { it }
            val dt = (t - last) / 1000f
            last = t
            val g = goal
            // a few points a second, faster the farther it has to go
            val speed = maxOf(18f, abs(g - counted) * 1.6f)
            counted = if (counted > g) maxOf(g, counted - speed * dt) else minOf(g, counted + speed * dt)
        }
    }
    LaunchedEffect(setup) {
        val started = System.currentTimeMillis()
        var n = 0
        var p = 0
        delay(1400)
        while (!fight.over) {
            // the recharges wait for the hp to be counted
            snapshotFlow { counted == goal }.first { it }
            // the jump: the time runs fast to the next thing that happens, and the floor takes a step
            val before = fight.events.size
            launch { walked.animateTo(floor(walked.value) + 1f, tween(420, easing = LinearEasing)) }
            while (!fight.over && fight.events.size == before) {
                repeat(JUMP_TICKS) { if (!fight.over && fight.events.size == before) fight.step() }
                shown = fight.view()
                withFrameMillis { }
            }
            shown = fight.view()
            val you = shown.sides[0]
            Music.mix((System.currentTimeMillis() - started) / 1000f, you.hp * 100 < you.maxHp * 35, you.hasted, you.allies.maxOfOrNull { it.chance } ?: 0f)
            var crit = 0
            for (e in fight.events.drop(before)) {
                if (e.kind == "crit") { crit = e.value.toInt(); continue }
                // what reaches the opponent rises from it as a number
                val onFoe = e.side == 0 && e.kind in setOf("attack", "interfere", "skill", "burn") && (e.kind != "skill" || e.name.endsWith("|atacar"))
                val foeHeal = e.side == 1 && e.kind == "heal"
                if (onFoe || foeHeal) {
                    val c = e.kind == "attack" && crit > 0
                    pops = pops.filter { System.currentTimeMillis() - it.born < 1600 } +
                        Pop(++p, if (foeHeal) "+${e.value}" else "−${e.value}" + if (c) " ×$crit" else "",
                            if (foeHeal) Ink.act else if (c) Ink.gold else Color.White, System.currentTimeMillis(), ((p * 37) % 60 - 30) / 100f)
                }
                val plain = beatOf(++n, e, setup) ?: continue
                val b = if (e.kind == "attack" && crit > 0) plain.copy(crit = crit, second = "crítico ×$crit · ${e.value} de dano") else plain
                if (e.kind == "attack") crit = 0
                beat = b
                when (b.shape) {
                    "attack" -> if (b.crit > 0) Sfx.boom() else Sfx.hit()
                    "heal" -> Sfx.heal()
                    "trick" -> Sfx.entity()
                    "entity" -> Sfx.boom()
                    "level" -> Sfx.levelUp()
                }
                delay(readMs(b.text))
                b.second?.let {
                    beat = b.copy(n = ++n, text = it, shape = "none")
                    delay(readMs(it))
                }
            }
        }
        snapshotFlow { counted == goal }.first { it }
        beat = null
        over = true
        onOverNow()
    }

    val you = shown.sides[0]
    val foe = shown.sides[1]
    val frozen = shown.frozen
    // blows that come at the screen shake it, a critical twice as hard
    val shake = remember { Animatable(0f) }
    LaunchedEffect(beat?.n) {
        val b = beat ?: return@LaunchedEffect
        if (b.shape == "attack" || b.shape == "entity") {
            shake.snapTo(if (b.crit > 0) 2f else 1f)
            shake.animateTo(0f, tween(if (b.shape == "entity" || b.crit > 0) 650 else 450, easing = LinearEasing))
        }
    }
    CompositionLocalProvider(LocalInk provides ink) {
        Box(Modifier.fillMaxSize().padding(10.dp)) {
            val jitter = with(LocalDensity.current) { (shake.value * 7.dp.toPx() * if ((beat?.n ?: 0) % 2 == 0) 1 else -1).toInt() }
            Column(Modifier.fillMaxSize().offset { IntOffset(jitter, -jitter / 2) }, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                MessageBox(
                    when {
                        over && ended != null -> endText(ended)
                        over -> "…"
                        beat != null -> beat!!.text
                        else -> "${setup.foe.name} está na sua frente"
                    },
                )
                Box(Modifier.fillMaxWidth().weight(1f).clipToBounds()) {
                    val camera = beat?.takeIf { it.shape == "entity" }
                    if (camera != null) EntityCamera(camera, Modifier.fillMaxSize())
                    else Stage(setup, foe, frozen, over && ended?.won == true, look, walked.value, Modifier.fillMaxSize())
                    Shapes(beat, Modifier.fillMaxSize())
                    Pops(pops, Modifier.fillMaxSize())
                    LevelBadge(beat?.takeIf { it.shape == "level" && it.side == 1 }, Modifier.align(Alignment.TopCenter).padding(top = 30.dp))
                }
                if (over && ended != null) EndSummary(ended)
                Box(Modifier.fillMaxWidth()) {
                    LevelBadge(beat?.takeIf { it.shape == "level" && it.side == 0 }, Modifier.align(Alignment.TopCenter))
                }
                val grey = frozen || you.stunned
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterHorizontally), verticalAlignment = Alignment.CenterVertically) {
                    HpCard(setup.you.name, counted, goal, if (grey) Ink.mute else ink, you, you.level)
                    Skills(you, if (grey) Ink.mute else ink)
                    Chances(you)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    if (over && ended != null) Key({ Sfx.tap(0); onBack() }, Modifier.weight(1f).height(3.remDp)) { KeyIcon(Icon.LEFT) } else Box(Modifier.weight(1f))
                    Box(Modifier.weight(3f))
                    Key({ Sfx.tap(0); onHome(!over) }, Modifier.weight(1f).height(3.remDp)) { KeyIcon(Icon.CIRCLE, 16.dp) }
                }
            }
        }
    }
}

/** One message at a time, in a box. */
@Composable
private fun MessageBox(text: String) {
    val ink = LocalInk.current
    Box(Modifier.fillMaxWidth().heightIn(min = 4.2.remDp).border(1.5.dp, ink).background(Color.Black).padding(horizontal = 0.9.remDp, vertical = 0.8.remDp)
        .testTag("message"), contentAlignment = Alignment.CenterStart) {
        BasicText("• ${caps(text)}", style = TextStyle(fontFamily = Display, fontSize = 0.92.rem, fontWeight = FontWeight.Medium, lineHeight = 1.4.em,
            letterSpacing = 0.05.em, color = Color.White), maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

/** Where the opponent stands: the floor's own floor, filled, in perspective to
 *  a horizon — its rows a step nearer at every jump — and the opponent as one
 *  frame of static over its shadow, its name above. Grey while it cannot act. */
@Composable
private fun Stage(setup: FightSetup, foe: SideView, frozen: Boolean, beaten: Boolean, look: Look, walked: Float, modifier: Modifier) {
    val grey = frozen || foe.stunned
    BoxWithConstraints(modifier) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val horizon = h * 0.4f
        val feet = h * 0.74f
        Canvas(Modifier.fillMaxSize()) {
            val stroke = 1.dp.toPx()
            // the floor, lighter as it nears
            val rows = 8
            for (r in 0 until rows) {
                val y0 = horizon + (h - horizon) * (r / rows.toFloat()).pow(1.7f)
                val y1 = horizon + (h - horizon) * ((r + 1) / rows.toFloat()).pow(1.7f)
                drawRect(lerp(Color.Black, look.floor, 0.35f + 0.65f * r / rows), Offset(0f, y0), Size(w, y1 - y0 + 1f))
            }
            val vx = w / 2
            val edge = lerp(look.floor, Color.Black, 0.5f)
            for (k in -7..7) drawLine(edge, Offset(vx + k * w * 0.025f, horizon), Offset(vx + k * w * 0.3f, h), stroke)
            // the rows' lines, a step nearer at every jump
            val phase = walked - floor(walked)
            for (r in 0..rows) {
                val q = ((r + phase) / rows).coerceIn(0f, 1f)
                val y = horizon + (h - horizon) * q.pow(1.7f)
                drawLine(edge.copy(alpha = 0.4f + 0.6f * q), Offset(0f, y), Offset(w, y), stroke)
            }
            drawLine(look.frame.copy(alpha = 0.5f), Offset(0f, horizon), Offset(w, horizon), stroke)
            // the shadow at the opponent's feet
            val sw = w * 0.3f
            drawOval(Color.Black.copy(alpha = 0.8f), Offset(vx - sw / 2, feet - sw * 0.08f), Size(sw, sw * 0.16f))
        }
        val density = LocalDensity.current
        val fw = with(density) { minOf(w * 0.26f, (feet - horizon) * 1.2f).toDp() }
        val fh = fw * 1.45f
        val top = with(density) { feet.toDp() } - fh
        val left = with(density) { (w / 2).toDp() } - fw / 2
        BasicText(caps(setup.foe.name), Modifier.fillMaxWidth().padding(top = 4.dp),
            style = TextStyle(fontFamily = Display, fontSize = 0.72.rem, letterSpacing = 0.15.em, color = if (grey) Ink.mute else Ink.enemy,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center))
        if (!beaten) {
            Static(Modifier.offset(left, top).size(fw, fh).border(1.5.dp, if (grey) Ink.mute else if (foe.burning) Ink.late else Ink.enemy).testTag("foe"),
                opacity = if (grey) 0.3f else 0.6f)
            if (foe.shielded) Canvas(Modifier.offset(left - fw * 0.2f, top - fh * 0.08f).size(fw * 1.4f, fh * 1.16f)) {
                drawOval(Ink.journey.copy(alpha = 0.75f), Offset.Zero, size, style = Stroke(2.5.dp.toPx()))
            }
        }
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
        UnstableFrames(b.color, Modifier.size(side))
        BasicText(caps(b.entity ?: ""), Modifier.align(Alignment.BottomCenter).padding(bottom = 6.dp),
            style = TextStyle(fontFamily = Display, fontSize = 1.rem, letterSpacing = 0.25.em, color = b.color))
    }
}

/** Frames of static that will not hold still: a few of them, overlapping,
 *  thrown a little each moment, tinted `tint`. */
@Composable
private fun UnstableFrames(tint: Color, modifier: Modifier, count: Int = 9) {
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
            drawRect(tint.copy(alpha = 0.75f), Offset(x, y), Size(fw, fh), style = Stroke(1.2.dp.toPx()))
        }
    }
}

/** The numbers that rise from the opponent — damage in white, a critical's in
 *  gold, what it healed in green — and fade. */
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
    else -> "derrota · a jornada recomeça"
}

/** What the fight gave, at its end: the levels and what they brought, the item. */
@Composable
private fun EndSummary(r: FightEnd) {
    val l = r.levels
    val lines = buildList {
        if (!r.won) add("de volta ao primeiro andar, ao primeiro nível, sem itens")
        else if (l.left) add("você saiu: os níveis desta luta se perderam")
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
 *  they fill the screen. A critical's is doubled. */
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
        val stroke = (if (b.shape == "entity" || b.crit > 0) 5 else 4).dp.toPx()
        val full = size.maxDimension * 1.5f
        val small = 10.dp.toPx()
        // toward the opponent when it is the profile's; out at the screen when it is the opponent's
        val k = if (b.side == 0) p else 1f - p
        val s = small + (full - small) * (1f - k).pow(2f)
        val c = Offset(eye.x + (foe.x - eye.x) * k, eye.y + (foe.y - eye.y) * k)
        val tint = if (b.crit > 0) Ink.gold else b.color
        val color = tint.copy(alpha = if (b.side == 0) 0.4f + 0.6f * p else 1f - p * 0.7f)
        val fill = color.copy(alpha = color.alpha * 0.18f)
        when (b.shape) {
            "attack" -> {
                drawRect(fill, Offset(c.x - s / 2, c.y - s / 2), Size(s, s))
                drawRect(color, Offset(c.x - s / 2, c.y - s / 2), Size(s, s), style = Stroke(stroke))
                if (b.crit > 0) drawRect(color, Offset(c.x - s * 0.36f, c.y - s * 0.36f), Size(s * 0.72f, s * 0.72f), style = Stroke(stroke))
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
            val flash = (if (b.side == 1) (1f - p) * 0.22f else (if (p > 0.85f) (1f - p) / 0.15f * 0.18f else 0f)) * if (b.crit > 0) 1.8f else 1f
            if (flash > 0f) drawRect(tint.copy(alpha = flash.coerceAtMost(0.5f)))
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
 *  roll toward the hp left, never jumping — `counted` is where it is, `hp`
 *  where it goes. What a trick or an entity did to the profile shows on the
 *  card: grey when it cannot act, a second border with a shield, gold while
 *  strengthened. */
@Composable
private fun HpCard(name: String, counted: Float, hp: Float, ink: Color, you: SideView, level: Int) {
    val edge = if (you.boosted) Ink.gold else ink
    Column(
        Modifier.then(if (you.shielded) Modifier.border(1.5.dp, ink).padding(3.dp) else Modifier)
            .border(1.5.dp, edge).background(Color.Black).padding(horizontal = 0.9.remDp, vertical = 0.55.remDp).testTag("hp"),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(0.25.remDp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.5.remDp)) {
            BasicText(caps(name), style = TextStyle(fontFamily = Display, fontSize = 0.74.rem, letterSpacing = 0.12.em, color = if (ink == Ink.mute) Ink.mute else Color.White), maxLines = 1)
            BasicText("NV $level", style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, color = Ink.gold))
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(0.4.remDp)) {
            BasicText("HP", style = TextStyle(fontFamily = Mono, fontSize = 0.7.rem, color = ink))
            Odometer(counted, digits = maxOf(3, hp.toLong().toString().length), color = if (hp <= 0f) Ink.danger else if (ink == Ink.mute) Ink.mute else Color.White)
        }
        val marks = listOfNotNull(
            if (you.stunned) "atordoado" else null, if (you.shielded) "escudo" else null,
            if (you.boosted) "forte" else null, if (you.hasted) "veloz" else null, if (you.denying) "nega" else null,
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
private fun Skills(you: SideView, ink: Color) {
    val grey = ink == Ink.mute
    val slots = you.moves.take(2).map { Triple(it.first.substringBefore(" ("), it.second, ink) } +
        listOf(Triple(you.heal.first.substringBefore(" ("), you.heal.second, if (grey) ink else Ink.act)) +
        listOf(Triple(TRICK_NAME[you.trick ?: ""] ?: (you.trick ?: "truque"), you.charge, if (grey) ink else if (you.ready) Color.White else Ink.gold))
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
                    if (you.hasted && !grey) BasicText("x2", style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, fontWeight = FontWeight.Bold, color = Ink.gold))
                }
                BasicText(caps(name.take(7)), style = TextStyle(fontFamily = Mono, fontSize = 0.5.rem, color = c), maxLines = 1)
            }
        }
    }
}

/** How likely each entity at the profile's side is to step in within the next
 *  second of the fight's time: it grows the longer the fight lasts. */
@Composable
private fun Chances(you: SideView) {
    if (you.allies.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        for (a in you.allies) Column(horizontalAlignment = Alignment.CenterHorizontally) {
            val c = voiceInk(a.id)
            BasicText(caps(a.name), style = TextStyle(fontFamily = Mono, fontSize = 0.5.rem, color = c), maxLines = 1)
            BasicText("${(a.chance * 100).toInt()}%", style = TextStyle(fontFamily = Mono, fontSize = 0.9.rem, fontWeight = FontWeight.SemiBold, color = c))
        }
    }
}
