package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The durable queue, which is the whole of M3's promise: a thought someone
 * typed survives a dead network, a closed app and a killed process.
 *
 * Storage is a seam so these run on the JVM. What backs it is encrypted and
 * Android-only, and gets its own instrumentation tests; what it *means* to
 * queue, retry and give up is decided here.
 */
class CaptureQueueTest {

    private class FakeStorage : QueueStorage {
        var items: List<PendingCapture> = emptyList()
        var saves = 0
        override fun load() = items
        override fun save(items: List<PendingCapture>) {
            this.items = items
            saves++
        }
    }

    private fun queue(storage: QueueStorage = FakeStorage(), ceiling: Int = 3) =
        CaptureQueue(storage, ceiling = ceiling)

    @Test
    fun `an added capture is waiting to send`() {
        val queue = queue()

        val added = queue.add("a thought", key = "key-1", createdAt = 100)

        assertEquals("a thought", added.text)
        assertEquals("key-1", added.key)
        assertEquals(QueueState.WAITING, added.state)
        assertEquals(0, added.attempts)
        assertEquals(listOf(added), queue.waiting())
    }

    @Test
    fun `what was added outlives the object that added it`() {
        // The point of the whole exercise. A process death between typing and
        // sending must not be the end of the thought.
        val storage = FakeStorage()
        queue(storage).add("survives", key = "key-1", createdAt = 100)

        val afterRestart = queue(storage)

        assertEquals("survives", afterRestart.waiting().single().text)
    }

    @Test
    fun `captures come back in the order they were typed`() {
        // The Inbox is read in created-at order, so the queue must not
        // reorder somebody's morning.
        val queue = queue()
        queue.add("second", key = "key-2", createdAt = 200)
        queue.add("first", key = "key-1", createdAt = 100)
        queue.add("third", key = "key-3", createdAt = 300)

        assertEquals(listOf("first", "second", "third"), queue.waiting().map { it.text })
    }

    @Test
    fun `a delivered capture leaves the queue`() {
        val queue = queue()
        queue.add("sent", key = "key-1", createdAt = 100)

        queue.delivered("key-1")

        assertTrue(queue.all().isEmpty())
    }

    @Test
    fun `a failed attempt is counted but costs nothing`() {
        val queue = queue()
        queue.add("still here", key = "key-1", createdAt = 100)

        queue.failed("key-1")

        val item = queue.waiting().single()
        assertEquals(1, item.attempts)
        assertEquals("still here", item.text)
        assertEquals("key-1", item.key)
        assertEquals(QueueState.WAITING, item.state)
    }

    @Test
    fun `retrying stops at the ceiling`() {
        // Without this an item failing for an unrecognised reason -- a base
        // URL answering 404, a proxy stuck at 502 -- retries until the
        // battery is gone, on a queue that will never drain.
        val queue = queue(ceiling = 3)
        queue.add("doomed", key = "key-1", createdAt = 100)

        repeat(3) { queue.failed("key-1") }

        assertTrue(queue.waiting().isEmpty())
        assertEquals(QueueState.STALLED, queue.all().single().state)
    }

    @Test
    fun `a stalled capture keeps its text and its key`() {
        // Reaching the ceiling is a display change, never data loss. The key
        // matters as much as the text: a later manual retry has to be the
        // same write, not a second one.
        val queue = queue(ceiling = 2)
        queue.add("give up on me", key = "key-1", createdAt = 100)

        repeat(5) { queue.failed("key-1") }

        val item = queue.all().single()
        assertEquals("give up on me", item.text)
        assertEquals("key-1", item.key)
        assertEquals(QueueState.STALLED, item.state)
    }

    @Test
    fun `a rejected capture stops at once without spending the ceiling`() {
        // A 400 is the server saying this text is not acceptable. Repeating
        // it changes nothing, and the fix is a person editing it.
        val queue = queue(ceiling = 3)
        queue.add("", key = "key-1", createdAt = 100)

        queue.rejected("key-1")

        val item = queue.all().single()
        assertEquals(QueueState.REJECTED, item.state)
        assertTrue(queue.waiting().isEmpty())
    }

