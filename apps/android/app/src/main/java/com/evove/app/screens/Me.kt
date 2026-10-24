package com.evove.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.min
import com.evove.app.Bus
import com.evove.app.Evove
import com.evove.app.api.Api
import com.evove.app.api.AttrNode
import com.evove.app.api.UserState
import com.evove.app.sound.Sfx
import com.evove.app.ui.AttributeFigure
import com.evove.app.ui.Bar
import com.evove.app.ui.Big
import com.evove.app.ui.Cells
import com.evove.app.ui.Display
import com.evove.app.ui.DrawnCell
import com.evove.app.ui.Empty
import com.evove.app.ui.GRID_COLS
import com.evove.app.ui.GRID_GAP_DP
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.KeyText
import com.evove.app.ui.LocalInk
import com.evove.app.ui.MarkBar
import com.evove.app.ui.Message
import com.evove.app.ui.Mono
import com.evove.app.ui.Selector
import com.evove.app.ui.Small
import com.evove.app.ui.Stats
import com.evove.app.ui.caps
import com.evove.app.ui.drawBoxes
import com.evove.app.ui.figureOf
import com.evove.app.ui.packFree
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import com.evove.app.ui.unitFor
import com.evove.app.ui.wrapWords
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import java.text.Collator
import java.util.Locale
import kotlin.math.floor

// The profile's attributes, walked as agir's actions are: cells of one size,
// in rows, the selector turning the pages — first the ones gaining marks most
// recently, then every attribute of each star level, ★1 the leaves, Físico
// far above. A tap opens one: its figure — the body with the part trained
// lit, a close on an arm, a leg or the torso, the brain with its region, or a
// web of its parts for what the mind does — its rank and its marks.

private const val SCALE = 2
private val DELAY = intArrayOf(0, 110, 60, 170, 30, 220, 140, 90, 200)

val pt: Collator = Collator.getInstance(Locale.forLanguageTag("pt-BR"))

private fun kids(n: AttrNode) = n.children.filter { it.primary != false }

/** Every attribute once, by its primary place, keyed; and the keys above each. */
private fun flatten(list: List<AttrNode>): Pair<Map<String, AttrNode>, Map<String, List<String>>> {
    val out = LinkedHashMap<String, AttrNode>()
    val chains = HashMap<String, List<String>>()
    fun walk(n: AttrNode, above: List<String>) {
        if (n.key !in out) {
            out[n.key] = n
            chains[n.key] = above + n.key
        }
        kids(n).forEach { walk(it, above + n.key) }
    }
    list.forEach { walk(it, emptyList()) }
    return out to chains
}

/** A page of the walk: its title and the attributes on it. */
private data class Leaf(val title: String, val items: List<AttrNode>)

