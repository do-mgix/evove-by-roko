package com.evove.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.min
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.evove.app.sound.Sfx

// The long pages — the profile, the attributes and actions, the calendar, the
// login — in the dark screen's terms. They were white pages, with grey lines and
// one teal accent, and they keep what made them pages: they scroll, since what
// they hold does not fit the grid. Everything else is the dark screen's: the
// display on top with the glyph of the module they belong to, outlines in its
// color, monospaced text, and the bar at the bottom with the way back.

val paperText = TextStyle(fontFamily = Mono, fontSize = 0.8.rem, color = Paper.text)
val paperMuted = TextStyle(fontFamily = Mono, fontSize = 0.7.rem, color = Paper.muted)

/** A color moved toward black by 30%, as the header marks were drawn. */
fun darker(c: Color, t: Float = 0.3f) = Color(c.red * (1 - t), c.green * (1 - t), c.blue * (1 - t))

/** A long page: the display, a scrolling column under it, and the bar with the
 *  way back — the bar's first two squares, as in every screen. */
@Composable
fun PaperPage(option: HomeOption?, title: String, onBack: () -> Unit, scroll: Boolean = true, content: @Composable ColumnScope.() -> Unit) {
    val ink = option?.color ?: Ink.act
    CompositionLocalProvider(LocalInk provides ink) {
        BoxWithConstraints(Modifier.fillMaxSize().padding(10.dp)) {
            val unit = unitFor(maxWidth)
            val row = min(unit * GRID_COLS, maxWidth)
            Column(Modifier.fillMaxSize()) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 0.4.remDp, vertical = 0.6.remDp),
                    horizontalArrangement = Arrangement.spacedBy(0.7.remDp, Alignment.End),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    BasicText(caps(title), style = TextStyle(fontFamily = Display, fontWeight = FontWeight.Medium, fontSize = 0.95.rem, letterSpacing = 0.2.em, color = Color.White))
                    if (option != null) GlyphView(option.glyph, ink, 1.6.remDp, stroke = 1.7f)
                }
                Column(
                    Modifier.weight(1f).fillMaxWidth().then(if (scroll) Modifier.verticalScroll(rememberScrollState()) else Modifier)
                        .padding(horizontal = 0.4.remDp, vertical = 0.5.remDp),
                    verticalArrangement = Arrangement.spacedBy(0.9.remDp),
                    content = content,
                )
                Bar(unit, row, Modifier.align(Alignment.End)) {
                    Key({ Sfx.tap(0); onBack() }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
                }
            }
        }
    }
}

/** A section of a long page: its name, and an outline around it. */
@Composable
fun PaperCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    val ink = LocalInk.current
    Column(
        Modifier.fillMaxWidth().border(1.5.dp, ink.copy(alpha = 0.55f)).padding(horizontal = 0.8.remDp, vertical = 0.75.remDp),
        verticalArrangement = Arrangement.spacedBy(0.5.remDp),
    ) {
        BasicText(caps(title), style = Type.label.copy(color = ink))
        content()
    }
}

/** A name and its value, on one line of a card. */
@Composable
fun PaperRow(name: String, value: String, note: String? = null, action: Pair<String, () -> Unit>? = null) {
    Row(horizontalArrangement = Arrangement.spacedBy(0.75.remDp), verticalAlignment = Alignment.Top) {
        BasicText(caps(name), Modifier.widthIn(min = 6.remDp), style = paperMuted.copy(fontSize = 0.66.rem, letterSpacing = 0.06.em))
        Column(Modifier.weight(1f)) {
            BasicText(value, style = paperText)
            if (note != null) BasicText(note, style = paperMuted.copy(fontSize = 0.66.rem))
            if (action != null) PaperInline(action.first, action.second)
        }
    }
}

@Composable
fun PaperInline(text: String, onClick: () -> Unit) =
    BasicText(caps(text), Modifier.clickable { Sfx.tap(4); onClick() }.padding(vertical = 3.dp), style = paperMuted.copy(fontSize = 0.66.rem, color = LocalInk.current, letterSpacing = 0.06.em))

@Composable
fun PaperField(
    value: String,
    onChange: (String) -> Unit,
    placeholder: String,
    password: Boolean = false,
    type: KeyboardType = KeyboardType.Text,
    actions: KeyboardActions = KeyboardActions.Default,
    singleLine: Boolean = true,
    modifier: Modifier = Modifier,
) {
    val ink = LocalInk.current
    BasicTextField(
        value, onChange,
        modifier.fillMaxWidth().padding(bottom = 0.5.remDp)
            .background(ink.copy(alpha = 0.06f)).border(1.5.dp, ink).padding(horizontal = 0.7.remDp, vertical = 0.6.remDp),
        singleLine = singleLine,
        textStyle = TextStyle(fontFamily = Mono, fontSize = 0.9.rem, color = Color.White),
        cursorBrush = SolidColor(ink),
        visualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
        keyboardOptions = KeyboardOptions(keyboardType = if (password) KeyboardType.Password else type, imeAction = if (singleLine) ImeAction.Done else ImeAction.Default),
        keyboardActions = actions,
        decorationBox = { inner ->
            Box {
                if (value.isEmpty()) BasicText(placeholder, style = TextStyle(fontFamily = Mono, fontSize = 0.9.rem, color = Color.White.copy(alpha = 0.35f)))
                inner()
            }
        },
    )
}

