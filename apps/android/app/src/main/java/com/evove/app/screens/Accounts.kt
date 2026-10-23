package com.evove.app.screens

import androidx.compose.foundation.layout.Box
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
// only here. Removing an account ends its session.

private const val ROW_DP = 50

@Composable
fun AccountsScreen(
    current: String?,
    onUse: (Prefs.Account) -> Unit,
    onAdd: () -> Unit,
    onTest: (String) -> Unit,
    onBack: (() -> Unit)?,
    onEmpty: () -> Unit,
) {
    var accounts by remember { mutableStateOf(Prefs.accounts) }
    var removing by remember { mutableStateOf(false) }
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

    fun remove(a: Prefs.Account) {
        Sfx.tap(0)
        Prefs.forget(a.username)
        accounts = Prefs.accounts
        scope.launch { Api.logoutToken(a.token) }
        if (accounts.isEmpty()) onEmpty()
    }

    DarkScreen(
        Ink.attributes, display = 0.16f,
        displayContent = {
            if (message.isNotEmpty()) Message(message)
            else {
                Big(if (removing) "remover" else "contas")
                Small(if (removing) "toque numa conta para tirá-la do aparelho" else "${accounts.size} neste aparelho" + (current?.let { " · em uso: $it" } ?: ""))
            }
        },
        bar = {
            Key({ Sfx.tap(3); onAdd() }, Modifier.at(1)) { KeyIcon(Icon.PLUS) }
            Key(::test, Modifier.at(2), enabled = !busy) { KeyIcon(Icon.DICE) }
            Key({ Sfx.tap(5); removing = !removing }, Modifier.at(3), on = removing, enabled = accounts.isNotEmpty()) { KeyIcon(Icon.TRASH) }
            Key({ Sfx.tap(2); page++ }, Modifier.at(4)) { KeyIcon(Icon.DOWN) }
            if (onBack != null) Key({ Sfx.tap(0); onBack() }, Modifier.at(6)) { KeyIcon(Icon.CIRCLE, 16.dp) }
            else Box(Modifier.at(6))
        },
    ) { info ->
        val ink = LocalInk.current
        val perPage = maxOf(1, floor((info.height.value - 16) / (ROW_DP + 8)).toInt())
        val pages = maxOf(1, ceil(accounts.size / perPage.toFloat()).toInt())
        val at = page % pages
        if (accounts.isEmpty()) Empty("nenhuma conta — entre, crie uma ou sorteie uma de teste")
        for (a in accounts.drop(at * perPage).take(perPage)) {
            val inUse = a.username == current
            ListRow({ if (removing) remove(a) else if (!inUse) { Sfx.tap(7); onUse(a) } else onBack?.invoke() }) {
                IconView(if (removing) Icon.CROSS else if (inUse) Icon.CHECK else Icon.USER, if (removing) Ink.danger else ink, 16.dp)
                Grow(a.username, upper = true)
                if (a.test) Tag("teste")
                if (inUse) Tag("em uso")
            }
        }
        if (pages > 1) Ticks(pages, at)
    }
}