@Composable
fun MeScreen(onHome: () -> Unit, onProfile: () -> Unit, onDetails: () -> Unit) {
    var user by remember { mutableStateOf<UserState?>(null) }
    var roots by remember { mutableStateOf<List<AttrNode>>(emptyList()) }
    var recent by remember { mutableStateOf<List<AttrNode>>(emptyList()) }
    var page by remember { mutableIntStateOf(0) }
    var detail by remember { mutableStateOf<AttrNode?>(null) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        try {
            val u = scope.async { Api.user() }
            val t = scope.async { Api.attributeTree() }
            val r = scope.async { Api.recentAttributes(24) }
            user = u.await()
            roots = t.await().roots
            recent = r.await()
        } catch (e: Exception) {
            message = listOf(e.message ?: "erro")
        }
    }

    var first by remember { mutableStateOf(true) }
    LaunchedEffect(Bus.user) {
        load()
        if (first) Sfx.powerOn()
        first = false
    }

    val (all, chains) = remember(roots) { flatten(roots) }
    val maxStar = maxOf(1, all.values.maxOfOrNull { it.star } ?: 1)

    fun claim(n: AttrNode) {
        if (busy || n.claim == null) return
        busy = true
        scope.launch {
            try {
                val r = Api.claimRank(n.key)
                Sfx.gains()
                message = listOf("${r.ranks} ${if (r.ranks == 1) "rank" else "ranks"}", "+${r.pointsGained} pts · +${r.tokensGained}t")
                Bus.bumpUser()
                Evove.refresh()
                detail = n.copy(claim = null)
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    BackHandler(enabled = detail != null) { detail = null }

    val ink = Ink.attributes
    CompositionLocalProvider(LocalInk provides ink) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
            val unit = unitFor(maxWidth)
            val row = min(unit * GRID_COLS, maxWidth)
            val tall = maxHeight
            val side = unit * SCALE
            // how many cells a page holds, three to a row
            val fit = maxOf(1, floor(((tall * 0.82f - unit) / side).toDouble()).toInt() - 1)
            val perPage = fit * (GRID_COLS / SCALE)
            val pages = remember(all, recent, perPage) {
                val out = mutableListOf<Leaf>()
                val r = recent.mapNotNull { all[it.key] ?: it }.distinctBy { it.key }
                r.chunked(perPage).ifEmpty { listOf(emptyList()) }.forEach { out += Leaf("recentes", it) }
                for (st in 1..maxStar) {
                    val list = all.values.filter { it.star == st }
                        .sortedWith(compareByDescending<AttrNode> { it.totalMarks }.thenComparator { a, b -> pt.compare(a.name, b.name) })
                    list.chunked(perPage).forEach { out += Leaf("★$st", it) }
                }
                out
            }
            if (page >= pages.size) page = 0
            val here = pages.getOrNull(page)
            Column(Modifier.fillMaxSize()) {
                Column(
                    Modifier.fillMaxWidth().height(tall * 0.18f).padding(horizontal = 0.4.remDp, vertical = 0.5.remDp),
                    verticalArrangement = Arrangement.spacedBy(0.35.remDp, Alignment.Bottom),
                    horizontalAlignment = Alignment.End,
                ) {
                    val d = detail
                    val u = user
                    when {
                        message.isNotEmpty() -> Message(message)
                        d != null -> { Big(d.name); Small("${d.rank} ${d.rankName ?: ""} · ★${d.star} · ${d.marks}/${d.need}") }
                        u != null -> {
                            BasicText(
                                buildAnnotatedString {
                                    append(u.rankSymbol)
                                    withStyle(SpanStyle(fontSize = 0.8.rem, letterSpacing = 0.2.em, color = Color.White)) { append("  " + caps(u.rankName ?: "")) }
                                },
                                style = TextStyle(fontFamily = Display, fontSize = 2.4.rem, lineHeight = 1.em, color = ink, textAlign = TextAlign.End),
                            )
                            Small("${here?.title ?: ""} · ${u.nickname ?: u.username} · nível ${u.level}")
                            Box(Modifier.widthIn(max = 16.remDp).fillMaxWidth()) { MarkBar(u.levelMarks, u.levelCost) }
                        }
                    }
                }
                val d = detail
                if (d != null) {
                    Detail(d, chains[d.key].orEmpty(), all, busy, row, Modifier.weight(1f).align(Alignment.End), ::claim)
                } else if (here == null || here.items.isEmpty()) {
                    Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.BottomEnd) { Empty("nada aqui ainda — aja") }
                } else {
                    AttributeCells(here.items, page, unit, Modifier.weight(1f).fillMaxWidth()) { n -> Sfx.tap(7); message = emptyList(); detail = n }
                }
                Bar(unit, row, Modifier.align(Alignment.End)) {
                    Key({ Sfx.tap(3); onDetails() }, Modifier.at(1)) { KeyIcon(Icon.TREE) }
                    Key({ Sfx.tap(5); onProfile() }, Modifier.at(2)) { KeyIcon(Icon.USER) }
                    Selector(
                        Evove.selector, page, pages.size, back = detail != null, Modifier.at(3, 3),
                        onNext = { page = (page + 1) % maxOf(1, pages.size); Evove.turn(); Sfx.powerOn() },
                        onStep = { i -> if (i != page) { page = i; Evove.turn() } },
                        onTap = { Sfx.tap(0); if (detail != null) detail = null else onHome() },
                    )
                    HomeKey { Sfx.tap(0); onHome() }
                }
            }
        }
    }
}

