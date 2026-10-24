package com.evove.app.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.setValue
import androidx.compose.runtime.getValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.evove.app.api.Maze
import com.evove.app.ui.Ink
import com.evove.app.ui.hex
import kotlinx.coroutines.delay
import kotlin.math.abs

// The floor's maze seen from inside, as the old dungeon crawlers drew it: a
// grid of blocks, the walls and the floor filled — each floor in its own tone
// of green or grey — fading into the dark the farther they are, a window's
// frame on some walls, doors as wide as a wall. The profile moves a step at a
// time — a step forward, a quarter turn — and whoever waits stands in a room
// as a frame of static. A small map of what was seen sits in the corner.

/** A floor's look: its walls, its floor, and the frames on its walls. */
internal data class Look(val wall: Color, val floor: Color, val frame: Color)

/** One look for each floor of an act: moss, concrete, sea green, blue grey,
 *  olive, graphite. */
internal val LOOKS = listOf(
    Look(hex("#4f7d57"), hex("#22382a"), hex("#a9d8a0")),
    Look(hex("#6d7470"), hex("#2c302e"), hex("#c9d1cc")),
    Look(hex("#3f8a7a"), hex("#1c3a35"), hex("#9fe3d2")),
    Look(hex("#5a6672"), hex("#262c33"), hex("#b8c4cf")),
    Look(hex("#6b7a3e"), hex("#2e341c"), hex("#cfd99a")),
    Look(hex("#45494c"), hex("#1d1f21"), hex("#a3a8ab")),
)

/** North, east, south, west — as the server counts them. */
internal val DIRS = listOf(0 to -1, 1 to 0, 0 to 1, -1 to 0)

/** How far the eye sees, in tiles ahead and to each side. */
private const val DEPTH = 5
private const val SIDE = 3
private const val NEAR = 0.3f

/** Where the profile stands and faces after `moves` (F, L, R, B) from `pos`
 *  facing `face`, and how many steps forward those took; a step into a wall
 *  is not taken. */
internal fun walked(maze: Maze, pos: List<Int>, face: Int, moves: String): Triple<Pair<Int, Int>, Int, Int> {
    var x = pos.getOrElse(0) { 1 }
    var y = pos.getOrElse(1) { 1 }
    var f = face
    var steps = 0
    for (m in moves) when (m) {
        'L' -> f = (f + 3) % 4
        'R' -> f = (f + 1) % 4
        'B' -> f = (f + 2) % 4
        'F' -> {
            val (dx, dy) = DIRS[f]
            if (maze.passable(x + dx, y + dy)) { x += dx; y += dy; steps++ }
        }
    }
    return Triple(x to y, f, steps)
}

/** The turns that face whoever waits from `pos`, when it stands next to them. */
internal fun turnsToBoss(maze: Maze, x: Int, y: Int, face: Int): String {
    val k = DIRS.indexOfFirst { (dx, dy) -> x + dx == maze.boss[0] && y + dy == maze.boss[1] }
    if (k < 0) return ""
    return when ((k - face + 4) % 4) { 1 -> "R"; 2 -> "B"; 3 -> "L"; else -> "" }
}

private class Eye(val w: Float, val h: Float, val back: Float) {
    val cx = w / 2
    val cy = h * 0.5f
    val fx = w * 0.52f
    val fy = h * 0.66f
    fun dist(z: Float) = maxOf(NEAR, z + back)
    fun p(x: Float, y: Float, z: Float) = Offset(cx + x * fx / dist(z), cy + y * fy / dist(z))
}

private fun quad(a: Offset, b: Offset, c: Offset, d: Offset) = Path().apply { moveTo(a.x, a.y); lineTo(b.x, b.y); lineTo(c.x, c.y); lineTo(d.x, d.y); close() }

/** The dark the far things fade into. */
private fun fog(c: Color, dist: Float) = lerp(c, Color.Black, (dist / (DEPTH + 1.5f)).coerceIn(0f, 0.92f))

