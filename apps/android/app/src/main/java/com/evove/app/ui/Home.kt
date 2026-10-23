package com.evove.app.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.api.Line
import com.evove.app.api.Tile
import com.evove.app.sound.Sfx
import kotlinx.coroutines.delay

private const val HOME_COLS = 5f
private const val HOME_ROWS = 7f

/** The modules the app knows how to draw, and how they were dressed before the
 *  engine said so: the home falls back on them when the engine has never
 *  answered on this device. Nothing is written on them: a module is known by
 *  its glyph and its color. */
enum class HomeOption(val kind: String, val id: String, val label: String, val color: Color, val tone: Int, val glyph: Glyph, private val grid: List<Pair<Float, Float>>) {
    ACT("act", "act", "agir", Ink.act, 1, Glyphs.act, listOf(2.75f to 0f, 5f to 0f, 5f to 7f, 3.25f to 7f)),
    ATTRIBUTES("attributes", "attributes", "atributos", Ink.attributes, 5, Glyphs.attributes, listOf(0f to 0f, 1.75f to 0f, 1.25f to 2f, 0f to 2f)),
    ROKO("entity", "roko", "roko", Ink.roko, 3, Glyphs.roko, listOf(1.75f to 0f, 2.75f to 0f, 2.893f to 2f, 1.25f to 2f)),
    SHOP("shop", "shop", "shop", Ink.shop, 2, Glyphs.shop, listOf(0f to 2f, 1.75f to 2f, 1.25f to 4f, 0f to 4f)),
    LOGS("agenda", "agenda", "agenda", Ink.agenda, 4, Glyphs.logs, listOf(1.75f to 2f, 2.893f to 2f, 3.036f to 4f, 1.25f to 4f)),
    BUILD("build", "build", "construir", Ink.build, 7, Glyphs.build, listOf(0f to 4f, 1.4f to 4f, 1.7f to 7f, 0.214f to 7f)),
    JOURNEY("journey", "journey", "jornada", Ink.journey, 6, Glyphs.journey, listOf(1.4f to 4f, 3.036f to 4f, 3.25f to 7f, 1.7f to 7f));

    fun asTile(delay: Int) = Tile(id, kind, label, "", "", tone, grid.map { (x, y) -> listOf(x.toDouble(), y.toDouble()) }, delay)

    companion object {
        /** Every module, laid out as the home was before the engine. */
        val fallback: List<Tile> get() = entries.mapIndexed { i, o -> o.asTile(intArrayOf(0, 340, 260, 190, 70, 230, 130)[i]) }

        fun of(kind: String): HomeOption? = entries.find { it.kind == kind }
    }
}

/** How a tile is drawn: the engine's color and glyph, or its kind's. */
fun Tile.ink(): Color = runCatching { hex(color) }.getOrNull() ?: HomeOption.of(kind)?.color ?: Ink.act
fun Tile.mark(): Glyph = if (glyph.isNotEmpty()) Glyphs.byName(glyph) else HomeOption.of(kind)?.glyph ?: Glyphs.act

/** The color of who speaks. */
fun voiceInk(entity: String?): Color = when (entity) {
    "roko" -> Ink.roko
    "eve" -> Ink.eve
    else -> Color.White
}

/** The tile home: the modules of this session, and above them, where a thumb
 *  does not reach, the last thing an entity said, typed out. A tap on it puts
 *  it away; a long press there opens the accounts. */
