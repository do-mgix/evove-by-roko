package com.evove.app.ui

import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import com.evove.app.Prefs
import com.evove.app.api.currentPeriod
import com.evove.app.sound.Sfx
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

private const val HOME_COLS = 5f
private const val HOME_ROWS = 7f

/** The home's options. Nothing is written on them: an option is known by its
 *  glyph and its color. They tile an area in the bottom-right corner, a grid of
 *  squares five across and seven down; their shapes share their vertices. */
enum class HomeOption(val label: String, val color: Color, val tone: Int, val glyph: Glyph, grid: List<Pair<Float, Float>>) {
    ACT("agir", Ink.act, 1, Glyphs.act, listOf(2.75f to 0f, 5f to 0f, 5f to 7f, 3.25f to 7f)),
    ATTRIBUTES("atributos", Ink.attributes, 5, Glyphs.attributes, listOf(0f to 0f, 1.75f to 0f, 1.25f to 2f, 0f to 2f)),
    ROKO("roko", Ink.roko, 3, Glyphs.roko, listOf(1.75f to 0f, 2.75f to 0f, 2.893f to 2f, 1.25f to 2f)),
    SHOP("shop", Ink.shop, 2, Glyphs.shop, listOf(0f to 2f, 1.75f to 2f, 1.25f to 4f, 0f to 4f)),
    LOGS("agenda", Ink.agenda, 4, Glyphs.logs, listOf(1.75f to 2f, 2.893f to 2f, 3.036f to 4f, 1.25f to 4f)),
    BUILD("construir", Ink.build, 7, Glyphs.build, listOf(0f to 4f, 1.4f to 4f, 1.7f to 7f, 0.214f to 7f)),
    JOURNEY("jornada", Ink.journey, 6, Glyphs.journey, listOf(1.4f to 4f, 3.036f to 4f, 3.25f to 7f, 1.7f to 7f));

    /** Its shape in the unit square, clockwise from the top left. */
    val polygon: List<Offset> = grid.map { (x, y) -> Offset(x / HOME_COLS, y / HOME_ROWS) }

    /** Acts logged before it appears. */
    val unlockAt: Int get() = when (this) {
        ACT, SHOP, ATTRIBUTES -> 0
        LOGS -> 1
        JOURNEY -> 3
        ROKO -> 5
        BUILD -> 10
    }

    /** When it comes on, at its own moment: an uneven order reads as a machine. */
    val delayMs: Int get() = when (this) {
        ACT -> 0; LOGS -> 70; JOURNEY -> 130; SHOP -> 190; BUILD -> 230; ROKO -> 260; ATTRIBUTES -> 340
    }

    companion object {
        fun unlockedFor(acts: Int): Set<HomeOption> = entries.filter { acts >= it.unlockAt }.toSet()
    }
}

/** How the home is used, counted on the device: which option is opened in
 *  which part of the day. The home lights the one most opened at this hour. */
object Usage {
    private const val KEY = "evove_usage"

    private fun read(): MutableMap<String, MutableMap<String, Int>> = try {
        Json.parseToJsonElement(Prefs.string(KEY) ?: "{}").jsonObject.mapValues { (_, v) ->
            v.jsonObject.mapValues { it.value.jsonPrimitive.int }.toMutableMap()
        }.toMutableMap()
    } catch (_: Exception) {
        mutableMapOf()
    }

    fun recordOpen(o: HomeOption) {
        val counts = read()
        val here = counts.getOrPut(currentPeriod()) { mutableMapOf() }
        here[o.name] = (here[o.name] ?: 0) + 1
        Prefs.putString(KEY, JsonObject(counts.mapValues { (_, m) -> JsonObject(m.mapValues { kotlinx.serialization.json.JsonPrimitive(it.value) }) }).toString())
    }

    fun suggested(among: Set<HomeOption>): HomeOption? {
        val here = read()[currentPeriod()] ?: emptyMap()
        val best = here.entries.filter { e -> among.any { it.name == e.key } }.maxByOrNull { it.value }
        return best?.let { HomeOption.valueOf(it.key) } ?: HomeOption.ACT.takeIf { it in among }
    }
}

/** The tile home. */
@Composable
fun HomeScreen(visible: Set<HomeOption>, fresh: Set<HomeOption>, hint: HomeOption?, onOpen: (HomeOption) -> Unit) {
    // the screen comes on with a sound, when one has been allowed (after a tap)
    LaunchedEffect(Unit) { Sfx.powerOn() }
    val density = LocalDensity.current.density
    BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val shown = HomeOption.entries.filter { it in visible }
        val cells = remember(shown, fresh, w, h) {
            val aw = HOME_COLS * gridUnit(w, density)
            val ah = aw * HOME_ROWS / HOME_COLS
            val left = w - aw
            val top = h - ah
            shown.map { o ->
                val shape = inset(o.polygon.map { Offset(left + it.x * aw, top + it.y * ah) }, GRID_GAP_DP * density)
                DrawnCell(
                    shape,
                    (shape.minOf { it.x } + shape.maxOf { it.x }) / 2,
                    (shape.minOf { it.y } + shape.maxOf { it.y }) / 2,
                    o.color,
                    o.delayMs,
                    fresh = o in fresh,
                )
            }
        }
        Cells(
            cells,
            key = shown,
            modifier = Modifier.fillMaxSize(),
            tubeMs = 500f,
            settleMs = 400f,
            hint = shown.indexOf(hint),
            onDown = { Sfx.tap(shown[it].tone) },
            onTap = { onOpen(shown[it]) },
        ) { i, c, alpha ->
            val cw = c.shape.maxOf { it.x } - c.shape.minOf { it.x }
            val ch = c.shape.maxOf { it.y } - c.shape.minOf { it.y }
            val side = maxOf(20 * density, minOf(cw * 0.45f, ch * 0.45f, 64 * density))
            drawGlyph(shown[i].glyph, Offset(c.cx - side / 2, c.cy - side / 2), side, c.color.copy(alpha = alpha), stroke = 2.4f * density)
        }
    }
}
