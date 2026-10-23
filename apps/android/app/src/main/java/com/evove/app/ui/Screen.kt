package com.evove.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.layout.layoutId
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.min

// The screen every dark page shares, as Screen.svelte built it: the display on
// top, right-aligned; the middle, as wide as a row of the grid and gathered in
// the bottom-right corner; the bar, the grid's bottom row, with its buttons.
// Nothing scrolls: a page that holds more turns its pages.

/** The one color of the screen: outlines, icons and the wash of what is pressed. */
val LocalInk = staticCompositionLocalOf { Ink.act }

val Number.remDp: Dp get() = (toFloat() * 18f).dp

/** The grid's square, and how tall the middle is, for a page to cut its lists. */
data class BodyInfo(val unit: Dp, val height: Dp, val width: Dp)

/** The grid's square on a screen `width` wide. */
@Composable
fun unitFor(width: Dp): Dp = min(width, PHONE_WIDTH_DP.dp) * SHRINK / GRID_COLS

@Composable
fun DarkScreen(
    ink: Color,
    display: Float = 0.16f,
    displayContent: @Composable ColumnScope.() -> Unit,
    bar: @Composable BarScope.() -> Unit,
    body: @Composable ColumnScope.(BodyInfo) -> Unit,
) {
    CompositionLocalProvider(LocalInk provides ink) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
            val unit = unitFor(maxWidth)
            val row = min(unit * GRID_COLS, maxWidth)
            val tall = maxHeight
            Column(Modifier.fillMaxSize()) {
                Column(
                    Modifier.fillMaxWidth().height(tall * display).clipToBounds().padding(horizontal = 0.4.remDp, vertical = 0.5.remDp),
                    verticalArrangement = Arrangement.spacedBy(0.35.remDp, Alignment.Bottom),
                    horizontalAlignment = Alignment.End,
                    content = displayContent,
                )
                BoxWithConstraints(Modifier.weight(1f).width(row).align(Alignment.End).clipToBounds()) {
                    val info = BodyInfo(unit, maxHeight, maxWidth)
                    Column(
                        Modifier.fillMaxSize().padding(6.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.Bottom),
                    ) { body(info) }
                }
                Bar(unit, row, Modifier.align(Alignment.End), bar)
            }
        }
    }
}

/** Where a button of the bar stands: from column `col` (1–6), `span` wide. */
data class BarSlot(val col: Int, val span: Int)

class BarScope {
    fun Modifier.at(col: Int, span: Int = 1): Modifier = this.layoutId(BarSlot(col, span))
}

/** The grid's bottom row: six columns, 12dp apart, home always in the last. */
@Composable
fun Bar(unit: Dp, row: Dp, modifier: Modifier = Modifier, content: @Composable BarScope.() -> Unit) {
    val scope = remember { BarScope() }
    val gap = with(LocalDensity.current) { 12.dp.roundToPx() }
    Layout(
        content = { scope.content() },
        modifier = modifier.width(row).height(unit).padding(6.dp),
    ) { measurables, constraints ->
        val w = constraints.maxWidth
        val h = constraints.maxHeight
        val col = (w - 5 * gap) / 6f
        val placed = measurables.map { m ->
            val slot = m.layoutId as? BarSlot ?: BarSlot(1, 1)
            val width = (slot.span * col + (slot.span - 1) * gap).toInt()
            val x = ((slot.col - 1) * (col + gap)).toInt()
            m.measure(Constraints.fixed(width.coerceAtLeast(0), h)) to x
        }
        layout(w, h) { placed.forEach { (p, x) -> p.place(x, 0) } }
    }
}

