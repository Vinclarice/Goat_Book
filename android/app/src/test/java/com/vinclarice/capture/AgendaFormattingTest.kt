package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Same rules as frontend/src/agenda.ts's bucketFor and its query filter. */
class AgendaFormattingTest {

    @Test
    fun `no due date is someday`() {
        assertEquals(AgendaBucket.SOMEDAY, bucketFor(null, "2026-08-11"))
    }

    @Test
    fun `a past due date is overdue`() {
        assertEquals(AgendaBucket.OVERDUE, bucketFor("2026-08-10", "2026-08-11"))
    }

    @Test
    fun `todays due date is today`() {
        assertEquals(AgendaBucket.TODAY, bucketFor("2026-08-11", "2026-08-11"))
    }

    @Test
    fun `within the week horizon is week`() {
        assertEquals(AgendaBucket.WEEK, bucketFor("2026-08-18", "2026-08-11"))
    }

    @Test
    fun `exactly on the horizon boundary is still week`() {
        // WEEK_HORIZON_DAYS is 7 -- the 7th day out is inclusive.
        assertEquals(AgendaBucket.WEEK, bucketFor("2026-08-18", "2026-08-11"))
    }

    @Test
    fun `past the horizon is later`() {
        assertEquals(AgendaBucket.LATER, bucketFor("2026-08-19", "2026-08-11"))
    }

    @Test
    fun `an empty query matches everything`() {
        assertTrue(matchesQuery("Call the vet", ""))
        assertTrue(matchesQuery("Call the vet", "   "))
    }

    @Test
    fun `a query matches case-insensitively as a substring`() {
        assertTrue(matchesQuery("Call the vet", "VET"))
        assertTrue(matchesQuery("Call the vet", "the"))
    }

    @Test
    fun `a query that does not appear does not match`() {
        assertFalse(matchesQuery("Call the vet", "dentist"))
    }

    private fun task(
        id: Int,
        text: String = "Task $id",
        areaId: Int = 1,
        tags: List<String> = emptyList(),
    ) = AgendaTaskEntry(
        id = id,
        text = text,
        dueDate = null,
        tags = tags,
        areaId = areaId,
        projectId = null,
    )

    @Test
    fun `with no filters set everything matches`() {
        val tasks = listOf(task(1), task(2))

        assertEquals(tasks, filterTasks(tasks, areaId = null, tag = null, query = ""))
    }

    @Test
    fun `an area filter narrows to that area only`() {
        val tasks = listOf(task(1, areaId = 3), task(2, areaId = 4))

        assertEquals(listOf(task(1, areaId = 3)), filterTasks(tasks, areaId = 3, tag = null, query = ""))
    }

    @Test
    fun `a tag filter requires the tag to be present`() {
        val tasks = listOf(task(1, tags = listOf("urgent")), task(2, tags = listOf("someday")))

        assertEquals(
            listOf(task(1, tags = listOf("urgent"))),
            filterTasks(tasks, areaId = null, tag = "urgent", query = ""),
        )
    }

    @Test
    fun `area, tag and query filters combine with AND`() {
        val tasks = listOf(
            task(1, text = "Call the vet", areaId = 3, tags = listOf("urgent")),
            task(2, text = "Call the vet", areaId = 3, tags = listOf("someday")),
            task(3, text = "Buy milk", areaId = 3, tags = listOf("urgent")),
        )

        val result = filterTasks(tasks, areaId = 3, tag = "urgent", query = "vet")

        assertEquals(listOf(tasks[0]), result)
    }

    private fun dated(id: Int, dueDate: String?) = task(id).copy(dueDate = dueDate)

    @Test
    fun `the overdue scope keeps only overdue tasks`() {
        val tasks = listOf(dated(1, "2026-08-10"), dated(2, "2026-08-11"), dated(3, null))

        val result = filterTasks(
            tasks, areaId = null, tag = null, query = "",
            scope = AgendaScope.OVERDUE, today = "2026-08-11",
        )

        assertEquals(listOf(dated(1, "2026-08-10")), result)
    }

    @Test
    fun `the week scope is cumulative -- overdue and today count as this week too`() {
        val tasks = listOf(dated(1, "2026-08-10"), dated(2, "2026-08-11"), dated(3, "2026-08-30"))

        val result = filterTasks(
            tasks, areaId = null, tag = null, query = "",
            scope = AgendaScope.WEEK, today = "2026-08-11",
        )

        assertEquals(listOf(dated(1, "2026-08-10"), dated(2, "2026-08-11")), result)
    }

    @Test
    fun `no scope selected leaves every bucket in`() {
        val tasks = listOf(dated(1, "2026-08-10"), dated(2, null))

        assertEquals(tasks, filterTasks(tasks, areaId = null, tag = null, query = "", scope = null))
    }

    @Test
    fun `tomorrow is one day after today`() {
        assertEquals("2026-08-12", tomorrow("2026-08-11"))
    }

    @Test
    fun `next Monday from a Tuesday is six days out`() {
        // 2026-08-11 is a Tuesday.
        assertEquals("2026-08-17", nextMonday("2026-08-11"))
    }

    @Test
    fun `next Monday from a Monday is a full week out, not today`() {
        assertEquals("2026-08-17", nextMonday("2026-08-10"))
    }
}
