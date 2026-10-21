package com.evove.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.evove.app.Page
import com.evove.app.api.Action
import com.evove.app.api.Api
import com.evove.app.api.CalendarMonth
import com.evove.app.api.LogEntry
import com.evove.app.api.fold
import com.evove.app.ui.Paper
import com.evove.app.ui.PaperButton
import com.evove.app.ui.PaperError
import com.evove.app.ui.PaperField
import com.evove.app.ui.PaperInline
import com.evove.app.ui.PaperModal
import com.evove.app.ui.PaperPage
import com.evove.app.ui.paperMuted
import com.evove.app.ui.paperText
import com.evove.app.ui.rem
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth

private val MONTHS = listOf("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
private val WEEKDAYS = listOf("S", "T", "Q", "Q", "S", "S", "D")

/** The month: a past day shows its records, a future one takes an event. */
@Composable
fun CalendarPage(onBack: () -> Unit) {
    val today = remember { LocalDate.now() }
    var year by remember { mutableIntStateOf(today.year) }
    var month by remember { mutableIntStateOf(today.monthValue) }
    var cal by remember { mutableStateOf<CalendarMonth?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var selected by remember { mutableStateOf<String?>(null) }
    var dayLogs by remember { mutableStateOf<List<LogEntry>>(emptyList()) }
    var dayLoading by remember { mutableStateOf(false) }
    var actions by remember { mutableStateOf<List<Action>>(emptyList()) }
    var eventDate by remember { mutableStateOf<String?>(null) }
    var picker by remember { mutableStateOf(false) }
    var version by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { actions = runCatching { Api.actions() }.getOrDefault(emptyList()) }
    LaunchedEffect(year, month, version) {
        loading = true
        error = null
        try { cal = Api.calendar(year, month) } catch (e: Exception) { error = e.message ?: "erro" } finally { loading = false }
    }
    fun goMonth(y: Int, m: Int) { year = y; month = m; selected = null; dayLogs = emptyList() }

    PaperPage(Page.CALENDAR.option, Page.CALENDAR.title, onBack) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Nav("‹") { val ym = YearMonth.of(year, month).minusMonths(1); goMonth(ym.year, ym.monthValue) }
            BasicText("${MONTHS[month - 1]} $year", Modifier.weight(1f).clickable { picker = !picker }, style = paperText.copy(fontSize = 1.rem, textAlign = TextAlign.Center))
            Nav("›") { val ym = YearMonth.of(year, month).plusMonths(1); goMonth(ym.year, ym.monthValue) }
        }
        if (picker) {
            BasicText("ano", style = paperMuted)
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                for (y in today.year - 2..today.year + 2) Choice("$y", y == year, Modifier.weight(1f)) { year = y }
            }
            BasicText("mês", style = paperMuted)
            for (row in MONTHS.indices.chunked(6)) Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                for (i in row) Choice(MONTHS[i].take(3), i + 1 == month, Modifier.weight(1f)) { goMonth(year, i + 1); picker = false }
            }
        }
        val c = cal
        when {
            loading -> BasicText("…", style = paperMuted)
            error != null -> PaperError(error)
            c != null -> {
                Row { for (w in WEEKDAYS) BasicText(w, Modifier.weight(1f), style = paperMuted.copy(textAlign = TextAlign.Center)) }
                // leading blanks: the week starts on monday
                val first = LocalDate.of(c.year, c.month, 1)
                val cells = List(first.dayOfWeek.value - 1) { null } + (1..first.lengthOfMonth()).map { first.withDayOfMonth(it) }
                for (week in cells.chunked(7)) Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                    for (d in week + List(7 - week.size) { null }) {
                        if (d == null) { Box(Modifier.weight(1f)); continue }
                        val iso = d.toString()
                        val data = c.days[iso]
                        val future = d.isAfter(today)
                        Column(
                            Modifier.weight(1f).aspectRatio(0.8f)
                                .border(if (iso == selected) 2.dp else 1.dp, if (d == today || iso == selected) Paper.accent else Paper.line, RoundedCornerShape(3.dp))
                                .background(if (future) Color(0xFFFAFAFA) else Color.White)
                                .clickable {
                                    if (future) eventDate = iso
                                    else {
                                        selected = iso
                                        dayLoading = true
                                        scope.launch {
                                            dayLogs = runCatching { Api.logsByDate(iso).logs }.getOrDefault(emptyList())
                                            dayLoading = false
                                        }
                                    }
                                }.padding(3.dp),
                        ) {
                            BasicText("${d.dayOfMonth}", style = paperMuted.copy(color = if (future) Paper.muted else Paper.text))
                            for (ev in data?.events.orEmpty().take(2)) BasicText(ev.label, style = paperMuted.copy(fontSize = 0.5.rem, color = Paper.accent), maxLines = 1, overflow = TextOverflow.Ellipsis)
                            if ((data?.events?.size ?: 0) > 2) BasicText("+${data!!.events.size - 2}", style = paperMuted.copy(fontSize = 0.5.rem))
                            if ((data?.logCount ?: 0) > 0) Box(Modifier.size(5.dp).background(Paper.accent, CircleShape))
                        }
                    }
                }
                val s = selected
                if (s == null) {
                    BasicText("selecione uma data", style = paperMuted)
                    BasicText("toque numa data passada para ver os logs · numa futura para criar um evento", style = paperMuted.copy(fontSize = 0.7.rem))
                } else {
                    Row { BasicText(short(s), Modifier.weight(1f), style = paperText); BasicText("${dayLogs.size} logs", style = paperMuted) }
                    for (ev in c.days[s]?.events.orEmpty()) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        BasicText("evento", style = paperMuted.copy(color = Paper.accent)); BasicText(ev.label, style = paperText)
                    }
                    when {
                        dayLoading -> BasicText("…", style = paperMuted)
                        dayLogs.isEmpty() -> BasicText("sem logs", style = paperMuted)
                        else -> for (l in dayLogs) Row {
                            BasicText(logText(l.content), Modifier.weight(1f), style = paperText)
                            BasicText("+${l.marks}", style = paperMuted)
                        }
                    }
                }
            }
        }
    }

    eventDate?.let { date ->
        var label by remember(date) { mutableStateOf("") }
        var query by remember(date) { mutableStateOf("") }
        var action by remember(date) { mutableStateOf<Action?>(null) }
        var busy by remember { mutableStateOf(false) }
        PaperModal("evento especial", { eventDate = null }) {
            BasicText("para ${short(date)}", style = paperText)
            BasicText("ação (opcional)", style = paperMuted)
            val a = action
            if (a != null) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BasicText("act", style = paperMuted); BasicText(a.name, Modifier.weight(1f), style = paperText)
                PaperInline("×") { action = null; query = "" }
            } else {
                PaperField(query, { query = it }, "buscar ação...")
                val q = fold(query.trim())
                if (q.isNotEmpty()) for (x in actions.filter { fold(it.name).contains(q) }.take(6)) {
                    BasicText(x.name, Modifier.fillMaxWidth().clickable { action = x; query = x.name }.padding(vertical = 5.dp), style = paperText)
                }
            }
            BasicText("label", style = paperMuted)
            PaperField(label, { label = it }, if (a != null) "ex.: com mãe (vazio usa \"${a.name}\")" else "texto livre")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { eventDate = null }
                PaperButton(if (busy) "..." else "criar", enabled = !busy && (label.isNotBlank() || a != null), modifier = Modifier.weight(1f)) {
                    busy = true
                    scope.launch {
                        try {
                            Api.createEvent(date, label.trim().ifEmpty { a?.name ?: "" }, a?.id)
                            eventDate = null
                            version++
                        } catch (e: Exception) {
                            error = e.message ?: "erro"
                        } finally {
                            busy = false
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Choice(text: String, on: Boolean, modifier: Modifier, onClick: () -> Unit) {
    BasicText(
        text,
        modifier.border(1.dp, if (on) Paper.accent else Paper.line, RoundedCornerShape(3.dp)).clickable(onClick = onClick).padding(vertical = 5.dp),
        style = paperText.copy(fontSize = 0.75.rem, color = if (on) Paper.accent else Paper.text, textAlign = TextAlign.Center),
    )
}
