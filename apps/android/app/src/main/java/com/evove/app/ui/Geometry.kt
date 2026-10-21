package com.evove.app.ui

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.min

// The grid every screen stands on, and the shapes of its cells — a port of
// apps/web/src/lib/homeLayout.ts. Everything here is in pixels.

/** A place on a grid of squares: x, y, width and height, in squares. */
data class Box(val x: Float, val y: Float, val w: Float, val h: Float)

/** How a cell's sides lean. A rectangle; a trapezoid narrowing upwards, its
 *  sides / \ ; a prism, both sides // ; or one of a pair of neighbours sharing
 *  a slanted side, so the two still fit as a rectangle. */
enum class Form { RECT, TRAP, PRISM, PAIR_L, PAIR_R }

/** How far a slanted side leans, as a share of a unit's width. */
const val SLANT = 0.2f

/** How much of each side of the screen the interface takes. */
const val SHRINK = 0.9f

/** The grid: six squares across, taking SHRINK of the width. */
const val GRID_COLS = 6

/** Half the gap between two cells, in dp. */
const val GRID_GAP_DP = 6f

/** The widest a screen counts as, in dp: a phone's. */
const val PHONE_WIDTH_DP = 420f

/** The side of one of the grid's squares, for a screen `w` px wide. */
fun gridUnit(w: Float, density: Float): Float = min(w, PHONE_WIDTH_DP * density) * SHRINK / GRID_COLS

/** A rectangle's corners, clockwise from the top left, leaned into `form`. */
fun formShape(x0: Float, y0: Float, x1: Float, y1: Float, form: Form, s: Float): List<Offset> {
    val (tl, tr, br, bl) = when (form) {
        Form.TRAP -> listOf(s, -s, 0f, 0f)
        Form.PRISM -> listOf(s, 0f, -s, 0f)
        Form.PAIR_L -> listOf(0f, s, -s, 0f)
        Form.PAIR_R -> listOf(s, 0f, 0f, -s)
        Form.RECT -> listOf(0f, 0f, 0f, 0f)
    }
    return listOf(Offset(x0 + tl, y0), Offset(x1 + tr, y0), Offset(x1 + br, y1), Offset(x0 + bl, y1))
}

/** Lays cells of whole sizes, w × h in units, on a grid `cols` wide: each in
 *  turn at the first place it fits, reading the rows top to bottom and each
 *  from the right, so smaller cells fill the holes larger ones leave. */
fun packFree(sizes: List<Pair<Int, Int>>, cols: Int): Pair<List<Box>, Int> {
    val used = HashSet<Long>()
    fun key(x: Int, y: Int) = (y.toLong() shl 20) or x.toLong()
    fun free(x: Int, y: Int, w: Int, h: Int): Boolean {
        for (j in y until y + h) for (i in x until x + w) if (key(i, j) in used) return false
        return true
    }
    var rows = 0
    val boxes = sizes.map { (w0, h) ->
        val w = min(w0, cols)
        var placed: Box? = null
        var y = 0
        while (placed == null) {
            var x = 0
            while (x + w <= cols) {
                if (free(x, y, w, h)) {
                    for (j in y until y + h) for (i in x until x + w) used += key(i, j)
                    rows = maxOf(rows, y + h)
                    placed = Box((cols - x - w).toFloat(), y.toFloat(), w.toFloat(), h.toFloat())
                    break
                }
                x++
            }
            y++
        }
        placed
    }
    return boxes to rows
}

/** A cell drawn: its polygon, centre, width and height. */
data class Cell(val shape: List<Offset>, val cx: Float, val cy: Float, val w: Float, val h: Float)

/** Draws boxes of a grid `rows` tall and `cols` wide, its units `side` px wide,
 *  gathered in the bottom-right corner of a w×h area, each pulled in by `gap`
 *  on every side and leaned into its form by `slant`. */