    @Test
    fun `a manual retry reuses the original key rather than minting a new one`() {
        // Minting a fresh key here is exactly how a stalled capture becomes a
        // duplicated note the moment the network returns.
        val queue = queue(ceiling = 2)
        queue.add("try again", key = "key-1", createdAt = 100)
        repeat(2) { queue.failed("key-1") }

        queue.retry("key-1")

        val item = queue.waiting().single()
        assertEquals("key-1", item.key)
        assertEquals(QueueState.WAITING, item.state)
        assertEquals(0, item.attempts)
    }

    @Test
    fun `a rejected capture can be retried too, once its text is fixed`() {
        val queue = queue()
        queue.add("bad", key = "key-1", createdAt = 100)
        queue.rejected("key-1")

        queue.retry("key-1")

        assertEquals(QueueState.WAITING, queue.waiting().single().state)
    }

    @Test
    fun `bookkeeping for a capture that is already gone changes nothing`() {
        // Two deliveries of the same item can race -- a foreground submit and
        // a background drain -- and the loser must not resurrect it or throw.
        val queue = queue()
        queue.add("sent", key = "key-1", createdAt = 100)
        queue.delivered("key-1")

        queue.delivered("key-1")
        queue.failed("key-1")
        queue.retry("key-1")

        assertTrue(queue.all().isEmpty())
    }

    @Test
    fun `every change is written down, not just held in memory`() {
        // A queue that only persists on some paths is a queue that loses
        // things on exactly the paths nobody tested.
        val storage = FakeStorage()
        val queue = queue(storage)
        queue.add("a", key = "key-1", createdAt = 100)

        val afterAdd = storage.saves
        queue.failed("key-1")
        queue.retry("key-1")
        queue.delivered("key-1")

        assertTrue(afterAdd >= 1)
        assertEquals(afterAdd + 3, storage.saves)
    }

    @Test
    fun `a capture is found by its key`() {
        val queue = queue()
        queue.add("findable", key = "key-1", createdAt = 100)

        assertNotNull(queue.find("key-1"))
        assertNull(queue.find("key-absent"))
    }

    @Test
    fun `tags are optional and default to none`() {
        val queue = queue()

        val added = queue.add("no tags here", key = "key-1", createdAt = 100)

        assertEquals(emptyList<String>(), added.tags)
    }

    @Test
    fun `tags survive a process restart same as the text does`() {
        // Same reasoning as "what was added outlives the object that added
        // it" -- a queued-while-offline capture must not lose its tags
        // between being written down and finally being sent.
        val storage = FakeStorage()
        queue(storage).add(
            "design a boss fight", key = "key-1", createdAt = 100,
            tags = listOf("game-dev"),
        )

        val afterRestart = queue(storage)

        assertEquals(listOf("game-dev"), afterRestart.waiting().single().tags)
    }

    /**
     * Storage with a widened read-modify-write window.
     *
     * The race this reproduces is real but narrow, so the sleep makes it
     * findable rather than lucky. Nothing here is artificial otherwise: two
     * separate CaptureQueue objects over one store is exactly how the app
     * runs, since MainActivity and CaptureWorker each construct their own.
     */
    private class SlowStorage : QueueStorage {
        @Volatile
        private var items: List<PendingCapture> = emptyList()

        override fun load(): List<PendingCapture> {
            val snapshot = items
            Thread.sleep(1)
            return snapshot
        }

        override fun save(items: List<PendingCapture>) {
            this.items = items
        }
    }

    @Test
    fun `a foreground add and a background delivery cannot lose each other's work`() {
        // The one failure this app exists to prevent, and it had no guard.
        // add() and delivered() each load, mutate and save; interleaved, the
        // later save overwrites the earlier one -- so a thought typed while
        // the worker was finishing a delivery vanished, or a delivered
        // capture came back to be sent a second time.
        //
        // Note the two queue objects. A lock on the instance would pass a
        // test that shared one and still fail in the app, because the
        // activity and the worker never share an instance.
        repeat(50) { round ->
            val storage = SlowStorage()
            val foreground = CaptureQueue(storage)
            val background = CaptureQueue(storage)
            foreground.add("already queued", key = "old", createdAt = 1)

            val adding = Thread { foreground.add("a new thought", key = "new", createdAt = 2) }
            val delivering = Thread { background.delivered("old") }
            adding.start()
            delivering.start()
            adding.join()
            delivering.join()

            assertEquals(
                "round $round: the new capture survives and the delivered one stays gone",
                listOf("new"),
                foreground.all().map { it.key },
            )
        }
    }
}