/** A button of the bar or of the page: see-through, square-cornered, outlined. */
@Composable
fun Key(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    on: Boolean = false,
    ghost: Boolean = false,
    content: @Composable RowScope.() -> Unit,
) {
    val ink = LocalInk.current
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    Row(
        modifier
            .alpha(if (!enabled) 0.35f else if (ghost) 0.6f else 1f)
            .background(if ((pressed && enabled) || on) ink.copy(alpha = 0.25f) else Color.Transparent)
            .then(if (ghost) Modifier.dashed(ink) else Modifier.border(1.5.dp, ink))
            .clickable(source, null, enabled = enabled, onClick = onClick)
            .padding(horizontal = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(0.4.remDp, Alignment.CenterHorizontally),
        verticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

fun Modifier.dashed(color: Color, width: Dp = 1.5.dp): Modifier = drawBehind {
    val px = width.toPx()
    drawRect(color, topLeft = Offset(px / 2, px / 2), size = size.copy(size.width - px, size.height - px),
        style = Stroke(px, pathEffect = PathEffect.dashPathEffect(floatArrayOf(3 * px, 2 * px))))
}

@Composable
fun KeyIcon(icon: Icon, size: Dp = 20.dp) = IconView(icon, LocalInk.current, size)

@Composable
fun KeyText(text: String, style: TextStyle = Type.key) =
    BasicText(caps(text), style = style.copy(color = LocalInk.current), maxLines = 1, overflow = TextOverflow.Ellipsis)

/** Home: the bar's last square, under the thumb. */
@Composable
fun BarScope.HomeKey(onClick: () -> Unit) {
    Key(onClick, Modifier.at(6)) { KeyIcon(Icon.CIRCLE, 16.dp) }
}

/** A row of a list: a line of text, outlined; a tap opens it. */
@Composable
fun ListRow(
    onClick: (() -> Unit)?,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    dashed: Boolean = false,
    minHeight: Dp = 2.6.remDp,
    background: Color? = null,
    content: @Composable RowScope.() -> Unit,
) {
    val ink = LocalInk.current
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    Row(
        modifier
            .fillMaxWidth()
            .heightIn(min = minHeight)
            .alpha(if (enabled) 1f else 0.35f)
            .background(if (pressed) ink.copy(alpha = 0.25f) else background ?: ink.copy(alpha = 0.08f))
            .then(if (dashed) Modifier.dashed(ink) else Modifier.border(1.5.dp, ink.copy(alpha = 0.7f)))
            .then(if (onClick != null) Modifier.clickable(source, null, enabled = enabled, onClick = onClick) else Modifier)
            .padding(horizontal = 0.7.remDp, vertical = 0.35.remDp),
        horizontalArrangement = Arrangement.spacedBy(0.6.remDp),
        verticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

@Composable
fun RowScope.Grow(text: String, style: TextStyle = Type.row, upper: Boolean = false) =
    BasicText(if (upper) caps(text) else text, Modifier.weight(1f), style = style, maxLines = 1, overflow = TextOverflow.Ellipsis)

@Composable
fun Tag(text: String, color: Color = LocalInk.current) =
    BasicText(text, style = Type.row.copy(fontSize = 0.72.rem, color = color), maxLines = 1)

/** What the display says, in its two sizes. */
@Composable
fun Big(text: String, color: Color = Color.White, size: Float = 1.5f) =
    BasicText(caps(text), style = Type.big.copy(color = color, fontSize = size.rem, textAlign = TextAlign.End))

@Composable
fun Small(text: String) = BasicText(text, style = Type.small.copy(textAlign = TextAlign.End))

/** The display's message: a big first line, small ones after. */
@Composable
fun Message(lines: List<String>) = lines.forEachIndexed { i, l -> if (i == 0) Big(l) else Small(l) }

@Composable
fun Label(text: String, modifier: Modifier = Modifier) =
    BasicText(caps(text), modifier, style = Type.label.copy(color = LocalInk.current.copy(alpha = 0.85f)))

@Composable
fun Empty(text: String) =
    BasicText(text, Modifier.fillMaxWidth().padding(vertical = 0.8.remDp), style = Type.empty.copy(textAlign = TextAlign.End))

/** A box of text to write in. */
@Composable
fun Field(
    value: String,
    onChange: (String) -> Unit,
    placeholder: String,
    modifier: Modifier = Modifier,
    singleLine: Boolean = true,
    maxLength: Int = Int.MAX_VALUE,
    keyboard: KeyboardOptions = KeyboardOptions.Default,
    password: Boolean = false,
) {
    val ink = LocalInk.current
    BasicTextField(
        value,
        { onChange(it.take(maxLength)) },
        modifier
            .fillMaxWidth()
            .background(ink.copy(alpha = 0.06f))
            .border(1.5.dp, ink)
            .padding(horizontal = 0.7.remDp, vertical = 0.6.remDp),
        singleLine = singleLine,
        keyboardOptions = if (password) keyboard.copy(keyboardType = KeyboardType.Password) else keyboard,
        visualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
        textStyle = TextStyle(fontFamily = Mono, fontSize = 0.9.rem, color = Color.White),
        cursorBrush = SolidColor(ink),
        decorationBox = { inner ->
            Box {
                if (value.isEmpty()) BasicText(placeholder, style = TextStyle(fontFamily = Mono, fontSize = 0.9.rem, color = Color.White.copy(alpha = 0.35f)))
                inner()
            }
        },
    )
}

/** Name and value pairs, in an outlined box. */
@Composable
fun Stats(pairs: List<Pair<String, String>>, modifier: Modifier = Modifier, valueStyle: TextStyle = Type.row.copy(fontSize = 0.85.rem)) {
    val ink = LocalInk.current
    Column(
        modifier.fillMaxWidth().border(1.5.dp, ink).padding(0.8.remDp),
        verticalArrangement = Arrangement.spacedBy(0.4.remDp),
    ) {
        for ((k, v) in pairs) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(1.remDp)) {
                BasicText(caps(k), Modifier.weight(1f), style = Type.label.copy(fontSize = 0.7.rem, color = ink, letterSpacing = Type.big.letterSpacing))
                BasicText(v, style = valueStyle.copy(textAlign = TextAlign.End))
            }
        }
    }
}

/** The ticks of where a page stands. */
@Composable
fun Ticks(count: Int, at: Int, modifier: Modifier = Modifier, color: Color = Color.White) {
    Row(modifier.fillMaxHeight().clipToBounds(), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
        repeat(count) { i ->
            Box(Modifier.width(4.dp).height(if (i == at) 16.dp else 10.dp).background(color.copy(alpha = if (i == at) 1f else 0.3f)))
        }
    }
}

// ---------------------------------------------------------------- the frame

/** The frame: a fixed border around the whole interface, inside the screen's
 *  margins, over a black backdrop with a faint band of green sliding up and
 *  down through it, so the screens alternate between black and a glow. */
@Composable
fun Frame(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    val drift = rememberInfiniteTransition(label = "drift")
    val t by drift.animateFloat(
        0f, 1f,
        infiniteRepeatable(tween(12_000, easing = androidx.compose.animation.core.FastOutSlowInEasing), RepeatMode.Reverse),
        label = "band",
    )
    val shape = androidx.compose.foundation.shape.RoundedCornerShape(28.dp)
    Box(
        modifier
            .fillMaxSize()
            .border(1.5.dp, Color.White.copy(alpha = 0.14f), shape)
            .clip(shape)
            .drawBehind {
                // a band three times the frame's height, moved by two thirds of it
                val h = size.height * 3
                val y = -t * h * 0.666f
                drawRect(
                    Brush.verticalGradient(
                        0f to Color.Black, 0.3f to Color.Black, 0.5f to hex("#04200f"), 0.7f to Color.Black, 1f to Color.Black,
                        startY = y, endY = y + h,
                    ),
                )
            },
    ) { content() }
}

/** Runs `block` every `ms` while the composable lives. */
@Composable
fun Ticker(ms: Long, block: () -> Unit) {
    LaunchedEffect(ms) {
        while (true) {
            kotlinx.coroutines.delay(ms)
            block()
        }
    }
}

/** A value that runs from 0 to `to` milliseconds once, from when `key` changes. */
@Composable
fun clockOnce(key: Any?, to: Float): Float {
    val a = remember(key) { Animatable(0f) }
    LaunchedEffect(key) { a.animateTo(to, tween(to.toInt(), easing = LinearEasing)) }
    return a.value
}
