package com.evove.app.screens

import android.graphics.Bitmap
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.min
import com.evove.app.Bus
import com.evove.app.Evove
import com.evove.app.ui.Selector
import com.evove.app.api.Api
import com.evove.app.api.ShopAction
import com.evove.app.api.ShopGroup
import com.evove.app.api.ShopState
import com.evove.app.api.formatCode
import com.evove.app.sound.Sfx
import com.evove.app.ui.Bar
import com.evove.app.ui.Big
import com.evove.app.ui.Cells
import com.evove.app.ui.DrawnCell
import com.evove.app.ui.GRID_COLS
import com.evove.app.ui.GRID_GAP_DP
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.KeyText
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Message
import com.evove.app.ui.Mono
import com.evove.app.ui.SLANT
import com.evove.app.ui.Small
import com.evove.app.ui.Static
import com.evove.app.ui.caps
import com.evove.app.ui.dashed
import com.evove.app.ui.drawBoxes
import com.evove.app.ui.formsFor
import com.evove.app.ui.packFree
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import com.evove.app.ui.seeded
import com.evove.app.ui.unitFor
import com.evove.app.ui.wrapWords
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToInt

// The shop is walked like the acting screen: a display on top, cells in the
// middle, a bar with two buttons at the bottom. It opens on its first screen,
// where the catalog is discovered, and the centre button turns the page through
// what was discovered, one attribute after the other; with an action chosen it
// goes back a step instead. That button is the selector (ui/Selector.kt), whose
// level the engine keeps: an arrow, then a grooved wheel, then a strip.
//
// Only what was discovered is sold. Discovering changes with use: frames of
// static to tap open, one by one; then a single button for the day's; then
// nothing to do, they open on arrival.

private const val SCALE = 3
private const val SMALL = 2
private const val PER_PAGE = 6
private val DELAY = intArrayOf(0, 110, 60, 170, 30, 220, 140, 90, 200, 50)

val TYPE_LABEL = mapOf(
    0 to "sessão", 1 to "reps", 2 to "segundos", 3 to "minutos", 4 to "horas",
    5 to "letras", 6 to "linhas", 7 to "palavras", 8 to "grupo",
)

/** Where the pages stand: null is the first screen, then a page of a group each. */
private data class Stop(val group: Int, val page: Int, val pages: Int)

/** A cell's size by what it costs: two side by side for the dear ones, one, or
 *  two thirds of one for the free. */
private fun sizeOf(a: ShopAction) = if (a.cost >= 300) 2 * SCALE to SCALE else if (a.cost > 0) SCALE to SCALE else SMALL to SMALL

