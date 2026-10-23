package com.evove.app.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.evove.app.Evove
import com.evove.app.Page
import com.evove.app.sound.Sfx
import com.evove.app.api.Ally
import com.evove.app.api.Api
import com.evove.app.api.Project
import com.evove.app.api.SessionInfo
import com.evove.app.api.UserState
import com.evove.app.ui.PaperButton
import com.evove.app.ui.PaperCard
import com.evove.app.ui.PaperError
import com.evove.app.ui.PaperField
import com.evove.app.ui.PaperInline
import com.evove.app.ui.PaperPage
import com.evove.app.ui.PaperRow
import com.evove.app.ui.Paper
import com.evove.app.ui.paperMuted
import com.evove.app.ui.paperText
import com.evove.app.ui.rem
import kotlinx.coroutines.async
import kotlinx.coroutines.launch

/** Timestamps come back without a zone: printed as the server wrote them. */
private fun stamp(iso: String) = iso.take(16).replace("T", " ")

private fun checkpointIn(seconds: Long): String {
    val d = seconds / 86400
    val h = (seconds % 86400) / 3600
    val m = (seconds % 3600) / 60
    return if (d > 0) "${d}d ${h}h" else "${h}h ${m}m"
}

@Composable
fun ProfilePage(onBack: () -> Unit, onAccounts: () -> Unit, onLogout: (everywhere: Boolean) -> Unit) {
    var info by remember { mutableStateOf<SessionInfo?>(null) }
    var user by remember { mutableStateOf<UserState?>(null) }
    var allies by remember { mutableStateOf<List<Ally>>(emptyList()) }
    var emblems by remember { mutableStateOf<List<Project>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        try {
            val i = scope.async { Api.sessionInfo() }
            val u = scope.async { Api.user() }
            val a = scope.async { runCatching { Api.allies().items }.getOrDefault(emptyList()) }
            val e = scope.async { runCatching { Api.emblems() }.getOrDefault(emptyList()) }
            info = i.await(); user = u.await(); allies = a.await(); emblems = e.await()
        } catch (x: Exception) {
            error = x.message ?: "erro"
        } finally {
            loading = false
        }
    }

    PaperPage(Page.PROFILE.option, Page.PROFILE.title, onBack) {
        val i = info
        val u = user
        if (loading) BasicText("carregando...", style = paperMuted)
        PaperError(error)
        if (i != null) {
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                BasicText(com.evove.app.ui.caps(i.username), style = paperText.copy(fontSize = 1.4.rem))
                BasicText("PERFIL", style = paperMuted)
            }
            EvoveCard()
            PaperButton("contas deste aparelho", ghost = true, onClick = onAccounts)
            if (u != null) {
                PaperCard("identidade") {
                    PaperRow("nickname", u.nickname ?: "—", action = "sortear outro" to {
                        scope.launch { runCatching { Api.rerollNickname() }.onSuccess { user = u.copy(nickname = it.nickname) }.onFailure { error = it.message } }
                    })
                    PaperRow("passcode", u.passcode ?: "—", "quem tiver vira seu aliado")
                }
                PaperCard("aliados") {
                    if (allies.isEmpty()) BasicText("nenhum ainda", style = paperMuted)
                    for (a in allies) PaperRow(a.nickname, "estágio ${a.stage} · ${a.marks} marcas", action = "remover" to {
                        scope.launch { runCatching { Api.removeAlly(a.nickname) }; allies = runCatching { Api.allies().items }.getOrDefault(allies) }
                    })
                    var passcode by remember { mutableStateOf("") }
                    var allyError by remember { mutableStateOf<String?>(null) }
                    var busy by remember { mutableStateOf(false) }
                    fun add() {
                        if (passcode.isBlank() || busy) return
                        busy = true
                        allyError = null
                        scope.launch {
                            try {
                                Api.addAlly(passcode)
                                passcode = ""
                                allies = Api.allies().items
                            } catch (e: Exception) {
                                allyError = e.message ?: "erro"
                            } finally {
                                busy = false
                            }
                        }
                    }
                    PaperField(passcode, { passcode = it.take(8) }, "passcode de outro perfil", actions = KeyboardActions(onDone = { add() }))
                    PaperButton(if (busy) "..." else "adicionar", enabled = passcode.isNotBlank() && !busy, onClick = ::add)
                    PaperError(allyError)
                }
                if (emblems.isNotEmpty()) PaperCard("emblemas") {
                    for (p in emblems) PaperRow("★ ${p.name}", "${if (p.outcome == "completed") "completado" else "finalizado"} · ${p.stats.todosDone}/${p.stats.todos} to-dos · ${p.stats.marks} marcas")
                }
                PaperCard("jornada") {
                    PaperRow("day", "${u.day}", "desde o primeiro login")
                    PaperRow("streak", "${u.consecutiveDays}", "dias consecutivos")
                    PaperRow("stage", "${u.stage}", "checkpoint em ${checkpointIn(u.checkpointSecondsLeft)}")
                }
            }
            PaperCard("conta") {
                PaperRow("user id", "${i.userId}")
                PaperRow("username", i.username)
                PaperRow("criada em", i.createdAt.take(10))
                var editing by remember { mutableStateOf(false) }
                if (!editing) PaperRow("e-mail", i.email ?: "—", action = (if (i.email != null) "alterar" else "adicionar") to { editing = true })
                else {
                    // the recovery e-mail is changed with the password, like deleting
                    var draft by remember { mutableStateOf(i.email ?: "") }
                    var password by remember { mutableStateOf("") }
                    var busy by remember { mutableStateOf(false) }
                    var emailError by remember { mutableStateOf<String?>(null) }
                    fun save() {
                        if (password.isEmpty() || busy) return
                        busy = true
                        emailError = null
                        scope.launch {
                            try {
                                info = i.copy(email = Api.setRecoveryEmail(draft.trim(), password))
                                editing = false
                            } catch (e: Exception) {
                                emailError = e.message ?: "erro"
                            } finally {
                                busy = false
                                password = ""
                            }
                        }
                    }
                    BasicText("usado só para recuperar a senha; deixe vazio para remover", style = paperMuted)
                    PaperField(draft, { draft = it }, "e-mail", type = KeyboardType.Email)
                    PaperField(password, { password = it }, "sua senha", password = true, actions = KeyboardActions(onDone = { save() }))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PaperButton(if (busy) "..." else "salvar", enabled = password.isNotEmpty() && !busy, modifier = Modifier.weight(1f), onClick = ::save)
                        PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { editing = false }
                    }
                    PaperError(emailError)
                }
            }
            PaperCard("sessão") {
                PaperRow("iniciada", stamp(i.session.createdAt))
                PaperRow("expira", stamp(i.session.expiresAt))
                PaperRow("sessões ativas", "${i.activeSessions}")
                PaperRow("api", Api.BASE)
            }
            PaperInline("política de privacidade") {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(Api.BASE + "/privacidade")))
            }
        }

        // outside the load: signing out must work even when the details fail
        PaperCard("log out") {
            var confirmAll by remember { mutableStateOf(false) }
            Exit("log out", "encerra só esta sessão") { onLogout(false) }
            if (confirmAll) {
                BasicText("encerrar todas as sessões, inclusive esta?", style = paperText)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PaperButton("encerrar", danger = true, modifier = Modifier.weight(1f)) { onLogout(true) }
                    PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { confirmAll = false }
                }
            } else Exit("log out everywhere", "encerra a sessão em todos os dispositivos") { confirmAll = true }
        }

        PaperCard("excluir conta") {
            var deleting by remember { mutableStateOf(false) }
            if (!deleting) Exit("excluir conta", "apaga a conta e todos os dados") { deleting = true }
            else {
                // deleting asks for the password again, and only then for the tap
                var password by remember { mutableStateOf("") }
                var busy by remember { mutableStateOf(false) }
                var deleteError by remember { mutableStateOf<String?>(null) }
                fun confirm() {
                    if (password.isEmpty() || busy) return
                    busy = true
                    deleteError = null
                    scope.launch {
                        try { Api.deleteAccount(password) } catch (e: Exception) { deleteError = e.message ?: "erro" } finally { busy = false }
                    }
                }
                BasicText(
                    "Apaga a conta e todos os dados dela — atributos, ações, registros, agenda e projetos — em todos os dispositivos. Não pode ser desfeito.",
                    style = paperText.copy(color = Paper.error),
                )
                PaperField(password, { password = it }, "sua senha", password = true, actions = KeyboardActions(onDone = { confirm() }))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PaperButton(if (busy) "..." else "excluir para sempre", danger = true, enabled = password.isNotEmpty() && !busy, modifier = Modifier.weight(1f), onClick = ::confirm)
                    PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { deleting = false }
                }
                PaperError(deleteError)
            }
        }
    }
}

