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
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.evove.app.sound.Sfx

// The pages read on white, each under the dark page it opens from: the login,
// the profile, the long lists. Arial-like, grey lines, one teal accent.

val paperText = TextStyle(fontFamily = Sans, fontSize = 0.85.rem, color = Paper.text)
val paperMuted = TextStyle(fontFamily = Sans, fontSize = 0.75.rem, color = Paper.muted)

/** The header of a white page: the way back, and the glyph of the tile it
 *  belongs to — or its title, for a page with no tile. */
@Composable
fun ScreenHeader(option: HomeOption?, title: String, onBack: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().background(Color.White).padding(horizontal = 0.9.remDp, vertical = 0.6.remDp),
        horizontalArrangement = Arrangement.spacedBy(0.75.remDp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val source = remember { MutableInteractionSource() }
        val pressed by source.collectIsPressedAsState()
        Box(
            Modifier.size(2.2.remDp).border(1.dp, if (pressed) Paper.accent else Paper.line, RoundedCornerShape(3.dp))
                .clickable(source, null) { Sfx.tap(0); onBack() },
            contentAlignment = Alignment.Center,
        ) { BasicText("‹", style = TextStyle(fontFamily = Sans, fontSize = 1.3.rem, color = if (pressed) Paper.accent else Paper.soft)) }
        if (option != null) GlyphView(option.glyph, darker(option.color), 1.6.remDp, stroke = 1.7f)
        else BasicText(caps(title), style = TextStyle(fontFamily = Display, fontWeight = FontWeight.Medium, fontSize = 0.85.rem, letterSpacing = 0.2.em, color = Paper.text))
    }
    Box(Modifier.fillMaxWidth().height(1.dp).background(Paper.line))
}

/** A color moved toward black by 30%, as the header marks are drawn. */
fun darker(c: Color, t: Float = 0.3f) = Color(c.red * (1 - t), c.green * (1 - t), c.blue * (1 - t))

/** A white page: its header, and a scrolling column under it. */
@Composable
fun PaperPage(option: HomeOption?, title: String, onBack: () -> Unit, scroll: Boolean = true, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().background(Color.White)) {
        ScreenHeader(option, title, onBack)
        Column(
            Modifier.weight(1f).fillMaxWidth().then(if (scroll) Modifier.verticalScroll(rememberScrollState()) else Modifier).padding(1.remDp),
            verticalArrangement = Arrangement.spacedBy(1.remDp),
            content = content,
        )
    }
}

/** A section of a white page. */
@Composable
fun PaperCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier.fillMaxWidth().border(1.dp, Paper.line, RoundedCornerShape(6.dp)).padding(horizontal = 1.remDp, vertical = 0.85.remDp),
        verticalArrangement = Arrangement.spacedBy(0.5.remDp),
    ) {
        BasicText(caps(title), style = paperMuted.copy(fontSize = 0.7.rem, letterSpacing = 0.1.em))
        content()
    }
}

/** A name and its value, on one line of a card. */
@Composable
fun PaperRow(name: String, value: String, note: String? = null, action: Pair<String, () -> Unit>? = null) {
    Row(horizontalArrangement = Arrangement.spacedBy(0.75.remDp), verticalAlignment = Alignment.Top) {
        BasicText(name, Modifier.widthIn(min = 6.remDp), style = paperMuted)
        Column(Modifier.weight(1f)) {
            BasicText(value, style = paperText)
            if (note != null) BasicText(note, style = paperMuted.copy(fontSize = 0.7.rem))
            if (action != null) PaperInline(action.first, action.second)
        }
    }
}

@Composable
fun PaperInline(text: String, onClick: () -> Unit) =
    BasicText(text, Modifier.clickable(onClick = onClick).padding(vertical = 2.dp), style = paperMuted.copy(color = Paper.accent))

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
    BasicTextField(
        value, onChange,
        modifier.fillMaxWidth().padding(bottom = 0.75.remDp)
            .border(1.dp, Paper.line, RoundedCornerShape(4.dp)).padding(horizontal = 0.85.remDp, vertical = 0.6.remDp),
        singleLine = singleLine,
        textStyle = TextStyle(fontFamily = Sans, fontSize = 0.95.rem, color = Paper.text),
        cursorBrush = SolidColor(Paper.accent),
        visualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
        keyboardOptions = KeyboardOptions(keyboardType = if (password) KeyboardType.Password else type, imeAction = if (singleLine) ImeAction.Done else ImeAction.Default),
        keyboardActions = actions,
        decorationBox = { inner ->
            Box {
                if (value.isEmpty()) BasicText(placeholder, style = TextStyle(fontFamily = Sans, fontSize = 0.95.rem, color = Paper.muted.copy(alpha = 0.7f)))
                inner()
            }
        },
    )
}

/** A button of the white pages: outlined, filled while pressed. */
@Composable
fun PaperButton(text: String, enabled: Boolean = true, danger: Boolean = false, ghost: Boolean = false, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    val ink = if (danger) Paper.error else if (ghost) Paper.muted else Paper.text
    Box(
        modifier.fillMaxWidth().heightIn(min = 2.4.remDp).alpha(if (enabled) 1f else 0.4f)
            .background(if (pressed && enabled) ink else Color.White, RoundedCornerShape(4.dp))
            .border(1.dp, if (ghost) Paper.line else ink, RoundedCornerShape(4.dp))
            .clickable(source, null, enabled = enabled, onClick = onClick)
            .padding(horizontal = 1.remDp, vertical = 0.55.remDp),
        contentAlignment = Alignment.Center,
    ) { BasicText(text, style = paperText.copy(color = if (pressed && enabled) Color.White else ink)) }
}

@Composable
fun PaperError(text: String?) {
    if (text != null) BasicText(text, style = paperText.copy(fontSize = 0.8.rem, color = Paper.error))
}

/** A modal over the page: a title, a close, and its body. */
@Composable
fun PaperModal(title: String, onClose: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Column(
            Modifier.padding(0.75.remDp).fillMaxWidth().background(Color.White, RoundedCornerShape(8.dp))
                .border(1.dp, Paper.line, RoundedCornerShape(8.dp)),
        ) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 1.remDp, vertical = 0.75.remDp), verticalAlignment = Alignment.CenterVertically) {
                BasicText(caps(title), Modifier.weight(1f), style = paperMuted.copy(letterSpacing = 0.1.em))
                BasicText("×", Modifier.clickable(onClick = onClose).padding(horizontal = 6.dp), style = TextStyle(fontFamily = Sans, fontSize = 1.4.rem, color = Paper.muted))
            }
            Box(Modifier.fillMaxWidth().height(1.dp).background(Paper.line))
            Column(
                Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 1.25.remDp, vertical = 1.remDp),
                verticalArrangement = Arrangement.spacedBy(0.6.remDp),
                content = content,
            )
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
    val on = if (gold) hex("#b08a00") else Paper.text
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
        BasicText(label ?: "$filled/$segments", style = TextStyle(fontFamily = Sans, fontSize = 0.68.rem, color = Paper.muted, textAlign = TextAlign.Center))
    }
}