@Composable
fun ShopScreen(onHome: () -> Unit) {
    val ink = Ink.shop
    var groups by remember { mutableStateOf<List<ShopGroup>>(emptyList()) }
    var points by remember { mutableIntStateOf(0) }
    var owned by remember { mutableStateOf<Set<String>>(emptySet()) }
    var found by remember { mutableStateOf<ShopState?>(null) }
    var opened by remember { mutableStateOf<List<String>>(emptyList()) }
    var discovering by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var stop by remember { mutableIntStateOf(0) }
    var selected by remember { mutableStateOf<ShopAction?>(null) }
    var confirming by remember { mutableStateOf(false) }
    var buying by remember { mutableStateOf(false) }
    var forge by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun apply(s: ShopState) {
        groups = s.groups
        points = s.points
        owned = s.groups.flatMap { g -> g.actions.filter { it.owned }.map { it.name.uppercase() } }.toSet()
        found = s
        if (s.new.isNotEmpty()) message = listOf(
            if (s.new.size == 1) "descoberta" else "${s.new.size} descobertas",
            s.new.joinToString(" · ").lowercase(),
        )
    }
    suspend fun load() {
        try { apply(Api.shop()) } catch (e: Exception) { message = listOf(e.message ?: "erro ao carregar") } finally { loading = false }
    }

    var first by remember { mutableStateOf(true) }
    LaunchedEffect(Bus.user) {
        if (!first && forge == null) load()
        if (first) { load(); if (groups.isNotEmpty()) Sfx.powerOn() }
        first = false
    }

    // groups by name; what is owned leaves the shop, and a group with nothing
    // left leaves the walk
    val sorted = groups.sortedWith { a, b -> pt.compare(a.name, b.name) }
        .map { g -> g.copy(actions = g.actions.filter { it.name.uppercase() !in owned }) }
        .filter { it.actions.isNotEmpty() }
    val stops: List<Stop?> = listOf<Stop?>(null) + sorted.flatMapIndexed { gi, g ->
        val pages = maxOf(1, ceil(g.actions.size / PER_PAGE.toFloat()).toInt())
        (0 until pages).map { Stop(gi, it, pages) }
    }
    if (stop >= stops.size) stop = stops.size - 1
    val here = stops.getOrNull(stop)
    val group = here?.let { sorted[it.group] }
    val onPage = if (group != null) group.actions.drop(here.page * PER_PAGE).take(PER_PAGE) else emptyList()

    /** One step back: from the question to the stats, from the stats to the
     *  cells, from the cells to the first screen. False when there is none. */
    fun back(): Boolean {
        when {
            confirming -> confirming = false
            selected != null -> selected = null
            stop > 0 -> { stop = 0; message = emptyList() }
            else -> return false
        }
        return true
    }

    fun goTo(next: Int) {
        val n = next.coerceIn(0, stops.size - 1)
        if (n == stop) return
        Evove.turn()
        stop = n
        selected = null
        confirming = false
        message = emptyList()
        Sfx.tap(stop)
    }

    fun open() {
        val f = found ?: return
        if (discovering || f.left <= 0) return
        Sfx.tap(9)
        discovering = true
        scope.launch {
            try {
                val s = Api.discover()
                opened = opened + s.new
                apply(s)
                Sfx.gains()
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro ao descobrir")
            } finally {
                discovering = false
            }
        }
    }

    fun press() {
        val a = selected ?: return
        val g = group ?: return
        if (buying) return
        if (!confirming) { Sfx.tap(5); confirming = true; return }
        if (points < a.cost) { Sfx.tap(0); confirming = false; return }
        val at = here
        buying = true
        scope.launch {
            try {
                val res = Api.buy(a.packageAttribute, a.name)
                points = res.buildPoints
                owned = owned + a.name.uppercase()
                // the stops shift: stay on the group's page, or the one now in its place
                val after = sorted.map { s -> s.copy(actions = s.actions.filter { it.name.uppercase() !in owned }) }.filter { it.actions.isNotEmpty() }
                val gi = after.indexOfFirst { it.key == g.key }
                if (gi >= 0) {
                    var k = 1
                    for ((i, s) in after.withIndex()) {
                        val pages = maxOf(1, ceil(s.actions.size / PER_PAGE.toFloat()).toInt())
                        if (i == gi) { stop = k + minOf(at?.page ?: 0, pages - 1); break }
                        k += pages
                    }
                }
                Sfx.gains()
                // what roko says about it, when the purchase moved the story
                message = if (res.lines.isNotEmpty()) res.lines.map { it.text } else listOf("adquirida", a.name.lowercase())
                Evove.refresh()
                selected = null
                confirming = false
                Bus.bumpUser()
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro ao adquirir")
                confirming = false
            } finally {
                buying = false
            }
        }
    }

    BackHandler(enabled = forge != null || confirming || selected != null || stop > 0) {
        if (forge != null) forge = null else back()
    }

    CompositionLocalProvider(LocalInk provides ink) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
            val unit = unitFor(maxWidth)
            val row = min(unit * GRID_COLS, maxWidth)
            val tall = maxHeight
            Column(Modifier.fillMaxSize()) {
                Column(
                    Modifier.fillMaxWidth().height(tall * 0.16f).padding(horizontal = 0.4.remDp, vertical = 0.5.remDp),
                    verticalArrangement = Arrangement.spacedBy(0.4.remDp, Alignment.Bottom),
                    horizontalAlignment = Alignment.End,
                ) {
                    val sel = selected
                    when {
                        loading -> Small("…")
                        message.isNotEmpty() -> Message(message)
                        sel != null && group != null -> Big(sel.name, size = 1.6f)
                        group != null && here != null -> Small(listOfNotNull(
                            "${group.actions.size} ${if (group.actions.size == 1) "item" else "itens"}",
                            if (here.pages > 1) "${here.page + 1}/${here.pages}" else null,
                            "$points pts",
                        ).joinToString(" · "))
                        else -> {
                            Big("shop", size = 1.6f)
                            Small("$points pontos" + (found?.let { " · ${it.found}/${it.catalog} descobertas" } ?: ""))
                        }
                    }
                }
                val sel = selected
                when {
                    sel != null && group != null -> Panel(sel, confirming, buying, points, row, Modifier.weight(1f).align(Alignment.End), ::press)
                    group != null -> ShopCells(onPage, stop, unit, Modifier.weight(1f).fillMaxWidth()) { a ->
                        Sfx.tap(9); message = emptyList(); selected = a; confirming = false
                    }
                    else -> Column(Modifier.weight(1f).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Vault(found, discovering, opened, row, Modifier.weight(1f).align(Alignment.End), ::open)
                        Row(Modifier.width(row).align(Alignment.End), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Key({ Sfx.tap(3); forge = "patch" }, Modifier.weight(1f).heightIn(min = 2.6.remDp)) { KeyText("+ patch") }
                            Key({ Sfx.tap(3); forge = "attr" }, Modifier.weight(1f).heightIn(min = 2.6.remDp)) { KeyText("+ atributo") }
                        }
                    }
                }
                Bar(unit, row, Modifier.align(Alignment.End)) {
                    // where it stands: a tick per stop
                    Row(Modifier.at(1, 2).fillMaxHeight(), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
                        repeat(stops.size) { i ->
                            Box(Modifier.weight(1f, fill = false).widthIn(max = 6.dp).fillMaxWidth().height(if (i == stop) 18.dp else 10.dp)
                                .background(Color.White.copy(alpha = if (i == stop) 1f else 0.25f)))
                        }
                    }
                    Selector(
                        Evove.selector, stop, stops.size, back = selected != null && Evove.selector <= 1, Modifier.at(3, 3),
                        onNext = {
                            stop = (stop + 1) % stops.size
                            message = emptyList()
                            Evove.turn()
                            Sfx.powerOn()
                        },
                        onStep = ::goTo,
                        onTap = { Sfx.tap(0); if (!back()) onHome() },
                    )
                    HomeKey { Sfx.tap(0); onHome() }
                }
            }
        }
        forge?.let { ShopForge(it) { forge = null } }
    }
}

