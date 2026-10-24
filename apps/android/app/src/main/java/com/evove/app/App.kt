package com.evove.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.evove.app.api.Api
import com.evove.app.screens.AccountsScreen
import com.evove.app.screens.ActScreen
import com.evove.app.screens.AgendaScreen
import com.evove.app.screens.BuildScreen
import com.evove.app.screens.CalendarPage
import com.evove.app.screens.DetailsPage
import com.evove.app.screens.JourneyScreen
import com.evove.app.screens.LogsAt
import com.evove.app.screens.LogsScreen
import com.evove.app.screens.MeScreen
import com.evove.app.screens.ProfilePage
import com.evove.app.screens.RokoScreen
import com.evove.app.screens.Mode
import com.evove.app.screens.SandboxAttributesScreen
import com.evove.app.screens.ShopScreen
import com.evove.app.screens.StartScreen
import com.evove.app.ui.Frame
import com.evove.app.ui.HomeOption
import com.evove.app.ui.HomeScreen
import com.evove.app.ui.LoginScreen
import kotlinx.coroutines.launch

/** Bumped when a log is created, or the profile changes, so the screens that
 *  show them fetch again. */
object Bus {
    var logs by mutableIntStateOf(0)
        private set
    var user by mutableIntStateOf(0)
        private set
    fun bumpLogs() { logs++ }
    fun bumpUser() { user++ }
}

/** Every page past the home. A page with a parent opens from it, and going
 *  back lands there. */
enum class Page(val parent: Page? = null, val option: HomeOption? = null, val title: String = "") {
    // the first screen: the user, and the modes
    START,
    HOME, ACT, SHOP, BUILD, AGENDA, JOURNEY, ROKO, ME,
    PROFILE(ME, HomeOption.ATTRIBUTES, "perfil"),
    DETAILS(ME, HomeOption.ATTRIBUTES, "atributos e ações"),
    CALENDAR(AGENDA, HomeOption.LOGS, "calendário"),
    LOGS(AGENDA, HomeOption.LOGS, "registros"),
    ACCOUNTS(null, null, "contas"),
    SANDBOX,
    SANDBOX_ACT(SANDBOX),
    SANDBOX_ATTRIBUTES(SANDBOX),
    SANDBOX_ENTITIES(SANDBOX),
    COLETO(SANDBOX),
}

/** The screen a module of the engine opens, by its kind. */
private fun pageOf(kind: String) = when (kind) {
    "act" -> Page.ACT
    "agenda" -> Page.AGENDA
    "shop" -> Page.SHOP
    "entity" -> Page.ROKO
    "attributes" -> Page.ME
    "journey" -> Page.JOURNEY
    "build" -> Page.BUILD
    "sandbox_act" -> Page.SANDBOX_ACT
    "sandbox_attributes" -> Page.SANDBOX_ATTRIBUTES
    "sandbox_entities" -> Page.SANDBOX_ENTITIES
    "coleto" -> Page.COLETO
    else -> null
}

