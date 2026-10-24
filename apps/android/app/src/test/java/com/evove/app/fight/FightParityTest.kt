package com.evove.app.fight

import com.evove.app.api.Api
import com.evove.app.api.FightOutcome
import com.evove.app.api.FightSetup
import kotlinx.serialization.Serializable
import org.junit.Assert.assertEquals
import org.junit.Test

/** The fights backend/scripts/fight_cases.py wrote with what the server
 *  decided: the app's rules must reach the same end, to the tick. */
class FightParityTest {
    @Serializable
    private data class Case(val setup: FightSetup, val plays: List<Int>, val result: FightOutcome)

    @Test fun sameAsTheServer() {
        val text = javaClass.classLoader!!.getResource("fight_cases.json")!!.readText()
        val cases = Api.json.decodeFromString<List<Case>>(text)
        assert(cases.size >= 50)
        for ((n, c) in cases.withIndex()) {
            val f = Fight.replay(c.setup, c.plays)
            val you = f.sides[0]
            val foe = f.sides[1]
            val got = listOf(f.won, f.tick, maxOf(0, you.hp), maxOf(0, foe.hp), you.dealt, foe.dealt, you.heals, foe.heals,
                you.used, foe.used, you.interfered, foe.interfered, f.check)
            val want = c.result.let { r -> listOf(r.won, r.ticks, r.hp[0], r.hp[1], r.dealt[0], r.dealt[1], r.heals[0], r.heals[1],
                r.tricks[0], r.tricks[1], r.interfered[0], r.interfered[1], r.check) }
            assertEquals("fight $n", want, got)
        }
    }
}
