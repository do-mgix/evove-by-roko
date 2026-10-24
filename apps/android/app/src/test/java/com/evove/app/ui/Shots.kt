package com.evove.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.evove.app.Evove
import com.evove.app.Prefs
import com.evove.app.api.Api
import com.evove.app.api.EngineView
import com.evove.app.api.Line
import com.evove.app.screens.AccountsScreen
import com.evove.app.screens.ActScreen
import com.evove.app.screens.AgendaScreen
import com.evove.app.screens.BuildScreen
import com.evove.app.screens.CalendarPage
import com.evove.app.screens.DetailsPage
import com.evove.app.screens.LogsScreen
import com.evove.app.screens.ProfilePage
import com.evove.app.screens.Gain
import com.evove.app.screens.GainsScreen
import com.evove.app.screens.JourneyScreen
import com.evove.app.screens.MeScreen
import com.evove.app.screens.RokoScreen
import com.evove.app.screens.SandboxAttributesScreen
import com.evove.app.screens.ShopScreen
import com.evove.app.screens.StartScreen
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** The screens rendered into pictures, to look at them without a phone:
 *
 *     ./gradlew :app:testDebugUnitTest --tests '*Shots*' -Pshots
 *
 * writes build/shots/<name>.png, each screen fed the answers in Fixtures
 * instead of the server's. Without -Pshots it does nothing. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w393dp-h851dp-xxhdpi")
class Shots {
    @get:Rule
    val rule = createComposeRule()

    @Before
    fun setUp() {
        assumeTrue(System.getProperty("evove.shots") != null)
        Prefs.init(ApplicationProvider.getApplicationContext())
        Api.fake = Fixtures::answer
        Evove.apply(Api.json.decodeFromString<EngineView>(Fixtures.engine))
    }

    private fun fresh() = Evove.apply(Api.json.decodeFromString<EngineView>(Fixtures.engineFresh))

    /** Renders `content` in the frame, `ms` after it came on. */
    private fun shot(name: String, ms: Long = 3000, content: @Composable () -> Unit) {
        // the backdrop drifts forever: the clock is moved by hand
        rule.mainClock.autoAdvance = false
        rule.setContent {
            Box(Modifier.fillMaxSize().background(Color.Black).padding(8.dp)) { Frame { content() } }
        }
        rule.mainClock.advanceTimeBy(ms)
        rule.onRoot().captureRoboImage("${System.getProperty("evove.shots")}/$name.png")
    }

