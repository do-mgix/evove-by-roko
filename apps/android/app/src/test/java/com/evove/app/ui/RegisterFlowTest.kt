package com.evove.app.ui

import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
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

/** Creating a profile from the login's form. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h851dp-xxhdpi")
class RegisterFlowTest {
    @get:Rule
    val rule = createComposeRule()
    private val calls = mutableListOf<String>()

    @Before
    fun setUp() {
        Prefs.init(ApplicationProvider.getApplicationContext())
        Api.fake = { method, path ->
            calls += "$method $path"
            """{"token":"x","username":"vini","expires_at":"2026-11-22T08:30:12"}"""
        }
    }

    @Test
    fun createsAProfile() {
        var signed: String? = null
        rule.setContent { LoginScreen({ signed = it }) }
        rule.onNodeWithText("CRIAR UM PERFIL NOVO").performClick()
        val fields = rule.onAllNodes(hasSetTextAction())
        fields[0].performTextInput("vini")
        fields[1].performTextInput("senha12345")
        fields[2].performTextInput("senha12345")
        rule.onAllNodesWithText("CRIAR")[0].performClick()
        rule.waitForIdle()
        assertEquals(listOf("POST /auth/register"), calls)
        assertEquals("vini", signed)
    }
}
