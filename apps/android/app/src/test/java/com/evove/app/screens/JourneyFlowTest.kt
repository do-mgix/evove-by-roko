package com.evove.app.screens

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.printToString
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.evove.app.Prefs
import com.evove.app.api.Api
import com.evove.app.ui.Fixtures
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** A fight started where someone waits, played to its end and sent back. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h851dp-xxhdpi")
class JourneyFlowTest {
    @get:Rule
    val rule = createComposeRule()
    private val calls = mutableListOf<String>()

    @Before
    fun setUp() {
        Prefs.init(ApplicationProvider.getApplicationContext())
        Fixtures.dungeon = "wait"
        Api.fake = { method, path ->
            calls += "$method $path"
            if (path.startsWith("/dungeon/fight/end")) """{"won":true,"points":300,"lines":[],"result":{"won":true,"ticks":300,"hp":[100,0]}}"""
            else Fixtures.answer(method, path)
        }
    }

    @Test
    fun playsTheFightAndSendsItsEnd() {
        rule.mainClock.autoAdvance = false
        rule.setContent { JourneyScreen(onHome = {}) }
        rule.mainClock.advanceTimeBy(1500)
        rule.onNodeWithTag("fight-now").performClick()
        repeat(120) { rule.mainClock.advanceTimeBy(100) }
        // the fight is told one action at a time
        assertTrue(rule.onRoot().printToString(), rule.onAllNodesWithText("USOU", substring = true).fetchSemanticsNodes().isNotEmpty())
        var n = 0
        while (calls.none { it.startsWith("POST /dungeon/fight/end") } && n++ < 6000) rule.mainClock.advanceTimeBy(100)
        assertTrue(calls.toString(), calls.contains("POST /dungeon/fight"))
        assertTrue("never ended after $n ticks: $calls", calls.any { it.startsWith("POST /dungeon/fight/end") })
    }
}
