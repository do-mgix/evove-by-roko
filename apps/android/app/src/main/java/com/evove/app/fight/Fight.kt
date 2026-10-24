package com.evove.app.fight

import com.evove.app.api.FightEntity
import com.evove.app.api.FightSetup
import com.evove.app.api.FightSide

// The journey's fights, played live: the same rules as the server's
// (backend/src/domain/fight.py), tick by tick, in the same order and on the
// same generator, so what the person sees is what the server decides when it
// replays the fight with the ticks the tricks were played at. Every number is
// a whole one; FightParityTest checks both sides against the same fights.

const val TRICK_CD = 120
const val TRICK_ROLL = 60
private const val TRICK_PPM = 15_000
private const val STUN_TICKS = 50
private const val FURY_TICKS = 80
private const val THUD_TICKS = 40
private const val SHIELD_PCT = 60
private const val ECHO_PCT = 60
private const val HEAL_AT_PCT = 60
private const val DEFENSE_CAP = 75
private const val PATIENCE_BASE_PPM = 1000
private const val PATIENCE_GROWTH_PPM = 1
const val ABILITY_CD = 400
private const val ABILITY_FIRST = 300
private const val BOOST_TICKS = 100
private const val STAND_TICKS = 160
private const val HASTE_TICKS = 120
private const val BLOCK_TICKS = 240
private const val BURN_TICKS = 200
private const val DECREE_TICKS = 120
private const val MASK = 0xFFFFFFFFL

val TRICKS = listOf("atordoar", "furia", "baque", "rasteira", "escudo", "eco")
val SKILLS = listOf("negar", "atacar", "potencia", "cura", "truques")
private val EVENTS = listOf("attack", "heal", "trick", "skill", "ability", "interfere", "deny", "miss", "burn", "end", "level")
private const val ALLY_XP_NEED = 2
private const val ALLY_LEVEL_FORCA = 5
private const val ALLY_LEVEL_AGILIDADE = 1
private const val AGILIDADE_CAP = 12

fun skillCd(agilidade: Int) = maxOf(60, 240 - 16 * agilidade)

/** xorshift32, as the server's. */
class Rng(seed: Long) {
    private var x: Long = (seed and MASK).let { if (it == 0L) 0x9E3779B9L else it }

    fun next(): Long {
        var v = x
        v = v xor ((v shl 13) and MASK)
        v = v xor (v ushr 17)
        v = v xor ((v shl 5) and MASK)
        x = v and MASK
        return x
    }

    fun below(n: Int): Int = (next() % n).toInt()
}

class Move(val name: String, val dmg: Long, val decree: Long, val cd: Int, var t: Int)
class Heal(val name: String, val amount: Long, val cd: Int, var t: Int)

class Ally(val id: String, val name: String, var forca: Int, var agilidade: Int, val skill: String, val ability: String, var level: Int) {
    var skillT = skillCd(agilidade)
    var abilityT = ABILITY_FIRST
    var patience = 0
    var xp = 0
}

class Side(d: FightSide, val tricks: Boolean) {
    val name = d.name
    var hp = d.hp
    var maxHp = d.maxHp
    var resist = d.resist
    var defense = d.defense
    var absorb = d.absorb
    val moves = d.moves.mapIndexed { i, m -> Move(m.name, m.dmg, m.decree ?: m.dmg, m.cd, m.cd / 2 + 3 * i) }
    val heal = Heal(d.heal.name, d.heal.amount, d.heal.cd, d.heal.cd / 2)
    val allies = d.entities.map { e: FightEntity -> Ally(e.id, e.name, e.forca, e.agilidade, e.skill, e.ability, e.level) }
    // the journey's level, which every blow that lands feeds
    var level = d.level
    var xp = d.xp
    val xpNeed = d.xpNeed
    var bonus = d.bonus
    val up = d.perLevel
    var charge = TRICK_CD / 2
    var roll = 0
    var cur: String? = null
    var nxt: String? = null
    var stun = 0; var boost = 0; var stand = 0; var haste = 0; var block = 0; var burn = 0; var decree = 0
    var deny = 0; var doubt = 0; var shield = 0
    var last: Int? = null
    var dealt = 0L; var heals = 0; var used = 0; var interfered = 0

