@file:UseSerializers(LenientInt::class, LenientLong::class)

package com.evove.app.api

import kotlinx.serialization.Serializable
import kotlinx.serialization.UseSerializers

// What /engine answers: the profile's evove (backend/src/domain/engine.py).

/** A module on the home for this session: what it opens, how it is dressed,
 *  and its shape in the home's grid, five squares across and seven down. */
@Serializable
data class Tile(
    val id: String,
    val kind: String,
    val label: String = "",
    val color: String = "#00f0ff",
    val glyph: String = "act",
    val tone: Int = 0,
    val polygon: List<List<Double>> = emptyList(),
    val delay: Int = 0,
    val fresh: Boolean = false,
    val code: String? = null,
    // something waits in it: the journey's opponent, or a choice
    val alert: Boolean = false,
)

/** Something an entity — or the system — said about an event. */
@Serializable
data class Line(val entity: String = "roko", val text: String = "", val at: String? = null)

@Serializable
data class SelectorState(val level: Int = 1, val turns: Int = 0, val nextAt: Int? = null, val chance: Double? = null)

@Serializable
data class StoryState(val step: String = "done", val at: Int = 0, val of: Int = 0, val done: Boolean = true)

/** The one entity the profile carries. */
@Serializable
data class Carried(val id: String, val name: String = "", val title: String = "", val color: String = "#3dfff0", val glyph: String = "roko", val voice: String = "caps")

/** The modes of the first screen this profile can enter, and what the journey holds. */
@Serializable
data class Modes(
    val evove: Boolean = true,
    val sandbox: Boolean = false,
    val journey: Boolean = false,
    val journeyAlert: Boolean = false,
    val journeyEnding: String? = null,
)

@Serializable
data class ModuleInfo(val id: String, val label: String = "", val code: String? = null, val on: Boolean = false)

@Serializable
data class EngineView(
    val passcode: String = "",
    val session: Int = 0,
    val seed: Long = 0,
    val tiles: List<Tile> = emptyList(),
    val hint: String? = null,
    val modules: List<ModuleInfo> = emptyList(),
    val entities: List<String> = emptyList(),
    // the one carried, null for none
    val entity: Carried? = null,
    val modes: Modes = Modes(),
    val story: StoryState = StoryState(),
    // the actions handed out at the start that roko does not believe yet
    val doubted: List<String> = emptyList(),
    val line: Line? = null,
    val selector: SelectorState = SelectorState(),
    val counters: Map<String, Int> = emptyMap(),
    // in the answers to events and passcodes
    val lines: List<Line> = emptyList(),
    val kind: String? = null,
    val name: String? = null,
)

/** What deleting a log took back. */
@Serializable
data class RevertedLeaf(val key: String? = null, val id: Int? = null, val name: String, val marks: Double = 0.0)

@Serializable
data class Reverted(
    val marks: Int = 0,
    val tokens: Int = 0,
    val energy: Int = 0,
    val userMarks: Int = 0,
    val balance: Int = 0,
    val leaves: List<RevertedLeaf> = emptyList(),
    val custom: List<RevertedLeaf> = emptyList(),
)

@Serializable
data class DeletedLog(val ok: Boolean = true, val id: Int = 0, val reverted: Reverted? = null)

/** The sandbox's home (backend/src/domain/sandbox.py). */
@Serializable
data class SandboxHome(val tiles: List<Tile> = emptyList(), val acts: Int = 0, val actions: Int = 0, val talks: Int = 0, val entities: List<String> = emptyList())

/** A save code: the whole evove in one signed code. */
@Serializable
data class SaveCode(val code: String = "", val grouped: String = "", val length: Int = 0, val actions: Int = 0, val attributes: Int = 0)
