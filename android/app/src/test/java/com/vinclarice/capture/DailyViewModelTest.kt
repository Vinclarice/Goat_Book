package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Daily screen's own state: read on open like SettingsViewModel, and
 * now acted on -- focus pin/unpin, the day's own text, and every routine
 * action DayRoute.tsx itself offers. Writes reload the whole day on
 * success (a routine write answers a different shape than a focus/text
 * write does, so there's no single merge path) and never touch the
 * visible day on failure -- see write()'s own reasoning.
 */
class DailyViewModelTest {

    private class FakeStore(private var saved: String? = "tok_abc") : TokenStore {
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null }
    }

    private class FakeDailyApi(
        private var readResult: DayResult,
        private var writeResult: DayWriteResult = DayWriteSucceeded,
    ) : DailyApi {
        var readCalls = 0
        var lastWrite: Pair<String, List<Any?>>? = null

        fun respondToNextReadWith(result: DayResult) { readResult = result }

        override suspend fun getToday(token: String): DayResult {
            readCalls++
            return readResult
        }

        override suspend fun pinFocus(token: String, day: String, taskId: Int): DayWriteResult {
            lastWrite = "pin" to listOf(day, taskId)
            return writeResult
        }

        override suspend fun unpinFocus(token: String, day: String, taskId: Int): DayWriteResult {
            lastWrite = "unpin" to listOf(day, taskId)
            return writeResult
        }

        override suspend fun writeDayText(
            token: String, day: String, intentions: String, gratitude: String, happenings: String,
        ): DayWriteResult {
            lastWrite = "writeText" to listOf(day, intentions, gratitude, happenings)
            return writeResult
        }

        override suspend fun createRoutine(
            token: String, title: String, cadence: String, targetQuantity: Int, unit: String,
        ): DayWriteResult {
            lastWrite = "createRoutine" to listOf(title, cadence, targetQuantity, unit)
            return writeResult
        }

        override suspend fun logRoutine(token: String, routineId: Int, amount: Int): DayWriteResult {
            lastWrite = "log" to listOf(routineId, amount)
            return writeResult
        }

        override suspend fun skipRoutine(token: String, routineId: Int): DayWriteResult {
            lastWrite = "skip" to listOf(routineId)
            return writeResult
        }

        override suspend fun callRoutineEnough(token: String, routineId: Int): DayWriteResult {
            lastWrite = "enough" to listOf(routineId)
            return writeResult
        }

        override suspend fun pauseRoutine(token: String, routineId: Int): DayWriteResult {
            lastWrite = "pause" to listOf(routineId)
            return writeResult
        }

        override suspend fun resumeRoutine(token: String, routineId: Int): DayWriteResult {
            lastWrite = "resume" to listOf(routineId)
            return writeResult
        }
    }

    private val sampleDay = DayEntry(
        date = "2026-08-10",
        today = "2026-08-10",
        intentions = "Ship it",
        gratitude = "Coffee",
        happenings = "",
        compassPurpose = "",
        compassQuestion = "",
        focus = emptyList(),
        actionItems = emptyList(),
        areas = emptyList(),
        projects = emptyList(),
        showsActionItems = true,
        routines = emptyList(),
        routinesAreLoggable = true,
        pausedRoutines = emptyList(),
    )

    @Test
    fun `a loaded day is shown, not still loading`() = runTest {
        val model = DailyViewModel(FakeDailyApi(DayLoaded(sampleDay)), FakeStore())

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertEquals(sampleDay, state.day)
        assertNull(state.message)
    }

    @Test
    fun `an unauthorised token asks to reconnect, without discarding the message as an ordinary error tone`() = runTest {
        val model = DailyViewModel(FakeDailyApi(DayUnauthorised), FakeStore())

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertNull(state.day)
        assertTrue(state.isError)
        assertTrue(state.message!!.contains("Reconnect"))
    }

    @Test
    fun `an unreachable server reports its own reason`() = runTest {
        val model = DailyViewModel(FakeDailyApi(DayUnreachable("Could not reach Clarice.")), FakeStore())

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertEquals("Could not reach Clarice.", state.message)
        assertTrue(state.isError)
    }

    @Test
    fun `no stored token is a quiet state, not an error`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore(saved = null))

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertFalse(state.isError)
        assertNull(state.day)
        // Never asked the network with no token to send.
        assertEquals(0, api.readCalls)
    }

    @Test
    fun `loading seeds the draft text from the day`() = runTest {
        val model = DailyViewModel(FakeDailyApi(DayLoaded(sampleDay)), FakeStore())

        model.load()

        val state = model.state.value
        assertEquals("Ship it", state.draftIntentions)
        assertEquals("Coffee", state.draftGratitude)
        assertEquals("", state.draftHappenings)
    }

    @Test
    fun `a reload for the same date does not stomp on an in-progress edit`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())
        model.load()

        model.setDraftIntentions("Still typing...")
        model.load()

        assertEquals("Still typing...", model.state.value.draftIntentions)
    }

    @Test
    fun `a reload for a new date does reseed the draft`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())
        model.load()
        model.setDraftIntentions("Still typing...")

        api.respondToNextReadWith(DayLoaded(sampleDay.copy(date = "2026-08-11", intentions = "Fresh day")))
        model.load()

        assertEquals("Fresh day", model.state.value.draftIntentions)
    }

    @Test
    fun `saving the days text sends the current draft and reloads`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())
        model.load()
        model.setDraftIntentions("Updated")
        model.setDraftGratitude("Sunshine")

        model.saveDayText()

        assertEquals("writeText" to listOf("2026-08-10", "Updated", "Sunshine", ""), api.lastWrite)
        assertEquals(2, api.readCalls) // initial load + reload after success
        assertFalse(model.state.value.busy)
    }

    @Test
    fun `pinning a task sends the days own date and the task id`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())
        model.load()

        model.pinTask(42)

        assertEquals("pin" to listOf("2026-08-10", 42), api.lastWrite)
    }

    @Test
    fun `unpinning a task sends the days own date and the task id`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())
        model.load()

        model.unpinTask(42)

        assertEquals("unpin" to listOf("2026-08-10", 42), api.lastWrite)
    }

    @Test
    fun `logging a routine sends its id and amount`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())

        model.logRoutine(routineId = 3, amount = -1)

        assertEquals("log" to listOf(3, -1), api.lastWrite)
    }

    @Test
    fun `skip, enough, pause and resume each hit their own action`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())

        model.skipRoutine(3)
        assertEquals("skip" to listOf(3), api.lastWrite)

        model.callRoutineEnough(3)
        assertEquals("enough" to listOf(3), api.lastWrite)

        model.pauseRoutine(3)
        assertEquals("pause" to listOf(3), api.lastWrite)

        model.resumeRoutine(3)
        assertEquals("resume" to listOf(3), api.lastWrite)
    }

    @Test
    fun `keeping a new routine sends its fields`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())

        model.createRoutine("Practice Spanish", "daily", 5, "lessons")

        assertEquals(
            "createRoutine" to listOf("Practice Spanish", "daily", 5, "lessons"),
            api.lastWrite,
        )
    }

    @Test
    fun `keeping a routine with a blank title never reaches the network`() = runTest {
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, FakeStore())

        model.createRoutine("   ", "daily", 1, "")

        assertNull(api.lastWrite)
    }

    @Test
    fun `a failed write reports the message but keeps the day on screen`() = runTest {
        val api = FakeDailyApi(
            readResult = DayLoaded(sampleDay),
            writeResult = DayWriteRejected("That routine is paused."),
        )
        val model = DailyViewModel(api, FakeStore())
        model.load()

        model.logRoutine(3, 1)

        val state = model.state.value
        assertEquals(sampleDay, state.day)
        assertEquals("That routine is paused.", state.message)
        assertTrue(state.isError)
        assertFalse(state.busy)
    }

    @Test
    fun `a write with no stored token is refused before touching the network`() = runTest {
        // A day already on screen, but the token vanished since (disconnected
        // from Settings in the meantime) -- the realistic case this guards,
        // since a screen with nothing loaded has no pin button to tap.
        val store = FakeStore()
        val api = FakeDailyApi(DayLoaded(sampleDay))
        val model = DailyViewModel(api, store)
        model.load()
        store.clear()

        model.pinTask(42)

        assertNull(api.lastWrite)
        assertTrue(model.state.value.isError)
    }
}
