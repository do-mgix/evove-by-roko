package com.evove.app.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import com.evove.app.api.Api
import kotlinx.coroutines.launch

/** Entering, creating a profile, or asking for a new password. */
@Composable
fun LoginScreen(onSelected: (String) -> Unit) {
    var mode by remember { mutableStateOf("login") }
    var username by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    var sent by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    val canSubmit = username.isNotBlank() &&
        (mode == "forgot" || (password.length >= 8 && (mode == "login" || password == confirm)))

    fun switch(next: String) {
        mode = next
        error = null
        sent = false
        password = ""
        confirm = ""
    }

    fun submit() {
        if (!canSubmit || busy) return
        busy = true
        error = null
        scope.launch {
            try {
                if (mode == "forgot") {
                    Api.forgotPassword(username.trim())
                    sent = true
                } else {
                    val s = if (mode == "login") Api.login(username.trim(), password)
                    else Api.register(username.trim(), password, email.trim().ifEmpty { null })
                    password = ""
                    confirm = ""
                    onSelected(s.username)
                }
            } catch (e: Exception) {
                error = e.message ?: "erro"
            } finally {
                busy = false
            }
        }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(1.remDp),
        verticalArrangement = Arrangement.spacedBy(1.remDp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(
            Modifier.widthIn(max = 320.dp).fillMaxWidth()
                .background(Color.White, RoundedCornerShape(8.dp))
                .border(1.dp, Paper.line, RoundedCornerShape(8.dp))
                .padding(horizontal = 2.5.remDp * 0.8f, vertical = 2.remDp),
        ) {
            BasicText(
                "EVOVE", Modifier.fillMaxWidth().padding(bottom = 1.5.remDp),
                style = TextStyle(fontFamily = Sans, fontSize = 1.5.rem, color = Paper.accent, letterSpacing = 0.15.em, textAlign = TextAlign.Center),
            )
            BasicText(
                caps(when (mode) { "login" -> "entrar"; "register" -> "criar perfil"; else -> "recuperar senha" }),
                Modifier.padding(bottom = 0.75.remDp),
                style = TextStyle(fontFamily = Sans, fontSize = 0.7.rem, color = Paper.muted, letterSpacing = 0.1.em),
            )
            val next = KeyboardActions(onDone = { submit() })
            if (mode == "forgot") {
                if (sent) {
                    BasicText(
                        "Se a conta existir e tiver e-mail, o link para criar uma senha nova chega em alguns minutos. Confira o spam.",
                        Modifier.padding(bottom = 0.5.remDp),
                        style = TextStyle(fontFamily = Sans, fontSize = 0.85.rem, color = Paper.soft, lineHeight = 1.45.em),
                    )
                } else {
                    PaperField(username, { username = it }, "usuário ou e-mail", actions = next)
                    PaperButton(if (busy) "..." else "enviar link", enabled = canSubmit && !busy, onClick = ::submit)
                }
                PaperLink("voltar para entrar") { switch("login") }
            } else {
                PaperField(username, { username = it.take(24) }, "usuário", actions = next)
                PaperField(password, { password = it }, "senha", password = true, actions = next)
                if (mode == "register") {
                    PaperField(confirm, { confirm = it }, "repita a senha", password = true, actions = next)
                    PaperField(email, { email = it }, "e-mail (opcional, para recuperar a senha)", type = KeyboardType.Email, actions = next)
                    val rule = if (password.isNotEmpty() && password.length < 8) "mínimo de 8 caracteres"
                    else if (confirm.isNotEmpty() && password != confirm) "as senhas não conferem" else null
                    if (rule != null) BasicText(rule, Modifier.padding(bottom = 0.75.remDp), style = TextStyle(fontFamily = Sans, fontSize = 0.75.rem, color = Paper.accent))
                }
                PaperButton(if (busy) "..." else if (mode == "login") "entrar" else "criar", enabled = canSubmit && !busy, onClick = ::submit)
                PaperLink(if (mode == "login") "criar um perfil novo" else "já tenho um perfil") { switch(if (mode == "login") "register" else "login") }
                if (mode == "login") PaperLink("esqueci a senha") { switch("forgot") }
            }
            error?.let { BasicText(it, Modifier.padding(top = 0.75.remDp), style = TextStyle(fontFamily = Sans, fontSize = 0.8.rem, color = Paper.error)) }
        }
        BasicText(
            "política de privacidade",
            Modifier.clickable { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(Api.BASE + "/privacidade"))) },
            style = TextStyle(fontFamily = Sans, fontSize = 0.72.rem, color = Color.White.copy(alpha = 0.75f), textDecoration = TextDecoration.Underline),
        )
    }
}

@Composable
fun PaperLink(text: String, onClick: () -> Unit) {
    BasicText(
        text,
        Modifier.fillMaxWidth().padding(top = 0.9.remDp).clickable(onClick = onClick),
        style = TextStyle(fontFamily = Sans, fontSize = 0.78.rem, color = Paper.muted, textDecoration = TextDecoration.Underline, textAlign = TextAlign.Center),
    )
}
