package com.evove.app.screens

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import com.evove.app.Prefs
import com.evove.app.api.Api
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Deleting a log from the records' screen, against answers the server gave. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h851dp-xxhdpi")
class LogsFlowTest {
    @get:Rule
    val rule = createComposeRule()
    private val calls = mutableListOf<String>()

    @Before
    fun setUp() {
        Prefs.init(ApplicationProvider.getApplicationContext())
        Api.fake = { method, path ->
            calls += "$method $path"
            if (method == "DELETE") DELETED else LOGS
        }
    }

    @Test
    fun deletesAndShowsWhatWentBack() {
        rule.mainClock.autoAdvance = false
        rule.setContent { LogsScreen({}, {}) }
        rule.mainClock.advanceTimeBy(2000)
        rule.onNodeWithText("ESCALADA [1H30–2H]").performClick()
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithText("APAGAR").performClick()
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithText("APAGAR E REVERTER").performClick()
        rule.mainClock.advanceTimeBy(2000)
        assertTrue(calls.toString(), calls.any { it.startsWith("DELETE /logs/730004") })
        rule.onNodeWithText("APAGADO").assertExists()
    }

    @Test
    fun opensOnTheQuestionFromTheAgenda() {
        rule.mainClock.autoAdvance = false
        rule.setContent { LogsScreen({}, {}, at = 0, focus = 730004, delete = true) }
        rule.mainClock.advanceTimeBy(2000)
        rule.onNodeWithText("APAGAR?").assertExists()
        rule.onNodeWithText("APAGAR E REVERTER").performClick()
        rule.mainClock.advanceTimeBy(2000)
        assertTrue(calls.toString(), calls.any { it.startsWith("DELETE /logs/730004") })
    }

    private companion object {
        val LOGS = """{"day": 1, "offset": 0, "date": "2026-10-23", "logs": [{"id": 730002, "timestamp": "23 10 2026 : 08:23:16", "content": "APRESENTAÇÃO [20–40m]", "marks": 2, "tokens": 3, "order": 2, "period": "mo"}, {"id": 730003, "timestamp": "23 10 2026 : 08:23:50", "content": "ELEVAÇÃO LATERAL [120–180]", "marks": 4, "tokens": 1, "order": 3, "period": "mo"}, {"id": 730004, "timestamp": "23 10 2026 : 08:24:24", "content": "ESCALADA [1h30–2h]", "marks": 4, "tokens": 4, "order": 4, "period": "mo"}, {"id": 730005, "timestamp": "23 10 2026 : 08:24:36", "content": "ESPORTE [1h30–2h]", "marks": 4, "tokens": 4, "order": 5, "period": "mo"}, {"id": 730006, "timestamp": "23 10 2026 : 08:31:15", "content": "ELEVAÇÃO LATERAL [>180]", "marks": 1, "tokens": 1, "order": 6, "period": "mo"}]}"""
        val DELETED = """{"ok": true, "id": 730002, "removed": {"id": 730002, "timestamp": "23 10 2026 : 08:23:16", "content": "APRESENTAÇÃO [20–40m]", "status": "[CLOUD]", "xp": 0, "marks": 2, "tokens": 3, "coord": [1, 2], "period": "mo"}, "reverted": {"marks": 2, "tokens": -3, "energy": 1, "user_marks": 13, "balance": 10, "leaves": [{"key": "c_argumentacao", "name": "Argumentação", "marks": 2.0}, {"key": "broca", "name": "Broca (produção)", "marks": 0.8}, {"key": "amigdala", "name": "Amígdala", "marks": 0.5}, {"key": "executiva", "name": "Função Executiva", "marks": 0.4}, {"key": "wernicke", "name": "Wernicke (compreensão)", "marks": 0.3}], "custom": []}}"""
    }
}
