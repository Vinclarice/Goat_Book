package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The pool screen's state — android-overhaul-plan.md increment 3.
 *
 * Same rules `DailyViewModelTest` holds, because they are the ones that keep a
 * flaky network from looking like lost work: a failed write never blanks an
 * already-visible list, and every successful one reloads rather than patching
 * state by hand.
 *
 * **Picking goes through `DailyApi.pinFocus`**, not a pool verb of its own.
 * Choosing something for today is the day's act wherever it is performed, the
 * endpoint was already reachable by a bearer, and a second way to pin would be
 * a second definition of what picking means.
 */
class PoolViewModelTest {

    private val samplePool = PoolEntry(
        today = "2026-09-06",
        openCount = 3,
        fixed = emptyList(),
        floating = listOf(
            PoolFloatingRow(
                task = TaskEntry(7, "Write the plan doc", null, emptyList(), null, null),
                ageInDays = 36,
                pickedFor = emptyList(),
                unpickedForDays = 22,
                asksToBeKept = true,
            ),
        ),
    )

    private class FakePoolApi(
        private var result: PoolResult,
    ) : PoolApi {
        var calls = 0
        var lastHead: Boolean? = null

        fun respondWith(next: PoolResult) { result = next }

        override suspend fun getPool(token: String, head: Boolean): PoolResult {
            calls += 1
            lastHead = head
            return result
        }
    }

    private class FakePinApi(
        private val writeResult: DayWriteResult = DayWriteSucceeded,
    ) : DailyApi by UnusedDailyApi() {
        var lastPin: Pair<String, Int>? = null

        override suspend fun pinFocus(token: String, day: String, taskId: Int): DayWriteResult {
            lastPin = day to taskId
            return writeResult
        }
    }

    /** Everything the pool never calls. Delegation rather than a dozen stubs,
     *  so a new `DailyApi` verb does not silently grow a fake here. */
    private class UnusedDailyApi : DailyApi {
        private fun no(): Nothing = throw UnsupportedOperationException("the pool does not call this")
        override suspend fun getToday(token: String) = no()
        override suspend fun pinFocus(token: String, day: String, taskId: Int) = no()
        override suspend fun unpinFocus(token: String, day: String, taskId: Int) = no()
        override suspend fun decideAboutLeftover(
            token: String, day: String, taskId: Int, decision: String,
        ) = no()
        override suspend fun createRoutine(
            token: String, title: String, cadence: String, targetQuantity: Int, unit: String,
        ) = no()
        override suspend fun logRoutine(token: String, routineId: Int, amount: Int) = no()
        override suspend fun skipRoutine(token: String, routineId: Int) = no()
        override suspend fun pauseRoutine(token: String, routineId: Int) = no()
        override suspend fun resumeRoutine(token: String, routineId: Int) = no()
        override suspend fun callRoutineEnough(token: String, routineId: Int) = no()
    }

    private class FakeStore(private val token: String? = "tok_abc") : TokenStore {
        override fun read() = token
        override fun save(token: String) = Unit
        override fun clear() = Unit
    }

    @Test
    fun `a loaded pool is shown, not still loading`() = runTest {
        val model = PoolViewModel(FakePoolApi(PoolLoaded(samplePool)), FakeStore(), FakePinApi())

        model.load()

        val state = model.state.value
        assertFalse(state.loading)
        assertEquals(samplePool, state.pool)
        assertNull(state.message)
    }

    @Test
    fun `with no token there is nothing to ask for`() = runTest {
        val api = FakePoolApi(PoolLoaded(samplePool))
        val model = PoolViewModel(api, FakeStore(token = null), FakePinApi())

        model.load()

        assertEquals(0, api.calls)
        assertNull(model.state.value.pool)
    }

    @Test
    fun `a refused token says where to fix it rather than what broke`() = runTest {
        val model = PoolViewModel(FakePoolApi(PoolUnauthorised), FakeStore(), FakePinApi())

        model.load()

        assertTrue(model.state.value.isError)
        assertEquals("Reconnect in Settings to see the pool.", model.state.value.message)
    }

    @Test
    fun `picking pins the task against the pool's own today`() = runTest {
        // The pool's `today`, which the server supplied, never the device's
        // clock -- the same rule `deferTaskToTomorrow` follows on the day
        // screen, and it matters more here because a phone can be in any zone.
        val pin = FakePinApi()
        val model = PoolViewModel(FakePoolApi(PoolLoaded(samplePool)), FakeStore(), pin)
        model.load()

        model.pick(7)

        assertEquals("2026-09-06" to 7, pin.lastPin)
    }

    @Test
    fun `picking reloads so the row can say it is chosen`() = runTest {
        // `picked_for` is what stops a Pick control looking like it did
        // nothing, and only the server knows it -- so a successful pick asks
        // again rather than patching the row here.
        val api = FakePoolApi(PoolLoaded(samplePool))
        val model = PoolViewModel(api, FakeStore(), FakePinApi())
        model.load()

        model.pick(7)

        assertEquals(2, api.calls)
    }

    @Test
    fun `a failed pick leaves the list on screen`() = runTest {
        // DailyViewModel's rule, inherited on purpose: a write that fails must
        // never blank a page somebody is reading.
        val api = FakePoolApi(PoolLoaded(samplePool))
        val model = PoolViewModel(api, FakeStore(), FakePinApi(DayWriteUnauthorised))
        model.load()

        model.pick(7)

        assertEquals(samplePool, model.state.value.pool)
        assertTrue(model.state.value.isError)
        assertFalse(model.state.value.busy)
    }

    @Test
    fun `nothing is asked of the server without a task`() = runTest {
        val api = FakePoolApi(PoolLoaded(samplePool))
        val model = PoolViewModel(api, FakeStore(token = null), FakePinApi())

        model.pick(7)

        assertEquals(0, api.calls)
    }
}
