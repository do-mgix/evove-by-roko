package com.evove.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.KeyboardActions
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.evove.app.Bus
import com.evove.app.Page
import com.evove.app.api.Api
import com.evove.app.api.LogEntry
import com.evove.app.api.PERIODS
import com.evove.app.ui.Paper
import com.evove.app.ui.PaperButton
import com.evove.app.ui.PaperError
import com.evove.app.ui.PaperField
import com.evove.app.ui.PaperModal
import com.evove.app.ui.PaperPage
import com.evove.app.ui.PaperRow
import com.evove.app.ui.paperMuted
import com.evove.app.ui.paperText
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.launch
import java.time.LocalDate

/** A log's content without the note or the count: "3x corrida: leve" → "leve". */
fun logText(content: String): String {
    Regex("^(.+?)\\s*:\\s*(.+)$").find(content)?.let { return it.groupValues[2].trim() }
    Regex("^(\\d+)\\s*[xX]\\s*(.+)$").find(content)?.let { return it.groupValues[2].trim() }
    return content
}

private fun noteOf(content: String) = Regex("^(.+?)\\s*:\\s*(.+)$").find(content)?.groupValues?.get(2)?.trim() ?: ""

private fun relative(o: Int) = when (o) { 0 -> "today"; -1 -> "yesterday"; else -> "${o}d" }

private val DAYS_PT = listOf("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM")

/** The records of a day, to move, reorder, annotate or delete. A swipe walks
 *  the days. Reordering is by the arrows of a record, where the web page dragged. */
