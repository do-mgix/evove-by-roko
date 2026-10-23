package com.evove.app.screens

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.evove.app.Prefs
import com.evove.app.api.Api
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Starting an account over and deleting one, from the accounts. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h851dp-xxhdpi")
class AccountsFlowTest {
    @get:Rule
    val rule = createComposeRule()
    private val calls = mutableListOf<String>()

    @Before
    fun setUp() {
        Prefs.init(ApplicationProvider.getApplicationContext())
        Prefs.accounts = emptyList()
        Prefs.remember("roko", "r1")
        Prefs.remember("tqzmkp", "t1", test = true, password = "segredo123")
        Prefs.use(Prefs.accounts.first())
        Api.fake = { method, path ->
            calls += "$method $path"
            """{"token":"t2","username":"tqzmkp","expires_at":"2026-11-22T08:30:12"}"""
        }
    }

    @Test
    fun startsATestAccountOverWithItsOwnPassword() {
        var reset: String? = null
        rule.setContent { AccountsScreen("tqzmkp", {}, {}, {}, {}, {}, onReset = { reset = it }) }
        rule.waitForIdle()
        rule.onNodeWithTag("manage").performClick()
        rule.onNodeWithText("TQZMKP").performClick()
        rule.onNodeWithText("REINICIAR TUDO").performClick()
        rule.onAllNodesWithText("REINICIAR TUDO")[0].performClick()
        rule.waitForIdle()
        assertEquals(listOf("POST /auth/me/reset"), calls)
        assertEquals("tqzmkp", reset)
        assertEquals("t2", Prefs.token)
        assertEquals("t2", Prefs.accounts.first { it.username == "tqzmkp" }.token)
    }

    @Test
    fun deletesAnAccountAndTakesItOff() {
        var gone: String? = null
        rule.setContent { AccountsScreen("tqzmkp", {}, {}, {}, {}, {}, onGone = { gone = it }) }
        rule.waitForIdle()
        rule.onNodeWithTag("manage").performClick()
        rule.onNodeWithText("TQZMKP").performClick()
        rule.onNodeWithText("APAGAR PARA SEMPRE").performClick()
        rule.onAllNodesWithText("APAGAR PARA SEMPRE")[0].performClick()
        rule.waitForIdle()
        assertEquals(listOf("DELETE /auth/me"), calls)
        assertEquals("tqzmkp", gone)
        assertEquals(listOf("roko"), Prefs.accounts.map { it.username })
    }
}