    fun defenseNow() = minOf(DEFENSE_CAP, defense + (if (boost > 0) 15 else 0) + (if (stand > 0) 30 else 0) + (if (decree > 0) 10 else 0))
    fun resistNow() = resist + (if (boost > 0) 20 else 0) + (if (decree > 0) 20 else 0)
    fun absorbNow() = absorb + (if (decree > 0) 20 else 0)
    fun best(): Long = moves.maxOfOrNull { if (decree > 0) it.decree else it.dmg } ?: 1L
    fun cost(): Long = maxOf(1L, maxHp / (100 + resistNow()))
    val ready get() = tricks && charge >= TRICK_CD
}

/** What the screen draws of a side, at one tick. */
/** An entity at one tick: its skill and ability recharging, and the chance it
 *  steps in within the next second, which grows as the fight drags on. */
data class AllyView(val id: String, val name: String, val skill: Float, val ability: Float, val chance: Float, val level: Int = 1)
data class SideView(
    val name: String, val hp: Long, val maxHp: Long, val moves: List<Pair<String, Float>>, val heal: Pair<String, Float>,
    val charge: Float, val ready: Boolean, val trick: String?, val next: String?, val allies: List<AllyView>,
    val level: Int = 1, val xp: Float = 0f,
    // what the tricks and the entities did to it, for the screen to show
    val stunned: Boolean = false, val shielded: Boolean = false, val boosted: Boolean = false, val hasted: Boolean = false,
    val burning: Boolean = false, val doubting: Boolean = false, val denying: Boolean = false,
)
data class FightView(val tick: Int, val sides: List<SideView>, val events: List<FightEvent>, val over: Boolean, val won: Boolean, val frozen: Boolean = false)

/** Something that happened, for the screen to show: at `t`, by side `s`. */
data class FightEvent(val t: Int, val kind: String, val side: Int, val value: Long, val name: String)

class Fight(setup: FightSetup) {
    private val rng = Rng(setup.seed)
    val maxTicks = setup.maxTicks
    val sides = listOf(Side(setup.you, true), Side(setup.foe, setup.foe.tricks))
    var tick = 0
        private set
    var freeze = 0
        private set
    var over = false
        private set
    var won = false
        private set
    var check = 0L
        private set
    val events = mutableListOf<FightEvent>()

    init {
        for (s in sides) if (s.tricks) { s.cur = draw(); s.nxt = draw() }
    }

    private fun draw() = TRICKS[rng.below(TRICKS.size)]

    /** The fight as it stands, copied: a value the screen can hold as state. */
    fun view(): FightView = FightView(tick, sides.map { s ->
        SideView(
            s.name, s.hp, s.maxHp,
            s.moves.map { it.name to (1f - it.t / it.cd.toFloat()) },
            s.heal.name to (1f - s.heal.t / s.heal.cd.toFloat()),
            s.charge / TRICK_CD.toFloat(), s.ready, s.cur, s.nxt,
            s.allies.map {
                val p = (PATIENCE_BASE_PPM + PATIENCE_GROWTH_PPM * (it.patience + 5)) / 1_000_000.0
                AllyView(it.id, it.name, 1f - it.skillT / skillCd(it.agilidade).toFloat(), 1f - it.abilityT / ABILITY_CD.toFloat(),
                    (1 - Math.pow(1 - p, 10.0)).toFloat(), it.level)
            },
            level = s.level, xp = if (s.xpNeed > 0) s.xp / s.xpNeed.toFloat() else 0f,
            stunned = s.stun > 0, shielded = s.shield > 0, boosted = s.boost > 0 || s.decree > 0, hasted = s.haste > 0,
            burning = s.burn > 0, doubting = s.doubt > 0, denying = s.deny > 0,
        )
    }, events.filter { it.kind != "end" }.takeLast(5), over, won, frozen = freeze > 0)

    private fun event(kind: String, side: Int, value: Long, name: String = "") {
        events += FightEvent(tick, kind, side, value, name)
        check = (check * 31 + tick * 7L + EVENTS.indexOf(kind) * 13L + side * 17L + value) and MASK
    }

    private fun hit(i: Int, dmg: Long, kind: String, name: String) {
        sides[1 - i].hp -= dmg
        sides[i].dealt += dmg
        event(kind, i, dmg, name)
    }