@Composable
internal fun MazeView(maze: Maze, pos: Pair<Int, Int>, face: Int, look: Look, seen: String, modifier: Modifier, onMove: (Char) -> Unit) {
    // a step forward glides the eye one tile on; a turn is a cut
    val back = remember { Animatable(0f) }
    val last = remember { intArrayOf(pos.first, pos.second) }
    LaunchedEffect(pos) {
        val moved = abs(pos.first - last[0]) + abs(pos.second - last[1]) == 1
        last[0] = pos.first; last[1] = pos.second
        if (moved) {
            back.snapTo(1f)
            back.animateTo(0f, tween(170, easing = FastOutSlowInEasing))
        }
    }
    var tick by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) { delay(90); tick++ }
    }
    Box(
        modifier.clipToBounds().testTag("maze").pointerInput(Unit) {
            var dx = 0f
            var dy = 0f
            detectDragGestures(onDragStart = { dx = 0f; dy = 0f }, onDragEnd = {
                val min = 24.dp.toPx()
                when {
                    abs(dx) > abs(dy) && abs(dx) > min -> onMove(if (dx > 0) 'L' else 'R')
                    dy < -min -> onMove('F')
                    dy > min -> onMove('B')
                }
            }) { change, drag -> change.consume(); dx += drag.x; dy += drag.y }
        },
    ) {
        Canvas(Modifier.fillMaxSize()) { drawMaze(maze, pos, face, look, Eye(size.width, size.height, back.value), tick) }
        MiniMap(maze, pos, face, look, seen, Modifier.align(Alignment.TopEnd).padding(6.dp))
    }
}

private fun DrawScope.drawMaze(maze: Maze, pos: Pair<Int, Int>, face: Int, look: Look, eye: Eye, tick: Int) {
    val (fx, fy) = DIRS[face]
    val (rx, ry) = DIRS[(face + 1) % 4]
    fun world(l: Int, d: Int) = (pos.first + fx * d + rx * l) to (pos.second + fy * d + ry * l)
    fun solid(l: Int, d: Int): Boolean = world(l, d).let { (x, y) -> maze.at(x, y).let { it == '#' || it == 'D' } }
    // the ceiling and, under the floor's tiles, its far dark
    drawRect(fog(look.floor, 3f).copy(alpha = 1f), Offset(0f, eye.cy), Size(size.width, size.height - eye.cy))
    drawRect(lerp(look.floor, Color.Black, 0.8f), Offset.Zero, Size(size.width, eye.cy))
    val line = 1.dp.toPx()
    val first = if (eye.back > 0.01f) -1 else 0
    val order = (-SIDE..SIDE).sortedByDescending { abs(it) }
    for (d in DEPTH downTo first) for (l in order) {
        val (wx, wy) = world(l, d)
        val tile = maze.at(wx, wy)
        val z0 = d.toFloat()
        val z1 = d + 1f
        val x0 = l - 0.5f
        val x1 = l + 0.5f
        if (tile == '#' || tile == 'D') {
            val door = tile == 'D'
            // the side facing the corridor, for a block beside it
            if (l < 0 && !solid(l + 1, d)) wallFace(eye, look, x1, z0, x1, z1, 0.72f, door, window(wx, wy, (face + 1) % 4) && !door, line)
            if (l > 0 && !solid(l - 1, d)) wallFace(eye, look, x0, z1, x0, z0, 0.72f, door, window(wx, wy, (face + 3) % 4) && !door, line)
            // the side facing the eye
            if (z0 + eye.back > NEAR + 0.1f && !solid(l, d - 1)) wallFace(eye, look, x0, z0, x1, z0, 1f, door, window(wx, wy, (face + 2) % 4) && !door, line)
        } else {
            val a = eye.p(x0, 0.5f, z1); val b = eye.p(x1, 0.5f, z1); val c = eye.p(x1, 0.5f, z0); val e = eye.p(x0, 0.5f, z0)
            val floor = quad(a, b, c, e)
            drawPath(floor, fog(look.floor, eye.dist(z0 + 0.5f)))
            drawPath(floor, fog(lerp(look.floor, Color.Black, 0.45f), eye.dist(z0 + 0.5f)), style = Stroke(line))
            val top = quad(eye.p(x0, -0.5f, z1), eye.p(x1, -0.5f, z1), eye.p(x1, -0.5f, z0), eye.p(x0, -0.5f, z0))
            drawPath(top, fog(lerp(look.floor, Color.Black, 0.72f), eye.dist(z0 + 0.5f)))
            if (maze.chests.any { it.getOrNull(0) == wx && it.getOrNull(1) == wy }) chest(eye, l.toFloat(), z0 + 0.5f, line)
            if (wx == maze.boss.getOrNull(0) && wy == maze.boss.getOrNull(1)) waiter(eye, l.toFloat(), z0 + 0.5f, tick, line)
        }
    }
}