@Composable
private fun Exit(label: String, note: String, onClick: () -> Unit) {
    Column {
        PaperButton(label, ghost = true, onClick = onClick)
        BasicText(note, style = paperMuted.copy(fontSize = 0.7.rem))
    }
}

/** The profile's evove as the server keeps it: the passcode that hands the
 *  build to someone else, a field for someone else's or a module's, every
 *  module with its code once it is had, the selector and what moves it, the
 *  counters the rules watch, the story's step — and going back to its start. */
@Composable
private fun EvoveCard() {
    val v = Evove.view
    var code by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var said by remember { mutableStateOf<String?>(null) }
    var resetting by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun send() {
        if (code.isBlank() || busy) return
        busy = true
        said = null
        scope.launch {
            try {
                val r = Api.passcode(code)
                Evove.apply(r)
                said = r.lines.lastOrNull()?.text
                code = ""
                Sfx.gains()
            } catch (e: Exception) {
                said = e.message ?: "erro"
            } finally {
                busy = false
            }
        }
    }

    PaperCard("evove") {
        if (v == null) { BasicText("…", style = paperMuted); return@PaperCard }
        PaperRow("passcode", v.passcode, "quem digitar recebe este evove: módulos, entidades e seletor — os dados ficam com você")
        PaperRow("sessão", "${v.session}", "o layout da home muda a cada uma")
        PaperRow("história", if (v.story.done) "contada" else "${v.story.at}/${v.story.of} · ${v.story.step}")
        val sel = v.selector
        PaperRow("seletor", "nível ${sel.level}", when (sel.level) {
            1 -> "${sel.turns}/${sel.nextAt ?: 1000} viradas para o nível 2"
            2 -> "${((sel.chance ?: 0.0) * 100).toInt()}% de chance de nível 3 a cada sessão"
            else -> "o último, por enquanto"
        })
        PaperRow("contagens", listOf("visits", "acts", "opens", "talks", "buys", "plans").joinToString(" · ") { k -> "${v.counters[k] ?: 0} ${mapOf("visits" to "visitas", "acts" to "atos", "opens" to "aberturas", "talks" to "conversas", "buys" to "compras", "plans" to "planos")[k] ?: k}" })
        PaperRow("entidades", v.entities.joinToString(" · ").ifEmpty { "nenhuma ainda" })
        for (m in v.modules) PaperRow(m.label, if (m.on) (m.code ?: "—") else "??????", if (m.on) null else "ainda não")
        PaperField(code, { code = it.take(16) }, "digite um passcode", actions = KeyboardActions(onDone = { send() }))
        PaperButton(if (busy) "..." else "carregar", enabled = code.isNotBlank() && !busy, onClick = ::send)
        said?.let { BasicText(com.evove.app.ui.caps(it), style = paperText.copy(color = com.evove.app.ui.LocalInk.current)) }
        if (!resetting) PaperButton("recomeçar o tutorial", ghost = true) { resetting = true }
        else {
            BasicText("o evove volta ao primeiro passo: só agir na home, a história de novo. seus dados ficam.", style = paperText)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PaperButton("recomeçar", danger = true, modifier = Modifier.weight(1f)) {
                    scope.launch {
                        runCatching { Api.resetEngine() }.onSuccess { Evove.apply(it); said = "tutorial recomeçado" }.onFailure { said = it.message }
                        resetting = false
                    }
                }
                PaperButton("cancelar", ghost = true, modifier = Modifier.weight(1f)) { resetting = false }
            }
        }
    }
}