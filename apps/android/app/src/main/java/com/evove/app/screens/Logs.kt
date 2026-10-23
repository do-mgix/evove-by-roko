package com.evove.app.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.evove.app.Bus
import com.evove.app.api.Api
import com.evove.app.api.LogEntry
import com.evove.app.api.PERIODS
import com.evove.app.api.Reverted
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Empty
import com.evove.app.ui.Field
import com.evove.app.ui.Grow
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.KeyText
import com.evove.app.ui.Label
import com.evove.app.ui.ListRow
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Message
import com.evove.app.ui.Small
import com.evove.app.ui.Stats
import com.evove.app.ui.Tag
import com.evove.app.ui.Ticks
import com.evove.app.ui.Type
import com.evove.app.ui.caps
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.launch
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToInt

/** A log's content without the note or the count: "3x corrida: leve" → "leve". */
fun logText(content: String): String {
    Regex("^(.+?)\\s*:\\s*(.+)$").find(content)?.let { return it.groupValues[2].trim() }
    Regex("^(\\d+)\\s*[xX]\\s*(.+)$").find(content)?.let { return it.groupValues[2].trim() }
    return content
}

private fun noteOf(content: String) = Regex("^(.+?)\\s*:\\s*(.+)$").find(content)?.groupValues?.get(2)?.trim() ?: ""

/** "corrida [30m–1h] : leve" → "corrida [30m–1h]". */
private fun headOf(content: String) = content.split(" : ").first()

private fun relative(o: Int) = when (o) { 0 -> "hoje"; -1 -> "ontem"; else -> "${-o} dias atrás" }

private const val ROW_DP = 50

private sealed interface LogPane {
    data object List : LogPane
    data class Open(val log: LogEntry) : LogPane
    data class Note(val log: LogEntry) : LogPane
    data class Confirm(val log: LogEntry) : LogPane
    data class Undone(val log: LogEntry, val reverted: Reverted?) : LogPane
}

/** The records of a day, and everything that can be done to one: its period,
 *  its place in the day, the day it is filed under, its note — and deleting
 *  it, which takes back what its act gave, marks and ranks and tokens and hp,
 *  and says so. */