/** A button of the long pages: the dark screen's key, a line of text in it. */
@Composable
fun PaperButton(text: String, enabled: Boolean = true, danger: Boolean = false, ghost: Boolean = false, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val ink = if (danger) Ink.danger else LocalInk.current
    CompositionLocalProvider(LocalInk provides ink) {
        Key({ Sfx.tap(if (danger) 0 else 6); onClick() }, modifier.fillMaxWidth().heightIn(min = 2.6.remDp), enabled = enabled, ghost = ghost) {
            KeyText(text)
        }
    }
}

@Composable
fun PaperError(text: String?) {
    if (text != null) BasicText(caps(text), style = paperText.copy(fontSize = 0.75.rem, color = Paper.error))
}

/** A modal over the page: a title, a close, and its body, outlined in the
 *  page's color on black. */
@Composable
fun PaperModal(title: String, onClose: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    val ink = LocalInk.current
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        CompositionLocalProvider(LocalInk provides ink) {
            Column(Modifier.padding(0.75.remDp).fillMaxWidth().background(Color.Black).border(1.5.dp, ink)) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 1.remDp, vertical = 0.7.remDp), verticalAlignment = Alignment.CenterVertically) {
                    BasicText(caps(title), Modifier.weight(1f), style = Type.label.copy(color = ink))
                    BasicText("×", Modifier.clickable { Sfx.tap(0); onClose() }.padding(horizontal = 6.dp), style = TextStyle(fontFamily = Mono, fontSize = 1.3.rem, color = ink))
                }
                Box(Modifier.fillMaxWidth().height(1.5.dp).background(ink.copy(alpha = 0.5f)))
                Column(
                    Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 1.remDp, vertical = 0.9.remDp),
                    verticalArrangement = Arrangement.spacedBy(0.6.remDp),
                    content = content,
                )
            }
        }
    }
}

/** Marks toward the next rank: a bar cut into one segment per mark, rounded
 *  only at its ends, the count floating in the middle. `from` makes the
 *  segments past it blink, where the bar just grew. */
@Composable
fun MarkBar(
    marks: Int, need: Int, height: Dp = 16.dp, gold: Boolean = false, from: Int? = null, label: String? = null,
    modifier: Modifier = Modifier,
    /** makes each segment a button: tapping the n-th picks n */
    onPick: ((Int) -> Unit)? = null,
) {
    val segments = maxOf(1, need)
    val filled = marks.coerceIn(0, segments)
    val on = if (gold) Ink.gold else Color.White
    val blink = if (from != null) clockOnce(from, 3000f) else 3000f
    Box(modifier.fillMaxWidth().height(height), contentAlignment = Alignment.Center) {
        val pick = if (onPick != null) Modifier.pointerInput(segments) {
            detectTapGestures { p -> onPick((p.x / size.width * segments).toInt().coerceIn(0, segments - 1) + 1) }
        } else Modifier
        Canvas(Modifier.fillMaxSize().then(pick)) {
            val r = size.height / 2
            val clip = androidx.compose.ui.graphics.Path().apply {
                addRoundRect(androidx.compose.ui.geometry.RoundRect(0f, 0f, size.width, size.height, r, r))
            }
            clipPath(clip) {
                if (segments > 40 && onPick == null) {
                    drawRect(Paper.line)
                    drawRect(on, size = size.copy(width = size.width * filled / segments))
                } else {
                    val gap = 2.dp.toPx()
                    val w = (size.width - gap * (segments - 1)) / segments
                    for (i in 0 until segments) {
                        val fresh = from != null && i >= from && i < filled
                        // blinking: 0.5s a beat, six of them, faint then lit
                        val dim = fresh && blink < 3000f && (blink % 500f) < 250f
                        val c = if (i < filled) on.copy(alpha = if (dim) 0.15f else 1f) else Paper.line
                        drawRect(c, Offset(i * (w + gap), 0f), androidx.compose.ui.geometry.Size(w, size.height))
                    }
                }
            }
        }
        BasicText(label ?: "$filled/$segments", Modifier.alpha(0.95f), style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, color = if (filled * 2 >= segments) Color.Black else Color.White, textAlign = TextAlign.Center))
    }
}
