package com.evove.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.min
import com.evove.app.Prefs
import com.evove.app.sound.Sfx
import com.evove.app.ui.Bar
import com.evove.app.ui.Box
import com.evove.app.ui.DOT_R
import com.evove.app.ui.Form
import com.evove.app.ui.GRID_COLS
import com.evove.app.ui.GRID_GAP_DP
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.LocalInk
import com.evove.app.ui.SLANT
import com.evove.app.ui.Small
import com.evove.app.ui.encloses
import com.evove.app.ui.drawGlyph
import com.evove.app.ui.formShape
import com.evove.app.ui.formsFor
import com.evove.app.ui.packFree
import com.evove.app.ui.polygonPath
import com.evove.app.ui.remDp
import com.evove.app.ui.tubeOn
import com.evove.app.ui.unitFor
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlin.math.abs
import kotlin.math.floor

// A page for building buttons on the grid: the grid's squares lie faint in
// the bottom-right corner; a tap on one square and then another makes a button
// across the rectangle between them, wearing an icon. A tap on a button turns
// it to the next form, a long press to the next icon, and two quick taps take
// it away. The bar's wide button throws a whole layout at random. What is
// built is kept on this device.

private const val DOUBLE_MS = 280L
private const val KEY = "evove_built"
private val SIZES = listOf(1 to 1, 2 to 1, 1 to 2, 2 to 2, 3 to 2, 2 to 3, 3 to 3)
private val FORMS = Form.entries

@Serializable
private data class Built(val box: List<Int>, val form: String = "rect", val icon: String? = null) {
    val x get() = box[0]
    val y get() = box[1]
    val w get() = box[2]
    val h get() = box[3]
}

@Serializable
private data class Kept(val rows: Int, val built: List<Built>)

private val FORM_NAMES = mapOf(Form.RECT to "rect", Form.TRAP to "trap", Form.PRISM to "prism", Form.PAIR_L to "pairL", Form.PAIR_R to "pairR")
private fun formOf(name: String) = FORM_NAMES.entries.find { it.value == name }?.key ?: Form.RECT
private fun iconOf(name: String?) = Icon.entries.find { it.name.lowercase() == name } ?: Icon.DOTS
private fun cover(b: Built) = buildList { for (i in b.x until b.x + b.w) for (j in b.y until b.y + b.h) add(i to j) }