@Composable
fun LogsPage(onBack: () -> Unit) {
    var offset by remember { mutableIntStateOf(0) }
    var logs by remember { mutableStateOf<List<LogEntry>>(emptyList()) }
    var day by remember { mutableStateOf<Int?>(null) }
    var date by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var selected by remember { mutableStateOf<LogEntry?>(null) }
    val scope = rememberCoroutineScope()

    fun load(o: Int) {
        loading = true
        error = null
        scope.launch {
            try {
                val r = Api.logs(o)
                logs = r.logs; day = r.day; date = r.date; offset = r.offset
            } catch (e: Exception) {
                error = e.message ?: "erro"
            } finally {
                loading = false
            }
        }
    }
    LaunchedEffect(Bus.logs) { load(offset) }
    fun go(delta: Int) { if (offset + delta <= 0) load(offset + delta) }

    fun move(l: LogEntry, by: Int) {
        val i = logs.indexOfFirst { it.id == l.id }
        val j = i + by
        val d = day ?: return
        if (i < 0 || j !in logs.indices) return
        val next = logs.toMutableList().also { it.add(j, it.removeAt(i)) }
        logs = next
        scope.launch {
            try {
                Api.reorderLogs(d, next.map { it.id })
                logs = next.mapIndexed { k, x -> x.copy(order = k + 1) }
                selected = logs.find { it.id == l.id }
            } catch (e: Exception) {
                error = e.message ?: "erro ao reordenar"
            }
        }
    }

    PaperPage(Page.LOGS.option, Page.LOGS.title, onBack) {
        var drag by remember { mutableStateOf(0f) }
        Column(
            Modifier.fillMaxWidth().pointerInput(Unit) {
                detectHorizontalDragGestures(onDragStart = { drag = 0f }, onDragEnd = {
                    if (drag > 60 * density) go(-1) else if (drag < -60 * density) go(1)
                }) { _, amount -> drag += amount }
            },
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Nav("‹") { go(-1) }
                BasicText("LOGS", Modifier.weight(1f), style = paperMuted)
                val weekday = runCatching { DAYS_PT[LocalDate.parse(date).dayOfWeek.value - 1] }.getOrDefault("")
                BasicText(weekday, style = paperMuted.copy(color = Paper.accent, fontWeight = FontWeight.Bold))
                BasicText(relative(offset), style = paperMuted.copy(color = Paper.soft))
                day?.let { BasicText("day $it", style = paperMuted) }
                if (date.length >= 10) BasicText(short(date), style = paperMuted)
                Nav("›", enabled = offset < 0) { go(1) }
            }
            when {
                loading -> BasicText("…", style = paperMuted)
                error != null -> PaperError(error)
                logs.isEmpty() -> BasicText("sem logs", style = paperMuted)
            }
            for (l in logs) {
                Row(
                    Modifier.fillMaxWidth().clickable { selected = l }.padding(horizontal = 4.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically,
                ) {
                    l.period?.let { BasicText(it, style = paperMuted) }
                    BasicText(logText(l.content), Modifier.weight(1f), style = paperText)
                    if (l.tokens != 0) BasicText("${if (l.tokens > 0) "+" else ""}${l.tokens}t", style = paperMuted.copy(color = if (l.tokens < 0) Paper.error else Paper.accent))
                    BasicText("+${l.marks}", style = paperMuted)
                }
                Box(Modifier.fillMaxWidth().height(1.dp).background(Paper.line))
            }
        }
    }

    selected?.let { s ->
        var editing by remember(s.id) { mutableStateOf(false) }
        var confirming by remember(s.id) { mutableStateOf(false) }
        var draft by remember(s.id) { mutableStateOf("") }
        var saving by remember { mutableStateOf(false) }
        fun close() { selected = null }
        fun save(block: suspend () -> Unit) {
            if (saving) return
            saving = true
            scope.launch {
                try { block() } catch (e: Exception) { error = e.message ?: "erro ao salvar" } finally { saving = false }
            }
        }
        PaperModal("log", ::close) {
            PaperRow("id", "${s.id}")
            PaperRow("timestamp", s.timestamp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                BasicText("período", Modifier.width(6.remDp), style = paperMuted)
                for (p in PERIODS) {
                    val on = s.period == p
                    BasicText(p, Modifier.border(1.dp, if (on) Paper.accent else Paper.line, RoundedCornerShape(3.dp))
                        .clickable(enabled = !saving && !on) {
                            save {
                                Api.setLogPeriod(s.id, p)
                                logs = logs.map { if (it.id == s.id) it.copy(period = p) else it }
                                selected = s.copy(period = p)
                            }
                        }.padding(horizontal = 10.dp, vertical = 4.dp),
                        style = paperText.copy(color = if (on) Paper.accent else Paper.text))
                }
            }
            PaperRow("order", "${s.order}")
            PaperRow("marcas", "+${s.marks}")
            if (s.tokens != 0) PaperRow("tokens", if (s.tokens > 0) "+${s.tokens} recebidos" else "${-s.tokens} gastos")
            PaperRow("content", s.content)
            when {
                editing -> {
                    fun saveNote() = save {
                        val u = Api.updateLogNote(s.id, draft.trim())
                        logs = logs.map { if (it.id == s.id) it.copy(content = u.content) else it }
                        selected = s.copy(content = u.content)
                        editing = false
                    }
                    PaperField(draft, { draft = it }, "nota", actions = KeyboardActions(onDone = { saveNote() }))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PaperButton("cancelar", ghost = true, enabled = !saving, modifier = Modifier.weight(1f)) { editing = false }
                        PaperButton(if (saving) "..." else "salvar", enabled = !saving, modifier = Modifier.weight(1f)) { saveNote() }
                    }
                }
                confirming -> {
                    BasicText("apagar este log?", style = paperText)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PaperButton("não", ghost = true, enabled = !saving, modifier = Modifier.weight(1f)) { confirming = false }
                        PaperButton(if (saving) "..." else "apagar", danger = true, enabled = !saving, modifier = Modifier.weight(1f)) {
                            save { Api.deleteLog(s.id); logs = logs.filter { it.id != s.id }; close() }
                        }
                    }
                }
                else -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PaperButton("↑", ghost = true, enabled = logs.firstOrNull()?.id != s.id, modifier = Modifier.weight(1f)) { move(s, -1) }
                        PaperButton("↓", ghost = true, enabled = logs.lastOrNull()?.id != s.id, modifier = Modifier.weight(1f)) { move(s, 1) }
                        PaperButton("← dia", ghost = true, enabled = !saving, modifier = Modifier.weight(1f)) {
                            save { Api.shiftLogDay(s.id, -1); logs = logs.filter { it.id != s.id }; close() }
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PaperButton("editar nota", ghost = true, modifier = Modifier.weight(1f)) { draft = noteOf(s.content); editing = true }
                        PaperButton("apagar", danger = true, modifier = Modifier.weight(1f)) { confirming = true }
                    }
                }
            }
        }
    }
}

@Composable
fun Nav(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    BasicText(
        text,
        Modifier.border(1.dp, Paper.line, RoundedCornerShape(3.dp)).clickable(enabled = enabled, onClick = onClick).padding(horizontal = 12.dp, vertical = 2.dp),
        style = paperText.copy(fontSize = 1.2.rem, color = if (enabled) Paper.soft else Paper.line),
    )
}