/** A page of attributes as cells of one size, three to a row, packed into the
 *  bottom-right corner: the name, and the rank under it. */
@Composable
private fun AttributeCells(list: List<AttrNode>, page: Int, unit: Dp, modifier: Modifier, onChoose: (AttrNode) -> Unit) {
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val ink = LocalInk.current
    val style = TextStyle(fontFamily = Mono, fontSize = with(density) { 12.dp.toSp() }, color = ink)
    val rankStyle = TextStyle(fontFamily = Display, fontSize = with(density) { 15.dp.toSp() }, color = Color.White)
    BoxWithConstraints(modifier) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val side = with(density) { unit.toPx() }
        val laid = remember(list, page, w, h, side) {
            if (list.isEmpty()) return@remember emptyList<Pair<DrawnCell, List<String>>>()
            val (boxes, rows) = packFree(List(list.size) { SCALE to SCALE }, GRID_COLS)
            drawBoxes(boxes, rows, w, h, side, GRID_GAP_DP * density.density).mapIndexed { i, c ->
                val perLine = maxOf(6, floor((c.w / density.density - 14) / 7.8f).toInt())
                DrawnCell(c.shape, c.cx, c.cy, if (list[i].claim != null) Ink.gold else ink, DELAY[i % DELAY.size]) to wrapWords(list[i].name, perLine, 2)
            }
        }
        val texts = remember(laid) {
            laid.mapIndexed { i, (_, lines) -> lines.map { measurer.measure(caps(it), style) } + measurer.measure(list[i].rank, rankStyle) }
        }
        Cells(laid.map { it.first }, key = list, modifier = Modifier.fillMaxSize(), onTap = { onChoose(list[it]) }) { i, c, alpha ->
            val t = texts[i]
            val step = 15 * density.density
            var y = c.cy - t.size * step / 2 + step / 2
            for (x in t) {
                drawText(x, topLeft = Offset(c.cx - x.size.width / 2, y - x.size.height / 2), alpha = alpha)
                y += step
            }
        }
    }
}

/** One attribute: its figure, its rank and marks, and its reward when ranks
 *  wait to be claimed. */
@Composable
private fun Detail(d: AttrNode, chain: List<String>, all: Map<String, AttrNode>, busy: Boolean, row: Dp, modifier: Modifier, onClaim: (AttrNode) -> Unit) {
    val ink = LocalInk.current
    val kind = figureOf(chain)
    // the web's parts: its children, or, for a leaf, it and its siblings
    val parent = chain.dropLast(1).lastOrNull()?.let { all[it] }
    val parts = (if (kids(d).size >= 3) kids(d) else parent?.let(::kids) ?: listOf(d)).take(8)
    val top = maxOf(1, parts.maxOfOrNull { it.totalMarks } ?: 1)
    Column(modifier.widthIn(max = row).fillMaxWidth().padding(6.dp), verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.Bottom)) {
        AttributeFigure(kind, ink, Modifier.fillMaxWidth().weight(1f), parts.map { it.name to it.totalMarks / top.toFloat() })
        Stats(listOf("rank" to "${d.rank} · ${d.rankName ?: ""}", "marcas" to "${d.marks}/${d.need}", "total" to "${d.totalMarks}",
            "estrela" to "★${d.star}", "grau" to "${d.degree}"))
        MarkBar(d.marks, d.need, gold = true)
        d.claim?.let { c ->
            Key({ onClaim(d) }, Modifier.fillMaxWidth().heightIn(min = 2.8.remDp), enabled = !busy) {
                KeyIcon(Icon.STAR, 16.dp); KeyText("reclamar ${c.ranks} · +${c.points} pts")
            }
        }
    }
}
