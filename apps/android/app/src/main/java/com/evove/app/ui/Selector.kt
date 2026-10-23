package com.evove.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import com.evove.app.sound.Sfx

// The selector: the button in the middle of the bar that walks a screen's
// pages, and the part of the interface that evolves the most visibly. Its level
// is the profile's, kept by the engine:
//
//   1  an arrow — each tap the next page;
//   2  after 1000 turns, a grooved wheel — slid to walk the pages, tapped to go
//      back a step;
//   3  by chance, at some later session, a strip with one segment per page —
//      tapped where one wants to go, slid like the wheel, tapped where it
//      stands to go back.

private const val STEP_DP = 34f
private const val MAX_SEGMENTS = 14

/** The selector at `level`. `back` turns the arrow around: a step back is all
 *  there is to do, as with an action chosen. `onStep` moves to a page, `onTap`
 *  takes the step back. */
@Composable
fun Selector(level: Int, stop: Int, count: Int, back: Boolean, modifier: Modifier, onNext: () -> Unit, onStep: (Int) -> Unit, onTap: () -> Unit) {
    when {
        back || level <= 1 || count < 2 -> Key({ if (back) onTap() else onNext() }, modifier) { KeyIcon(if (back) Icon.LEFT else Icon.RIGHT) }
        level == 2 || count > MAX_SEGMENTS -> Wheel(stop, count, modifier, onStep, onTap)
        else -> Strip(stop, count, modifier, onStep, onTap)
    }
}

/** The grooved wheel: slid, it walks the pages; tapped, it goes back. */
@Composable
private fun Wheel(stop: Int, count: Int, modifier: Modifier, onStep: (Int) -> Unit, onTap: () -> Unit) {
    val ink = LocalInk.current
    val density = LocalDensity.current.density
    val step = STEP_DP * density
    var groove by remember { mutableFloatStateOf(0f) }
    var dragging by remember { mutableStateOf(false) }
    var startStop by remember { mutableIntStateOf(0) }
    var startGroove by remember { mutableFloatStateOf(0f) }
    var dx by remember { mutableFloatStateOf(0f) }
    Canvas(
        modifier.fillMaxSize().border(1.5.dp, if (dragging) Color.White else ink)
            .pointerInput(Unit) { detectTapGestures { onTap() } }
            .pointerInput(count) {
                detectHorizontalDragGestures(
                    onDragStart = { dragging = true; startStop = stop; startGroove = groove; dx = 0f },
                    onDragEnd = { dragging = false; groove = startGroove + (stop - startStop) * step; if (stop != startStop) Sfx.powerOn() },
                    onDragCancel = { dragging = false },
                ) { change, amount ->
                    change.consume()
                    val min = -startStop * step - step * 0.4f
                    val max = (count - 1 - startStop) * step + step * 0.4f
                    dx = (dx + amount).coerceIn(min, max)
                    groove = startGroove + dx
                    onStep(startStop + (dx / step).toInt())
                }
            },
    ) {
        // thin ridges that roll with the finger, like a thumb wheel, fading at the ends
        val gap = 9 * density
        var x = ((groove % gap) + gap) % gap
        while (x < size.width) {
            drawRect(ink.copy(alpha = 0.85f), Offset(x, 0f), androidx.compose.ui.geometry.Size(1.5f * density, size.height))
            x += gap
        }
        drawRect(Brush.horizontalGradient(0f to Color.Black, 0.22f to Color.Transparent, 0.78f to Color.Transparent, 1f to Color.Black))
    }
}

/** The strip: one segment per page, the one it stands on lit. */
@Composable
private fun Strip(stop: Int, count: Int, modifier: Modifier, onStep: (Int) -> Unit, onTap: () -> Unit) {
    val ink = LocalInk.current
    var width by remember { mutableFloatStateOf(1f) }
    fun at(x: Float) = (x / width * count).toInt().coerceIn(0, count - 1)
    Row(
        modifier.fillMaxSize().border(1.5.dp, ink).padding(3.dp)
            .pointerInput(count, stop) {
                width = size.width.toFloat().coerceAtLeast(1f)
                detectTapGestures { p -> val i = at(p.x); if (i == stop) onTap() else { Sfx.tap(i); onStep(i) } }
            }
            .pointerInput(count) {
                width = size.width.toFloat().coerceAtLeast(1f)
                detectHorizontalDragGestures { change, _ -> change.consume(); onStep(at(change.position.x)) }
            },
    ) {
        repeat(count) { i ->
            Box(
                Modifier.weight(1f).fillMaxHeight().padding(horizontal = 1.5.dp)
                    .background(if (i == stop) ink else ink.copy(alpha = 0.16f)),
            )
        }
    }
}
