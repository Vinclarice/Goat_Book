package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Daily screen's own state: read on open, same instinct as
 * SettingsViewModel -- the day this shows has to be the server's current
 * answer, not something remembered from last time.
 */
class DailyViewModelTest {

    private class FakeStore(private var saved: String? = "tok_abc") : TokenStore {
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null }
    }

    private class FakeDailyApi(private val result: DayResult) : DailyApi {
        var calls = 0
        override suspend fun getToday(token: String): DayResult {
            calls++
            return result
        }
    }

    private val sampleDay = DayEntry(
        date = "2026-08-10",
        today = "2026-08-10",
        intentions = "Ship it",
        gratitude = "",
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
        assertEquals(0, api.calls)
    }
}