    @Test fun home() = shot("home") { HomeScreen(Evove.view!!.tiles, "act", Evove.view!!.line, {}, {}, {}) }
    @Test fun homeFallback() = shot("home-fallback") { HomeScreen(HomeOption.fallback, "act", null, {}, {}, {}) }
    @Test fun homeComingOn() = shot("home-coming-on", 180) { HomeScreen(Evove.view!!.tiles, "act", null, {}, {}, {}) }
    @Test fun homeStory() { fresh(); shot("home-story") { HomeScreen(Evove.view!!.tiles, "act", Evove.view!!.line, {}, {}, {}) } }
    @Test fun login() = shot("login") { LoginScreen({}, {}) }
    @Test fun accounts() {
        Prefs.remember("tqzmkp", "y", test = true); Prefs.remember("roko", "x")
        shot("accounts") { AccountsScreen("roko", {}, {}, {}, {}, {}) }
    }
    @Test fun act() = shot("act") { ActScreen(onHome = {}) }
    @Test fun actStory() { fresh(); shot("act-story") { ActScreen(onHome = {}) } }
    @Test fun start() = shot("start") { StartScreen("roko", {}, {}) }
    @Test fun sandbox() = shot("sandbox") {
        HomeScreen(Api.json.decodeFromString<com.evove.app.api.SandboxHome>(Fixtures.answer("GET", "/sandbox")).tiles, "act",
            Line("coleto", "sandbox! tudo liberado, chefe!"), {}, {}, {})
    }
    @Test fun sandboxAct() = shot("sandbox-act") { ActScreen(onHome = {}, sandbox = true) }
    @Test fun sandboxAttributes() = shot("sandbox-attributes") { SandboxAttributesScreen {} }
    @Test fun coleto() = shot("coleto") { RokoScreen(onHome = {}, sandbox = true, focus = "coleto") }
    @Test fun entityMute() { Fixtures.mute = true; try { shot("entity-mute") { RokoScreen(onHome = {}) } } finally { Fixtures.mute = false } }
    @Test fun journeyWaiting() = dungeon("wait") { shot("journey-waiting") { JourneyScreen(onHome = {}) } }
    @Test fun journeyChoice() = dungeon("choice") { shot("journey-choice") { JourneyScreen(onHome = {}) } }
    @Test fun journeyEnding() = dungeon("ending") { shot("journey-ending") { JourneyScreen(onHome = {}) } }
    @Test fun journeyAct3() = dungeon("act3") { shot("journey-act3") { JourneyScreen(onHome = {}) } }
    @Test fun journeyFight() = dungeon("wait") {
        rule.mainClock.autoAdvance = false
        rule.setContent { Box(Modifier.fillMaxSize().background(Color.Black).padding(8.dp)) { Frame { JourneyScreen(onHome = {}) } } }
        rule.mainClock.advanceTimeBy(1500)
        rule.onNodeWithTag("fight-now").performClick()
        // a tick at a time, as a phone would run them
        repeat(120) {
            rule.mainClock.advanceTimeBy(100)
            org.robolectric.shadows.ShadowLooper.idleMainLooper(100, java.util.concurrent.TimeUnit.MILLISECONDS)
        }
        rule.onRoot().captureRoboImage("${System.getProperty("evove.shots")}/journey-fight.png")
    }

    private fun dungeon(kind: String, block: () -> Unit) {
        Fixtures.dungeon = kind
        try { block() } finally { Fixtures.dungeon = "walk" }
    }
    @Test fun gains() = shot("gains") {
        GainsScreen("CORRIDA · 5km", 3, 4, listOf(Gain("a", "Resistência", "α", "β", 2, 3, 3), Gain("b", "Velocidade", "β", "β", 1, 3, 5)),
            listOf(Line("roko", "AGORA EU ACREDITO."), Line("roko", "PODE FALAR COMIGO."))) {}
    }
    @Test fun gainsDoubt() = shot("gains-doubt") {
        GainsScreen("CORRIDA · 10–30m", 1, 2, listOf(Gain("a", "Resistência", "α", "α", 1, 1, 3)), listOf(Line("roko", "CORRIDA."),
            Line("roko", "AS MARCAS SÃO SUAS. MAS DAQUI EU NÃO VI ACONTECER."),
            Line("roko", "DO OUTRO LADO DO VIDRO TEM ALGUÉM. É ESSA PESSOA QUE EU CONTO."),
            Line("roko", "O QUE ELA FAZ DE VERDADE? PROCURE NO SHOP."))) {}
    }
    @Test fun shop() = shot("shop") { ShopScreen {} }
    @Test fun journey() = shot("journey") { JourneyScreen(onHome = {}) }
    @Test fun me() = shot("me") { MeScreen({}, {}, {}) }
    @Test fun agenda() = shot("agenda") { AgendaScreen({}, {}, {}) }
    @Test fun roko() = shot("roko") { RokoScreen(onHome = {}) }
    @Test fun build() = shot("build") { BuildScreen {} }
    @Test fun profile() = shot("profile") { ProfilePage({}, {}) {} }
    @Test fun details() = shot("details") { DetailsPage {} }
    @Test fun logs() = shot("logs") { LogsScreen({}, {}) }
    @Test fun calendar() = shot("calendar") { CalendarPage {} }
}
