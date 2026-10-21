package com.evove.app.ui

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp

// The cells a screen is made of — the home's options, a page of actions, the
// shop's items, the buttons built — as see-through polygons that come on like a
// tube set warming: a bright line opening into the picture, then a few quick
// flickers while it settles (the tube-on and settle keyframes of app.css).

/** A cell to draw: its shape, its colour, and when it comes on. */
class DrawnCell(
    val shape: List<Offset>,
    val cx: Float,
    val cy: Float,
    val color: Color,
    val delayMs: Int = 0,
    val strokeDp: Float = 1.5f,
    /** revealed just now: it glows as it comes on, once */
    val fresh: Boolean = false,
) {
    val path: Path = polygonPath(shape)
}

private val TUBE = CubicBezierEasing(0.2f, 0.8f, 0.3f, 1f)

/** The tube's scale and opacity, `t` ms into its `ms` of coming on. */
internal fun tubeOn(t: Float, ms: Float): Triple<Float, Float, Float> {
    if (t <= 0f) return Triple(0.15f, 0.006f, 0f)
    if (t >= ms) return Triple(1f, 1f, 1f)
    val p = t / ms
    fun seg(a: Float, b: Float) = TUBE.transform(((p - a) / (b - a)).coerceIn(0f, 1f))
    fun lerp(a: Float, b: Float, k: Float) = a + (b - a) * k
    return when {
        p < 0.12f -> seg(0f, 0.12f).let { Triple(lerp(0.15f, 1f, it), 0.006f, it) }
        p < 0.45f -> Triple(1f, 0.006f, 1f)
        p < 0.80f -> Triple(1f, lerp(0.006f, 1.04f, seg(0.45f, 0.8f)), 1f)
        else -> Triple(1f, lerp(1.04f, 1f, seg(0.8f, 1f)), 1f)
    }
}

private val SETTLE = floatArrayOf(0f, 0.15f, 0.3f, 0.5f, 0.65f, 0.8f)
private val SETTLE_OPACITY = floatArrayOf(1f, 0.35f, 1f, 0.6f, 1f, 0.85f)

/** The flicker that follows, in steps. */
private fun settle(t: Float, ms: Float): Float {
    if (t < 0f || t >= ms) return 1f
    val p = t / ms
    var o = 1f
    for (i in SETTLE.indices) if (p >= SETTLE[i]) o = SETTLE_OPACITY[i]
    return o
}

/**
 * The cells, drawn on one canvas. `key` restarts the coming-on; `onDown` is
 * the finger landing on a cell, `onTap` it lifting there, `onLong` a press held.
 * `inside` draws what a cell carries — a glyph, a name — at the opacity given.
 */
@Composable
fun Cells(
    cells: List<DrawnCell>,
    key: Any?,
    modifier: Modifier = Modifier,
    tubeMs: Float = 450f,
    settleMs: Float = 350f,
    hint: Int = -1,
    onDown: (Int) -> Unit = {},
    onTap: (Int) -> Unit,
    onLong: ((Int) -> Unit)? = null,
    inside: DrawScope.(index: Int, cell: DrawnCell, alpha: Float) -> Unit = { _, _, _ -> },
) {
    val last = (cells.maxOfOrNull { if (it.fresh) 900 else it.delayMs } ?: 0) + tubeMs + settleMs + if (cells.any { it.fresh }) 2400f else 0f
    val clock = clockOnce(key, last)
    var pressed by remember { mutableStateOf(-1) }
    val current by rememberUpdatedState(cells)
    val down by rememberUpdatedState(onDown)
    val tap by rememberUpdatedState(onTap)
    val long by rememberUpdatedState(onLong)
    fun hit(p: Offset) = current.indexOfLast { it.shape.encloses(p) }

    Canvas(
        modifier.pointerInput(onLong != null) {
            detectTapGestures(
                onPress = { p ->
                    val i = hit(p)
                    if (i >= 0) {
                        down(i)
                        pressed = i
                        tryAwaitRelease()
                        pressed = -1
                    }
                },
                onTap = { p -> hit(p).takeIf { it >= 0 }?.let(tap) },
                onLongPress = if (onLong != null) { p -> hit(p).takeIf { it >= 0 }?.let { long?.invoke(it) } } else null,
            )
        },
    ) {
        cells.forEachIndexed { i, c ->
            val delay = if (c.fresh) 900f else c.delayMs.toFloat()
            val t = clock - delay
            val (sx, sy, op) = tubeOn(t, tubeMs)
            val alpha = op * settle(t - tubeMs, settleMs)
            if (alpha <= 0f) return@forEachIndexed
            // revealed just now: the wash starts bright and fades to its usual
            val reveal = if (c.fresh) ((t - tubeMs) / 2400f).coerceIn(0f, 1f) else 1f
            val wash = if (pressed == i) 0.3f else if (c.fresh && reveal < 1f) 0.6f + (0.1f - 0.6f) * reveal else 0.1f
            withTransform({ scale(sx, sy, pivot = Offset(c.cx, c.cy)) }) {
                if (c.fresh && reveal < 1f) {
                    // the glow around it, as the drop-shadow did
                    for (k in 1..3) drawPath(c.path, c.color.copy(alpha = alpha * (1 - reveal) * 0.12f), style = Stroke(width = (6 * k).dp.toPx()))
                }
                drawPath(c.path, c.color.copy(alpha = alpha * wash))
                val stroke = (if (i == hint) 2.5f else c.strokeDp).dp.toPx()
                drawPath(c.path, c.color.copy(alpha = alpha), style = Stroke(width = stroke, join = StrokeJoin.Miter))
                inside(i, c, alpha)
            }
        }
    }
}