fun drawBoxes(
    boxes: List<Box>, rows: Int, w: Float, h: Float, side: Float, gap: Float,
    forms: List<Form> = emptyList(), cols: Int = GRID_COLS, slant: Float = side * SLANT,
): List<Cell> {
    val left = w - cols * side
    val top = h - rows * side
    return boxes.mapIndexed { i, b ->
        // quarters sit closer together, or they would be all gap
        val g = if (b.w < 1) gap / 2 else gap
        val x0 = left + b.x * side + g
        val y0 = top + b.y * side + g
        val x1 = left + (b.x + b.w) * side - g
        val y1 = top + (b.y + b.h) * side - g
        Cell(formShape(x0, y0, x1, y1, forms.getOrElse(i) { Form.RECT }, slant), (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0)
    }
}

/** Forms for the cells of packed rows: now and then two neighbours share a
 *  slanted side, the others are rectangles, trapezoids or prisms. Drawn from
 *  `rand`, so the same page keeps its forms. */
fun formsFor(boxes: List<Box>, rand: () -> Float): List<Form> {
    val forms = MutableList(boxes.size) { Form.RECT }
    val byRow = LinkedHashMap<Float, MutableList<Int>>()
    boxes.forEachIndexed { i, b -> if (b.w >= 1) byRow.getOrPut(b.y) { mutableListOf() } += i }
    for (row in byRow.values) {
        row.sortBy { boxes[it].x }
        var k = 0
        while (k < row.size) {
            val i = row[k]
            val j = row.getOrNull(k + 1)
            val v = rand() + 0.5f
            if (j != null && boxes[i].x + boxes[i].w == boxes[j].x && boxes[i].h == boxes[j].h && v < 0.35f) {
                forms[i] = Form.PAIR_L
                forms[j] = Form.PAIR_R
                k++
            } else forms[i] = if (v < 0.6f) Form.RECT else if (v < 0.8f) Form.TRAP else Form.PRISM
            k++
        }
    }
    return forms
}

/** A small deterministic generator, in −0.5…0.5: the same seed, the same page. */
fun seeded(seed: Int): () -> Float {
    var state = (((seed + 7).toLong() * 2654435761L) and 0xFFFFFFFFL).toInt()
    if (state == 0) state = 1
    return {
        state = state xor (state shl 13)
        state = state xor (state ushr 17)
        state = state xor (state shl 5)
        ((state.toLong() and 0xFFFFFFFFL) % 10000).toFloat() / 10000f - 0.5f
    }
}

/** Moves every edge of a convex polygon `d` inwards. */
fun inset(points: List<Offset>, d: Float): List<Offset> {
    val n = points.size
    var area = 0f
    for (i in 0 until n) {
        val a = points[i]; val b = points[(i + 1) % n]
        area += a.x * b.y - b.x * a.y
    }
    val sign = if (area > 0) 1f else -1f
    val lines = points.mapIndexed { i, p ->
        val q = points[(i + 1) % n]
        val dx = q.x - p.x; val dy = q.y - p.y
        val len = hypot(dx, dy).takeIf { it > 0 } ?: 1f
        val nx = (-dy / len) * sign; val ny = (dx / len) * sign
        Offset(p.x + nx * d, p.y + ny * d) to Offset(dx, dy)
    }
    return lines.mapIndexed { i, (ap, ad) ->
        val (bp, bd) = lines[(i + n - 1) % n]
        val cross = bd.x * ad.y - bd.y * ad.x
        if (abs(cross) < 1e-9f) ap
        else {
            val t = ((ap.x - bp.x) * ad.y - (ap.y - bp.y) * ad.x) / cross
            Offset(bp.x + bd.x * t, bp.y + bd.y * t)
        }
    }
}

fun polygonPath(points: List<Offset>): Path = Path().apply {
    points.forEachIndexed { i, p -> if (i == 0) moveTo(p.x, p.y) else lineTo(p.x, p.y) }
    close()
}

/** Whether `p` is inside the polygon. */
fun List<Offset>.encloses(p: Offset): Boolean {
    var inside = false
    var j = size - 1
    for (i in indices) {
        val a = this[i]; val b = this[j]
        if ((a.y > p.y) != (b.y > p.y) && p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x) inside = !inside
        j = i
    }
    return inside
}

/** Breaks a name into lines of at most `perLine` characters, at most `max`. */
fun wrapWords(name: String, perLine: Int, max: Int): List<String> {
    val lines = mutableListOf<String>()
    var line = ""
    for (word in name.split(Regex("\\s+"))) {
        if (line.isNotEmpty() && "$line $word".length > perLine) {
            lines += line
            line = word
        } else line = if (line.isNotEmpty()) "$line $word" else word
    }
    if (line.isNotEmpty()) lines += line
    return lines.take(max)
}
