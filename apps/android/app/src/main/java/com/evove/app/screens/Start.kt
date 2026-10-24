package com.evove.app.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.evove.app.Evove
import com.evove.app.api.Api
import com.evove.app.api.SaveCode
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Field
import com.evove.app.ui.Glyph
import com.evove.app.ui.GlyphView
import com.evove.app.ui.Glyphs
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.KeyText
import com.evove.app.ui.Label
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Message
import com.evove.app.ui.Mono
import com.evove.app.ui.Small
import com.evove.app.ui.Type
import com.evove.app.ui.caps
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.launch

// The first screen: who is using the app, and which mode to enter — the evove,
// whose story is the tutorial; the sandbox, open once it is told, where every
// action is free; the journey, a mode of its own once its module opens, whose
// key blinks when someone waits in it. And the save: the whole evove as one
// code, to copy somewhere safe, or to paste and mount.

enum class Mode { EVOVE, SANDBOX, JOURNEY }

private enum class StartPane { MODES, SAVE, LOAD }

@Composable
fun StartScreen(username: String, onMode: (Mode) -> Unit, onAccounts: () -> Unit) {
    var pane by remember { mutableStateOf(StartPane.MODES) }
    var save by remember { mutableStateOf<SaveCode?>(null) }
    var typed by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val clipboard = remember { context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager }

    LaunchedEffect(Unit) { Sfx.powerOn(); Evove.refresh() }

    fun open(p: StartPane) {
        Sfx.tap(4)
        message = emptyList()
        pane = p
        if (p == StartPane.SAVE) {
            save = null
            scope.launch {
                try { save = Api.saveCode() } catch (e: Exception) { message = listOf("save", e.message ?: "erro") }
            }
        }
    }

    fun copy() {
        val s = save ?: return
        clipboard?.setPrimaryClip(ClipData.newPlainText("evove", s.code))
        Sfx.gains()
        message = listOf("copiado", "${s.length} letras")
    }

    fun mount() {
        if (busy || typed.isBlank()) return
        busy = true
        scope.launch {
            try {
                Evove.apply(Api.mountSave(typed))
                typed = ""
                Sfx.gains()
                message = listOf("save montado", "ranks, atributos e ações carregados")
                pane = StartPane.MODES
            } catch (e: Exception) {
                message = listOf("save", e.message ?: "não reconhecido")
            } finally {
                busy = false
            }
        }
    }

    BackHandler(enabled = pane != StartPane.MODES) { pane = StartPane.MODES; message = emptyList() }

    val view = Evove.view
    val modes = view?.modes
    DarkScreen(
        Ink.act, display = 0.2f,
        displayContent = {
            if (message.isNotEmpty()) Message(message)
            else {
                Big("evove", size = 2f)
                Small(caps(username) + (view?.entity?.let { " · ${it.name}" } ?: if (view != null) " · sem entidade" else ""))
            }
        },
        bar = {
            Key({ Sfx.tap(5); onAccounts() }, Modifier.at(1).testTag("accounts")) { KeyIcon(Icon.USER) }
            Key({ open(StartPane.SAVE) }, Modifier.at(2), on = pane == StartPane.SAVE) { KeyIcon(Icon.SCAN) }
            Key({ open(StartPane.LOAD) }, Modifier.at(3), on = pane == StartPane.LOAD) { KeyIcon(Icon.DOWN) }
            Key({ Sfx.tap(0); onMode(Mode.EVOVE) }, Modifier.at(6)) { KeyIcon(Icon.CIRCLE, 16.dp) }
        },
    ) {
        when (pane) {
            StartPane.MODES -> {
                val story = view?.story
                ModeKey(
                    Glyphs.act, Ink.act, "evove",
                    if (story != null && !story.done) "tutorial ${story.at}/${story.of}" else "o seu evove",
                    enabled = true, alert = false, tag = "mode-evove",
                ) { onMode(Mode.EVOVE) }
                ModeKey(
                    Glyphs.act, Ink.sandbox, "sandbox",
                    if (modes?.sandbox == true) "tudo liberado, nada custa" else "termine o tutorial",
                    enabled = modes?.sandbox == true, alert = false, tag = "mode-sandbox",
                ) { onMode(Mode.SANDBOX) }
                ModeKey(
                    Glyphs.journey, Ink.journey, "jornada",
                    when {
                        modes?.journeyEnding == "free" -> "livre"
                        modes?.journeyEnding != null -> "só um código"
                        modes?.journeyAlert == true -> "alguém espera por você"
                        modes?.journey == true -> "explorando sozinho"
                        else -> "abre no evove"
                    },
                    enabled = modes?.journey == true, alert = modes?.journeyAlert == true, tag = "mode-journey",
                ) { onMode(Mode.JOURNEY) }
            }
            StartPane.SAVE -> {
                Label("save · o evove inteiro num código")
                val s = save
                BasicText(
                    s?.grouped ?: "…",
                    Modifier.fillMaxWidth().weight(1f, fill = false).border(1.5.dp, LocalInk.current).padding(0.7.remDp),
                    style = TextStyle(fontFamily = Mono, fontSize = 0.62.rem, color = Color.White, lineHeight = 0.95.rem),
                )
                if (s != null) Small("${s.actions} ações · ${s.attributes} atributos · sem patches, thoughts nem registros")
                Key(::copy, Modifier.fillMaxWidth().heightIn(min = 2.8.remDp), enabled = s != null) { KeyIcon(Icon.LINK); KeyText("copiar") }
            }
            StartPane.LOAD -> {
                Label("carregar save · substitui ranks, atributos e ações")
                Field(typed, { typed = it }, "cole o código aqui", singleLine = false,
                    keyboard = KeyboardOptions(imeAction = ImeAction.Done))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Key({
                        Sfx.tap(3)
                        clipboard?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.text?.let { typed = it.toString() }
                    }, Modifier.weight(1f).heightIn(min = 2.8.remDp)) { KeyText("colar") }
                    CompositionLocalProvider(LocalInk provides Ink.danger) {
                        Key(::mount, Modifier.weight(1f).heightIn(min = 2.8.remDp), enabled = !busy && typed.isNotBlank()) {
                            KeyText(if (busy) "…" else "montar")
                        }
                    }
                }
            }
        }
    }
}

/** A mode to enter: its mark, its name, a line on where it stands; a blinking
 *  dot when something waits in it. */
@Composable
private fun ModeKey(glyph: Glyph, ink: Color, label: String, note: String, enabled: Boolean, alert: Boolean, tag: String, onClick: () -> Unit) {
    CompositionLocalProvider(LocalInk provides ink) {
        Key({ Sfx.tap(7); onClick() }, Modifier.fillMaxWidth().heightIn(min = 4.4.remDp).testTag(tag), enabled = enabled) {
            GlyphView(glyph, ink, 1.8.remDp)
            Column(Modifier.weight(1f).padding(start = 0.4.remDp), verticalArrangement = Arrangement.spacedBy(0.15.remDp)) {
                BasicText(caps(label), style = Type.key.copy(fontSize = 1.05.rem, color = ink))
                BasicText(note, Modifier.alpha(0.7f), style = Type.small.copy(fontSize = 0.7.rem))
            }
            if (alert) {
                val blink = rememberInfiniteTransition(label = "alert")
                val a by blink.animateFloat(1f, 0.15f, infiniteRepeatable(tween(700, easing = LinearEasing), RepeatMode.Reverse), label = "a")
                Box(Modifier.padding(end = 0.4.remDp).size(10.dp).alpha(a).background(ink).align(Alignment.CenterVertically))
            }
        }
    }
}
