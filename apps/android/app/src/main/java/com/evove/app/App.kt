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
import com.evove.app.screens.ActScreen
import com.evove.app.screens.AgendaScreen
import com.evove.app.screens.BuildScreen
import com.evove.app.screens.CalendarPage
import com.evove.app.screens.DetailsPage
import com.evove.app.screens.JourneyScreen
import com.evove.app.screens.LogsPage
import com.evove.app.screens.MeScreen
import com.evove.app.screens.ProfilePage
import com.evove.app.screens.RokoScreen
import com.evove.app.screens.ShopScreen
import com.evove.app.ui.Frame
import com.evove.app.ui.HomeOption
import com.evove.app.ui.HomeScreen
import com.evove.app.ui.LoginScreen
import com.evove.app.ui.Usage
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

/** Every page past the home. The white ones open over the dark page they
 *  belong to, and going back lands there. */
enum class Page(val parent: Page? = null, val option: HomeOption? = null, val title: String = "") {
    HOME, ACT, SHOP, BUILD, AGENDA, JOURNEY, ROKO, ME,
    PROFILE(ME, HomeOption.ATTRIBUTES, "perfil"),
    DETAILS(ME, HomeOption.ATTRIBUTES, "atributos e ações"),
    CALENDAR(AGENDA, HomeOption.LOGS, "calendário"),
    LOGS(AGENDA, HomeOption.LOGS, "registros"),
}

private fun pageOf(o: HomeOption) = when (o) {
    HomeOption.ACT -> Page.ACT
    HomeOption.LOGS -> Page.AGENDA
    HomeOption.SHOP -> Page.SHOP
    HomeOption.ROKO -> Page.ROKO
    HomeOption.ATTRIBUTES -> Page.ME
    HomeOption.JOURNEY -> Page.JOURNEY
    HomeOption.BUILD -> Page.BUILD
}

private const val ACTS_KEY = "evove_acts"
private const val SEEN_KEY = "evove_seen_options"

@Composable
fun App() {
    // A session kept from a previous launch signs straight in; the server
    // renews it while it is in use.
    var username by remember { mutableStateOf(if (Prefs.token != null) Prefs.username else null) }
    var page by remember { mutableStateOf(Page.HOME) }
    val scope = rememberCoroutineScope()

    // A rejected session anywhere drops straight back to login.
    DisposableEffect(Unit) {
        Api.onUnauthorized = { username = null }
        onDispose { Api.onUnauthorized = null }
    }
    LaunchedEffect(Unit) { if (username != null) runCatching { Api.sessionInfo() } }

    // The home reveals its options as acts are logged. The count is kept on the
    // device too, so the home draws at once; an option seen for the first time
    // comes on last, glowing.
    var acts by remember { mutableIntStateOf(if (Prefs.has(ACTS_KEY)) Prefs.int(ACTS_KEY) else -1) }
    var seen by remember {
        mutableStateOf(Prefs.string(SEEN_KEY)?.split(",")?.mapNotNull { n -> HomeOption.entries.find { it.name == n } }?.toSet() ?: emptySet())
    }
    val visible = if (acts >= 0) HomeOption.unlockedFor(acts) else HomeOption.entries.toSet()
    val fresh = if (seen.isNotEmpty()) visible - seen else emptySet()

    LaunchedEffect(username, Bus.user) {
        if (username == null) return@LaunchedEffect
        runCatching { Api.user() }.onSuccess {
            acts = it.acts
            Prefs.putInt(ACTS_KEY, it.acts)
        }
    }

    fun goHome() { page = Page.HOME }
    fun back() { page = page.parent ?: Page.HOME }

    BackHandler(enabled = username != null && page != Page.HOME) { back() }

    Box(
        Modifier.fillMaxSize().background(Color.Black)
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .padding(8.dp),
    ) {
        Frame {
            val name = username
            if (name == null) {
                LoginScreen { username = it; page = Page.HOME }
                return@Frame
            }
            when (page) {
                Page.HOME -> HomeScreen(visible, fresh, Usage.suggested(visible)) { o ->
                    Usage.recordOpen(o)
                    seen = seen + visible
                    Prefs.putString(SEEN_KEY, seen.joinToString(",") { it.name })
                    page = pageOf(o)
                }
                Page.ACT -> ActScreen(onHome = ::goHome)
                Page.SHOP -> ShopScreen(onHome = ::goHome)
                Page.BUILD -> BuildScreen(onHome = ::goHome)
                Page.AGENDA -> AgendaScreen(onHome = ::goHome, onCalendar = { page = Page.CALENDAR }, onLogs = { page = Page.LOGS })
                Page.JOURNEY -> JourneyScreen(onHome = ::goHome)
                Page.ROKO -> RokoScreen(onHome = ::goHome)
                Page.ME -> MeScreen(onHome = ::goHome, onProfile = { page = Page.PROFILE }, onDetails = { page = Page.DETAILS })
                Page.PROFILE -> ProfilePage(onBack = ::back) { everywhere ->
                    username = null
                    scope.launch { if (everywhere) Api.logoutEverywhere() else Api.logout() }
                }
                Page.DETAILS -> DetailsPage(onBack = ::back)
                Page.CALENDAR -> CalendarPage(onBack = ::back)
                Page.LOGS -> LogsPage(onBack = ::back)
            }
        }
    }
}
