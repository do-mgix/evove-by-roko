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
import com.evove.app.Prefs
import com.evove.app.api.Api
import com.evove.app.screens.ActScreen
import com.evove.app.screens.AgendaScreen
import com.evove.app.screens.BuildScreen
import com.evove.app.screens.CalendarPage
import com.evove.app.screens.DetailsPage
import com.evove.app.screens.LogsPage
import com.evove.app.screens.ProfilePage
import com.evove.app.screens.Gain
import com.evove.app.screens.GainsScreen
import com.evove.app.screens.JourneyScreen
import com.evove.app.screens.MeScreen
import com.evove.app.screens.RokoScreen
import com.evove.app.screens.ShopScreen
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
    }

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

    @Test fun home() = shot("home") { HomeScreen(HomeOption.entries.toSet(), emptySet(), HomeOption.ACT) {} }
    @Test fun homeComingOn() = shot("home-coming-on", 180) { HomeScreen(HomeOption.entries.toSet(), setOf(HomeOption.BUILD), HomeOption.ACT) {} }
    @Test fun login() = shot("login") { LoginScreen {} }
    @Test fun act() = shot("act") { ActScreen {} }
    @Test fun gains() = shot("gains") {
        GainsScreen("CORRIDA · 5km", 3, 4, listOf(Gain("a", "Resistência", "α", "β", 2, 3, 3), Gain("b", "Velocidade", "β", "β", 1, 3, 5)), null) {}
    }
    @Test fun shop() = shot("shop") { ShopScreen {} }
    @Test fun journey() = shot("journey") { JourneyScreen {} }
    @Test fun me() = shot("me") { MeScreen({}, {}, {}) }
    @Test fun agenda() = shot("agenda") { AgendaScreen({}, {}, {}) }
    @Test fun roko() = shot("roko") { RokoScreen {} }
    @Test fun build() = shot("build") { BuildScreen {} }
    @Test fun profile() = shot("profile") { ProfilePage({}) {} }
    @Test fun details() = shot("details") { DetailsPage {} }
    @Test fun logs() = shot("logs") { LogsPage {} }
    @Test fun calendar() = shot("calendar") { CalendarPage {} }
}
