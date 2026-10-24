@file:UseSerializers(LenientInt::class, LenientLong::class)

package com.evove.app.api

import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.UseSerializers
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.JsonElement

// What the API answers, as the web client typed it (apps/web/src/lib/api.ts).
// Field names are the server's snake_case, mapped by the Json in Api.kt; every
// field the server may leave out has a default, so a missing one never fails a
// whole screen.

// Python keeps marks, values and scores as floats and writes them "3.0" or
// "2.5": a whole number here takes either, cut down to its integer part.
private fun Decoder.whole(): Double =
    if (this is JsonDecoder) decodeJsonElement().jsonPrimitive.content.toDouble() else decodeDouble()

object LenientInt : KSerializer<Int> {
    override val descriptor = PrimitiveSerialDescriptor("LenientInt", PrimitiveKind.INT)
    override fun deserialize(decoder: Decoder) = kotlin.math.floor(decoder.whole()).toInt()
    override fun serialize(encoder: Encoder, value: Int) = encoder.encodeInt(value)
}

object LenientLong : KSerializer<Long> {
    override val descriptor = PrimitiveSerialDescriptor("LenientLong", PrimitiveKind.LONG)
    override fun deserialize(decoder: Decoder) = kotlin.math.floor(decoder.whole()).toLong()
    override fun serialize(encoder: Encoder, value: Long) = encoder.encodeLong(value)
}

@Serializable
data class Session(val token: String, val username: String, val expiresAt: String = "")

@Serializable
data class SessionTimes(val createdAt: String = "", val expiresAt: String = "")

@Serializable
data class SessionInfo(
    val userId: Int,
    val username: String,
    val createdAt: String = "",
    val email: String? = null,
    val session: SessionTimes = SessionTimes(),
    val activeSessions: Int = 0,
)

@Serializable
data class TierOption(val index: Int, val label: String, val marks: Int = 0)

@Serializable
data class PathStep(val key: String, val name: String)

@Serializable
data class Leaf(val key: String, val name: String, val weight: Double = 0.0)

@Serializable
data class WeightedAttribute(val id: Int, val name: String, val weight: Double = 0.0)

@Serializable
data class Action(
    val id: String,
    val name: String,
    val type: Int = 0,
    val diff: Int = 0,
    val value: Int = 0,
    val score: Int = 0,
    val tokenCost: Int = 0,
    val tokenGain: Int = 0,
    val logOnly: Boolean = false,
    val tiers: List<TierOption> = emptyList(),
    val path: List<PathStep> = emptyList(),
    val leaves: List<Leaf> = emptyList(),
    val baseActionId: String? = null,
    val attributes: List<WeightedAttribute> = emptyList(),
)

@Serializable
data class ActResult(
    val id: String,
    val name: String,
    val value: Int = 0,
    val score: Int = 0,
    val marks: Int = 0,
    val nominal: Int = 0,
    val windowMarks: Int = 0,
    val windowLimit: Int = 0,
    val userMarks: Int = 0,
    val logOnly: Boolean = false,
    val tokenGain: Int = 0,
    val tokenCost: Int = 0,
    val tokensWasted: Int = 0,
    val tokens: Int = 0,
    val inAgenda: Boolean = false,
    val energyPenalty: Int = 0,
    val energy: Int = 0,
    val journeyReset: Boolean = false,
    val roko: String? = null,
    /** who said `roko`: the entity carried, coleto, or the system */
    val speaker: String = "roko",
    /** what the act moved in the story, said by whoever said it */
    val lines: List<Line> = emptyList(),
)

@Serializable
data class ActionWindow(val windowMarks: Int = 0, val limit: Int = 0, val hours: Int = 0, val options: List<TierOption> = emptyList())

@Serializable
data class Bonuses(val maxEnergy: Int = 0, val maxTokens: Int = 0, val xpMultiplier: Double = 1.0, val pointsMultiplier: Double = 1.0)