    private fun attack(i: Int, m: Int, pct: Int = 100, free: Boolean = false) {
        val s = sides[i]
        val o = sides[1 - i]
        val move = s.moves[m]
        if (!free) s.hp -= s.cost()
        s.last = m
        var dmg = (if (s.decree > 0) move.decree else move.dmg) * pct / 100 * (100 + s.bonus) / 100
        if (s.boost > 0) dmg = dmg * 125 / 100
        if (o.deny > 0) {
            o.deny -= 1
            event("deny", i, 0, move.name)
            return
        }
        if (s.doubt > 0) {
            s.doubt -= 1
            if (rng.below(2) == 0) {
                event("miss", i, 0, move.name)
                return
            }
        }
        dmg = dmg * (100 - o.defenseNow()) / 100
        if (o.shield > 0) {
            o.shield = 0
            dmg = dmg * (100 - SHIELD_PCT) / 100
        }
        dmg = maxOf(1L, dmg)
        o.hp -= dmg
        s.dealt += dmg
        event("attack", i, dmg, move.name)
        grow(i)
    }

    /** A blow landed: experience, and a level when it is enough. */
    private fun grow(i: Int) {
        val s = sides[i]
        if (s.xpNeed <= 0) return
        s.xp += 1
        if (s.xp < s.xpNeed) return
        s.xp = 0
        s.level += 1
        s.maxHp += s.up.hp
        s.hp += s.up.hp
        s.resist += s.up.resist
        s.defense += s.up.defense
        s.bonus += s.up.bonus
        event("level", i, s.level.toLong(), s.name)
    }

    private fun allyGrows(i: Int, e: Ally) {
        e.xp += 1
        if (e.xp < ALLY_XP_NEED) return
        e.xp = 0
        e.level += 1
        e.forca += ALLY_LEVEL_FORCA
        e.agilidade = minOf(AGILIDADE_CAP, e.agilidade + ALLY_LEVEL_AGILIDADE)
        event("level", i, e.level.toLong(), e.name)
    }

    private fun heal(i: Int, amount: Long, name: String) {
        val s = sides[i]
        val got = maxOf(0L, minOf(s.maxHp - s.hp, amount * s.absorbNow() / 100))
        s.hp += got
        event("heal", i, got, name)
    }

    private fun trick(i: Int, trick: String) {
        val s = sides[i]
        val o = sides[1 - i]
        when (trick) {
            "atordoar" -> o.stun = maxOf(o.stun, STUN_TICKS)
            // everything of one's own recharges twice as fast for a while
            "furia" -> s.haste = maxOf(s.haste, FURY_TICKS)
            "baque" -> freeze = maxOf(freeze, THUD_TICKS)
            "rasteira" -> if (o.moves.isNotEmpty()) {
                var k = 0
                for (j in o.moves.indices) if (o.moves[j].t < o.moves[k].t) k = j
                o.moves[k].t = o.moves[k].cd
            }
            "escudo" -> s.shield = 1
            "eco" -> s.last?.let { attack(i, it, ECHO_PCT, free = true) }
        }
        event("trick", i, TRICKS.indexOf(trick).toLong(), trick)
    }

    private fun play(i: Int) {
        val s = sides[i]
        if (!s.ready) return
        val t = s.cur ?: return
        s.used += 1
        s.cur = s.nxt
        s.nxt = draw()
        s.charge = 0
        s.roll = 0
        trick(i, t)
    }

    private fun skill(i: Int, e: Ally) {
        val s = sides[i]
        when (e.skill) {
            "negar" -> s.deny += 1
            "atacar" -> { hit(i, maxOf(1L, s.best() * e.forca / 40), "skill", "${e.name}|atacar"); return }
            "potencia" -> s.boost = BOOST_TICKS
            "cura" -> { heal(i, s.maxHp * 12 / 100, e.name); return }
            "truques" -> { trick(i, draw()); trick(i, draw()) }
        }
        event("skill", i, SKILLS.indexOf(e.skill).toLong(), "${e.name}|${e.skill}")
    }

