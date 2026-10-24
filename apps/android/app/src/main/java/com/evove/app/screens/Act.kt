package com.evove.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.min
import com.evove.app.Bus
import com.evove.app.Evove
import com.evove.app.api.Line
import com.evove.app.ui.Selector
import com.evove.app.api.Action
import com.evove.app.api.Api
import com.evove.app.api.AttrNode
import com.evove.app.api.currentPeriod
import com.evove.app.api.fold
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
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Message
import com.evove.app.ui.Mono
import com.evove.app.ui.SLANT
import com.evove.app.ui.Small
import com.evove.app.ui.caps
import com.evove.app.ui.drawBoxes
import com.evove.app.ui.formsFor
import com.evove.app.ui.packFree
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import com.evove.app.ui.seeded
import com.evove.app.ui.unitFor
import com.evove.app.ui.wrapWords
import kotlinx.coroutines.launch
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToInt

// The screen, top to bottom: the display (messages, and what is being typed),
// the actions as cells — or, once one is chosen, its tiers — and the bar with
// two buttons: the arrow turns the page, the circle goes home. A button here
// takes SCALE × SCALE of the grid's squares, or sizes between, like 2×3.

private const val SCALE = 2
private const val PER_PAGE = 8
private val DELAY = intArrayOf(0, 110, 60, 170, 30, 220, 140, 90)

/** The sizes a button may take, in its own squares: one, two side by side, or
 *  one and a half tall. */
private val SIZES = listOf(1f to 1f, 2f to 1f, 1f to 1.5f)

/** The sizes of a page's cells, the same for the same page every time; when
 *  they would not fit `fit` rows, the last large ones give way to squares. */
private fun sizes(n: Int, rand: () -> Float, fit: Int): MutableList<Pair<Int, Int>> {
    val out = MutableList(n) {
        val v = rand() + 0.5f
        val (w, h) = SIZES[if (v < 0.4f) 1 else if (v < 0.75f) 0 else 2]
        (w * SCALE).roundToInt() to (h * SCALE).roundToInt()
    }
    var i = n - 1
    while (i >= 0 && packFree(out, GRID_COLS).second > fit) { out[i] = SCALE to SCALE; i-- }
    return out
}

private class GainsShown(val title: String, val tokens: Int, val marks: Int, val list: List<Gain>, val lines: List<Line>)

/** One of the actions handed out at the start, which roko does not believe yet. */
private val Action.doubted get() = Evove.view?.doubted?.contains(name.uppercase()) == true

/** The leaves whose marks grew since `before`, with where each bar stood. */
private fun diff(prev: Map<String, AttrNode>?, now: List<AttrNode>): List<Gain> {
    if (prev == null) return emptyList()
    return now.filter { it.totalMarks > (prev[it.key]?.totalMarks ?: 0) }.map { a ->
        val was = prev[a.key]
        val rankBefore = was?.rank ?: "α"
        // Still on the same rank: the bar grew from where it was. A rank crossed:
        // the old rank's bar, filled to the end from where it stood.
        if (was != null && was.rankIndex == a.rankIndex) Gain(a.key, a.name, rankBefore, a.rank, was.marks, if (a.max) a.need else a.marks, a.need)
        else {
            val need = was?.need ?: 3
            Gain(a.key, a.name, rankBefore, a.rank, was?.marks ?: 0, need, need)
        }
    }.sortedByDescending { it.marks - it.from }
}