@Composable
fun LogsScreen(onBack: () -> Unit, onHome: () -> Unit) {
    var offset by remember { mutableIntStateOf(0) }
    var logs by remember { mutableStateOf<List<LogEntry>>(emptyList()) }
    var day by remember { mutableStateOf<Int?>(null) }
    var date by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var pane by remember { mutableStateOf<LogPane>(LogPane.List) }
    var page by remember { mutableIntStateOf(0) }
    var busy by remember { mutableStateOf(false) }
    var draft by remember { mutableStateOf("") }
    val field = remember { FocusRequester() }
    val scope = rememberCoroutineScope()

    suspend fun load(o: Int) {
        loading = true
        try {
            val r = Api.logs(o)
            logs = r.logs; day = r.day; date = r.date; offset = r.offset
            message = emptyList()
        } catch (e: Exception) {
            message = listOf(e.message ?: "erro")
        } finally {
            loading = false
        }
    }
    var first by remember { mutableStateOf(true) }
    LaunchedEffect(Bus.logs) { load(offset); if (first) Sfx.powerOn(); first = false }

    fun run(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        scope.launch {
            try { block() } catch (e: Exception) { message = listOf(e.message ?: "erro") } finally { busy = false }
        }
    }

    fun go(delta: Int) {
        if (offset + delta > 0) return
        Sfx.tap(if (delta < 0) 1 else 3)
        page = 0
        scope.launch { load(offset + delta); Sfx.powerOn() }
    }

    fun move(l: LogEntry, by: Int) {
        val i = logs.indexOfFirst { it.id == l.id }
        val j = i + by
        val d = day ?: return
        if (i < 0 || j !in logs.indices) return
        Sfx.tap(if (by < 0) 1 else 3)
        val next = logs.toMutableList().also { it.add(j, it.removeAt(i)) }
        run {
            Api.reorderLogs(d, next.map { it.id })
            logs = next.mapIndexed { k, x -> x.copy(order = k + 1) }
            pane = LogPane.Open(logs.first { it.id == l.id })
        }
    }

    fun back() {
        message = emptyList()
        pane = when (val p = pane) {
            is LogPane.Note -> LogPane.Open(p.log)
            is LogPane.Confirm -> LogPane.Open(p.log)
            else -> LogPane.List
        }
    }

    BackHandler(enabled = pane != LogPane.List) { back() }

    val p = pane
    DarkScreen(
        Ink.agenda, display = 0.16f,
        displayContent = {
            when {
                message.isNotEmpty() -> Message(message)
                p is LogPane.Open -> { Big(headOf(p.log.content)); Small(listOfNotNull(p.log.period, "${p.log.order}º do dia", p.log.timestamp.takeLast(8)).joinToString(" · ")) }
                p is LogPane.Note -> { Big("nota"); Small(headOf(p.log.content)) }
                p is LogPane.Confirm -> { Big("apagar?"); Small("o que o ato deu volta atrás") }
                p is LogPane.Undone -> { Big("apagado"); Small(headOf(p.log.content)) }
                loading -> Small("…")
                else -> { Big(relative(offset)); Small(listOfNotNull(dateLabel(date).ifEmpty { null }, day?.let { "dia $it" }, "${logs.size} registros").joinToString(" · ")) }
            }
        },
        bar = {
            if (p == LogPane.List) {
                Key({ go(-1) }, Modifier.at(1)) { KeyIcon(Icon.LEFT) }
                Key({ go(1) }, Modifier.at(2), enabled = offset < 0) { KeyIcon(Icon.RIGHT) }
                Key({ Sfx.tap(2); page++; Sfx.powerOn() }, Modifier.at(3)) { KeyIcon(Icon.DOWN) }
                Key({ Sfx.tap(0); onBack() }, Modifier.at(5)) { KeyIcon(Icon.CALENDAR) }
            } else {
                Key({ Sfx.tap(0); back() }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
            }
            HomeKey { Sfx.tap(0); onHome() }
        },
    ) { info ->
        val ink = LocalInk.current
        val h = Modifier.heightIn(min = 2.8.remDp)
        when (p) {
            LogPane.List -> {
                val perPage = maxOf(1, floor((info.height.value - 30) / (ROW_DP + 8)).toInt())
                val pages = maxOf(1, ceil(logs.size / perPage.toFloat()).toInt())
                val at = page % pages
                if (!loading && logs.isEmpty()) Empty("nenhum registro neste dia")
                for (l in logs.drop(at * perPage).take(perPage)) ListRow({ Sfx.tap(6); pane = LogPane.Open(l) }, minHeight = 3.1.remDp) {
                    Tag(l.period ?: "··")
                    Column(Modifier.weight(1f)) {
                        BasicText(caps(headOf(l.content)), style = Type.row, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        val note = noteOf(l.content)
                        if (note.isNotEmpty()) BasicText(note, style = Type.row.copy(fontSize = 0.7.rem, color = Color.White.copy(alpha = 0.55f)), maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    if (l.tokens != 0) Tag("${if (l.tokens > 0) "+" else "−"}${kotlin.math.abs(l.tokens)}t", if (l.tokens < 0) Ink.danger else ink)
                    Tag("+${l.marks}")
                }
                if (pages > 1) Ticks(pages, at, Modifier.height(20.dp))
            }
            is LogPane.Open -> {
                val l = p.log
                Stats(buildList {
                    add("marcas" to "+${l.marks}")
                    if (l.tokens != 0) add("tokens" to if (l.tokens > 0) "+${l.tokens} recebidos" else "${-l.tokens} gastos")
                    add("quando" to l.timestamp)
                    add("id" to "${l.id}")
                })
                Label("período")
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (period in PERIODS) Key({
                        if (l.period == period) return@Key
                        Sfx.tap(4)
                        run {
                            Api.setLogPeriod(l.id, period)
                            logs = logs.map { if (it.id == l.id) it.copy(period = period) else it }
                            pane = LogPane.Open(l.copy(period = period))
                        }
                    }, Modifier.weight(1f).then(h), on = l.period == period, enabled = !busy) { KeyText(period) }
                }
                Label("lugar e dia")
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Key({ move(l, -1) }, Modifier.weight(1f).then(h), enabled = !busy && logs.firstOrNull()?.id != l.id) { KeyIcon(Icon.UP) }
                    Key({ move(l, 1) }, Modifier.weight(1f).then(h), enabled = !busy && logs.lastOrNull()?.id != l.id) { KeyIcon(Icon.DOWN) }
                    for (delta in listOf(-1, 1)) Key({
                        Sfx.tap(5)
                        run {
                            Api.shiftLogDay(l.id, delta)
                            logs = logs.filter { it.id != l.id }
                            pane = LogPane.List
                            message = listOf(if (delta < 0) "para o dia anterior" else "para o dia seguinte", headOf(l.content))
                            Bus.bumpLogs()
                        }
                    }, Modifier.weight(1f).then(h), enabled = !busy && (delta < 0 || offset < 0)) {
                        KeyIcon(if (delta < 0) Icon.LEFT else Icon.RIGHT, 16.dp); KeyText("dia")
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Key({ Sfx.tap(6); draft = noteOf(l.content); pane = LogPane.Note(l) }, Modifier.weight(1f).then(h)) { KeyIcon(Icon.PENCIL); KeyText("nota") }
                    Key({ Sfx.tap(0); pane = LogPane.Confirm(l) }, Modifier.weight(1f).then(h)) { KeyIcon(Icon.TRASH); KeyText("apagar") }
                }
            }
            is LogPane.Note -> {
                val l = p.log
                LaunchedEffect(l.id) { runCatching { field.requestFocus() } }
                fun save() = run {
                    val u = Api.updateLogNote(l.id, draft.trim())
                    logs = logs.map { if (it.id == l.id) it.copy(content = u.content) else it }
                    pane = LogPane.Open(l.copy(content = u.content))
                    Sfx.tap(8)
                }
                Field(draft, { draft = it }, "nota", Modifier.focusRequester(field), maxLength = 200,
                    keyboard = KeyboardOptions(imeAction = ImeAction.Done))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Key({ draft = "" }, Modifier.weight(1f).then(h)) { KeyIcon(Icon.CROSS) }
                    Box(Modifier.weight(1f))
                    Key({ save() }, Modifier.weight(3f).then(h), enabled = !busy) { KeyIcon(Icon.CHECK) }
                }
            }
            is LogPane.Confirm -> {
                val l = p.log
                BasicText(
                    caps("o registro some, e com ele o que o ato deu: as marcas da ação, do perfil e de cada atributo — " +
                        "rank incluído —, a janela de 6 horas, os tokens e o hp."),
                    style = Type.row.copy(fontSize = 0.75.rem, color = Color.White.copy(alpha = 0.75f), lineHeight = 1.15.rem),
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Key({ Sfx.tap(0); pane = LogPane.Open(l) }, Modifier.weight(1f).then(h)) { KeyIcon(Icon.LEFT) }
                    Box(Modifier.weight(1f))
                    androidx.compose.runtime.CompositionLocalProvider(LocalInk provides Ink.danger) {
                        Key({
                            run {
                                val r = Api.deleteLog(l.id)
                                logs = logs.filter { it.id != l.id }
                                pane = LogPane.Undone(l, r.reverted)
                                Sfx.gains()
                                Bus.bumpLogs(); Bus.bumpUser()
                            }
                        }, Modifier.weight(3f).then(h), enabled = !busy) { KeyIcon(Icon.TRASH); KeyText("apagar e reverter") }
                    }
                }
            }
            is LogPane.Undone -> {
                val r = p.reverted
                if (r == null) Empty("nenhum ato por trás deste registro: só a linha saiu")
                else {
                    Stats(buildList {
                        add("marcas" to "−${r.marks}")
                        if (r.tokens != 0) add("tokens" to (if (r.tokens > 0) "+${r.tokens}" else "−${-r.tokens}") + " · saldo ${r.balance}")
                        if (r.energy != 0) add("hp" to "+${r.energy} de volta")
                        add("marcas do perfil" to "${r.userMarks}")
                    })
                    val all = r.leaves + r.custom
                    if (all.isNotEmpty()) {
                        Label("atributos")
                        for (leaf in all.take(6)) ListRow(null) {
                            Grow(leaf.name, upper = true)
                            Tag("−${(leaf.marks * 10).roundToInt() / 10.0}")
                        }
                        if (all.size > 6) Small("+${all.size - 6} atributos")
                    }
                }
                Key({ Sfx.tap(0); pane = LogPane.List }, Modifier.fillMaxWidth().then(h)) { KeyIcon(Icon.CHECK) }
            }
        }
    }
}