@Composable
fun App() {
    // A session kept from a previous launch signs straight in; the server
    // renews it while it is in use.
    var username by remember { mutableStateOf(if (Prefs.token != null) Prefs.username else null) }
    var page by remember { mutableStateOf(Page.START) }
    // where the journey was entered from, to go back there
    var journeyFrom by remember { mutableStateOf(Page.START) }
    var sandboxTiles by remember { mutableStateOf<List<com.evove.app.api.Tile>>(emptyList()) }
    val activity = androidx.compose.ui.platform.LocalContext.current as? android.app.Activity
    // the accounts screen over the login: another account is being added
    var adding by remember { mutableStateOf(false) }
    var logsAt by remember { mutableStateOf(LogsAt()) }
    val scope = rememberCoroutineScope()

    // A rejected session anywhere drops back to the accounts kept, or to login.
    DisposableEffect(Unit) {
        Api.onUnauthorized = { username = null; page = if (Prefs.accounts.isNotEmpty()) Page.ACCOUNTS else Page.START }
        onDispose { Api.onUnauthorized = null }
    }

    // Each account has its own evove: drawn from the device at once, then the
    // visit tells the server the app came on and brings this session's home.
    LaunchedEffect(username) {
        Evove.switchTo(username)
        if (username != null) {
            Evove.visit(cold = true)
            runCatching { Api.sessionInfo() }
        }
    }

    fun goHome() { Evove.flush(); page = Page.HOME }
    fun back() {
        page = page.parent ?: when (page) {
            Page.HOME, Page.SANDBOX, Page.ACCOUNTS -> Page.START
            Page.JOURNEY -> journeyFrom
            else -> Page.HOME
        }
    }
    fun signedIn(name: String) { username = name; adding = false; page = Page.START; Bus.bumpUser() }
    fun enterSandbox() {
        page = Page.SANDBOX
        scope.launch { runCatching { Api.sandboxVisit() }.onSuccess { sandboxTiles = it.tiles } }
    }

    BackHandler(enabled = (username != null && page != Page.START) || adding) {
        if (adding) adding = false else back()
    }

    Box(
        Modifier.fillMaxSize().background(Color.Black)
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .padding(8.dp),
    ) {
        Frame {
            val name = username
            if (adding || (name == null && page != Page.ACCOUNTS)) {
                LoginScreen(
                    onSelected = ::signedIn,
                    onAccounts = if (Prefs.accounts.isNotEmpty()) ({ adding = false; page = Page.ACCOUNTS }) else null,
                )
                return@Frame
            }
            if (page == Page.ACCOUNTS || name == null) {
                AccountsScreen(
                    current = name,
                    onUse = { a -> Prefs.use(a); signedIn(a.username) },
                    onAdd = { adding = true },
                    onTest = ::signedIn,
                    onBack = if (name != null) ({ page = Page.START }) else null,
                    onEmpty = { username = null; page = Page.START },
                    // the account in use started over: its evove drawn again from the first step
                    onReset = { n -> if (n == username) { Evove.switchTo(n); Evove.visit(cold = true); Bus.bumpUser() } },
                    onGone = { n -> if (n == username) { username = null; page = Page.ACCOUNTS } },
                )
                return@Frame
            }
            val view = Evove.view
            when (page) {
                Page.START -> StartScreen(
                    username = name,
                    onMode = { m ->
                        when (m) {
                            Mode.EVOVE -> page = Page.HOME
                            Mode.SANDBOX -> enterSandbox()
                            Mode.JOURNEY -> { journeyFrom = Page.START; page = Page.JOURNEY }
                        }
                    },
                    onAccounts = { page = Page.ACCOUNTS },
                )
                Page.HOME -> HomeScreen(
                    tiles = view?.tiles ?: HomeOption.fallback,
                    hint = view?.hint ?: "act",
                    said = Evove.said,
                    onOpen = { t ->
                        pageOf(t.kind)?.let {
                            Evove.open(t.id)
                            if (it == Page.JOURNEY) journeyFrom = Page.HOME
                            page = it
                        }
                    },
                    onDismiss = Evove::dismiss,
                    onAccounts = { page = Page.ACCOUNTS },
                    onStart = { Evove.flush(); page = Page.START },
                )
                Page.SANDBOX -> HomeScreen(
                    tiles = sandboxTiles,
                    hint = "act",
                    said = remember { com.evove.app.api.Line("coleto", listOf("sandbox! tudo liberado, chefe!", "aqui nada custa. coleto garante!", "agir à vontade! coleto anota!").random()) },
                    onOpen = { t ->
                        pageOf(t.kind)?.let {
                            scope.launch { runCatching { Api.sandboxOpen(t.id) } }
                            page = it
                        }
                    },
                    onDismiss = {},
                    onAccounts = { page = Page.ACCOUNTS },
                    onStart = { page = Page.START },
                )
                Page.SANDBOX_ACT -> ActScreen(onHome = { page = Page.SANDBOX }, sandbox = true)
                Page.SANDBOX_ATTRIBUTES -> SandboxAttributesScreen(onHome = { page = Page.SANDBOX })
                Page.SANDBOX_ENTITIES -> RokoScreen(onHome = { page = Page.SANDBOX }, sandbox = true)
                Page.COLETO -> RokoScreen(onHome = { page = Page.SANDBOX }, sandbox = true, focus = "coleto")
                Page.ACT -> ActScreen(onHome = ::goHome)
                Page.SHOP -> ShopScreen(onHome = ::goHome)
                Page.BUILD -> BuildScreen(onHome = ::goHome)
                Page.AGENDA -> AgendaScreen(onHome = ::goHome, onCalendar = { page = Page.CALENDAR }, onLogs = { at -> logsAt = at; page = Page.LOGS })
                Page.JOURNEY -> JourneyScreen(
                    onHome = { Evove.flush(); page = journeyFrom },
                    // the evove undone: the app closes by itself
                    onClose = { activity?.finishAndRemoveTask() },
                )
                Page.ROKO -> RokoScreen(onHome = ::goHome)
                Page.ME -> MeScreen(onHome = ::goHome, onProfile = { page = Page.PROFILE }, onDetails = { page = Page.DETAILS })
                Page.PROFILE -> ProfilePage(onBack = ::back, onAccounts = { page = Page.ACCOUNTS }) { everywhere ->
                    // off the device at once; the server hears of it when it can
                    val token = Prefs.token
                    Prefs.clearSession()
                    username = null
                    page = if (Prefs.accounts.isNotEmpty()) Page.ACCOUNTS else Page.START
                    if (token != null) scope.launch { Api.logoutToken(token, everywhere) }
                }
                Page.DETAILS -> DetailsPage(onBack = ::back)
                Page.CALENDAR -> CalendarPage(onBack = ::back)
                Page.LOGS -> LogsScreen(onBack = ::back, onHome = ::goHome, at = logsAt.offset, focus = logsAt.id, delete = logsAt.delete)
                Page.ACCOUNTS -> {}
            }
        }
    }
}
