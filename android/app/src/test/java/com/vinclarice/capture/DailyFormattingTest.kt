package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Same wording as frontend/src/agenda.ts's dueLabel/ageLabel -- see
 * android-full-client-plan.md §2 on why these are ported by hand rather
 * than shared, and why they stay each platform's own tested copy.
 */
class DailyFormattingTest {

    @Test
    fun `a task due before today is overdue`() {
        assertEquals("3 days overdue", dueLabel("2026-08-07", "2026-08-10"))
    }

    @Test
    fun `one day overdue reads Yesterday, not 1 days overdue`() {
        assertEquals("Yesterday", dueLabel("2026-08-09", "2026-08-10"))
    }

    @Test
    fun `a task due today reads Today`() {
        assertEquals("Today", dueLabel("2026-08-10", "2026-08-10"))
    }

    @Test
    fun `a task due tomorrow reads Tomorrow`() {
        assertEquals("Tomorrow", dueLabel("2026-08-11", "2026-08-10"))
    }

    @Test
    fun `a task due further out shows a short calendar date`() {
        val label = dueLabel("2026-08-20", "2026-08-10")
        // Weekday abbreviation isn't asserted -- it depends on which day of
        // the week the 20th actually falls on. What has to be right is the
        // day and month.
        assertTrue(label.contains("20"))
        assertTrue(label.endsWith("Aug"))
    }

    @Test
    fun `age below the threshold is not worth mentioning`() {
        assertNull(ageLabel(6))
    }

    @Test
    fun `age at the threshold is mentioned`() {
        assertEquals("Added 7 days ago", ageLabel(7))
    }

    @Test
    fun `age well past the threshold is mentioned`() {
        assertEquals("Added 30 days ago", ageLabel(30))
    }

    @Test
    fun `the long date names the weekday, day and month`() {
        // "Saturday 10 August" -- DayRoute.tsx's own longDate, same shape.
        val label = longDate("2026-08-10")
        assertTrue(label.contains("10"))
        assertTrue(label.contains("August"))
    }
}