@Composable
fun HomeScreen(tiles: List<Tile>, hint: String?, said: Line?, onOpen: (Tile) -> Unit, onDismiss: () -> Unit, onAccounts: () -> Unit) {
    // the screen comes on with a sound, when one has been allowed (after a tap)
    LaunchedEffect(Unit) { Sfx.powerOn() }
    val density = LocalDensity.current.density
    BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
        val w = constraints.maxWidth.toFloat()
        val h = constraints.maxHeight.toFloat()
        val aw = HOME_COLS * gridUnit(w, density)
        val ah = aw * HOME_ROWS / HOME_COLS
        val top = h - ah
        val cells = remember(tiles, w, h) {
            val left = w - aw
            tiles.map { t ->
                val pts = t.polygon.map { Offset(left + (it[0].toFloat() / HOME_COLS) * aw, top + (it[1].toFloat() / HOME_ROWS) * ah) }
                val shape = inset(pts, GRID_GAP_DP * density)
                DrawnCell(
                    shape,
                    (shape.minOf { it.x } + shape.maxOf { it.x }) / 2,
                    (shape.minOf { it.y } + shape.maxOf { it.y }) / 2,
                    t.ink(),
                    t.delay,
                    fresh = t.fresh,
                )
            }
        }
        Cells(
            cells,
            key = tiles.map { it.id to it.polygon },
            modifier = Modifier.fillMaxSize(),
            tubeMs = 500f,
            settleMs = 400f,
            hint = tiles.indexOfFirst { it.id == hint },
            onDown = { Sfx.tap(tiles[it].tone) },
            onTap = { onOpen(tiles[it]) },
        ) { i, c, alpha ->
            val cw = c.shape.maxOf { it.x } - c.shape.minOf { it.x }
            val ch = c.shape.maxOf { it.y } - c.shape.minOf { it.y }
            val side = maxOf(20 * density, minOf(cw * 0.45f, ch * 0.45f, 64 * density))
            drawGlyph(tiles[i].mark(), Offset(c.cx - side / 2, c.cy - side / 2), side, c.color.copy(alpha = alpha), stroke = 2.4f * density)
        }
        // over the canvas, which would take its touches, and above the tiles
        Said(said, Modifier.fillMaxWidth().height(with(LocalDensity.current) { (top - 8 * density).coerceAtLeast(0f).toDp() }), onDismiss, onAccounts)
        // the way out of any evove, however little of it is open: faint, in the
        // corner, to the accounts — switch, create, start over, delete
        Box(
            Modifier.align(Alignment.TopEnd).size(44.dp).clickable { Sfx.tap(5); onAccounts() },
            contentAlignment = Alignment.Center,
        ) { IconView(Icon.LIST, Color.White.copy(alpha = 0.28f), 20.dp) }
    }
}

/** The display above the tiles: who spoke, and what, a letter at a time. */
@Composable
private fun Said(line: Line?, modifier: Modifier, onDismiss: () -> Unit, onAccounts: () -> Unit) {
    var typed by remember(line) { mutableStateOf("") }
    LaunchedEffect(line) {
        val text = line?.text ?: return@LaunchedEffect
        for (i in 1..text.length) {
            delay(32)
            typed = text.take(i)
            if (i % 4 == 0) Sfx.tap(i % 10)
        }
    }
    val blink = rememberInfiniteTransition(label = "caret")
    val caret by blink.animateFloat(1f, 0f, infiniteRepeatable(tween(1000, easing = LinearEasing), RepeatMode.Restart), label = "on")
    Box(
        modifier.pointerInput(line) {
            detectTapGestures(onTap = { if (line != null) { Sfx.tap(0); onDismiss() } }, onLongPress = { Sfx.tap(5); onAccounts() })
        }.padding(horizontal = 0.5.remDp, vertical = 0.8.remDp),
        contentAlignment = Alignment.BottomEnd,
    ) {
        if (line != null) Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(0.4.remDp)) {
            val ink = voiceInk(line.entity)
            if (line.entity != "system") BasicText(caps(line.entity), style = TextStyle(fontFamily = Display, fontSize = 0.7.rem, letterSpacing = 0.3.em, color = ink.copy(alpha = 0.7f)))
            BasicText(
                buildAnnotatedString {
                    append(if (line.entity == "eve") typed else caps(typed))
                    withStyle(SpanStyle(color = if (caret > 0.5f || typed.length < line.text.length) ink else Color.Transparent)) { append("▍") }
                },
                style = TextStyle(fontFamily = Display, fontSize = 1.05.rem, fontWeight = FontWeight.Medium, lineHeight = 1.5.em,
                    letterSpacing = 0.06.em, color = Color.White, textAlign = TextAlign.End),
            )
        }
    }
}