/** A page of a group's actions, each cell as large as it costs. */
@Composable
private fun ShopCells(list: List<ShopAction>, seed: Int, unit: Dp, modifier: Modifier, onChoose: (ShopAction) -> Unit) {
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val ink = LocalInk.current
    val nameStyle = TextStyle(fontFamily = Mono, fontSize = with(density) { 11.5.dp.toSp() }, color = ink)
    val costStyle = TextStyle(fontFamily = Mono, fontSize = with(density) { 10.dp.toSp() }, color = ink.copy(alpha = 0.7f))
    BoxWithConstraints(modifier) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val side = with(density) { unit.toPx() }
        val fit = if (side > 0) floor(h / side).toInt() else 0
        class Laid(val cell: DrawnCell, val lines: List<String>, val small: Boolean)
        val laid = remember(list, seed, w, h, side) {
            if (list.isEmpty() || fit == 0) return@remember emptyList<Laid>()
            // when the cells would not fit, the last ones give way to smaller sizes,
            // a step at a time, until they fit or all are as small as they go
            val wanted = list.map(::sizeOf).toMutableList()
            var packed = packFree(wanted, GRID_COLS)
            var i = wanted.size - 1
            var guard = 0
            while (packed.second > fit && wanted.any { it.first > SMALL } && guard++ < 100) {
                if (wanted[i].first > SMALL) {
                    wanted[i] = if (wanted[i].first > SCALE) SCALE to SCALE else SMALL to SMALL
                    packed = packFree(wanted, GRID_COLS)
                }
                i = (if (i == 0) wanted.size else i) - 1
            }
            val forms = formsFor(packed.first, seeded(seed))
            drawBoxes(packed.first, packed.second, w, h, side, GRID_GAP_DP * density.density, forms, slant = side * SCALE * SLANT).mapIndexed { k, c ->
                val hd = c.h / density.density
                val small = hd < 52
                val perLine = maxOf(5, floor((c.w / density.density - 14) / 7.6f).toInt())
                Laid(DrawnCell(c.shape, c.cx, c.cy, ink, DELAY[k % DELAY.size]), wrapWords(list[k].name, perLine, if (small) 1 else if (hd < 80) 2 else 3), small)
            }
        }
        val texts = remember(laid) {
            laid.mapIndexed { k, l ->
                l.lines.map { measurer.measure(caps(it), nameStyle) } +
                    if (l.small) emptyList() else listOf(measurer.measure(caps(if (list[k].cost > 0) "${list[k].cost} pts" else "grátis"), costStyle))
            }
        }
        Cells(laid.map { it.cell }, key = list, modifier = Modifier.fillMaxSize(), onTap = { onChoose(list[it]) }) { k, c, alpha ->
            val lines = texts[k]
            val step = 14 * density.density
            var y = c.cy - (laid[k].lines.size * step) / 2 + (if (laid[k].small) 7 * density.density else 0f)
            lines.forEachIndexed { j, t ->
                if (j == laid[k].lines.size) y += 2 * density.density
                drawText(t, topLeft = Offset(c.cx - t.size.width / 2, y - t.size.height / 2), alpha = alpha)
                y += step
            }
        }
    }
}

