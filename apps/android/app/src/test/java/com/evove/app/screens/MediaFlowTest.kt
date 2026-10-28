package com.evove.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.evove.app.Prefs
import com.evove.app.api.Api
import com.evove.app.ui.Frame
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Tagging the thought of a leisure record with a title, against answers the
 *  server gave. With -Pshots it also leaves pictures of the panes. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w393dp-h851dp-xxhdpi")
class MediaFlowTest {
    @get:Rule
    val rule = createComposeRule()
    private val calls = mutableListOf<String>()

    @Before
    fun setUp() {
        Prefs.init(ApplicationProvider.getApplicationContext())
        Api.fake = { method, path ->
            calls += "$method $path"
            when {
                path.startsWith("/agenda/day") -> DAY
                method == "POST" && path == "/media" -> MADE
                path.startsWith("/media") -> TITLES
                else -> "{}"
            }
        }
    }

    private fun shot(name: String) {
        val dir = System.getProperty("evove.shots") ?: return
        rule.onRoot().captureRoboImage("$dir/$name.png")
    }

    private fun open() {
        rule.mainClock.autoAdvance = false
        rule.setContent { Box(Modifier.fillMaxSize().background(Color.Black).padding(8.dp)) { Frame { AgendaScreen({}, {}, {}) } } }
        rule.mainClock.advanceTimeBy(2000)
    }

    @Test
    fun offersTheTitlesOfTheRecordsKind() {
        open()
        rule.onNodeWithText("JOGOS [1–2H]").performClick()
        rule.mainClock.advanceTimeBy(1000)
        assertTrue(calls.toString(), calls.any { it == "GET /media?kind=jogo" })
        rule.onNodeWithText("CUPHEAD").performClick()
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithText("sobre Cuphead").assertExists()
        shot("agenda-thought-title")
    }

    @Test
    fun createsATitleFromTheSearch() {
        open()
        rule.onNodeWithText("JOGOS [1–2H]").performClick()
        rule.mainClock.advanceTimeBy(1000)
        rule.onNodeWithText("OUTRO TÍTULO").performClick()
        rule.mainClock.advanceTimeBy(500)
        rule.onAllNodes(hasSetTextAction())[0].performTextInput("Hollow")
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithText("HOLLOW KNIGHT").assertExists()
        shot("agenda-pick-title")
        rule.onAllNodes(hasSetTextAction())[0].performTextInput(" Knight Silksong")
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithText("CRIAR \"HOLLOW KNIGHT SILKSONG\"").performClick()
        rule.mainClock.advanceTimeBy(1000)
        assertTrue(calls.toString(), calls.any { it == "POST /media" })
        rule.onNodeWithText("sobre Hollow Knight Silksong").assertExists()
    }

    @Test
    fun listsTheTitlesFromThePlan() {
        open()
        rule.onNodeWithTag("plan").performClick()
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithTag("titles").performClick()
        rule.mainClock.advanceTimeBy(1000)
        assertTrue(calls.toString(), calls.any { it == "GET /media" })
        rule.onNodeWithText("Mother 3").performClick()
        rule.mainClock.advanceTimeBy(500)
        rule.onNodeWithText("VIRAR PATCH").assertExists()
        shot("agenda-title-open")
    }

    private companion object {
        val DAY = """{"date":"2026-10-28","offset":0,"day":45,"logs":[
            {"id":1,"content":"TRABALHO [6–8 h]","period":"mo","tokens":2},
            {"id":2,"content":"JOGOS [1–2h]","period":"ni","tokens":-6,"kind":"jogo"},
            {"id":3,"content":"SÉRIE [1 ep]","period":"ni","tokens":-3,"kind":"serie","thought":{"id":9,"content":"o torneio","media":{"id":7,"kind":"serie","title":"Dragon Ball Super","status":"ativo"}}}],
            "cycle":{"acted":true,"todo":false,"thoughts":1,"logs":3,"day_thought":false,"complete":false}}"""
        val TITLES = """{"items":[
            {"id":1,"kind":"jogo","title":"Cuphead","status":"ativo","uses":2,"days":2,"last":"2026-10-27"},
            {"id":2,"kind":"jogo","title":"Hollow Knight","status":"fila"},
            {"id":3,"kind":"jogo","title":"Mother 3","status":"finalizado","uses":5,"days":4,"last":"2026-09-01","can_patch":true}],
            "kinds":[{"key":"jogo","label":"jogo","actions":["JOGOS"]}],"statuses":["ativo","fila","finalizado","retirado","morto"],"patch_after_days":3}"""
        val MADE = """{"id":4,"kind":"jogo","title":"Hollow Knight Silksong","status":"ativo","uses":0,"days":0}"""
    }
}
