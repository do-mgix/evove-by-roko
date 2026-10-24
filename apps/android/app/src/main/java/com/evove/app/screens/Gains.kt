package com.evove.app.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.api.Line
import com.evove.app.sound.Sfx
import com.evove.app.ui.voiceInk
import com.evove.app.ui.Display
import com.evove.app.ui.Ink
import com.evove.app.ui.MarkBar
import com.evove.app.ui.caps
import com.evove.app.ui.hex
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.delay

/** One attribute that gained from the act: where its bar was, where it is. */
data class Gain(
    val key: String,
    val name: String,
    val rankBefore: String,
    val rank: String,
    /** segments filled before the act, on the bar shown */
    val from: Int,
    val marks: Int,
    val need: Int,
)

/** Fades in and rises a little when it first appears. */
@Composable
fun Arrive(ms: Int = 350, content: @Composable () -> Unit) {
    val a = remember { Animatable(0f) }
    LaunchedEffect(Unit) { a.animateTo(1f, tween(ms)) }
    androidx.compose.foundation.layout.Box(Modifier.graphicsLayer { alpha = a.value; translationY = (1 - a.value) * 6.dp.toPx() }) { content() }
}

/** After an act, everything else is gone and what it paid arrives, one part
 *  after the other; a tap goes on. */
@Composable
fun GainsScreen(title: String, tokens: Int, marks: Int, gains: List<Gain>, lines: List<Line>, onDone: () -> Unit) {
    var step by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        Sfx.gains()
        delay(350); step = 1   // tokens
        delay(750); step = 2   // marks and the bars
        delay(1500); step = 3  // roko
    }
    val font = TextStyle(fontFamily = Display, letterSpacing = 0.12.em)
    Column(
        Modifier.fillMaxSize()
            .clickable(remember { MutableInteractionSource() }, null) { Sfx.tap(0); onDone() }
            .padding(horizontal = 1.25.remDp, vertical = 1.5.remDp),
        verticalArrangement = Arrangement.spacedBy(1.5.remDp),
    ) {
        BasicText(caps(title), style = font.copy(fontSize = 0.95.rem, fontWeight = FontWeight.Medium, color = Ink.shop))
        Column(
            Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(1.remDp, Alignment.CenterVertically),
        ) {
            fun line(n: String, unit: String, color: Color) = buildAnnotatedString {
                withStyle(SpanStyle(color = color)) { append(n) }
                withStyle(SpanStyle(fontSize = 0.95.rem, fontWeight = FontWeight.Normal, color = Color.White.copy(alpha = 0.7f))) { append(" ${caps(unit)}") }
            }
            val big = font.copy(fontSize = 2.4.rem, fontWeight = FontWeight.SemiBold)
            if (step >= 1) Arrive {
                val signed = if (tokens > 0) "+$tokens" else if (tokens < 0) "−${-tokens}" else "0"
                BasicText(line(signed, "tokens", if (tokens < 0) Ink.agenda else Ink.act), style = big)
            }
            if (step >= 2) {
                Arrive { BasicText(line("+$marks", if (marks == 1) "marca" else "marcas", Ink.roko), style = big) }
                for (g in gains) Arrive {
                    Column(verticalArrangement = Arrangement.spacedBy(0.4.remDp)) {
                        Row {
                            BasicText(caps(g.name), Modifier.weight(1f), style = font.copy(fontSize = 0.75.rem, color = Color.White), maxLines = 1, overflow = TextOverflow.Ellipsis)
                            BasicText(if (g.rankBefore == g.rank) g.rank else "${g.rankBefore} → ${g.rank}", style = font.copy(fontSize = 0.75.rem, color = Ink.attributes))
                        }
                        MarkBar(g.marks, g.need, gold = true, from = g.from)
                    }
                }
            }
        }
        // what the entities say about it, each in its own voice and color
        if (step >= 3) Arrive(600) {
            Column(verticalArrangement = Arrangement.spacedBy(0.6.remDp)) {
                for (l in lines.ifEmpty { listOf(Line("roko", "registrado. o que vem a seguir?")) }) {
                    BasicText(com.evove.app.ui.voiced(l.entity, l.text), style = font.copy(fontSize = 0.85.rem, lineHeight = 1.5.em, color = voiceInk(l.entity)))
                }
            }
        }
    }
}
