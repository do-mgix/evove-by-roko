package com.evove.app.screens

import androidx.compose.foundation.layout.Box
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import com.evove.app.ui.Field
import com.evove.app.ui.KeyText
import com.evove.app.ui.Type
import com.evove.app.ui.caps
import com.evove.app.ui.rem
import com.evove.app.ui.remDp
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.evove.app.Prefs
import com.evove.app.api.Api
import com.evove.app.sound.Sfx
import com.evove.app.ui.Big
import com.evove.app.ui.DarkScreen
import com.evove.app.ui.Empty
import com.evove.app.ui.Grow
import com.evove.app.ui.Icon
import com.evove.app.ui.IconView
import com.evove.app.ui.Ink
import com.evove.app.ui.Key
import com.evove.app.ui.KeyIcon
import com.evove.app.ui.ListRow
import com.evove.app.ui.LocalInk
import com.evove.app.ui.Message
import com.evove.app.ui.Small
import com.evove.app.ui.Tag
import com.evove.app.ui.Ticks
import kotlinx.coroutines.launch
import kotlin.math.ceil
import kotlin.math.floor

// The accounts kept on this device, as a machine with several users keeps
// them: each one signed in, a tap switches to it, with its own evove — its
// modules, its story — and its own data. A test account is made in one tap, with
// a random name and password, to walk the evove from its first step; it lives
// only here. Each account can be started over from nothing, deleted for good,
// or only taken off the device, which ends its session.

private const val ROW_DP = 50

private sealed interface AccountPane {
    data object List : AccountPane
    data class Manage(val account: Prefs.Account) : AccountPane
    data class Confirm(val account: Prefs.Account, val delete: Boolean) : AccountPane
}