/** Whether a wall's side facing `dir` carries a window's frame: the same each
 *  time it is seen. */
private fun window(x: Int, y: Int, dir: Int) = ((x * 73856093) xor (y * 19349663) xor (dir * 83492791)).let { abs(it) % 5 == 0 }

/** A wall's side from (xa, za) to (xb, zb) on the floor, filled, shaded by
 *  `light`; a door on it, or a window's frame. */
private fun DrawScope.wallFace(eye: Eye, look: Look, xa: Float, za: Float, xb: Float, zb: Float, light: Float, door: Boolean, window: Boolean, line: Float) {
    val dist = eye.dist((za + zb) / 2)
    fun at(u: Float, v: Float) = eye.p(xa + (xb - xa) * u, v - 0.5f, za + (zb - za) * u)
    fun part(u0: Float, v0: Float, u1: Float, v1: Float) = quad(at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1))
    val wall = fog(lerp(Color.Black, look.wall, light), dist)
    val whole = part(0f, 0f, 1f, 1f)
    drawPath(whole, wall)
    drawPath(whole, fog(lerp(look.wall, Color.Black, 0.5f), dist), style = Stroke(line))
    val frame = fog(look.frame, dist)
    if (door) {
        // as wide as the wall: a frame around it, the leaf darker, a handle
        val leaf = part(0.1f, 0.12f, 0.9f, 1f)
        drawPath(leaf, fog(lerp(look.wall, Color.Black, 0.55f), dist))
        drawPath(leaf, frame, style = Stroke(line * 2.2f))
        drawPath(part(0.18f, 0.2f, 0.82f, 0.52f), frame.copy(alpha = 0.5f), style = Stroke(line))
        drawPath(part(0.18f, 0.6f, 0.82f, 0.92f), frame.copy(alpha = 0.5f), style = Stroke(line))
        drawPath(part(0.74f, 0.56f, 0.8f, 0.6f), frame)
    } else if (window) {
        val glass = part(0.25f, 0.2f, 0.75f, 0.58f)
        drawPath(glass, fog(lerp(look.wall, Color.Black, 0.7f), dist))
        drawPath(glass, frame, style = Stroke(line * 2f))
        drawLine(frame, at(0.5f, 0.2f), at(0.5f, 0.58f), line * 1.4f)
        drawLine(frame, at(0.25f, 0.39f), at(0.75f, 0.39f), line * 1.4f)
    }
}

/** A chest on the floor at the middle of its tile. */
private fun DrawScope.chest(eye: Eye, x: Float, z: Float, line: Float) {
    val dist = eye.dist(z)
    val gold = fog(Ink.gold, dist)
    val front = quad(eye.p(x - 0.18f, 0.28f, z - 0.15f), eye.p(x + 0.18f, 0.28f, z - 0.15f), eye.p(x + 0.18f, 0.5f, z - 0.15f), eye.p(x - 0.18f, 0.5f, z - 0.15f))
    val top = quad(eye.p(x - 0.18f, 0.28f, z + 0.15f), eye.p(x + 0.18f, 0.28f, z + 0.15f), eye.p(x + 0.18f, 0.28f, z - 0.15f), eye.p(x - 0.18f, 0.28f, z - 0.15f))
    drawPath(top, fog(lerp(Ink.gold, Color.Black, 0.55f), dist))
    drawPath(front, fog(lerp(Ink.gold, Color.Black, 0.7f), dist))
    drawPath(top, gold, style = Stroke(line * 1.4f))
    drawPath(front, gold, style = Stroke(line * 1.4f))
}