/** The colored area: the stats, then the question; a tap moves it on. */
@Composable
private fun Panel(a: ShopAction, confirming: Boolean, buying: Boolean, points: Int, row: Dp, modifier: Modifier, onPress: () -> Unit) {
    val ink = LocalInk.current
    val text = TextStyle(fontFamily = Mono, color = ink)
    Column(
        modifier.width(row).background(ink.copy(alpha = 0.1f)).border(1.5.dp, ink)
            .clickable(remember { MutableInteractionSource() }, null, enabled = !buying, onClick = onPress)
            .padding(horizontal = 1.5.remDp, vertical = 1.4.remDp),
        verticalArrangement = if (confirming) Arrangement.Center else Arrangement.spacedBy(1.remDp, Alignment.Bottom),
        horizontalAlignment = if (confirming) Alignment.CenterHorizontally else Alignment.Start,
    ) {
        if (confirming) {
            val short = points < a.cost
            BasicText(caps(if (short) "faltam ${a.cost - points} pts" else if (buying) "…" else "adquirir?"), style = text.copy(fontSize = 2.rem, textAlign = TextAlign.Center))
            BasicText(if (short) "saldo $points pts" else "${a.cost} pts · saldo $points pts", Modifier.alpha(0.7f), style = text.copy(fontSize = 0.85.rem))
        } else {
            val tokens = if (a.tokenGain > 0) "+${a.tokenGain} tokens por execução" else if (a.tokenCost > 0) "−${a.tokenCost} tokens por execução" else null
            val rows = buildList {
                if (a.code != null) add("id" to formatCode(a.code))
                add("tipo" to (TYPE_LABEL[a.type] ?: "${a.type}"))
                add("dificuldade" to "d${a.diff}")
                if (tokens != null) add("tokens" to tokens)
                add("custo" to "${a.cost} pts")
                add("autor" to "by ${a.author ?: "roko"}")
            }
            Column(verticalArrangement = Arrangement.spacedBy(0.35.remDp)) {
                for ((k, v) in rows) Row(horizontalArrangement = Arrangement.spacedBy(1.remDp), verticalAlignment = Alignment.CenterVertically) {
                    BasicText(caps(k), Modifier.width(7.remDp).alpha(0.7f), style = text.copy(fontSize = 0.7.rem))
                    BasicText(v, style = text.copy(fontSize = 0.85.rem))
                }
            }
            if (a.leaves.isNotEmpty()) {
                Box(Modifier.fillMaxWidth().height(1.5.dp).background(ink.copy(alpha = 0.5f)))
                Column(verticalArrangement = Arrangement.spacedBy(0.2.remDp)) {
                    for (l in a.leaves) Row {
                        BasicText(l.name, Modifier.weight(1f), style = text.copy(fontSize = 0.8.rem))
                        BasicText("${(l.weight * 100).roundToInt()}%", style = text.copy(fontSize = 0.8.rem))
                    }
                }
            }
        }
    }
}

/** Where the catalog is discovered. */
@Composable
private fun Vault(found: ShopState?, discovering: Boolean, opened: List<String>, row: Dp, modifier: Modifier, onOpen: () -> Unit) {
    val ink = LocalInk.current
    val note = TextStyle(fontFamily = Mono, fontSize = 0.8.rem, color = ink, textAlign = TextAlign.End)
    Column(
        modifier.width(row).dashed(ink.copy(alpha = 0.4f)).padding(6.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp, Alignment.Bottom),
    ) {
        when {
            found == null -> BasicText("…", Modifier.fillMaxWidth().alpha(0.7f), style = note)
            found.left <= 0 -> BasicText(caps(if (found.found >= found.catalog) "tudo descoberto" else "nada mais hoje · volte amanhã"), Modifier.fillMaxWidth().alpha(0.7f), style = note)
            found.phase == "frames" -> {
                // frames of static: each tap opens one
                for (r in (0 until found.left).chunked(3)) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (i in r) Static(Modifier.weight(1f).aspectRatio(1f).border(1.5.dp, ink).clickable(enabled = !discovering, onClick = onOpen))
                    repeat(3 - r.size) { Box(Modifier.weight(1f)) }
                }
            }
            found.phase == "button" -> Key(onOpen, Modifier.fillMaxWidth().heightIn(min = 4.5.remDp), enabled = !discovering) {
                KeyIcon(Icon.SCAN, 28.dp)
                KeyText("descobrir ${found.left}", com.evove.app.ui.Type.key.copy(fontSize = 0.95.rem))
            }
            else -> BasicText(caps("as descobertas chegam sozinhas"), Modifier.fillMaxWidth().alpha(0.7f), style = note)
        }
        if (opened.isNotEmpty()) BasicText(caps(opened.joinToString(" · ").lowercase()), Modifier.fillMaxWidth(), style = note.copy(color = Color.White))
    }
}
