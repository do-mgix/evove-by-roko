@file:UseSerializers(LenientInt::class, LenientLong::class)

package com.evove.app.api

import kotlinx.serialization.Serializable
import kotlinx.serialization.UseSerializers

// What /dungeon answers: the journey as a mode (backend/src/domain/dungeon.py),
// and the setup of its fights (backend/src/domain/fight.py).

@Serializable
data class FightMove(
    val name: String,
    val dmg: Long,
    val decree: Long? = null,
    val cd: Int,
    val attribute: String = "",
    val multiplier: Double = 1.0,
)

@Serializable
data class FightHeal(val name: String, val amount: Long, val cd: Int)

@Serializable
data class FightEntity(val id: String, val name: String, val forca: Int, val agilidade: Int, val skill: String, val ability: String)

@Serializable
data class FightSide(
    val name: String,
    val hp: Long,
    val maxHp: Long,
    val resist: Int = 0,
    val defense: Int = 0,
    val absorb: Int = 100,
    val moves: List<FightMove> = emptyList(),
    val heal: FightHeal,
    val entities: List<FightEntity> = emptyList(),
    val tricks: Boolean = true,
    // the bar's hp per point of the journey's energy
    val perEnergy: Double = 10.0,
)

@Serializable
data class Opponent(val name: String = "", val title: String = "", val kind: String = "person", val entity: String? = null, val label: String? = null)

@Serializable
data class FightSetup(
    val seed: Long,
    val maxTicks: Int = 2400,
    val tickMs: Int = 100,
    val you: FightSide,
    val foe: FightSide,
    val opponent: Opponent = Opponent(),
)

/** What the server decided when it replayed the fight. */
@Serializable
data class FightOutcome(
    val won: Boolean = false,
    val ticks: Int = 0,
    val hp: List<Long> = emptyList(),
    val dealt: List<Long> = emptyList(),
    val heals: List<Int> = emptyList(),
    val tricks: List<Int> = emptyList(),
    val interfered: List<Int> = emptyList(),
    val check: Long = 0,
    val maxHp: Long = 0,
)

@Serializable
data class MapRooms(val w: Int = 7, val h: Int = 5, val path: List<List<Int>> = emptyList(), val rooms: List<List<Int>> = emptyList())

@Serializable
data class ChoiceOption(val id: String, val label: String)

@Serializable
data class Pending(val kind: String, val text: String = "", val options: List<ChoiceOption> = emptyList())

@Serializable
data class Partner(val id: String, val name: String, val color: String = "#ffffff", val glyph: String = "", val ability: String? = null)

@Serializable
data class Objective(val entity: String, val text: String = "", val need: Int = 1, val have: Int = 0, val done: Boolean = false, val unlocked: Boolean = false)

@Serializable
data class Act3(
    val pair: List<String> = emptyList(),
    val unlocked: List<String> = emptyList(),
    val done: List<String> = emptyList(),
    val fragments: Int = 0,
    val objectives: List<Objective> = emptyList(),
)

@Serializable
data class DungeonView(
    val act: Int = 1,
    val floor: Int = 1,
    val floorInAct: Int = 1,
    val of: Int? = null,
    val map: MapRooms = MapRooms(),
    val progress: Double = 0.0,
    val walkSeconds: Long = 0,
    val secondsLeft: Long = 0,
    val waiting: Boolean = false,
    val opponent: Opponent = Opponent(),
    val pending: Pending? = null,
    val ending: String? = null,
    val endingLines: List<String> = emptyList(),
    val intro: List<String> = emptyList(),
    val waitingLine: String = "",
    val wins: Int = 0,
    val losses: Int = 0,
    val fast: Boolean = false,
    val act3: Act3? = null,
    val companions: List<Partner> = emptyList(),
    val energy: Int = 0,
    val maxEnergy: Int = 25,
    val tokens: Int = 0,
    val recover: List<Recovery> = emptyList(),
    val checkpoint: JourneyState? = null,
    val fighting: Boolean = false,
    val code: String? = null,
)

@Serializable
data class FightEnd(
    val result: FightOutcome = FightOutcome(),
    val won: Boolean = false,
    val points: Int = 0,
    val journeyReset: Boolean = false,
    val lines: List<String> = emptyList(),
    val close: Boolean = false,
    val view: DungeonView = DungeonView(),
)

@Serializable
data class Chosen(val lines: List<String> = emptyList(), val view: DungeonView = DungeonView())
