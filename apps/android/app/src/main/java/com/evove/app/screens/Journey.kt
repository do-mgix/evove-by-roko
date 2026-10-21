package com.evove.app.screens

import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.Bus
import com.evove.app.api.Api
import com.evove.app.api.BossState
import com.evove.app.api.Equipment
import com.evove.app.api.EquipmentItem
import com.evove.app.api.FightResult
import com.evove.app.api.JourneyState
import com.evove.app.api.JourneyStats
import com.evove.app.api.Recovery
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Display
import com.evove.app.ui.Empty
import com.evove.app.ui.Grow
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
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// The journey: survive from one checkpoint to the next on an hp of 25, every
// act costing one. Tokens buy hp back. Between the points stand the bosses: the
// autobattler picks the lineup and the fight plays out in text, line by line.

private const val LINE_MS = 520L

private enum class Leg { MAIN, BOSS, FIGHT, STATS, EQUIP }

/** "2d 05h", "3h 07m", "4m 09s". */
fun clock(total: Long): String {
    val d = total / 86400
    val h = (total % 86400) / 3600
    val m = (total % 3600) / 60
    val s = total % 60
    fun p(n: Long) = n.toString().padStart(2, '0')
    return if (d > 0) "${d}d ${p(h)}h" else if (h > 0) "${h}h ${p(m)}m" else "${m}m ${p(s)}s"
}