/** Whoever waits: a frame of static standing on the floor, its shadow under it. */
private fun DrawScope.waiter(eye: Eye, x: Float, z: Float, tick: Int, line: Float) {
    val dist = eye.dist(z)
    val s0 = eye.p(x - 0.32f, 0.5f, z + 0.1f)
    val s1 = eye.p(x + 0.32f, 0.5f, z - 0.1f)
    drawOval(Color.Black.copy(alpha = 0.7f), Offset(s0.x, s1.y - (s0.y - s1.y)), Size(s1.x - s0.x, (s0.y - s1.y) * 2f + line))
    val a = eye.p(x - 0.24f, -0.28f, z)
    val b = eye.p(x + 0.24f, 0.45f, z)
    val cols = 8
    val rows = 12
    val cw = (b.x - a.x) / cols
    val ch = (b.y - a.y) / rows
    val rnd = java.util.Random(tick * 131L + 7)
    val dim = 1f - (dist / (DEPTH + 2f)).coerceIn(0f, 0.7f)
    drawRect(Color.Black, a, Size(b.x - a.x, b.y - a.y))
    for (i in 0 until cols) for (j in 0 until rows) {
        drawRect(Color.White.copy(alpha = (0.1f + rnd.nextFloat() * 0.55f) * dim), Offset(a.x + i * cw, a.y + j * ch), Size(cw, ch))
    }
    drawRect(Ink.enemy.copy(alpha = dim), a, Size(b.x - a.x, b.y - a.y), style = Stroke(line * 1.5f))
}

/** What was seen of the floor, small: walls, floor and doors, the chests and
 *  whoever waits once seen, and the profile as an arrow. */
@Composable
private fun MiniMap(maze: Maze, pos: Pair<Int, Int>, face: Int, look: Look, seen: String, modifier: Modifier) {
    val n = maze.size
    if (n == 0) return
    val cell = 4.dp
    Canvas(modifier.size(cell * n).background(Color.Black.copy(alpha = 0.7f)).border(1.dp, look.frame.copy(alpha = 0.5f)).testTag("minimap")) {
        val c = size.width / n
        for (y in 0 until n) for (x in 0 until n) {
            if (seen.getOrNull(y * n + x) != '1') continue
            val color = when (maze.at(x, y)) {
                '#' -> look.wall
                'D' -> look.frame
                else -> look.floor
            }
            drawRect(color, Offset(x * c, y * c), Size(c, c))
            if (maze.chests.any { it.getOrNull(0) == x && it.getOrNull(1) == y }) drawRect(Ink.gold, Offset(x * c + c * 0.2f, y * c + c * 0.2f), Size(c * 0.6f, c * 0.6f))
            if (maze.boss.getOrNull(0) == x && maze.boss.getOrNull(1) == y) drawRect(Ink.enemy, Offset(x * c, y * c), Size(c, c))
        }
        val (dx, dy) = DIRS[face]
        val ctr = Offset((pos.first + 0.5f) * c, (pos.second + 0.5f) * c)
        val tip = Offset(ctr.x + dx * c * 0.9f, ctr.y + dy * c * 0.9f)
        val l = Offset(ctr.x - dy * c * 0.6f - dx * c * 0.5f, ctr.y + dx * c * 0.6f - dy * c * 0.5f)
        val r = Offset(ctr.x + dy * c * 0.6f - dx * c * 0.5f, ctr.y - dx * c * 0.6f - dy * c * 0.5f)
        drawPath(Path().apply { moveTo(tip.x, tip.y); lineTo(l.x, l.y); lineTo(r.x, r.y); close() }, Color.White)
    }
}