@Composable
fun BuildScreen(onHome: () -> Unit) {
    val json = remember { Json { ignoreUnknownKeys = true } }
    // the boxes count their rows from the top of a grid `at` rows tall; when
    // the screen holds another number of rows, they move with its bottom edge
    val kept = remember { runCatching { json.decodeFromString<Kept>(Prefs.string(KEY) ?: "") }.getOrNull() ?: Kept(0, emptyList()) }
    var built by remember { mutableStateOf(kept.built) }
    var at by remember { mutableStateOf(kept.rows) }
    // when each button came on, for its tube to warm: a new or changed one
    var born by remember { mutableStateOf(built.map { 0L }) }
    var first by remember { mutableStateOf<Pair<Int, Int>?>(null) }
    var pending by remember { mutableStateOf<Pair<Int, Job>?>(null) }
    var now by remember { mutableLongStateOf(0L) }
    var gridRows by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()

    fun save() = Prefs.putString(KEY, json.encodeToString(Kept.serializer(), Kept(at, built)))
    fun set(next: List<Built>, changed: Set<Int>) {
        built = next
        born = next.indices.map { if (it in changed) now else born.getOrElse(it) { now } }
        save()
    }

    // the frame clock, ticking while a tube warms
    LaunchedEffect(born) {
        val start = withFrameMillis { it }
        if (now == 0L) now = start
        while (born.any { now - it < 400 }) withFrameMillis { now = it }
    }
    LaunchedEffect(Unit) { Sfx.powerOn() }
    BackHandler(enabled = first != null) { first = null }

    val ink = Ink.build
    CompositionLocalProvider(LocalInk provides ink) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
            val tall = maxHeight
            val wide = maxWidth
            Column(Modifier.fillMaxSize()) {
                Column(Modifier.fillMaxWidth().height(tall * 0.12f).padding(horizontal = 0.4.remDp, vertical = 0.5.remDp), verticalArrangement = androidx.compose.foundation.layout.Arrangement.Bottom, horizontalAlignment = Alignment.End) {
                    Small(if (first != null) "toque outra casa" else if (built.isNotEmpty()) "${built.size} ${if (built.size == 1) "botão" else "botões"}" else "toque duas casas")
                }
                val density = LocalDensity.current
                BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
                    val w = constraints.maxWidth.toFloat()
                    val h = constraints.maxHeight.toFloat()
                    // the grid every screen shares; on a screen too short for what is
                    // built, its squares shrink until all of it fits
                    val span = if (built.isNotEmpty()) at - built.minOf { it.y } else 0
                    val side = minOf(with(density) { unitFor(wide).toPx() }, if (span > 0) h / span else Float.MAX_VALUE)
                    val rows = if (side > 0) floor(h / side + 1e-6f).toInt() else 0
                    LaunchedEffect(rows) {
                        if (rows > 0 && rows != at) {
                            val down = rows - at
                            built = built.map { it.copy(box = listOf(it.x, it.y + down, it.w, it.h)) }
                            at = rows
                            save()
                        }
                    }
                    val left = w - GRID_COLS * side
                    val top = h - rows * side
                    val gap = GRID_GAP_DP * density.density
                    val taken = built.flatMap(::cover).toSet()
                    val shapes = built.map { b ->
                        val x0 = left + b.x * side + gap; val y0 = top + b.y * side + gap
                        val x1 = left + (b.x + b.w) * side - gap; val y1 = top + (b.y + b.h) * side - gap
                        formShape(x0, y0, x1, y1, formOf(b.form), side * SLANT)
                    }
                    val current by rememberUpdatedState(Triple(shapes, taken, Triple(left, top, side)))

                    fun square(x: Int, y: Int) {
                        if (x to y in taken) return
                        val f = first
                        if (f == null) { Sfx.tap(2); first = x to y; return }
                        first = null
                        if (f == x to y) { Sfx.tap(0); return }
                        val b = Built(listOf(minOf(f.first, x), minOf(f.second, y), abs(f.first - x) + 1, abs(f.second - y) + 1), "rect", Icon.BUTTON.random().name.lowercase())
                        // a button only where the squares are free
                        if (cover(b).any { it in taken }) { Sfx.tap(0); return }
                        Sfx.tap(7)
                        set(built + b, setOf(built.size))
                    }

                    fun button(i: Int) {
                        first = null
                        val p = pending
                        if (p != null && p.first == i) {
                            // the second of two quick taps: away with it
                            p.second.cancel()
                            pending = null
                            Sfx.tap(0)
                            born = born.filterIndexed { k, _ -> k != i }
                            built = built.filterIndexed { k, _ -> k != i }
                            save()
                            return
                        }
                        p?.second?.cancel()
                        pending = i to scope.launch {
                            delay(DOUBLE_MS)
                            pending = null
                            Sfx.tap(5)
                            set(built.mapIndexed { k, b -> if (k == i) b.copy(form = FORM_NAMES[FORMS[(FORMS.indexOf(formOf(b.form)) + 1) % FORMS.size]]!!) else b }, setOf(i))
                        }
                    }

                    fun long(i: Int) {
                        Sfx.tap(3)
                        set(built.mapIndexed { k, b ->
                            if (k == i) b.copy(icon = Icon.BUTTON[(Icon.BUTTON.indexOf(iconOf(b.icon)) + 1) % Icon.BUTTON.size].name.lowercase()) else b
                        }, setOf(i))
                    }

                    fun hit(p: Offset, onButton: (Int) -> Unit, onSquare: (Int, Int) -> Unit) {
                        val (sh, _, grid) = current
                        val i = sh.indexOfLast { it.encloses(p) }
                        if (i >= 0) return onButton(i)
                        val (l, t, s) = grid
                        if (s <= 0) return
                        val x = floor((p.x - l) / s).toInt()
                        val y = floor((p.y - t) / s).toInt()
                        if (x in 0 until GRID_COLS && y in 0 until rows) onSquare(x, y)
                    }

                    Canvas(
                        Modifier.fillMaxSize().pointerInput(Unit) {
                            detectTapGestures(
                                onTap = { p -> hit(p, ::button, ::square) },
                                onLongPress = { p -> hit(p, { long(it) }, { _, _ -> }) },
                            )
                        },
                    ) {
                        if (side <= 0 || rows <= 0) return@Canvas
                        // the grid's squares, faint until one is chosen
                        for (y in 0 until rows) for (x in 0 until GRID_COLS) {
                            if (x to y in taken) continue
                            val on = first == x to y
                            val tl = Offset(left + x * side + gap, top + y * side + gap)
                            val sz = Size(side - 2 * gap, side - 2 * gap)
                            drawRect(ink.copy(alpha = if (on) 0.25f else 0.03f), tl, sz)
                            drawRect(ink.copy(alpha = if (on) 1f else 0.18f), tl, sz, style = Stroke(1.dp.toPx()))
                        }
                        built.forEachIndexed { i, b ->
                            val shape = shapes[i]
                            val cx = (shape.minOf { it.x } + shape.maxOf { it.x }) / 2
                            val cy = (shape.minOf { it.y } + shape.maxOf { it.y }) / 2
                            val (sx, sy, op) = tubeOn((now - born.getOrElse(i) { 0L }).toFloat(), 400f)
                            val path = polygonPath(shape)
                            withTransform({ scale(sx, sy, pivot = Offset(cx, cy)) }) {
                                drawPath(path, ink.copy(alpha = op * if (pending?.first == i) 0.3f else 0.1f))
                                drawPath(path, ink.copy(alpha = op), style = Stroke(1.5.dp.toPx(), join = StrokeJoin.Miter))
                                val bw = shape.maxOf { it.x } - shape.minOf { it.x }
                                val bh = shape.maxOf { it.y } - shape.minOf { it.y }
                                val size = minOf(36.dp.toPx(), minOf(bw, bh) * 0.42f)
                                drawGlyph(iconOf(b.icon).glyph, Offset(cx - size / 2, cy - size / 2), size, ink.copy(alpha = op), 1.8f * size / 24f, DOT_R * 1.2f)
                            }
                        }
                    }

                    // the bar's shuffle needs the rows, laid out after it is composed
                    if (gridRows != rows) gridRows = rows
                }
                val unit = unitFor(wide)
                Bar(unit, min(unit * GRID_COLS, wide), Modifier.align(Alignment.End)) {
                    Key({
                        first = null
                        val rows = gridRows
                        if (rows <= 0) return@Key
                        // a whole layout at random: buttons of assorted sizes packed into
                        // the bottom-right corner while they fit
                        val want = 4 + (0 until 6).random()
                        var sizes = listOf<Pair<Int, Int>>()
                        for (k in 0 until want * 3) {
                            if (sizes.size >= want) break
                            val next = sizes + SIZES.random()
                            if (packFree(next, GRID_COLS).second <= rows) sizes = next
                        }
                        val (boxes, used) = packFree(sizes, GRID_COLS)
                        // packed from the top: lowered to the bottom of the grid
                        val lowered = boxes.map { Box(it.x, it.y + rows - used, it.w, it.h) }
                        val forms = formsFor(lowered) { Math.random().toFloat() - 0.5f }
                        set(lowered.mapIndexed { i, b ->
                            Built(listOf(b.x.toInt(), b.y.toInt(), b.w.toInt(), b.h.toInt()), FORM_NAMES[forms[i]]!!, Icon.BUTTON.random().name.lowercase())
                        }, lowered.indices.toSet())
                        Sfx.powerOn()
                    }, Modifier.at(3, 3)) { KeyIcon(Icon.SHUFFLE) }
                    HomeKey { Sfx.tap(0); onHome() }
                }
            }
        }
    }
}
