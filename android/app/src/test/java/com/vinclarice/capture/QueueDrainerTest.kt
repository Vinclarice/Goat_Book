package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Emptying the queue, which is the half of M3 that happens while nobody is
 * looking.
 *
 * The decisions worth arguing about are all about *stopping*: a drain that
 * keeps going after the network has clearly gone spends an attempt from
 * every item's budget on the same failure, and can stall an entire queue in
 * one pass over a five-minute outage.
 */
class QueueDrainerTest {

    private class FakeStore(token: String? = "tok_stored") : TokenStore {
        var saved: String? = token
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null }
    }

    private class FakeStorage : QueueStorage {
        var items: List<PendingCapture> = emptyList()
        override fun load() = items
        override fun save(items: List<PendingCapture>) { this.items = items }
    }

    /** Answers per key, so one drain can meet several outcomes. */
    private class FakeApi(
        private val byKey: Map<String, Disposition> = emptyMap(),
        private val fallback: Disposition = Disposition.DELIVERED,
    ) : ClariceApi {
        val keys = mutableListOf<String>()
        val texts = mutableListOf<String>()

        override suspend fun identify(token: String) = Identified(Identity("a", "a@b.c"))

        override suspend fun capture(
            token: String,
            text: String,
            idempotencyKey: String,
            tags: List<String>,
        ): Disposition {
            keys += idempotencyKey
            texts += text
            return byKey[idempotencyKey] ?: fallback
        }
    }

    private fun queueOf(vararg items: PendingCapture, ceiling: Int = 5): CaptureQueue {
        val storage = FakeStorage()
        storage.save(items.toList())
        return CaptureQueue(storage, ceiling = ceiling)
    }

    private fun waiting(key: String, text: String, at: Long, attempts: Int = 0) =
        PendingCapture(key = key, text = text, createdAt = at, attempts = attempts)

    @Test
    fun `an empty queue is already finished`() = runTest {
        val api = FakeApi()

        val report = QueueDrainer(api, FakeStore(), queueOf()).drain()

        assertTrue(report.finished)
        assertEquals(0, report.delivered)
        assertTrue(api.keys.isEmpty())
    }

    @Test
    fun `everything waiting is sent, oldest first`() = runTest {
        // The Inbox is read in created-at order. Draining newest-first would
        // scramble somebody's morning into the wrong sequence.
        val api = FakeApi()
        val queue = queueOf(
            waiting("key-2", "second", at = 200),
            waiting("key-1", "first", at = 100),
        )

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertEquals(listOf("first", "second"), api.texts)
        assertEquals(2, report.delivered)
        assertTrue(queue.all().isEmpty())
    }

    @Test
    fun `each request carries the key the item was queued with`() = runTest {
        val api = FakeApi()
        val queue = queueOf(waiting("key-1", "a", at = 100))

        QueueDrainer(api, FakeStore(), queue).drain()

        assertEquals(listOf("key-1"), api.keys)
    }

    @Test
    fun `a lost network ends the run rather than charging every item for it`() = runTest {
        // The decision this class exists to get right. Carrying on would
        // spend an attempt from all three budgets on one outage, and could
        // stall an entire queue in a single pass.
        val api = FakeApi(fallback = Disposition.RETRY_LATER)
        val queue = queueOf(
            waiting("key-1", "first", at = 100),
            waiting("key-2", "second", at = 200),
            waiting("key-3", "third", at = 300),
        )

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertEquals(listOf("first"), api.texts)
        assertFalse(report.finished)
        assertEquals(listOf(1, 0, 0), queue.all().map { it.attempts })
    }

    @Test
    fun `a revoked token ends the run and costs nobody an attempt`() = runTest {
        val api = FakeApi(fallback = Disposition.NEEDS_RECONNECT)
        val queue = queueOf(
            waiting("key-1", "first", at = 100),
            waiting("key-2", "second", at = 200),
        )

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertEquals(listOf("first"), api.texts)
        assertFalse(report.finished)
        assertEquals(listOf(0, 0), queue.all().map { it.attempts })
    }

    @Test
    fun `a rejected capture does not stop the ones behind it`() = runTest {
        // Unlike a dead network, a 400 says something about that text and
        // nothing about the queue. Stopping here would let one bad capture
        // block every good one behind it indefinitely.
        val api = FakeApi(byKey = mapOf("key-1" to Disposition.REJECTED))
        val queue = queueOf(
            waiting("key-1", "refused", at = 100),
            waiting("key-2", "fine", at = 200),
        )

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertEquals(listOf("refused", "fine"), api.texts)
        assertEquals(1, report.delivered)
        assertEquals(QueueState.REJECTED, queue.all().single().state)
    }

    @Test
    fun `a rejected capture leaves nothing waiting, so the run is finished`() = runTest {
        // It needs a person, not another attempt. Reporting unfinished here
        // would have the system wake up forever over something no retry can
        // fix.
        val api = FakeApi(fallback = Disposition.REJECTED)
        val queue = queueOf(waiting("key-1", "refused", at = 100))

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertTrue(report.finished)
    }

    @Test
    fun `stalled and rejected captures are never attempted`() = runTest {
        val api = FakeApi()
        val queue = queueOf(
            PendingCapture("key-1", "stalled", 100, attempts = 5, state = QueueState.STALLED),
            PendingCapture("key-2", "rejected", 200, state = QueueState.REJECTED),
        )

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertTrue(api.keys.isEmpty())
        assertTrue("nothing is waiting, so nothing is owed", report.finished)
        assertEquals(2, queue.all().size)
    }

    @Test
    fun `an item that hits the ceiling mid-drain stops being waiting`() = runTest {
        val api = FakeApi(fallback = Disposition.RETRY_LATER)
        val queue = queueOf(waiting("key-1", "doomed", at = 100, attempts = 2), ceiling = 3)

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertEquals(QueueState.STALLED, queue.all().single().state)
        assertTrue("a stalled item is not owed another wake-up", report.finished)
    }

    @Test
    fun `with no token nothing is attempted and the work is still owed`() = runTest {
        val api = FakeApi()
        val queue = queueOf(waiting("key-1", "a", at = 100))

        val report = QueueDrainer(api, FakeStore(token = null), queue).drain()

        assertTrue(api.keys.isEmpty())
        assertFalse(report.finished)
        assertEquals(0, queue.all().single().attempts)
    }

    @Test
    fun `the report says what was delivered and what is left`() = runTest {
        val api = FakeApi(byKey = mapOf("key-2" to Disposition.RETRY_LATER))
        val queue = queueOf(
            waiting("key-1", "first", at = 100),
            waiting("key-2", "second", at = 200),
            waiting("key-3", "third", at = 300),
        )

        val report = QueueDrainer(api, FakeStore(), queue).drain()

        assertEquals(1, report.delivered)
        assertEquals(2, report.waiting)
    }
}
