package com.evove.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Round-capped strokes on a 24×24 grid, and dots. */
class Glyph(d: String, val dots: List<Offset>) {
    val path: Path? = if (d.isBlank()) null else PathParser().parsePathString(d).toPath()
}

private fun g(d: String, vararg dots: Pair<Number, Number>) = Glyph(d, dots.map { Offset(it.first.toFloat(), it.second.toFloat()) })

/** Dot radius on the 24×24 grid. */
const val DOT_R = 1.5f

/** The home's glyphs: each a mutation of what the option used to show, far
 *  enough to need learning, close enough to be learned. */
object Glyphs {
    val act = g("M12 3.5 C12.8 7 11 9.5 12 14 M8.8 8.2 L15.2 6.6", 12 to 19)
    val shop = g("M5.5 9.5 C6.5 18.5 17.5 18.5 18.5 9.5 M8.5 9.5 C8.5 4.5 15.5 4.5 15.5 9.5", 12 to 13.5)
    val roko = g("M3.5 12 C7.5 6.5 16.5 6.5 20.5 12 M7 15.5 C10 18 14 18 17 15.5", 12 to 11.5, 4 to 17.5)
    val logs = g("M6.5 4.5 C5.8 9 7.2 15 6.5 19.5 M6.5 7.5 H16 M6.5 12 C9 11.4 11 12.6 13 12 M6.5 16.5 H18.5", 18.5 to 7.5)
    val attributes = g("M12 21 V12 M12 15 C9 13 7 11 7 5 M12 12 C14 10 17 8 19 4", 7 to 18.5)
    val build = g("M5 19.5 V9 H13.5 M9.5 4.5 H19 V15", 19 to 19.5)
    val journey = g("M7 4.5 C11 4.5 14 6 17 4.5 L7 19.5 C10 18 14 20.5 17 19.5", 12 to 12, 19.5 to 7.5)

    /** A glyph by the name the engine gives it; agir's when it is not one. */
    fun byName(name: String?): Glyph = when (name) {
        "shop" -> shop; "roko" -> roko; "logs" -> logs; "attributes" -> attributes
        "build" -> build; "journey" -> journey
        // every entity wears the same mark, only its color changes; so does none
        "eve", "osso", "zira", "mura", "no", "vela", "coleto", "mute" -> roko
        else -> act
    }
}

