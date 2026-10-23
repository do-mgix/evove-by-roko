package com.evove.app.screens

import android.app.DatePickerDialog
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
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
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.evove.app.Bus
import com.evove.app.Evove
import com.evove.app.api.Action
import com.evove.app.api.AgendaDay
import com.evove.app.api.Api
import com.evove.app.api.DayLog
import com.evove.app.api.Project
import com.evove.app.api.Todo
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Empty
import com.evove.app.ui.Field
import com.evove.app.ui.Grow
import com.evove.app.ui.HomeKey
import com.evove.app.ui.Icon
import com.evove.app.ui.IconView
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.KeyText
import com.evove.app.ui.Label
import com.evove.app.ui.ListRow
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Message
import com.evove.app.ui.Mono
import com.evove.app.ui.Small
import com.evove.app.ui.Stats
import com.evove.app.ui.Tag
import com.evove.app.ui.Ticks
import com.evove.app.ui.Type
import com.evove.app.ui.caps
import com.evove.app.ui.dashed
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import java.time.LocalDate
import kotlin.math.ceil
import kotlin.math.floor

// The agenda in two parts. The first is the day's records, a vertical list of
// what was done, each waiting for a thought, and at its end the thought of the
// day: the cycle — act, to-do, a thought on every act, the thought of the day —
// is complete only when every record carries its thought. The second part holds
// the to-dos, and below them the projects. Nothing scrolls: lists turn pages.

private const val ROW_DP = 50
private const val PICK = 6

private sealed interface Pane {
    data object List : Pane
    data class Thought(val log: DayLog?) : Pane
    data class Journal(val text: String) : Pane
    data class TodoOpen(val todo: Todo) : Pane
    data object NewTodo : Pane
    data class ProjectOpen(val project: Project) : Pane
    data object NewProject : Pane
}

private sealed interface Entry {
    data class Log(val log: DayLog) : Entry
    data object Day : Entry
    data class Heading(val text: String) : Entry
    data class TodoItem(val todo: Todo) : Entry
    data class ProjectItem(val project: Project) : Entry
    data class Add(val todo: Boolean) : Entry
}

private val WEEK = listOf("seg", "ter", "qua", "qui", "sex", "sáb", "dom")

/** "seg 20/10". */
fun dateLabel(iso: String?): String {
    val d = runCatching { LocalDate.parse(iso) }.getOrNull() ?: return ""
    return "${WEEK[d.dayOfWeek.value - 1]} ${d.dayOfMonth.toString().padStart(2, '0')}/${d.monthValue.toString().padStart(2, '0')}"
}

/** "20/10" of an ISO date. */
fun short(iso: String?): String = if (iso == null || iso.length < 10) "" else iso.substring(8, 10) + "/" + iso.substring(5, 7)

private fun hours(seconds: Long): String = when {
    seconds < 3600 -> "${seconds / 60}min"
    seconds < 86400 -> "${seconds / 3600}h"
    else -> "${seconds / 86400}d ${(seconds % 86400) / 3600}h"
}