    private fun ability(i: Int, e: Ally) {
        val s = sides[i]
        val o = sides[1 - i]
        when (e.ability) {
            "decreto" -> s.decree = DECREE_TICKS
            "pergunta" -> o.doubt = 3
            "ficar" -> s.stand = STAND_TICKS
            "pressa" -> s.haste = HASTE_TICKS
            "troca" -> { o.block = BLOCK_TICKS; heal(i, o.heal.amount, e.name) }
            "amarra" -> { for (m in o.moves) m.t = m.cd; o.stun = maxOf(o.stun, 10) }
            "chama" -> o.burn = BURN_TICKS
            else -> when (rng.below(3)) {
                0 -> o.stun = maxOf(o.stun, 15)
                1 -> s.deny += 1
                else -> heal(i, s.maxHp * 8 / 100, e.name)
            }
        }
        event("ability", i, 0, "${e.name}|${e.ability}")
    }

    /** One tick; `play` is whether the trick on offer was played at its start.
     *  Returns whether the fight is over. */
    fun step(play: Boolean = false): Boolean {
        if (over) return true
        val you = sides[0]
        val foe = sides[1]
        if (play) play(0)
        // the tricks play themselves, a little after they are charged
        for (i in sides.indices) if (sides[i].tricks && sides[i].charge >= TRICK_CD && rng.below(1_000_000) < TRICK_PPM) play(i)
        if (freeze > 0) {
            freeze -= 1
        } else {
            for (s in sides) {
                if (s.stun > 0) { s.stun -= 1; continue }
                val step = if (s.haste > 0) 2 else 1
                for (m in s.moves) m.t = maxOf(0, m.t - step)
                s.heal.t = maxOf(0, s.heal.t - step)
            }
            for ((i, s) in sides.withIndex()) {
                if (s.stun > 0) continue
                for ((k, m) in s.moves.withIndex()) {
                    if (m.t == 0 && s.hp > s.cost()) {
                        attack(i, k)
                        m.t = m.cd
                    }
                }
                if (s.heal.t == 0 && s.block == 0 && s.hp * 100 <= HEAL_AT_PCT * s.maxHp) {
                    heal(i, s.heal.amount, s.heal.name)
                    s.heals += 1
                    s.heal.t = s.heal.cd
                }
            }
            for ((i, s) in sides.withIndex()) {
                for (e in s.allies) {
                    e.skillT -= 1
                    if (e.skillT <= 0) { skill(i, e); allyGrows(i, e); e.skillT = skillCd(e.agilidade) }
                    e.abilityT -= 1
                    if (e.abilityT <= 0) { ability(i, e); allyGrows(i, e); e.abilityT = ABILITY_CD }
                }
            }
            for ((i, s) in sides.withIndex()) {
                for (e in s.allies) {
                    e.patience += 1
                    if (rng.below(1_000_000) < PATIENCE_BASE_PPM + PATIENCE_GROWTH_PPM * e.patience) {
                        hit(i, maxOf(1L, s.best() * e.forca / 10), "interfere", e.name)
                        s.interfered += 1
                        e.patience /= 2
                        allyGrows(i, e)
                    }
                }
            }
        }
        for ((i, s) in sides.withIndex()) {
            if (s.boost > 0) s.boost -= 1
            if (s.stand > 0) s.stand -= 1
            if (s.haste > 0) s.haste -= 1
            if (s.block > 0) s.block -= 1
            if (s.decree > 0) s.decree -= 1
            if (s.burn > 0) {
                s.burn -= 1
                if (s.burn % 20 == 0) hit(1 - i, maxOf(1L, s.maxHp * 2 / 100), "burn", "chama")
            }
            if (s.tricks) {
                if (s.charge < TRICK_CD) s.charge += 1
                else {
                    s.roll += 1
                    if (s.roll >= TRICK_ROLL) { s.cur = s.nxt; s.nxt = draw(); s.roll = 0 }
                }
            }
        }
        tick += 1
        if (you.hp <= 0 || foe.hp <= 0) {
            won = foe.hp <= 0 && you.hp > 0
            end()
        } else if (tick >= maxTicks) {
            won = you.hp * foe.maxHp > foe.hp * you.maxHp
            end()
        }
        return over
    }

    private fun end() {
        over = true
        event("end", if (won) 0 else 1, 0)
    }

    companion object {
        /** The fight `setup` describes with tricks played at `plays`, to its end. */
        fun replay(setup: FightSetup, plays: Collection<Int>): Fight {
            val at = plays.toSet()
            val f = Fight(setup)
            while (!f.step(f.tick in at)) Unit
            return f
        }
    }
}
