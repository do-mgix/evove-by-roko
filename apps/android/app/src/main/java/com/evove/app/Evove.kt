package com.evove.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.evove.app.api.Api
import com.evove.app.api.EngineView
import com.evove.app.api.Line
import com.evove.app.api.currentPeriod
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/** The profile's evove as the app holds it: what the server last said the
 *  interface is made of (`/engine`), kept on the device per account so the home
 *  draws at once, and what happened on the device since, sent in batches. */
object Evove {
    var view by mutableStateOf<EngineView?>(null)
        private set

    /** The latest thing said, for the home's display. */
    var said by mutableStateOf<Line?>(null)
        private set

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val sending = Mutex()
    private val pending = mutableListOf<JsonObject>()
    private var turns = 0
    private var account: String? = null

    private fun key(name: String) = "evove_engine:$name"

    /** The account in use changed: its own evove, from the device first. */
    fun switchTo(name: String?) {
        account = name
        pending.clear()
        turns = 0
        said = null
        view = name?.let { n -> Prefs.string(key(n))?.let { runCatching { Api.json.decodeFromString<EngineView>(it) }.getOrNull() } }
        said = view?.line
    }

    fun apply(v: EngineView) {
        view = v
        account?.let { Prefs.putString(key(it), Api.json.encodeToString(EngineView.serializer(), v.copy(lines = emptyList()))) }
        val last = v.lines.lastOrNull() ?: v.line
        if (last != null) said = last else if (v.line == null) said = null
    }

    /** The app came on. A cold start is always a new session; coming back from
     *  the background is one only after a pause, which the server judges. The
     *  turns the shop counted before the engine go along once. */
    fun visit(cold: Boolean) = scope.launch {
        val local = Prefs.int(LEGACY_TURNS_KEY)
        runCatching { Api.visit(cold, local) }.onSuccess {
            if (local > 0) Prefs.putInt(LEGACY_TURNS_KEY, 0)
            apply(it)
        }
    }

    fun refresh() = scope.launch { runCatching { Api.engine() }.onSuccess(::apply) }

    /** Work that must outlive the screen that started it — a fight left
     *  halfway, sent to be played out. */
    fun later(block: suspend () -> Unit) = scope.launch { block() }

    /** A module opened from the home. */
    fun open(module: String) {
        pending += JsonObject(mapOf("kind" to JsonPrimitive("open"), "module" to JsonPrimitive(module), "period" to JsonPrimitive(currentPeriod())))
        flush()
    }

    /** A page turned by the selector: counted here, sent every few, or at once
     *  when it crosses the mark of the next level. */
    fun turn() {
        turns++
        val v = view
        val at = v?.selector?.nextAt
        if (turns >= 25 || (at != null && v.selector.turns + turns >= at)) flush()
    }

    /** The line on the home was read. */
    fun dismiss() {
        said = null
        pending += JsonObject(mapOf("kind" to JsonPrimitive("dismiss")))
        flush()
    }

    fun flush() {
        if (turns > 0) {
            pending += JsonObject(mapOf("kind" to JsonPrimitive("turn"), "n" to JsonPrimitive(turns)))
            turns = 0
        }
        if (pending.isEmpty()) return
        val batch = pending.toList()
        pending.clear()
        scope.launch {
            sending.withLock {
                runCatching { Api.engineEvents(batch) }.onSuccess(::apply).onFailure {
                    // kept for the next call; the counts are worth more than the order
                    pending.addAll(0, batch)
                }
            }
        }
    }

    /** The level of the selector that turns pages, 1 to 3. */
    val selector: Int get() = view?.selector?.level ?: 1

    /** Turns the shop counted on the device before the engine took over. */
    const val LEGACY_TURNS_KEY = "evove_shop_turns"
}