@Composable
fun AgendaScreen(onHome: () -> Unit, onCalendar: () -> Unit, onLogs: () -> Unit) {
    var plan by remember { mutableStateOf(false) }
    var mode by remember { mutableStateOf<Pane>(Pane.List) }
    var offset by remember { mutableIntStateOf(0) }
    var day by remember { mutableStateOf<AgendaDay?>(null) }
    var todos by remember { mutableStateOf<List<Todo>>(emptyList()) }
    var projects by remember { mutableStateOf<List<Project>>(emptyList()) }
    var actions by remember { mutableStateOf<List<Action>>(emptyList()) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var page by remember { mutableIntStateOf(0) }
    var pages by remember { mutableIntStateOf(1) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    // what is being written
    var draft by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var chosen by remember { mutableStateOf<List<String>>(emptyList()) }
    var deadline by remember { mutableStateOf("") }
    var projectId by remember { mutableStateOf<String?>(null) }
    var pickPage by remember { mutableIntStateOf(0) }
    // the project a to-do was opened or made from, to go back to
    var from by remember { mutableStateOf<Project?>(null) }
    val field = remember { FocusRequester() }

    suspend fun loadDay() {
        try { day = Api.agendaDay(offset) } catch (e: Exception) { message = listOf(e.message ?: "erro") }
    }
    suspend fun loadPlan() {
        try {
            val t = scope.async { Api.todos() }
            val p = scope.async { Api.projects() }
            todos = t.await(); projects = p.await()
        } catch (e: Exception) { message = listOf(e.message ?: "erro") }
    }

    LaunchedEffect(Unit) {
        val a = scope.async { loadDay() }
        val b = scope.async { loadPlan() }
        a.await(); b.await()
        Sfx.powerOn()
    }
    var lastLogs by remember { mutableIntStateOf(Bus.logs) }
    LaunchedEffect(Bus.logs) { if (Bus.logs != lastLogs) { lastLogs = Bus.logs; loadDay() } }

    fun press(n: Int = 0) = Sfx.tap(n)
    fun back() {
        message = emptyList()
        val p = from
        mode = if (p != null && mode !is Pane.ProjectOpen) Pane.ProjectOpen(projects.find { it.id == p.id } ?: p) else Pane.List
        if (mode == Pane.List) from = null
    }
    /** What an entity said about it, when it moved the story. */
    fun heard(lines: List<com.evove.app.api.Line>) {
        if (lines.isEmpty()) return
        message = lines.map { it.text }
        Evove.refresh()
    }
    fun newTodo(project: Project?) {
        press(6)
        deadline = ""
        title = ""; chosen = emptyList(); projectId = project?.id; pickPage = 0
        from = project
        mode = Pane.NewTodo
        if (actions.isEmpty()) scope.launch { actions = runCatching { Api.actions() }.getOrDefault(emptyList()) }
    }
    fun fail(e: Exception) { message = listOf(e.message ?: "erro") }

    fun pickDate(onPicked: (String) -> Unit) {
        val now = LocalDate.now()
        DatePickerDialog(context, { _, y, m, d -> onPicked(LocalDate.of(y, m + 1, d).toString()) }, now.year, now.monthValue - 1, now.dayOfMonth).show()
    }

    fun openThought(log: DayLog?) {
        press(6)
        mode = Pane.Thought(log)
        draft = (if (log != null) log.thought?.content else day?.dayThought?.content) ?: ""
    }

    fun openItem(it: Entry) {
        when (it) {
            is Entry.Log -> openThought(it.log)
            Entry.Day -> openThought(null)
            is Entry.TodoItem -> { press(6); from = null; mode = Pane.TodoOpen(it.todo) }
            is Entry.ProjectItem -> { press(6); mode = Pane.ProjectOpen(it.project) }
            is Entry.Add -> {
                if (it.todo) newTodo(null)
                else {
                    press(6)
                    deadline = ""
                    title = ""
                    mode = Pane.NewProject
                }
            }
            is Entry.Heading -> {}
        }
    }

    fun busyRun(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        scope.launch {
            try { block() } catch (e: Exception) { fail(e) } finally { busy = false }
        }
    }

    BackHandler(enabled = mode != Pane.List) { back() }

    val m = mode
    val cycle = day?.cycle
    DarkScreen(
        Ink.agenda, display = 0.15f,
        displayContent = {
            when {
                message.isNotEmpty() -> Message(message)
                m is Pane.Thought -> { Big(m.log?.content ?: "thought do dia"); Small(if (m.log != null) "o que você pensa disso?" else "feche o ciclo do dia") }
                m is Pane.Journal -> { Big("journal"); Small(dateLabel(day?.date)) }
                m is Pane.TodoOpen -> {
                    val t = m.todo
                    Big(t.title)
                    Small(buildString {
                        projects.find { it.id == t.projectId }?.let { append(it.name).append(" · ") }
                        append(if (t.done) "concluído · +${t.reward} pts" else "${t.actions.count { it.acted }}/${t.actions.size} ações")
                        if (t.deadline != null) append(" · até ${short(t.deadline)}")
                        if (t.late) append(" · atrasado")
                    })
                }
                m is Pane.NewTodo -> {
                    Big("novo to-do")
                    val pn = projects.find { it.id == projectId }?.name
                    Small("${chosen.size} ${if (chosen.size == 1) "ação" else "ações"}" + (pn?.let { " · $it" } ?: "") + (if (deadline.isNotEmpty()) " · até ${short(deadline)}" else ""))
                }
                m is Pane.ProjectOpen -> {
                    val p = m.project
                    Big(p.name)
                    Small((if (p.emblem) (if (p.outcome == "completed") "emblema · completado" else "emblema · finalizado") else if (p.active) "ativo" else "desativado") +
                        " · ${p.stats.todosDone}/${p.stats.todos} to-dos")
                }
                m is Pane.NewProject -> { Big("novo projeto"); if (deadline.isNotEmpty()) Small("até ${short(deadline)}") }
                !plan -> {
                    Big(if (offset == 0) "hoje" else dateLabel(day?.date))
                    if (cycle != null) Small(if (cycle.complete) "ciclo completo" else "${cycle.thoughts}/${cycle.logs} thoughts · ${if (cycle.dayThought) "dia escrito" else "dia aberto"}")
                }
                else -> { Big("plano"); Small("${todos.count { !it.done }} abertos · ${projects.count { !it.emblem }} projetos") }
            }
        },
        bar = {
            fun nextPage() { press(2); page = (page + 1) % pages; Sfx.powerOn() }
            fun setPart(p: Boolean) {
                press(4); plan = p; page = 0; message = emptyList(); mode = Pane.List
                if (p) scope.launch { loadPlan() }
                Sfx.powerOn()
            }
            if (m != Pane.List) {
                Key({ press(0); back() }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
            } else if (!plan) {
                fun shift(delta: Int) {
                    press(if (delta < 0) 1 else 3)
                    offset = minOf(0, offset + delta); page = 0
                    scope.launch { loadDay() }
                }
                Key({ shift(-1) }, Modifier.at(1)) { KeyIcon(Icon.LEFT) }
                Key({ shift(1) }, Modifier.at(2), enabled = offset < 0) { KeyIcon(Icon.RIGHT) }
                Key(::nextPage, Modifier.at(3), enabled = pages > 1) { KeyIcon(Icon.DOWN) }
                Key({
                    val d = day ?: return@Key
                    press(5)
                    scope.launch {
                        try { mode = Pane.Journal(Api.journal(d.date).text.ifEmpty { "nada escrito neste dia" }) } catch (e: Exception) { fail(e) }
                    }
                }, Modifier.at(4)) { KeyIcon(Icon.BOOK) }
                Key({ setPart(true) }, Modifier.at(5)) { KeyIcon(Icon.CHECK) }
            } else {
                Key({ press(1); onCalendar() }, Modifier.at(1)) { KeyIcon(Icon.CALENDAR) }
                if (pages > 1) Ticks(pages, page, Modifier.at(2)) else Box(Modifier.at(2))
                Key(::nextPage, Modifier.at(3), enabled = pages > 1) { KeyIcon(Icon.DOWN) }
                Key({ setPart(false) }, Modifier.at(4)) { KeyIcon(Icon.LIST) }
            }
            HomeKey { press(0); onHome() }
        },
    ) { info ->
        val ink = LocalInk.current
        when (m) {
            is Pane.Thought -> {
                LaunchedEffect(m) { runCatching { field.requestFocus() } }
                Field(draft, { draft = it }, "escreva…", Modifier.weight(1f).heightIn(min = 6.remDp).focusRequester(field), singleLine = false)
                Row(Modifier.fillMaxWidth().heightIn(min = 2.8.remDp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Key({ draft = "" }, Modifier.weight(1f).heightIn(min = 2.8.remDp)) { KeyIcon(Icon.TRASH) }
                    if (m.log != null) Key({ press(1); onLogs() }, Modifier.weight(1f).heightIn(min = 2.8.remDp)) { KeyIcon(Icon.PENCIL) }
                    else Box(Modifier.weight(1f))
                    Box(Modifier.weight(1f))
                    Key({
                        val d = day ?: return@Key
                        busyRun {
                            val said = Api.setThought(d.date, draft, m.log?.id)
                            press(8)
                            loadDay()
                            mode = Pane.List
                            val done = day?.cycle?.complete == true
                            message = if (done) listOf("ciclo completo") else emptyList()
                            if (done) Sfx.gains()
                            heard(said.lines)
                        }
                    }, Modifier.weight(3f).heightIn(min = 2.8.remDp), enabled = !busy) { KeyIcon(Icon.CHECK) }
                }
            }
            is Pane.Journal -> BasicText(
                m.text,
                Modifier.weight(1f).fillMaxWidth().border(1.5.dp, ink).padding(0.7.remDp),
                style = TextStyle(fontFamily = Mono, fontSize = 0.75.rem, lineHeight = 1.5.rem * 0.75f, color = Color.White),
                overflow = TextOverflow.Clip,
            )
            is Pane.TodoOpen -> {
                val t = m.todo
                Label("ações")
                if (t.actions.isEmpty()) Empty("sem ações")
                for (a in t.actions) ListRow(null, Modifier.alpha(if (a.acted) 1f else 0.55f)) {
                    IconView(if (a.acted) Icon.CHECK else Icon.CIRCLE, if (a.acted) ink else Color.White.copy(alpha = 0.5f), 14.dp)
                    Grow(a.name)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Key({ busyRun { press(0); runCatching { Api.deleteTodo(t.id) }; loadPlan(); back() } }, Modifier.weight(1f).heightIn(min = 2.8.remDp)) { KeyIcon(Icon.TRASH) }
                    if (!t.done) {
                        Box(Modifier.weight(2f))
                        Key({
                            busyRun {
                                val r = Api.completeTodo(t.id)
                                Sfx.gains()
                                Bus.bumpUser()
                                loadPlan(); loadDay()
                                back()
                                message = listOf("+${r.reward} pontos", if (r.late) "concluído com atraso" else "concluído")
                            }
                        }, Modifier.weight(3f).heightIn(min = 2.8.remDp), enabled = !busy) { KeyIcon(Icon.CHECK); KeyText("concluir") }
                    }
                }
            }
            is Pane.NewTodo -> {
                LaunchedEffect(Unit) { runCatching { field.requestFocus() } }
                Field(title, { title = it }, "título", Modifier.focusRequester(field), maxLength = 128)
                val pickPages = maxOf(1, ceil(actions.size / PICK.toFloat()).toInt())
                Label("ações · ${pickPage + 1}/$pickPages")
                for (pair in actions.drop(pickPage * PICK).take(PICK).chunked(2)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (a in pair) {
                            Key({ press(7); chosen = if (a.id in chosen) chosen - a.id else chosen + a.id }, Modifier.weight(1f).heightIn(min = 2.6.remDp), on = a.id in chosen) {
                                KeyText(a.name, Type.key.copy(fontSize = 0.68.rem))
                            }
                        }
                        if (pair.size == 1) Box(Modifier.weight(1f))
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val h = Modifier.heightIn(min = 2.8.remDp)
                    Key({ press(2); pickPage = (pickPage + 1) % pickPages }, Modifier.weight(1f).then(h)) { KeyIcon(Icon.RIGHT) }
                    Key({ pickDate { deadline = it } }, Modifier.weight(1f).then(h), on = deadline.isNotEmpty()) { KeyIcon(Icon.FLAG, 16.dp) }
                    Key({
                        press(7)
                        val open = projects.filter { !it.emblem }
                        val i = open.indexOfFirst { it.id == projectId }
                        projectId = open.getOrNull(i + 1)?.id
                    }, Modifier.weight(1f).then(h), on = projectId != null) { KeyIcon(Icon.LIST) }
                    Key({
                        busyRun {
                            val said = Api.createTodo(title, chosen, deadline.ifEmpty { null }, projectId)
                            press(8); loadPlan()
                            val p = from
                            mode = if (p != null) Pane.ProjectOpen(projects.find { it.id == p.id } ?: p) else Pane.List
                            heard(said.lines)
                        }
                    }, Modifier.weight(3f).then(h), enabled = !busy && title.isNotBlank()) { KeyIcon(Icon.CHECK) }
                }
            }
            is Pane.ProjectOpen -> {
                // a project is its to-dos: they are listed in it, and made from it
                val p = m.project
                val its = todos.filter { it.projectId == p.id }
                Stats(buildList {
                    add("tempo ativo" to "${hours(p.stats.activeSeconds)} · parado ${hours(p.stats.inactiveSeconds)}")
                    add("ações · marcas" to "${p.stats.actions} · ${p.stats.marks}")
                    if (p.deadline != null) add("prazo" to short(p.deadline))
                })
                if (p.emblem) Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { IconView(Icon.STAR, ink, 32.dp) }
                Label("to-dos · ${its.count { it.done }}/${its.size}")
                val room = maxOf(1, floor((info.height.value - 230) / (ROW_DP + 8)).toInt())
                if (its.isEmpty()) Empty("nenhum to-do neste projeto")
                for (t in its.sortedBy { it.done }.take(room)) AgendaRow(Entry.TodoItem(t), day) { press(6); from = p; mode = Pane.TodoOpen(t) }
                if (its.size > room) Small("+${its.size - room} to-dos")
                if (!p.emblem) AgendaRow(Entry.Add(true), day) { newTodo(p) }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val h = Modifier.heightIn(min = 2.8.remDp)
                    Key({ busyRun { Api.deleteProject(p.id); mode = Pane.List; press(5); loadPlan() } }, Modifier.weight(1f).then(h), enabled = !busy) { KeyIcon(Icon.TRASH) }
                    if (!p.emblem) {
                        Key({ busyRun { mode = Pane.ProjectOpen(Api.setProjectActive(p.id, !p.active)); press(5); loadPlan() } }, Modifier.weight(1f).then(h), enabled = !busy) {
                            KeyIcon(if (p.active) Icon.PAUSE else Icon.PLAY)
                        }
                        Box(Modifier.weight(1f))
                        Key({
                            busyRun {
                                val ended = Api.endProject(p.id)
                                Sfx.gains()
                                mode = Pane.ProjectOpen(ended)
                                message = listOf("emblema", if (ended.outcome == "completed") "projeto completado" else "projeto finalizado")
                                press(5); loadPlan()
                            }
                        }, Modifier.weight(3f).then(h), enabled = !busy) { KeyIcon(Icon.FLAG); KeyText("emblema") }
                    }
                }
            }
            is Pane.NewProject -> {
                LaunchedEffect(Unit) { runCatching { field.requestFocus() } }
                Field(title, { title = it }, "nome do projeto", Modifier.focusRequester(field), maxLength = 128)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val h = Modifier.heightIn(min = 2.8.remDp)
                    Key({ pickDate { deadline = it } }, Modifier.weight(1f).then(h), on = deadline.isNotEmpty()) { KeyIcon(Icon.FLAG, 16.dp) }
                    Box(Modifier.weight(2f))
                    Key({ busyRun { val said = Api.createProject(title, deadline.ifEmpty { null }); press(8); loadPlan(); mode = Pane.List; heard(said.lines) } },
                        Modifier.weight(3f).then(h), enabled = !busy && title.isNotBlank()) { KeyIcon(Icon.CHECK) }
                }
            }
            Pane.List -> {
                val items: List<Entry> = if (!plan) (day?.logs ?: emptyList()).map { Entry.Log(it) } + Entry.Day
                else buildList {
                    add(Entry.Heading("to-dos")); todos.forEach { add(Entry.TodoItem(it)) }; add(Entry.Add(true))
                    add(Entry.Heading("projetos")); projects.forEach { add(Entry.ProjectItem(it)) }; add(Entry.Add(false))
                }
                val perPage = maxOf(1, floor((info.height.value - 64) / (ROW_DP + 8)).toInt())
                val count = maxOf(1, ceil(items.size / perPage.toFloat()).toInt())
                if (pages != count) pages = count
                if (page >= count) page = count - 1
                if (!plan && cycle != null) CycleSteps(cycle.acted, cycle.todo, cycle.thoughts, cycle.logs, cycle.dayThought, cycle.complete)
                // the records hang on a rail: a line through every node
                Column(
                    Modifier.fillMaxWidth().then(if (!plan) Modifier.drawBehind {
                        val x = (0.7 * 18 + 5.5).dp.toPx()
                        drawLine(ink.copy(alpha = 0.35f), Offset(x, 0f), Offset(x, size.height), 1.5.dp.toPx())
                    } else Modifier),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    for (it in items.drop(page * perPage).take(perPage)) AgendaRow(it, day, ::openItem)
                }
            }
        }
    }
}

@Composable
private fun AgendaRow(it: Entry, day: AgendaDay?, open: (Entry) -> Unit) {
    val ink = LocalInk.current
    val sub = Type.row.copy(fontSize = 0.72.rem, color = Color.White.copy(alpha = 0.55f))
    when (it) {
        is Entry.Heading -> Label(it.text)
        is Entry.Log -> ListRow({ open(it) }, minHeight = 3.1.remDp) {
            Node(it.log.thought != null)
            Tag(it.log.period ?: "··")
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(0.15.remDp)) {
                BasicText(caps(it.log.content), style = Type.row, maxLines = 1, overflow = TextOverflow.Ellipsis)
                BasicText(it.log.thought?.content ?: "sem thought", style = if (it.log.thought != null) sub.copy(color = ink) else sub, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        Entry.Day -> ListRow({ open(it) }, minHeight = 3.1.remDp, dashed = day?.dayThought == null) {
            Node(day?.dayThought != null, diamond = true)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(0.15.remDp)) {
                BasicText("THOUGHT DO DIA", style = Type.row, maxLines = 1)
                BasicText(day?.dayThought?.content ?: "toque para escrever", style = if (day?.dayThought != null) sub.copy(color = ink) else sub, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        is Entry.TodoItem -> ListRow({ open(it) }, Modifier.alpha(if (it.todo.done) 0.55f else 1f)) {
            IconView(if (it.todo.done) Icon.CHECK else Icon.SQUARE, if (it.todo.done) ink else Color.White.copy(alpha = 0.5f), 14.dp)
            Grow(it.todo.title)
            if (it.todo.late) BasicText("ATRASO", Modifier.border(1.dp, Ink.late).padding(horizontal = 0.35.remDp, vertical = 0.1.remDp),
                style = Type.row.copy(fontSize = 0.62.rem, color = Ink.late))
            Tag(if (it.todo.done) "+${it.todo.reward}" else "${it.todo.actions.count { a -> a.acted }}/${it.todo.actions.size}")
        }
        is Entry.ProjectItem -> ListRow({ open(it) }, Modifier.alpha(if (!it.project.active && !it.project.emblem) 0.55f else 1f)) {
            IconView(if (it.project.emblem) Icon.STAR else if (it.project.active) Icon.PLAY else Icon.PAUSE, ink, 14.dp)
            Grow(it.project.name)
            Tag("${it.project.stats.todosDone}/${it.project.stats.todos}")
        }
        is Entry.Add -> ListRow({ open(it) }, dashed = true) {
            IconView(Icon.PLUS, ink, 14.dp)
            Grow(caps(if (it.todo) "to-do" else "projeto"), Type.row.copy(color = ink))
        }
    }
}

/** A record's node on the rail: lit where a thought is. */
@Composable
private fun Node(on: Boolean, diamond: Boolean = false) {
    val ink = LocalInk.current
    val shape = if (diamond) androidx.compose.ui.graphics.RectangleShape else androidx.compose.foundation.shape.CircleShape
    Box(
        Modifier.size(11.dp).then(if (diamond) Modifier.rotate(45f) else Modifier)
            .background(if (on) ink else Color.Black, shape).border(1.5.dp, ink, shape),
    )
}

/** The four steps of the cycle, linked; the to-do the one that may be skipped. */
@Composable
private fun CycleSteps(acted: Boolean, todo: Boolean, thoughts: Int, logs: Int, dayThought: Boolean, complete: Boolean) {
    val ink = LocalInk.current
    val steps = listOf(
        Triple("agir", acted, false),
        Triple("to-do", todo, true),
        Triple("$thoughts/$logs", logs > 0 && thoughts == logs, false),
        Triple("dia", dayThought, false),
    )
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        steps.forEachIndexed { i, (label, done, optional) ->
            if (i > 0) Box(Modifier.weight(1f).height(1.5.dp).background(ink.copy(alpha = if (done) 1f else 0.25f)))
            val box = Modifier.alpha(if (done) 1f else 0.45f).background(if (done) ink.copy(alpha = 0.2f) else Color.Transparent)
            BasicText(
                caps(label),
                (if (optional) box.dashed(ink) else box.border(1.5.dp, ink))
                    .padding(horizontal = 0.45.remDp, vertical = 0.25.remDp),
                style = Type.row.copy(fontSize = 0.66.rem, color = if (complete) Color.White else ink),
            )
        }
    }
}
