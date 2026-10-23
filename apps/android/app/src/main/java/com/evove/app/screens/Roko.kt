package com.evove.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.Evove
import com.evove.app.api.Api
import com.evove.app.api.Line
import com.evove.app.api.Entity
import com.evove.app.api.text
import com.evove.app.sound.Sfx
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Display
import com.evove.app.ui.GlyphView
import com.evove.app.ui.Glyphs
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.Mono
import com.evove.app.ui.Small
import com.evove.app.ui.Stats
import com.evove.app.ui.caps
import com.evove.app.ui.dashed
import com.evove.app.ui.hex
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

// The entity's screen, text above all, as the autobattler is: its name, a box
// where what it says is typed out, and a tap anywhere on the box asks it for a
// line — if it is there, and if it wants to answer. Roko is the first entity;
// the arrow walks to the next when there are more.

private const val TYPE_MS = 28L

@Composable
fun RokoScreen(onHome: () -> Unit) {
    var list by remember { mutableStateOf<List<Entity>>(emptyList()) }
    var index by remember { mutableIntStateOf(0) }
    var showStats by remember { mutableStateOf(false) }
    var line by remember { mutableStateOf("") }
    var typed by remember { mutableStateOf("") }
    var away by remember { mutableStateOf(false) }
    var asking by remember { mutableStateOf(false) }
    var typer by remember { mutableStateOf<Job?>(null) }
    var talks by remember { mutableIntStateOf(0) }
    // what another entity said about the talk, typed out at the next tap
    var queue by remember { mutableStateOf<List<Line>>(emptyList()) }
    val scope = rememberCoroutineScope()

    val entity = list.getOrNull(index)
    val ink = entity?.color?.let { runCatching { hex(it) }.getOrNull() } ?: Ink.roko

    fun type(text: String) {
        typer?.cancel()
        line = text
        typed = ""
        typer = scope.launch {
            for (i in 1..text.length) {
                delay(TYPE_MS)
                typed = text.take(i)
                if (i % 3 == 0) Sfx.tap(i % 10)
            }
            typer = null
        }
    }

    fun ask() {
        val e = entity ?: return
        if (asking) return
        typer?.let {
            // a tap while it types finishes the line
            it.cancel()
            typer = null
            typed = line
            return
        }
        queue.firstOrNull()?.let { next ->
            queue = queue.drop(1)
            list.indexOfFirst { it.id == next.entity }.takeIf { it >= 0 }?.let { index = it }
            away = false
            Sfx.powerOn()
            type(next.text)
            return
        }
        asking = true
        scope.launch {
            try {
                val r = Api.talkTo(e.id)
                talks += 1
                away = !r.present
                type(if (r.present) r.line ?: "…" else "${e.name} NÃO ESTÁ AQUI.")
                if (r.lines.isNotEmpty()) {
                    // the talk moved the story: someone else may be here now
                    queue = r.lines
                    runCatching { Api.entities() }.onSuccess { list = it }
                    Evove.refresh()
                }
            } catch (x: Exception) {
                type((x.message ?: "…").uppercase())
            } finally {
                asking = false
            }
        }
    }

    LaunchedEffect(Unit) {
        try {
            list = Api.entities()
            Sfx.powerOn()
            ask()
        } catch (x: Exception) {
            type((x.message ?: "…").uppercase())
        }
    }

    BackHandler(enabled = showStats) { showStats = false }

    DarkScreen(
        ink, display = 0.2f,
        displayContent = {
            if (entity != null) {
                GlyphView(Glyphs.roko, ink, 2.6.remDp, modifier = Modifier.alpha(if (away) 0.25f else 1f))
                BasicText(caps(entity.name), style = TextStyle(fontFamily = Display, fontSize = 1.6.rem, fontWeight = FontWeight.SemiBold, letterSpacing = 0.25.em, color = ink))
                Small(entity.title)
            }
        },
        bar = {
            Key({ Sfx.tap(5); showStats = !showStats }, Modifier.at(1), on = showStats) { KeyIcon(Icon.BARS) }
            Key({ ask() }, Modifier.at(2, 3), enabled = !showStats) { KeyIcon(Icon.CHAT) }
            Key({
                Sfx.tap(2)
                index = (index + 1) % maxOf(1, list.size)
                showStats = false
                typed = ""; line = ""
                Sfx.powerOn()
            }, Modifier.at(5), enabled = list.size >= 2) { KeyIcon(Icon.RIGHT) }
            HomeKey { Sfx.tap(0); onHome() }
        },
    ) {
        if (showStats && entity != null) {
            Stats(
                entity.stats.map { (k, v) -> k to caps(v.text()) } + listOf(
                    "personalidade" to caps(entity.personality),
                    "presença" to "${(entity.presence * 100).roundToInt()}%",
                    "conversas" to "$talks",
                ),
                valueStyle = TextStyle(fontFamily = Display, fontSize = 0.85.rem, color = Color.White),
            )
        } else {
            val source = remember { MutableInteractionSource() }
            val pressed by source.collectIsPressedAsState()
            val blink = rememberInfiniteTransition(label = "caret")
            val caret by blink.animateFloat(1f, 0f, infiniteRepeatable(tween(1000, easing = LinearEasing), RepeatMode.Restart), label = "on")
            Column(
                Modifier.weight(1f).fillMaxWidth()
                    .alpha(if (away) 0.6f else 1f)
                    .background(ink.copy(alpha = if (pressed) 0.14f else 0.05f))
                    .then(if (away) Modifier.dashed(ink) else Modifier.border(1.5.dp, ink))
                    .clickable(source, null) { ask() }
                    .padding(horizontal = 1.remDp, vertical = 1.2.remDp),
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
            ) {
                val showCaret = typer != null || caret > 0.5f
                BasicText(
                    buildAnnotatedString {
                        append(if (entity?.voice == "lower") typed else caps(typed))
                        withStyle(SpanStyle(color = if (showCaret) ink else Color.Transparent)) { append("▍") }
                    },
                    style = TextStyle(fontFamily = Display, fontSize = 1.15.rem, fontWeight = FontWeight.Medium, lineHeight = 1.55.em, letterSpacing = 0.08.em, color = Color.White),
                )
                BasicText(
                    caps(if (asking) "…" else if (queue.isNotEmpty()) "${queue.first().entity} quer falar" else "toque para ouvir"),
                    Modifier.align(Alignment.End).alpha(0.6f),
                    style = TextStyle(fontFamily = Mono, fontSize = 0.7.rem, color = ink),
                )
            }
        }
    }
}