/** Agir. In the sandbox (`sandbox`) the same screen holds every action of the
 *  catalog, and acting is free: no window, no tokens, no logs — the marks go to
 *  the sandbox's own attributes, and coleto cheers. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ActScreen(onHome: () -> Unit, sandbox: Boolean = false) {
    val ink = if (sandbox) Ink.sandbox else Ink.act
    var actions by remember { mutableStateOf<List<Action>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var page by remember { mutableIntStateOf(0) }
    var query by remember { mutableStateOf("") }
    var typing by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf<Action?>(null) }
    var windowMarks by remember { mutableStateOf<Int?>(null) }
    var acting by remember { mutableStateOf(false) }
    var before by remember { mutableStateOf<Map<String, AttrNode>?>(null) }
    var gains by remember { mutableStateOf<GainsShown?>(null) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    val scope = rememberCoroutineScope()
    val focus = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val keyboardUp = WindowInsets.isImeVisible

    val q = fold(query.trim())
    // a passcode is typed after a #, as into a terminal
    val code = query.trim().startsWith("#")
    val matches = if (q.isEmpty() || code) emptyList()
    else if (q.all { it.isDigit() }) actions.filter { it.id.startsWith(q) }
    else actions.filter { fold(it.name).contains(q) }

    fun raiseKeyboard() {
        runCatching { focus.requestFocus() }
        keyboard?.show()
    }

    fun sendCode() {
        val typed = query.trim().removePrefix("#")
        if (typed.isEmpty()) return
        focusManager.clearFocus()
        query = ""
        scope.launch {
            try {
                val r = Api.passcode(typed)
                Evove.apply(r)
                message = r.lines.map { it.text }.ifEmpty { listOf("código aceito") }
                Sfx.gains()
            } catch (e: Exception) {
                message = listOf("código", e.message ?: "não reconhecido")
            }
        }
    }

    fun choose(a: Action) {
        Sfx.tap(9)
        selected = a
        windowMarks = null
        query = ""
        focusManager.clearFocus()
        before = null
        if (!sandbox) scope.launch { runCatching { Api.actionWindow(a.id) }.onSuccess { if (selected?.id == a.id) windowMarks = it.windowMarks } }
        scope.launch {
            runCatching { if (sandbox) Api.sandboxAttributes() else Api.attributes() }
                .onSuccess { list -> if (selected?.id == a.id) before = list.associateBy { it.key } }
        }
    }

    // one match left: it is the one, no need to confirm
    LaunchedEffect(matches.size, typing) {
        if (typing && matches.size == 1 && selected == null) choose(matches[0])
    }

    // Android's back closes the soft keyboard and leaves the field focused;
    // when the keyboard is gone, so is the typing
    var wasUp by remember { mutableStateOf(false) }
    LaunchedEffect(keyboardUp) {
        if (wasUp && !keyboardUp && typing) focusManager.clearFocus()
        wasUp = keyboardUp
    }

    fun act(option: Int) {
        val action = selected ?: return
        if (acting) return
        Sfx.tap(option + 1)
        acting = true
        scope.launch {
            try {
                val tier = action.tiers.find { it.index == option }
                val prev = before
                val r = if (sandbox) Api.sandboxAct(action.id, option) else Api.act(action.id, option, currentPeriod())
                val now = if (r.logOnly) emptyList() else runCatching { if (sandbox) Api.sandboxAttributes() else Api.attributes() }.getOrDefault(emptyList())
                gains = GainsShown(
                    if (tier != null) "${r.name} · ${tier.label}" else r.name,
                    r.tokenGain - r.tokensWasted - r.tokenCost,
                    r.marks,
                    diff(prev, now),
                    if (r.journeyReset) listOf(Line("system", "seu hp acabou. a jornada recomeçou do primeiro estágio."))
                    else r.lines.ifEmpty { listOfNotNull(r.roko?.let { Line(r.speaker, it) }) } +
                        listOfNotNull(r.claimed?.takeIf { it.ranks > 0 }?.let {
                            Line("system", "${it.ranks} ${if (it.ranks == 1) "rank reclamado" else "ranks reclamados"}: +${it.points} pontos · +${it.tokens} tokens")
                        }),
                )
                // an act can open a module, and changes the points and tokens on top
                Evove.refresh()
                message = emptyList()
                if (!sandbox) {
                    Bus.bumpLogs()
                    Bus.bumpUser()
                }
                selected = null
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro ao agir")
            } finally {
                acting = false
            }
        }
    }

    LaunchedEffect(Unit) {
        // the keyboard opens on arrival: typing is the fastest way to an action
        raiseKeyboard()
        try {
            actions = if (sandbox) Api.sandboxActions() else Api.actions()
            if (actions.isNotEmpty()) Sfx.powerOn()
            else message = listOf("nenhuma ação ainda", "adquira uma no shop")
        } catch (e: Exception) {
            message = listOf(e.message ?: "erro ao carregar")
        } finally {
            loading = false
        }
    }

    BackHandler(enabled = gains != null || selected != null) {
        if (gains != null) onHome() else selected = null
    }

    gains?.let { g ->
        GainsScreen(g.title, g.tokens, g.marks, g.list, g.lines, onDone = onHome)
        return
    }

    val shown = if (q.isNotEmpty() && !code) matches else actions
    val pages = maxOf(1, ceil(shown.size / PER_PAGE.toFloat()).toInt())
    if (page >= pages) page = 0
    val onPage = shown.drop(page * PER_PAGE).take(PER_PAGE)
    val full = typing && keyboardUp

    androidx.compose.runtime.CompositionLocalProvider(LocalInk provides ink) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
            val unit = unitFor(maxWidth)
            val row = min(unit * GRID_COLS, maxWidth)
            val tall = maxHeight
            Column(Modifier.fillMaxSize()) {
                // the display: messages, what is typed, what was chosen; a tap types
                Column(
                    Modifier.fillMaxWidth().then(if (full) Modifier.weight(1f) else Modifier.height(tall * 0.18f))
                        .clickable(remember { MutableInteractionSource() }, null) { selected = null; raiseKeyboard() }
                        .padding(horizontal = 0.4.remDp, vertical = 0.5.remDp),
                    verticalArrangement = Arrangement.spacedBy(0.4.remDp, Alignment.Bottom),
                    horizontalAlignment = Alignment.End,
                ) {
                    // the field itself is out of sight: the display shows what it holds
                    BasicTextField(
                        query, { query = it },
                        Modifier.size(1.dp).alpha(0f).focusRequester(focus).onFocusChanged {
                            typing = it.isFocused
                            if (!it.isFocused && selected == null) query = ""
                        },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false, imeAction = ImeAction.Go),
                        keyboardActions = KeyboardActions(onGo = { if (code) sendCode() else matches.firstOrNull()?.let(::choose) }),
                    )
                    val sel = selected
                    when {
                        sel != null -> {
                            Big(sel.name, size = 1.6f)
                            Small(
                                if (sandbox) "sandbox · sem custo, sem limite"
                                else listOfNotNull(if (sel.doubted) "não verificada" else null, windowMarks?.let { "$it/5 marcas nas últimas 6h" } ?: "…").joinToString(" · "),
                            )
                        }
                        typing && code -> {
                            Big(query, size = 1.6f)
                            Small("passcode · enter para carregar")
                        }
                        typing -> {
                            Big(query.ifEmpty { "▍" }, size = 1.6f)
                            if (q.isNotEmpty()) Small(
                                if (matches.isNotEmpty()) matches[0].name + if (matches.size > 1) " · +${matches.size - 1}" else "" else "nada",
                            )
                        }
                        loading -> Small("…")
                        else -> Message(message)
                    }
                }
                if (!full) {
                    val sel = selected
                    if (sel != null) Tiers(sel, acting, row, Modifier.weight(1f).align(Alignment.End), ::act)
                    else ActionCells(onPage, page, unit, Modifier.weight(1f).fillMaxWidth(), sandbox, ::choose)
                    Bar(unit, row, Modifier.align(Alignment.End)) {
                        if (pages > 1) Row(Modifier.at(1, 2).fillMaxHeight(), horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
                            repeat(pages) { i ->
                                Box(Modifier.size(6.dp).border(1.dp, Color.White.copy(alpha = if (i == page) 1f else 0.6f)).background(if (i == page) Color.White else Color.Transparent))
                            }
                        } else Box(Modifier.at(1, 2))
                        Selector(
                            Evove.selector, page, pages, back = selected != null, Modifier.at(3, 3),
                            onNext = { page = (page + 1) % pages; Evove.turn(); Sfx.powerOn() },
                            onStep = { i -> if (i != page) { page = i; Evove.turn() } },
                            onTap = { Sfx.tap(0); if (selected != null) selected = null else onHome() },
                        )
                        HomeKey { Sfx.tap(0); onHome() }
                    }
                }
            }
        }
    }
}

/** A page of actions as cells, packed into the bottom-right corner. */
@Composable
private fun ActionCells(list: List<Action>, page: Int, unit: Dp, modifier: Modifier, sandbox: Boolean, onChoose: (Action) -> Unit) {
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val ink = LocalInk.current
    val style = TextStyle(fontFamily = Mono, fontSize = with(density) { 13.dp.toSp() }, color = ink)
    BoxWithConstraints(modifier) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val side = with(density) { unit.toPx() }
        val fit = if (side > 0) floor(h / side).toInt() else 0
        val laid = remember(list, page, w, h, side) {
            if (list.isEmpty() || fit == 0) return@remember emptyList<Pair<DrawnCell, List<String>>>()
            val rand = seeded(page + 1)
            val (boxes, rows) = packFree(sizes(list.size, rand, fit), GRID_COLS)
            val forms = formsFor(boxes, rand)
            drawBoxes(boxes, rows, w, h, side, GRID_GAP_DP * density.density, forms, slant = side * SCALE * SLANT).mapIndexed { i, c ->
                val perLine = maxOf(6, floor((c.w / density.density - 16) / 8.4f).toInt())
                // a handed-out action roko doubts is drawn in white: there, not yet believed
                DrawnCell(c.shape, c.cx, c.cy, if (!sandbox && list[i].doubted) Color.White else ink, DELAY[i % DELAY.size]) to wrapWords(list[i].name, perLine, 3)
            }
        }
        val texts = remember(laid) { laid.mapIndexed { i, (_, lines) -> lines.map { measurer.measure(caps(it), if (!sandbox && list[i].doubted) style.copy(color = Color.White) else style) } } }
        Cells(laid.map { it.first }, key = list, modifier = Modifier.fillMaxSize(), onTap = { onChoose(list[it]) }) { i, c, alpha ->
            val lines = texts[i]
            val step = 16 * density.density
            var y = c.cy - (lines.size - 1) * step / 2
            for (t in lines) {
                drawText(t, topLeft = Offset(c.cx - t.size.width / 2, y - t.size.height / 2), alpha = alpha)
                y += step
            }
        }
    }
}