@Serializable
data class UserState(
    val username: String = "",
    val day: Int = 0,
    val consecutiveDays: Int = 0,
    val marks: Int = 0,
    val level: Int = 0,
    val rankLetter: String = "",
    val rankName: String? = null,
    val rankSymbol: String = "",
    val localLevelRoman: String = "",
    val localLevelsTotal: Int = 0,
    val nextMarks: Int = 0,
    val levelCost: Int = 0,
    val levelMarks: Int = 0,
    val stage: Int = 0,
    val energy: Int = 0,
    val skillPoints: Int = 0,
    val buildPoints: Int = 0,
    val points: Int = 0,
    val tokens: Int = 0,
    val maxTokens: Int = 0,
    val checkpointSecondsLeft: Long = 0,
    val attributesCount: Int = 0,
    val maxEnergy: Int = 0,
    val nickname: String? = null,
    val passcode: String? = null,
    val acts: Int = 0,
    val bonuses: Bonuses? = null,
)

@Serializable
data class Claim(val ranks: Int = 0, val tokens: Int = 0, val points: Int = 0, val skillPoints: Int = 0)

@Serializable
data class PatchAttachment(val id: String, val name: String, val attributes: List<UserAttribute> = emptyList())

/** Any attribute. A leaf is one with no children; only leaves hold a score. */
@Serializable
data class AttrNode(
    val key: String,
    val name: String,
    val degree: Int = 0,
    val star: Int = 1,
    val isLeaf: Boolean = false,
    val rank: String = "α",
    val rankName: String? = null,
    val rankIndex: Int = 0,
    val marks: Int = 0,
    val need: Int = 3,
    val totalMarks: Int = 0,
    val max: Boolean = false,
    val weight: Double? = null,
    val primary: Boolean? = null,
    val children: List<AttrNode> = emptyList(),
    val patches: List<PatchAttachment> = emptyList(),
    val custom: Boolean = false,
    val claim: Claim? = null,
    // in /attributes/recent and /attributes/usage
    val parent: String? = null,
    val secondsAgo: Long = 0,
    val uses: Int = 0,
)

@Serializable
data class AttributeTree(val roots: List<AttrNode> = emptyList())

@Serializable
data class ClaimResult(
    val key: String = "",
    val ranks: Int = 0,
    val tokensGained: Int = 0,
    val tokensWasted: Int = 0,
    val skillPointsGained: Int = 0,
    val pointsGained: Int = 0,
    val tokens: Int = 0,
    val skillPoints: Int = 0,
)

@Serializable
data class PatchRef(val id: String, val name: String, val weight: Double = 0.0)

/** An attribute the user created. */
@Serializable
data class UserAttribute(
    val id: Int,
    val name: String,
    val parentId: Int? = null,
    val isLeaf: Boolean = false,
    val rank: String = "α",
    val rankIndex: Int = 0,
    val marks: Int = 0,
    val need: Int = 3,
    val totalMarks: Int = 0,
    val max: Boolean = false,
    val children: List<UserAttribute> = emptyList(),
    val patches: List<PatchRef> = emptyList(),
)

@Serializable
data class NamedId(val id: Int, val name: String, val parentId: Int? = null)

@Serializable
data class CreatedPatch(val id: String, val name: String, val cost: Int = 0, val buildPoints: Int = 0)

@Serializable
data class SuggestionNode(val key: String, val code: String? = null, val label: String, val sourceLabel: String = "", val parent: String? = null)

@Serializable
data class SuggestionCatalog(val key: String, val name: String, val source: String = "", val note: String? = null, val nodes: List<SuggestionNode> = emptyList())

@Serializable
data class SuggestionCatalogs(val catalogs: List<SuggestionCatalog> = emptyList())

@Serializable
data class LogEntry(
    val id: Int,
    val timestamp: String = "",
    val content: String = "",
    val marks: Int = 0,
    val tokens: Int = 0,
    val order: Int = 0,
    val period: String? = null,
)

@Serializable
data class LogsResponse(val day: Int = 0, val offset: Int = 0, val date: String = "", val logs: List<LogEntry> = emptyList())

@Serializable
data class LogsByDate(val date: String = "", val day: Int? = null, val logs: List<LogEntry> = emptyList())

@Serializable
data class AgendaItem(
    val id: String? = null,
    val start: String = "",
    val end: String? = null,
    val day: String? = null,
    val label: String = "",
    val labelKind: String? = null,
    val labelId: String? = null,
)

@Serializable
data class CalendarDay(val logCount: Int = 0, val events: List<AgendaItem> = emptyList())

@Serializable
data class CalendarMonth(val year: Int, val month: Int, val days: Map<String, CalendarDay> = emptyMap())

@Serializable
data class JourneyPoint(val day: Int, val at: String = "", val reached: Boolean = false)

