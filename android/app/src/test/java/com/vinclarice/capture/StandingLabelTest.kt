package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Test

/** Same wording rules as DayRoute.tsx's standingLabel. */
class StandingLabelTest {

    private fun standing(
        progress: Int = 0,
        target: Int = 1,
        unit: String = "",
        outcome: String = "open",
        isMet: Boolean = false,
    ) = StandingEntry(
        routineId = 1,
        title = "Practice Spanish",
        cadence = "daily",
        progress = progress,
        target = target,
        unit = unit,
        outcome = outcome,
        isMet = isMet,
    )

    @Test
    fun `a skipped routine reads Skipped regardless of progress`() {
        assertEquals("Skipped", standingLabel(standing(outcome = "skipped", progress = 1)))
    }

    @Test
    fun `a plain yes-or-no routine not yet done reads Not yet`() {
        assertEquals("Not yet", standingLabel(standing(unit = "", target = 1, progress = 0)))
    }

    @Test
    fun `a plain yes-or-no routine done reads Done`() {
        assertEquals("Done", standingLabel(standing(unit = "", target = 1, progress = 1)))
    }

    @Test
    fun `a counted routine reads progress of target and unit`() {
        assertEquals(
            "3 of 5 lessons",
            standingLabel(standing(progress = 3, target = 5, unit = "lessons")),
        )
    }

    @Test
    fun `a partial outcome appends the enough note`() {
        assertEquals(
            "2 of 5 lessons — enough",
            standingLabel(standing(progress = 2, target = 5, unit = "lessons", outcome = "partial")),
        )
    }
}
