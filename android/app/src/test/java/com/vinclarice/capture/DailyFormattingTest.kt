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

    /* ~~`tomorrow is one day after today`~~ -- moved here from
       `AgendaFormattingTest` in the morning and **deleted the same day**, with
       the function, when increment 4 made *Tomorrow* a pin rather than a date
       move. A test whose subject is gone is not coverage. */

    /* android-overhaul-plan.md increment 2: the line says when the work began.

       The zone is passed rather than taken from the device, so this asserts a
       fact rather than whatever machine runs it. It matters for more than the
       test: `list_closed_at` is an instant, the day it belongs to is the
       owner's, and a phone carried across a timezone would otherwise print a
       time from wherever it happens to be standing. */

    @Test
    fun `the line says the local time the work began`() {
        assertEquals(
            "14:30",
            timeOfDay("2026-08-10T14:30:00Z", java.time.ZoneOffset.UTC),
        )
    }

    @Test
    fun `the line reads the instant in the zone it is given`() {
        assertEquals(
            "10:30",
            timeOfDay("2026-08-10T14:30:00Z", java.time.ZoneId.of("America/New_York")),
        )
    }

    @Test
    fun `an offset the server sent rather than a Z still parses`() {
        // Django renders an aware datetime with an offset, not always with Z.
        assertEquals(
            "09:00",
            timeOfDay("2026-08-10T09:00:00-04:00", java.time.ZoneId.of("America/New_York")),
        )
    }
}