@Serializable
data class Recovery(
    val kind: String,
    val cost: Int = 0,
    val heal: Int = 0,
    val cooldownHours: Double = 0.0,
    val secondsLeft: Long = 0,
    val ready: Boolean = false,
    val blocked: String? = null,
)

@Serializable
data class JourneyState(
    val stage: Int = 1,
    val stageDays: Int = 1,
    val startedAt: String = "",
    val nextCheckpointAt: String = "",
    val secondsLeft: Long = 0,
    val points: List<JourneyPoint> = emptyList(),
    val nextPointAt: String = "",
    val secondsToNextPoint: Long = 0,
    val energy: Int = 0,
    val maxEnergy: Int = 0,
    val energyPenalty: Int = 0,
    val resets: Int = 0,
    val checkpointSkillPoints: Int = 0,
    val buildPointsPerDay: Int = 0,
    val tokens: Int = 0,
    val balance: Int = 0,
    val recover: List<Recovery> = emptyList(),
)

@Serializable
data class RecoverResult(val healed: Int = 0, val energy: Int = 0, val maxEnergy: Int = 0, val tokens: Int = 0, val recover: List<Recovery> = emptyList())

@Serializable
data class BossType(val key: String, val name: String, val star: Int = 1)

@Serializable
data class Ability(val name: String, val type: String = "", val rank: String = "", val power: Int = 0)

@Serializable
data class Boss(
    val name: String,
    val stage: Int = 0,
    val slot: Int = 0,
    val rank: String = "",
    val rankName: String = "",
    val type: String = "",
    val types: List<BossType> = emptyList(),
    val hp: Int = 0,
    val mp: Int = 0,
    val attack: Int = 0,
    val special: Int = 0,
    val defense: Int = 0,
    val abilities: List<Ability> = emptyList(),
)

@Serializable
data class Move(
    val actionId: String,
    val name: String,
    val attribute: String = "",
    val attributeName: String = "",
    val rank: String = "",
    val rankIndex: Int = 0,
    val baseDamage: Int = 0,
    val multiplier: Double = 1.0,
    val kinship: String? = null,
    val against: String? = null,
    val damage: Int = 0,
)

@Serializable
data class BossState(
    val boss: Boss,
    val beaten: Boolean = false,
    val lineup: List<Move> = emptyList(),
    val hp: Int = 0,
    val maxHp: Int = 0,
    val armor: Int = 0,
    val reward: Int = 0,
)

@Serializable
data class FightLine(val who: String, val text: String, val damage: Int = 0, val bossHp: Int = 0, val hp: Int = 0)

@Serializable
data class FightResult(
    val won: Boolean = false,
    val log: List<FightLine> = emptyList(),
    val dealt: Int = 0,
    val taken: Int = 0,
    val boss: Boss,
    val lineup: List<Move> = emptyList(),
    val points: Int = 0,
    val energy: Int = 0,
    val journeyReset: Boolean = false,
)

@Serializable
data class JourneyStats(
    val fights: Int = 0,
    val wins: Int = 0,
    val losses: Int = 0,
    val bosses: Int = 0,
    val dealt: Int = 0,
    val taken: Int = 0,
    val bestHit: Int = 0,
    val pointsWon: Int = 0,
    val stage: Int = 0,
    val highestStage: Int = 0,
    val resets: Int = 0,
    val recoverUses: Int = 0,
    val energy: Int = 0,
    val maxEnergy: Int = 0,
)

@Serializable
data class EquipmentItem(
    val id: String,
    val slot: String,
    val name: String,
    val price: Int = 0,
    val text: String = "",
    val owned: Boolean = false,
    val worn: Boolean = false,
)

@Serializable
data class Equipment(val points: Int = 0, val slots: List<String> = emptyList(), val items: List<EquipmentItem> = emptyList())

@Serializable
data class Thought(val id: Int, val day: String = "", val logId: Int? = null, val content: String = "", val updatedAt: String = "")

@Serializable
data class DayLog(
    val id: Int,
    val timestamp: String = "",
    val content: String = "",
    val marks: Int = 0,
    val tokens: Int = 0,
    val order: Int = 0,
    val period: String? = null,
    val thought: Thought? = null,
)

@Serializable
data class DayCycle(
    val acted: Boolean = false,
    val todo: Boolean = false,
    val todosDone: Int = 0,
    val thoughts: Int = 0,
    val logs: Int = 0,
    val dayThought: Boolean = false,
    val complete: Boolean = false,
)