/** Generic icons, for buttons that are not one of the home's options. */
enum class Icon(val glyph: Glyph) {
    CIRCLE(g("M5 12 A7 7 0 1 0 19 12 A7 7 0 1 0 5 12 Z")),
    SQUARE(g("M6 6 H18 V18 H6 Z")),
    TRIANGLE(g("M12 5 L19 18 H5 Z")),
    DIAMOND(g("M12 4 L20 12 L12 20 L4 12 Z")),
    PLUS(g("M12 5 V19 M5 12 H19")),
    CROSS(g("M6.5 6.5 L17.5 17.5 M17.5 6.5 L6.5 17.5")),
    RIGHT(g("M5 12 H19 M13 6 L19 12 L13 18")),
    LEFT(g("M19 12 H5 M11 6 L5 12 L11 18")),
    UP(g("M12 19 V5 M6 11 L12 5 L18 11")),
    DOWN(g("M12 5 V19 M6 13 L12 19 L18 13")),
    DOTS(g("", 6 to 12, 12 to 12, 18 to 12)),
    SHUFFLE(g("M4 7 H8 L16 17 H20 M4 17 H8 L16 7 H20 M17.5 4.5 L20 7 L17.5 9.5 M17.5 14.5 L20 17 L17.5 19.5")),
    CHECK(g("M5 12.5 L10 17.5 L19 7")),
    CALENDAR(g("M5 7 H19 V19 H5 Z M5 10.5 H19 M9 4.5 V8 M15 4.5 V8")),
    BOOK(g("M12 6.5 C10.5 5 7.5 5 5 5.5 V18 C7.5 17.5 10.5 17.5 12 19 C13.5 17.5 16.5 17.5 19 18 V5.5 C16.5 5 13.5 5 12 6.5 Z M12 6.5 V19")),
    PENCIL(g("M5 19 L6 15 L15.5 5.5 L18.5 8.5 L9 18 Z M13.5 7.5 L16.5 10.5")),
    TRASH(g("M6 7 H18 M9.5 7 V5 H14.5 V7 M7.5 7 L8.5 19 H15.5 L16.5 7")),
    CLOCK(g("M5 12 A7 7 0 1 0 19 12 A7 7 0 1 0 5 12 Z M12 8 V12 L15 14")),
    PAUSE(g("M9 6 V18 M15 6 V18")),
    PLAY(g("M8 5.5 L18 12 L8 18.5 Z")),
    FLAG(g("M6 20 V4.5 M6 5 H17 L14.5 8.5 L17 12 H6")),
    STAR(g("M12 4 L14.3 9 L19.6 9.5 L15.5 13 L16.8 18.3 L12 15.5 L7.2 18.3 L8.5 13 L4.4 9.5 L9.7 9 Z")),
    HEART(g("M12 19 C5 14 4 10.5 5.5 8 C7 5.6 10.5 5.8 12 8.5 C13.5 5.8 17 5.6 18.5 8 C20 10.5 19 14 12 19 Z")),
    SWORD(g("M14.5 4.5 H19.5 V9.5 L10 19 H7.5 L5 16.5 V14 Z M6.5 12.5 L11.5 17.5 M4.5 19.5 L7 17")),
    SHIELD(g("M12 4 L19 6.5 V11.5 C19 15.5 16 18.5 12 20 C8 18.5 5 15.5 5 11.5 V6.5 Z")),
    BARS(g("M6 19 V12 M12 19 V6 M18 19 V9")),
    USER(g("M12 4.5 A3.5 3.5 0 1 0 12 11.5 A3.5 3.5 0 1 0 12 4.5 Z M5.5 19.5 C6.5 15.5 9 14 12 14 C15 14 17.5 15.5 18.5 19.5")),
    LIST(g("M9 7 H19 M9 12 H19 M9 17 H19", 5 to 7, 5 to 12, 5 to 17)),
    TREE(g("M12 6.5 V10 M12 10 H6.5 V14.5 M12 10 H17.5 V14.5 M12 10 V14.5", 12 to 4.5, 6.5 to 17, 12 to 17, 17.5 to 17)),
    EYE(g("M3.5 12 C7 6.5 17 6.5 20.5 12 C17 17.5 7 17.5 3.5 12 Z", 12 to 12)),
    COIN(g("M5 12 A7 7 0 1 0 19 12 A7 7 0 1 0 5 12 Z M12 8.5 V15.5")),
    CHAT(g("M5 6 H19 V15 H11 L7 18.5 V15 H5 Z")),
    LINK(g("M10 14 L14 10 M8.5 11.5 L6.5 13.5 A3 3 0 0 0 10.5 17.5 L12.5 15.5 M15.5 12.5 L17.5 10.5 A3 3 0 0 0 13.5 6.5 L11.5 8.5")),
    DICE(g("M5.5 5.5 H18.5 V18.5 H5.5 Z", 9 to 9, 15 to 15, 12 to 12)),
    BOLT(g("M13 3.5 L6.5 13 H11.5 L10.5 20.5 L17.5 10.5 H12.5 Z")),
    SCAN(g("M4 8 V4 H8 M16 4 H20 V8 M20 16 V20 H16 M8 20 H4 V16", 12 to 12)),
    AMULET(g("M7 4.5 L12 11 L17 4.5 M12 13 L15.5 16.5 L12 20 L8.5 16.5 Z"));

    companion object {
        /** The icons a built button may wear, in the order a long press walks them. */
        val BUTTON = listOf(CIRCLE, SQUARE, TRIANGLE, DIAMOND, PLUS, CROSS, RIGHT, LEFT, UP, DOWN, DOTS)
    }
}

/** Draws a glyph `side` px wide, its top-left at `topLeft`, its strokes
 *  `stroke` px wide on screen and its dots `dotR` of the 24-grid. */
fun DrawScope.drawGlyph(glyph: Glyph, topLeft: Offset, side: Float, color: Color, stroke: Float, dotR: Float = DOT_R) {
    val k = side / 24f
    translate(topLeft.x, topLeft.y) {
        scale(k, k, pivot = Offset.Zero) {
            glyph.path?.let {
                drawPath(it, color, style = Stroke(width = stroke / k, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
            for (d in glyph.dots) drawCircle(color, dotR, d)
        }
    }
}

/** An icon in the colour given, `size` wide. */
@Composable
fun IconView(icon: Icon, color: Color, size: Dp = 20.dp, modifier: Modifier = Modifier) {
    Canvas(modifier.size(size)) {
        drawGlyph(icon.glyph, Offset.Zero, this.size.width, color, stroke = 1.8f * this.size.width / 24f, dotR = DOT_R * 1.2f)
    }
}

/** A home glyph as a mark, `size` wide. */
@Composable
fun GlyphView(glyph: Glyph, color: Color, size: Dp, stroke: Float = 1.4f, modifier: Modifier = Modifier) {
    Canvas(modifier.size(size)) {
        drawGlyph(glyph, Offset.Zero, this.size.width, color, stroke = stroke * this.size.width / 24f)
    }
}
