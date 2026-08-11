package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Agenda screen's own state -- android-full-client-plan.md slice 2.
 * Read on open like DailyViewModel; writes reload the whole agenda on
 * success rather than patching one row in place, since completing a task
 * moves it between items and completed_today in a way a single-row patch
 * can't express, and a failed write must never blank an already-visible
 * list -- see write()'s own reasoning.
 */
class AgendaViewModelTest {

    private class FakeStore(private var saved: String? = "tok_abc") : TokenStore {
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null }
    }

    private class FakeAgendaApi(
        private var readResult: AgendaResult,
        private var writeResult: TaskWriteResult = TaskWriteUnreachable("unused"),
    ) : AgendaApi {
        var readCalls = 0
        var lastWrite: Triple<String, String, String?>? = null // (kind, url/or text, extra)

        fun respondToNextReadWith(result: AgendaResult) { readResult = result }

        override suspend fun getAgenda(token: String): AgendaResult {
            readCalls++
            return readResult
        }

        override suspend fun setTaskStatus(token: String, taskUrl: String, status: String): TaskWriteResult {
            lastWrite = Triple("status", taskUrl, status)
            return writeResult
        }

        override suspend fun rescheduleTask(token: String, taskUrl: String, dueDate: String?): TaskWriteResult {
            lastWrite = Triple("due_date", taskUrl, dueDate)
            return writeResult
        }

        override suspend fun createTask(
            token: String,
            createItemUrl: String,
            text: String,
            dueDate: String?,
        ): TaskWriteResult {
            lastWrite = Triple("create", createItemUrl, text)
            return writeResult
        }
    }

    private val area = AgendaAreaEntry(
        id = 3,
        title = "House hold",
        colorKey = "sky",
        openCount = 1,
        overdueCount = 1,
        createItemUrl = "/api/areas/3/items/",
    )

    private val task = AgendaTaskEntry(
        id = 7,
        text = "Pay tmobile bill",
        dueDate = "2026-07-31",
        tags = listOf("bills"),
        areaId = 3,
        projectId = null,
        url = "/api/items/7/",
    )

    private val sampleAgenda = AgendaEntry(
        today = "2026-08-11",
        items = listOf(task),
        completedToday = emptyList(),
        areas = listOf(area),
        projects = emptyList(),
    )

    @Test
    fun `a loaded agenda is shown, not still loading`() = runTest {
        val model = AgendaViewModel(FakeAgendaApi(AgendaLoaded(sampleAgenda)), FakeStore())

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertEquals(sampleAgenda, state.agenda)
        assertNull(state.message)
    }

    @Test
    fun `an unauthorised token asks to reconnect`() = runTest {
        val model = AgendaViewModel(FakeAgendaApi(AgendaUnauthorised), FakeStore())

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertNull(state.agenda)
        assertTrue(state.isError)
        assertTrue(state.message!!.contains("Reconnect"))
    }

    @Test
    fun `an unreachable server reports its own reason`() = runTest {
        val model = AgendaViewModel(
            FakeAgendaApi(AgendaUnreachable("Could not reach Clarice.")), FakeStore()
        )

        model.load()

        assertEquals("Could not reach Clarice.", model.state.value.message)
    }

    @Test
    fun `no stored token is quiet, not an error, and never asks the network`() = runTest {
        val api = FakeAgendaApi(AgendaLoaded(sampleAgenda))
        val model = AgendaViewModel(api, FakeStore(saved = null))

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertFalse(state.isError)
        assertNull(state.agenda)
        assertEquals(0, api.readCalls)
    }

    @Test
    fun `selecting an area filter twice clears it`() = runTest {
        val model = AgendaViewModel(FakeAgendaApi(AgendaLoaded(sampleAgenda)), FakeStore())

        model.setAreaFilter(3)
        assertEquals(3, model.state.value.areaFilter)

        model.setAreaFilter(3)
        assertNull(model.state.value.areaFilter)
    }

    @Test
    fun `selecting a different area replaces the filter rather than toggling`() = runTest {
        val model = AgendaViewModel(FakeAgendaApi(AgendaLoaded(sampleAgenda)), FakeStore())

        model.setAreaFilter(3)
        model.setAreaFilter(4)

        assertEquals(4, model.state.value.areaFilter)
    }

    @Test
    fun `setting the query updates it directly, no toggling`() = runTest {
        val model = AgendaViewModel(FakeAgendaApi(AgendaLoaded(sampleAgenda)), FakeStore())

        model.setQuery("vet")

        assertEquals("vet", model.state.value.query)
    }

    @Test
    fun `completing a task sends its own url and reloads on success`() = runTest {
        val api = FakeAgendaApi(
            readResult = AgendaLoaded(sampleAgenda),
            writeResult = TaskWriteSucceeded(task.copy(dueDate = null)),
        )
        val model = AgendaViewModel(api, FakeStore())
        model.load()

        model.completeTask(task)

        assertEquals(Triple("status", "/api/items/7/", "completed"), api.lastWrite)
        // load() ran once on open and once more as the reload after a
        // successful write.
        assertEquals(2, api.readCalls)
        assertFalse(model.state.value.busy)
    }

    @Test
    fun `reopening a task sends active`() = runTest {
        val api = FakeAgendaApi(
            readResult = AgendaLoaded(sampleAgenda),
            writeResult = TaskWriteSucceeded(task),
        )
        val model = AgendaViewModel(api, FakeStore())

        model.reopenTask(task)

        assertEquals(Triple("status", "/api/items/7/", "active"), api.lastWrite)
    }

    @Test
    fun `rescheduling sends the new due date`() = runTest {
        val api = FakeAgendaApi(
            readResult = AgendaLoaded(sampleAgenda),
            writeResult = TaskWriteSucceeded(task),
        )
        val model = AgendaViewModel(api, FakeStore())

        model.reschedule(task, "2026-09-01")

        assertEquals(Triple("due_date", "/api/items/7/", "2026-09-01"), api.lastWrite)
    }

    @Test
    fun `clearing a due date sends null through`() = runTest {
        val api = FakeAgendaApi(
            readResult = AgendaLoaded(sampleAgenda),
            writeResult = TaskWriteSucceeded(task),
        )
        val model = AgendaViewModel(api, FakeStore())

        model.reschedule(task, null)

        assertEquals(Triple("due_date", "/api/items/7/", null), api.lastWrite)
    }

    @Test
    fun `quick-add posts to the areas own create_item_url`() = runTest {
        val api = FakeAgendaApi(
            readResult = AgendaLoaded(sampleAgenda),
            writeResult = TaskWriteSucceeded(task),
        )
        val model = AgendaViewModel(api, FakeStore())

        model.quickAdd(area, "Call the vet", null)

        assertEquals(Triple("create", "/api/areas/3/items/", "Call the vet"), api.lastWrite)
    }

    @Test
    fun `quick-add with blank text never reaches the network`() = runTest {
        val api = FakeAgendaApi(AgendaLoaded(sampleAgenda))
        val model = AgendaViewModel(api, FakeStore())

        model.quickAdd(area, "   ", null)

        assertNull(api.lastWrite)
    }

    @Test
    fun `a failed write reports the message but keeps the list on screen`() = runTest {
        val api = FakeAgendaApi(
            readResult = AgendaLoaded(sampleAgenda),
            writeResult = TaskWriteRejected("Use a valid date (YYYY-MM-DD)."),
        )
        val model = AgendaViewModel(api, FakeStore())
        model.load()

        model.reschedule(task, "not-a-date")

        val state = model.state.value
        assertEquals(sampleAgenda, state.agenda)
        assertEquals("Use a valid date (YYYY-MM-DD).", state.message)
        assertTrue(state.isError)
        assertFalse(state.busy)
    }

    @Test
    fun `a write with no stored token is refused before touching the network`() = runTest {
        val api = FakeAgendaApi(AgendaLoaded(sampleAgenda))
        val model = AgendaViewModel(api, FakeStore(saved = null))

        model.completeTask(task)

        assertNull(api.lastWrite)
        assertTrue(model.state.value.isError)
    }
}