@Serializable
data class AgendaDay(
    val date: String = "",
    val offset: Int = 0,
    val day: Int = 0,
    val logs: List<DayLog> = emptyList(),
    val dayThought: Thought? = null,
    val cycle: DayCycle = DayCycle(),
)

@Serializable
data class Journal(val date: String = "", val summary: String = "", val entry: String = "", val text: String = "")

@Serializable
data class TodoAction(val id: String, val name: String, val acted: Boolean = false)

@Serializable
data class Todo(
    val id: Int,
    val title: String,
    val projectId: String? = null,
    val deadline: String? = null,
    val createdAt: String = "",
    val doneAt: String? = null,
    val done: Boolean = false,
    val reward: Int = 0,
    val late: Boolean = false,
    val actions: List<TodoAction> = emptyList(),
    // only in the answer to /todos/{id}/done
    val points: Int = 0,
)

@Serializable
data class ProjectStats(
    val activeSeconds: Long = 0,
    val inactiveSeconds: Long = 0,
    val actions: Int = 0,
    val marks: Int = 0,
    val todos: Int = 0,
    val todosDone: Int = 0,
)

@Serializable
data class Project(
    val id: String,
    val name: String,
    val deadline: String? = null,
    val active: Boolean = true,
    val createdAt: String = "",
    val endedAt: String? = null,
    val outcome: String? = null,
    val emblem: Boolean = false,
    val stats: ProjectStats = ProjectStats(),
)

@Serializable
data class Items<T>(val items: List<T> = emptyList())

@Serializable
data class ShopAction(
    val name: String,
    val code: String? = null,
    val type: Int = 0,
    val diff: Int = 0,
    val cost: Int = 0,
    val tokenCost: Int = 0,
    val tokenGain: Int = 0,
    val logOnly: Boolean = false,
    val packageAttribute: String = "",
    val leaves: List<Leaf> = emptyList(),
    val author: String? = null,
    val owned: Boolean = false,
    val new: Boolean = false,
)

@Serializable
data class ShopGroup(val key: String, val name: String, val actions: List<ShopAction> = emptyList())

@Serializable
data class ShopState(
    val phase: String = "frames",
    val rate: Int = 0,
    val left: Int = 0,
    val found: Int = 0,
    val catalog: Int = 0,
    val points: Int = 0,
    val new: List<String> = emptyList(),
    val groups: List<ShopGroup> = emptyList(),
)

@Serializable
data class Bought(val id: String = "", val name: String = "", val buildPoints: Int = 0, val lines: List<Line> = emptyList())

/** The answer of anything that may move the story: a thought, a to-do, a project. */
@Serializable
data class Said(val lines: List<Line> = emptyList())

@Serializable
data class Entity(
    val id: String,
    val name: String,
    val title: String = "",
    val color: String = "#3dfff0",
    val personality: String = "",
    /** "caps" shouts in capitals, "lower" speaks as typed */
    val voice: String = "caps",
    val presence: Double = 0.0,
    val willing: Double = 0.0,
    val stats: Map<String, JsonElement> = emptyMap(),
    val glyph: String = "roko",
    val trait: String? = null,
    val animated: Boolean = false,
    val battle: EntityBattle? = null,
    // in /entity: whether the profile carries none, and its affinity with each
    val none: Boolean = false,
    val affinity: Map<String, Double> = emptyMap(),
)

/** An entity in the journey's fights (backend/src/domain/fight.py). */
@Serializable
data class EntityBattle(val forca: Int = 10, val agilidade: Int = 1, val skill: String = "", val ability: String = "", val abilityName: String = "")

@Serializable
data class EntityTalk(
    val entity: String = "",
    val present: Boolean = false,
    val answered: Boolean = false,
    val line: String? = null,
    /** what the others said about the talk, when it moved the story */
    val lines: List<Line> = emptyList(),
)

@Serializable
data class Ally(val nickname: String, val marks: Int = 0, val stage: Int = 0)

@Serializable
data class Allies(val passcode: String = "", val items: List<Ally> = emptyList())

@Serializable
data class Nickname(val nickname: String)

@Serializable
data class EmailAnswer(val email: String? = null)

@Serializable
data class Ok(val ok: Boolean = true)
