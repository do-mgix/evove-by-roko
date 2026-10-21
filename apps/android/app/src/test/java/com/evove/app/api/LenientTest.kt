package com.evove.app.api

import org.junit.Assert.assertEquals
import org.junit.Test

class LenientTest {
    @Test fun wholeNumbersTakeFloats() {
        val a = Api.json.decodeFromString<Action>("""{"id":"1","name":"X","value":3.0,"score":2.5,"diff":2}""")
        assertEquals(3, a.value)
        assertEquals(2, a.score)
        assertEquals(2, a.diff)
        val l = Api.json.decodeFromString<List<Action>>("""[{"id":"1","name":"X","tiers":[{"index":1.0,"label":"a","marks":4.0}]}]""")
        assertEquals(4, l[0].tiers[0].marks)
    }
}