/** The tiers of the chosen action: the margin rises, three across. */
@Composable
private fun Tiers(action: Action, acting: Boolean, row: Dp, modifier: Modifier, onAct: (Int) -> Unit) {
    val ink = LocalInk.current
    val rows = action.tiers.chunked(3)
    Column(modifier.width(row).padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.Bottom)) {
        var n = 0
        for (r in rows) {
            Row(Modifier.weight(1f).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (t in r) {
                    val number = ++n
                    Key({ onAct(t.index) }, Modifier.weight(1f).fillMaxHeight(), enabled = !acting) {
                        Box(Modifier.fillMaxSize()) {
                            BasicText("$number", Modifier.align(Alignment.TopStart).padding(top = 0.3.remDp, start = 0.45.remDp).alpha(0.55f),
                                style = TextStyle(fontFamily = Mono, fontSize = 0.7.rem, color = ink))
                            Column(Modifier.align(Alignment.Center), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(0.3.remDp)) {
                                BasicText(t.label, style = TextStyle(fontFamily = Mono, fontSize = 0.85.rem, color = ink))
                                BasicText("${t.marks}", style = TextStyle(fontFamily = Mono, fontSize = 1.3.rem, color = ink))
                            }
                        }
                    }
                }
                repeat(3 - r.size) { Box(Modifier.weight(1f)) }
            }
        }
    }
}