@Composable
fun AccountsScreen(
    current: String?,
    onUse: (Prefs.Account) -> Unit,
    onAdd: () -> Unit,
    onTest: (String) -> Unit,
    onBack: (() -> Unit)?,
    onEmpty: () -> Unit,
    onReset: (String) -> Unit = {},
    onGone: (String) -> Unit = {},
) {
    var accounts by remember { mutableStateOf(Prefs.accounts) }
    var managing by remember { mutableStateOf(false) }
    var pane by remember { mutableStateOf<AccountPane>(AccountPane.List) }
    var password by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var page by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<List<String>>(emptyList()) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { Sfx.powerOn() }

    fun test() {
        if (busy) return
        busy = true
        Sfx.tap(9)
        scope.launch {
            try {
                val s = Api.registerTest()
                onTest(s.username)
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    // after an account left the device: the list again, or the login when none is left
    fun left(a: Prefs.Account) {
        accounts = Prefs.accounts
        pane = AccountPane.List
        if (a.username == current) onGone(a.username)
        if (accounts.isEmpty()) onEmpty()
    }

    fun remove(a: Prefs.Account) {
        Sfx.tap(0)
        Prefs.forget(a.username)
        scope.launch { Api.logoutToken(a.token) }
        message = listOf("fora do aparelho", a.username)
        left(a)
    }

    fun confirm(p: AccountPane.Confirm) {
        val pass = p.account.password ?: password
        if (busy || pass.isEmpty()) return
        busy = true
        scope.launch {
            try {
                if (p.delete) {
                    Api.deleteAccountOf(p.account, pass)
                    message = listOf("apagada", p.account.username)
                    Sfx.tap(0)
                    left(p.account)
                } else {
                    Api.resetAccount(p.account.token, pass)
                    accounts = Prefs.accounts
                    message = listOf("reiniciada", "${p.account.username} começa do zero")
                    pane = AccountPane.List
                    Sfx.gains()
                    onReset(p.account.username)
                }
                password = ""
            } catch (e: Exception) {
                message = listOf(e.message ?: "erro")
            } finally {
                busy = false
            }
        }
    }

    fun back() {
        message = emptyList()
        password = ""
        pane = when (val p = pane) {
            is AccountPane.Confirm -> AccountPane.Manage(p.account)
            else -> AccountPane.List
        }
    }

    BackHandler(enabled = pane != AccountPane.List) { back() }

    val p = pane
    DarkScreen(
        Ink.attributes, display = 0.16f,
        displayContent = {
            when {
                message.isNotEmpty() -> Message(message)
                p is AccountPane.Manage -> { Big(p.account.username); Small(listOfNotNull(if (p.account.test) "teste" else null, if (p.account.username == current) "em uso" else null).joinToString(" · ").ifEmpty { "neste aparelho" }) }
                p is AccountPane.Confirm -> { Big(if (p.delete) "apagar?" else "reiniciar?"); Small(p.account.username) }
                else -> {
                    Big(if (managing) "gerir" else "contas")
                    Small(if (managing) "toque numa conta para reiniciar, apagar ou tirar do aparelho" else "${accounts.size} neste aparelho" + (current?.let { " · em uso: $it" } ?: ""))
                }
            }
        },
        bar = {
            if (p == AccountPane.List) {
                Key({ Sfx.tap(3); onAdd() }, Modifier.at(1)) { KeyIcon(Icon.PLUS) }
                Key(::test, Modifier.at(2), enabled = !busy) { KeyIcon(Icon.DICE) }
                Key({ Sfx.tap(5); managing = !managing; message = emptyList() }, Modifier.at(3).testTag("manage"), on = managing, enabled = accounts.isNotEmpty()) { KeyIcon(Icon.DOTS) }
                Key({ Sfx.tap(2); page++ }, Modifier.at(4)) { KeyIcon(Icon.DOWN) }
            } else {
                Key({ Sfx.tap(0); back() }, Modifier.at(1, 2)) { KeyIcon(Icon.LEFT) }
            }
            if (onBack != null) Key({ Sfx.tap(0); onBack() }, Modifier.at(6)) { KeyIcon(Icon.CIRCLE, 16.dp) }
            else Box(Modifier.at(6))
        },
    ) { info ->
        val ink = LocalInk.current
        val h = Modifier.heightIn(min = 2.8.remDp)
        when (p) {
            AccountPane.List -> {
                val perPage = maxOf(1, floor((info.height.value - 16) / (ROW_DP + 8)).toInt())
                val pages = maxOf(1, ceil(accounts.size / perPage.toFloat()).toInt())
                val at = page % pages
                if (accounts.isEmpty()) Empty("nenhuma conta — entre, crie uma ou sorteie uma de teste")
                for (a in accounts.drop(at * perPage).take(perPage)) {
                    val inUse = a.username == current
                    ListRow({
                        message = emptyList()
                        if (managing) { Sfx.tap(6); pane = AccountPane.Manage(a) }
                        else if (!inUse) { Sfx.tap(7); onUse(a) } else onBack?.invoke()
                    }) {
                        IconView(if (managing) Icon.DOTS else if (inUse) Icon.CHECK else Icon.USER, ink, 16.dp)
                        Grow(a.username, upper = true)
                        if (a.test) Tag("teste")
                        if (inUse) Tag("em uso")
                    }
                }
                if (pages > 1) Ticks(pages, at)
            }
            is AccountPane.Manage -> {
                val a = p.account
                if (a.username != current) Key({ Sfx.tap(7); onUse(a) }, Modifier.fillMaxWidth().then(h)) { KeyIcon(Icon.CHECK); KeyText("usar") }
                Key({ Sfx.tap(5); remove(a) }, Modifier.fillMaxWidth().then(h)) { KeyIcon(Icon.CROSS); KeyText("tirar do aparelho") }
                CompositionLocalProvider(LocalInk provides Ink.danger) {
                    Key({ Sfx.tap(0); message = emptyList(); pane = AccountPane.Confirm(a, delete = false) }, Modifier.fillMaxWidth().then(h)) { KeyIcon(Icon.SHUFFLE); KeyText("reiniciar tudo") }
                    Key({ Sfx.tap(0); message = emptyList(); pane = AccountPane.Confirm(a, delete = true) }, Modifier.fillMaxWidth().then(h)) { KeyIcon(Icon.TRASH); KeyText("apagar para sempre") }
                }
            }
            is AccountPane.Confirm -> {
                BasicText(
                    caps(if (p.delete) "a conta e tudo o que ela tem somem, em todos os aparelhos. não volta."
                    else "tudo o que a conta tem — ações, registros, atributos, pontos, descobertas, agenda, jornada, aliados e o evove — some, " +
                        "e ela começa do primeiro passo, com o mesmo nome e a mesma senha. não volta."),
                    style = Type.row.copy(fontSize = 0.75.rem, color = Color.White.copy(alpha = 0.75f), lineHeight = 1.15.rem),
                )
                if (p.account.password == null) Field(password, { password = it }, "senha de ${p.account.username}", password = true,
                    keyboard = KeyboardOptions(imeAction = ImeAction.Done))
                CompositionLocalProvider(LocalInk provides Ink.danger) {
                    Key({ confirm(p) }, Modifier.fillMaxWidth().then(h), enabled = !busy && (p.account.password != null || password.isNotEmpty())) {
                        KeyIcon(if (p.delete) Icon.TRASH else Icon.SHUFFLE); KeyText(if (busy) "…" else if (p.delete) "apagar para sempre" else "reiniciar tudo")
                    }
                }
            }
        }
    }
}