@Composable
fun JourneyScreen(onHome: () -> Unit) {
    var mode by remember { mutableStateOf(Leg.MAIN) }
    var state by remember { mutableStateOf<JourneyState?>(null) }
    var boss by remember { mutableStateOf<BossState?>(null) }
    var stats by remember { mutableStateOf<JourneyStats?>(null) }
    var gear by remember { mutableStateOf<Equipment?>(null) }
    var fight by remember { mutableStateOf<FightResult?>(null) }
    var shown by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var loadedAt by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var player by remember { mutableStateOf<Job?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        try {
            val j = scope.async { Api.journey() }
            val b = scope.async { Api.boss() }
            state = j.await()
            boss = b.await()
            loadedAt = System.currentTimeMillis()
            now = loadedAt
        } catch (e: Exception) {
            message = listOf(e.message ?: "erro")
        }
    }

    val elapsed = (now - loadedAt) / 1000
    val st = state
    val secondsLeft = st?.let { maxOf(0, it.secondsLeft - elapsed) } ?: 0
    val toPoint = st?.let { maxOf(0, it.secondsToNextPoint - elapsed) } ?: 0
    val progress = st?.let { (1 - secondsLeft / (it.stageDays * 86400f)).coerceIn(0f, 1f) } ?: 0f

    fun press(n: Int = 0) = Sfx.tap(n)

    fun go(m: Leg) {
        press(if (m == Leg.MAIN) 0 else 4)
        mode = m
        message = emptyList()
        if (m == Leg.STATS) scope.launch { runCatching { Api.journeyStats() }.onSuccess { stats = it } }
        if (m == Leg.EQUIP) scope.launch { runCatching { Api.equipment() }.onSuccess { gear = it } }
        Sfx.powerOn()
    }

    fun finish() {
        player?.cancel()
        player = null
        val f = fight ?: return
        shown = f.log.size
        if (f.won) Sfx.gains()
        Bus.bumpUser()
        scope.launch { load() }
    }

    fun skip() {
        val f = fight ?: return
        if (shown < f.log.size) finish()
    }

    fun back(): Boolean {
        if (mode == Leg.FIGHT) {
            skip()
            val f = fight
            if (f != null && shown >= f.log.size) {
                mode = Leg.MAIN
                fight = null
            }
            return true
        }
        if (mode != Leg.MAIN) {
            mode = Leg.MAIN
            message = emptyList()
            return true
        }
        return false
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

    fun startFight() {
        if (busy) return
        busy = true
        press(9)
        scope.launch {
            try {
                val f = Api.fight()
                fight = f
                shown = 0
                mode = Leg.FIGHT
                message = emptyList()
                player = scope.launch {
                    while (shown < f.log.size) {
                        delay(LINE_MS)
                        shown += 1
                        press(if (f.log[shown - 1].who == "you") 3 else 1)
                    }
                    finish()
                }
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
                press(if (item.owned) 5 else 8)
                if (!item.owned) Sfx.gains()
                Bus.bumpUser()
                load()
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(Unit) {
        load()
        Sfx.powerOn()
    }
    Ticker(1000) {
        now = System.currentTimeMillis()
        if (state != null && toPoint == 0L && now - loadedAt > 5000) scope.launch { load() }
    }

    BackHandler(enabled = mode != Leg.MAIN) { back() }

    val f = fight
    val last = if (f != null && shown > 0) f.log[minOf(shown, f.log.size) - 1] else null
    val over = f != null && shown >= f.log.size

    DarkScreen(
        Ink.journey, display = 0.15f,
        displayContent = {
            val b = boss
            when {
                message.isNotEmpty() -> Message(message)
                mode == Leg.BOSS && b != null -> { Big("${b.boss.name} (${b.boss.rank})"); Small(b.boss.type) }
                mode == Leg.FIGHT && f != null -> {
                    Big(if (over) (if (f.won) "vitória" else "derrota") else f.boss.name)
                    Small(
                        if (!over) "toque para pular"
                        else if (f.won) "+${f.points} pontos"
                        else "−${f.taken} hp" + if (f.journeyReset) " · a jornada recomeçou" else "",
                    )
                }
                mode == Leg.STATS -> { Big("stats"); Small("da jornada") }
                mode == Leg.EQUIP -> { Big("equipamento"); Small(gear?.let { "${it.points} pontos" } ?: "…") }
                st != null -> { Big("estágio ${st.stage}"); Small("checkpoint em ${clock(secondsLeft)}" + if (st.resets > 0) " · ${st.resets} reinícios" else "") }
                else -> Small("…")
            }
        },
        bar = {
            if (mode == Leg.MAIN) {
                Key({ go(Leg.BOSS) }, Modifier.at(1)) { KeyIcon(Icon.BOLT) }
                Key({ go(Leg.EQUIP) }, Modifier.at(2)) { KeyIcon(Icon.SHIELD) }
                Key({ go(Leg.STATS) }, Modifier.at(3)) { KeyIcon(Icon.BARS) }
            } else {
                Key({ press(0); back() }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
            }
            HomeKey { press(0); onHome() }
        },
    ) {
        val ink = LocalInk.current
        when {
            mode == Leg.MAIN && st != null -> {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Label("hp ${st.energy}/${st.maxEnergy}")
                    val low = st.energy <= st.maxEnergy * 0.3
                    Row(Modifier.fillMaxWidth().height(18.dp), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                        repeat(maxOf(1, st.maxEnergy)) { i ->
                            val on = i < st.energy
                            val c = if (on && low) Ink.danger else ink
                            Box(Modifier.weight(1f).fillMaxHeight().alpha(if (on) 1f else 0.35f).border(1.dp, c).background(if (on) c else Color.Transparent))
                        }
                    }
                }
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Label("estágio · ${st.points.count { it.reached }}/${st.points.size} pontos · próximo em ${clock(toPoint)}")
                    BoxWithConstraints(Modifier.fillMaxWidth().padding(vertical = 4.dp).height(10.dp)) {
                        val w = maxWidth
                        Box(Modifier.fillMaxSize().border(1.5.dp, ink))
                        Box(Modifier.width(w * progress).fillMaxHeight().background(ink.copy(alpha = 0.45f)))
                        for (p in st.points) {
                            Box(
                                Modifier.offset(x = w * (p.day / st.stageDays.toFloat()) - 1.dp, y = (-4).dp).width(2.dp).height(14.dp)
                                    .background(Color.White.copy(alpha = if (p.reached) 1f else 0.4f)),
                            )
                        }
                    }
                }
                Label("recuperar · ${st.tokens} tokens")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val labels = mapOf("small" to "pequena", "large" to "grande")
                    for (r in st.recover) {
                        Key({ heal(r) }, Modifier.weight(1f).heightIn(min = 4.remDp), enabled = !busy && r.ready) {
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
                boss?.let { b ->
                    Label("chefe do trecho")
                    ListRow({ go(Leg.BOSS) }, Modifier.alpha(if (b.beaten) 0.55f else 1f)) {
                        IconView(if (b.beaten) Icon.CHECK else Icon.BOLT, Color.White, 16.dp)
                        Grow(caps("${b.boss.name} (${b.boss.rank}) · ${b.boss.type}"))
                        Tag(if (b.beaten) "vencido" else "${b.boss.hp} hp")
                    }
                }
            }
            mode == Leg.BOSS && boss != null -> BossView(boss!!, busy, ::startFight)
            mode == Leg.FIGHT && f != null -> {
                val bossHp = last?.bossHp ?: f.boss.hp
                val myHp = last?.hp ?: (st?.energy ?: 0)
                val font = TextStyle(fontFamily = Display)
                Column(
                    Modifier.weight(1f).fillMaxWidth().border(1.5.dp, ink)
                        .clickable(remember { MutableInteractionSource() }, null) { skip() }
                        .padding(0.8.remDp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Row {
                        BasicText("VOCÊ $myHp", Modifier.weight(1f), style = font.copy(fontSize = 0.72.rem, letterSpacing = 0.08.em, color = ink))
                        BasicText(caps("${f.boss.name} $bossHp/${f.boss.hp}"), style = font.copy(fontSize = 0.72.rem, letterSpacing = 0.08.em, color = ink))
                    }
                    BoxWithConstraints(Modifier.fillMaxWidth().height(6.dp).border(1.dp, ink)) {
                        Box(Modifier.width(maxWidth * (bossHp / maxOf(1, f.boss.hp).toFloat()).coerceIn(0f, 1f)).fillMaxHeight().background(ink))
                    }
                    Column(Modifier.weight(1f).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(0.55.remDp, Alignment.Bottom)) {
                        val upTo = minOf(shown, f.log.size)
                        for (k in maxOf(0, upTo - 7) until upTo) {
                            val l = f.log[k]
                            androidx.compose.runtime.key(k) {
                                Arrive(300) {
                                    BasicText(
                                        buildAnnotatedString {
                                            append(l.text)
                                            withStyle(SpanStyle(color = ink)) { append(if (l.who == "you") " −${l.damage}" else " −${l.damage} hp") }
                                        },
                                        style = font.copy(fontSize = 0.8.rem, letterSpacing = 0.06.em, color = if (l.who == "you") Color.White else Ink.enemy),
                                    )
                                }
                            }
                        }
                        if (over) BasicText(
                            caps(if (f.won) "${f.boss.name} caiu." else "você recuou."),
                            style = font.copy(fontSize = 1.rem, fontWeight = FontWeight.SemiBold, color = ink),
                        )
                    }
                }
            }
            mode == Leg.STATS -> {
                val s = stats
                if (s == null) Empty("…")
                else Stats(listOf(
                    "lutas" to "${s.fights}", "vitórias" to "${s.wins}", "derrotas" to "${s.losses}",
                    "chefes vencidos" to "${s.bosses}", "dano causado" to "${s.dealt}", "dano recebido" to "${s.taken}",
                    "maior golpe" to "${s.bestHit}", "pontos ganhos" to "${s.pointsWon}", "maior estágio" to "${s.highestStage}",
                    "reinícios" to "${s.resets}", "recuperações" to "${s.recoverUses}",
                ))
            }
            mode == Leg.EQUIP -> {
                val g = gear
                if (g == null) Empty("…")
                else for (slot in g.slots) {
                    Label(slot)
                    for (item in g.items.filter { it.slot == slot }) {
                        val icon = when (slot) { "arma" -> Icon.SWORD; "armadura" -> Icon.SHIELD; else -> Icon.AMULET }
                        ListRow(
                            { useItem(item) },
                            enabled = !busy && (item.owned || g.points >= item.price),
                            background = if (item.worn) ink.copy(alpha = 0.22f) else null,
                        ) {
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
            }
        }
    }
}

@Composable
private fun ColumnScope.BossView(state: BossState, busy: Boolean, onFight: () -> Unit) {
    val ink = LocalInk.current
    val b = state.boss
    val line = Type.row
    Stats(listOf("hp" to "${b.hp}", "mp" to "${b.mp}", "ataque" to "${b.attack}", "especial" to "${b.special}", "defesa" to "${b.defense}%"))
    Label("habilidades")
    for (a in b.abilities) {
        BasicText(buildAnnotatedString {
            append(caps(a.name))
            withStyle(SpanStyle(color = ink)) { append(" · ${a.power}") }
        }, style = line, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
    Label("escalação · fraco contra ${b.types.joinToString(", ") { it.name.lowercase() }}")
    if (state.lineup.isEmpty()) Empty("nenhuma ação para lutar — adquira no shop")
    for (m in state.lineup) {
        BasicText(buildAnnotatedString {
            append(caps(m.name))
            if (m.multiplier > 1) withStyle(SpanStyle(color = ink)) { append(" ×${trim(m.multiplier)} ${caps(m.kinship)}") }
            withStyle(SpanStyle(color = ink)) { append("  → ${m.damage}") }
        }, style = line, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
    Key(onFight, Modifier.fillMaxWidth().heightIn(min = 3.remDp), enabled = !busy && !state.beaten && state.lineup.isNotEmpty() && state.hp > 0) {
        KeyIcon(Icon.BOLT)
        KeyText(if (state.beaten) "vencido" else "lutar · +${state.reward}", Type.key.copy(fontSize = 0.9.rem, fontFamily = Mono))
    }
}

/** 1.5 as "1.5", 2.0 as "2". */
fun trim(d: Double): String = if (d == Math.floor(d)) d.toLong().toString() else d.toString()
