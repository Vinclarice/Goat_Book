package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The capture screen's decisions, without a screen.
 *
 * The rule everything here serves is unchanged since M2 -- a thought someone
 * typed is never lost -- but M3 changes how it is kept. The field used to be
 * the only place an unsent capture lived, so a failed send had to leave the
 * text on screen. Now the queue holds it durably before the network is
 * touched at all, which is what lets the field clear on every path except
 * the one where a person has to edit the text themselves.
 */
class CaptureViewModelTest {

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

    private class FakeApi(var disposition: Disposition) : ClariceApi {
        val keys = mutableListOf<String>()
        val texts = mutableListOf<String>()
        val tokens = mutableListOf<String>()
        /** What the queue held at the moment the request went out. */
        var queuedWhenCalled: List<PendingCapture>? = null
        var queue: CaptureQueue? = null

        override suspend fun identify(token: String) = Identified(Identity("a", "a@b.c"))

        override suspend fun capture(token: String, text: String, idempotencyKey: String):
            Disposition {
            queuedWhenCalled = queue?.all()
            tokens += token
            texts += text
            keys += idempotencyKey
            return disposition
        }
    }

    private class FakeScheduler : DeliveryScheduler {
        var asked = 0
        override fun schedule() { asked++ }
    }

    private class Fixture(
        val api: FakeApi,
        val queue: CaptureQueue,
        val model: CaptureViewModel,
        val scheduler: FakeScheduler,
    )

    private fun fixture(
        disposition: Disposition = Disposition.DELIVERED,
        store: TokenStore = FakeStore(),
        ceiling: Int = 5,
    ): Fixture {
        val api = FakeApi(disposition)
        val queue = CaptureQueue(FakeStorage(), ceiling = ceiling)
        api.queue = queue
        val scheduler = FakeScheduler()
        var clock = 1_000L
        return Fixture(
            api,
            queue,
            // Advancing, so two captures in one test are ordered rather than
            // tied -- the queue sorts by created-at.
            CaptureViewModel(api, store, queue, scheduler, now = { clock += 1; clock }),
            scheduler,
        )
    }

    @Test
    fun `typing updates the field`() {
        val f = fixture()

        f.model.onTextChange("buy milk")

        assertEquals("buy milk", f.model.state.value.text)
    }

    @Test
    fun `a capture is durable before the network is asked anything`() = runTest {
        // The heart of M3. If the process dies during the request, or the
        // radio never answers, the thought is already written down.
        val f = fixture(Disposition.DELIVERED)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(listOf("buy milk"), f.api.queuedWhenCalled!!.map { it.text })
    }

    @Test
    fun `a delivered capture clears the field, confirms, and leaves nothing queued`() = runTest {
        val f = fixture(Disposition.DELIVERED)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals("", f.model.state.value.text)
        assertNotNull(f.model.state.value.message)
        assertFalse(f.model.state.value.isError)
        assertTrue(f.queue.all().isEmpty())
    }

    @Test
    fun `the request carries the queued item's own key`() = runTest {
        // Not a freshly minted one. The key in the queue is what a retry will
        // use, and if the first attempt used a different one the retry would
        // write a second note rather than replaying the first.
        val f = fixture(Disposition.RETRY_LATER)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(f.queue.all().single().key, f.api.keys.single())
    }

    @Test
    fun `it sends the stored token`() = runTest {
        val f = fixture(store = FakeStore("tok_mine"))
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(listOf("tok_mine"), f.api.tokens)
    }

    @Test
    fun `every capture gets its own key`() = runTest {
        // Two thoughts are two captures. Reusing a key across them would
        // make the server treat the second as a replay of the first and
        // silently drop it.
        val f = fixture()

        f.model.onTextChange("first")
        f.model.submit()
        f.model.onTextChange("second")
        f.model.submit()

        assertEquals(2, f.api.keys.size)
        assertNotEquals(f.api.keys[0], f.api.keys[1])
    }

    @Test
    fun `a key is a uuid the server will accept`() = runTest {
        // The server rejects a malformed Idempotency-Key with 400, so an
        // invented format here would fail every capture.
        val f = fixture()
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertTrue(
            f.api.keys.single(),
            Regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
                .matches(f.api.keys.single()),
        )
    }

    @Test
    fun `an unsendable capture is kept, and the field is freed for the next one`() = runTest {
        // The M2 behaviour reversed, and only safe because of the queue: the
        // text is somewhere durable now, so holding the screen hostage to it
        // would stop someone capturing the next thought for no reason.
        val f = fixture(Disposition.RETRY_LATER)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals("", f.model.state.value.text)
        assertEquals(listOf("buy milk"), f.queue.waiting().map { it.text })
        assertFalse("being offline is not an error", f.model.state.value.isError)
        assertTrue(f.model.state.value.message!!.contains("online", ignoreCase = true))
    }

    @Test
    fun `a foreground failure spends one attempt`() = runTest {
        val f = fixture(Disposition.RETRY_LATER)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(1, f.queue.all().single().attempts)
    }

    @Test
    fun `a revoked token queues the capture without spending an attempt`() = runTest {
        // The ceiling exists to stop pointless repetition. A revoked token is
        // not pointless repetition -- it has a known cause and a known fix,
        // and burning attempts on it would strand the queue at the moment
        // reconnecting was supposed to drain it.
        val f = fixture(Disposition.NEEDS_RECONNECT)
        f.model.onTextChange("buy milk")

        f.model.submit()

        val item = f.queue.waiting().single()
        assertEquals(0, item.attempts)
        assertEquals("buy milk", item.text)
        assertTrue(f.model.state.value.message!!.contains("reconnect", ignoreCase = true))
    }

    @Test
    fun `a rejected capture comes back to the field so it can be fixed`() = runTest {
        // The one path that returns the text: only a person can make a 400
        // acceptable, and they cannot edit it from the queue.
        val f = fixture(Disposition.REJECTED)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals("buy milk", f.model.state.value.text)
        assertTrue(f.model.state.value.isError)
    }

    @Test
    fun `a rejected capture is still not discarded`() = runTest {
        // "Remove a queued item only after a successful, parsed server
        // response" has no exception for this. The copy in the field is not
        // durable; the queued one is.
        val f = fixture(Disposition.REJECTED)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(QueueState.REJECTED, f.queue.all().single().state)
    }

    @Test
    fun `an empty field queues nothing and sends nothing`() = runTest {
        val f = fixture()
        f.model.onTextChange("   ")

        f.model.submit()

        assertTrue(f.api.texts.isEmpty())
        assertTrue(f.queue.all().isEmpty())
    }

    @Test
    fun `with no token the capture is queued and the network is never asked`() = runTest {
        // Also an M2 reversal. Refusing to accept the capture used to be the
        // safest thing available; now it is the worst, because the queue can
        // hold it until a token exists.
        val f = fixture(store = FakeStore(token = null))
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertTrue(f.api.texts.isEmpty())
        assertEquals(listOf("buy milk"), f.queue.waiting().map { it.text })
        assertEquals("", f.model.state.value.text)
        assertTrue(f.model.state.value.message!!.contains("reconnect", ignoreCase = true))
    }

    @Test
    fun `the pending count is what is actually waiting`() = runTest {
        val f = fixture(Disposition.RETRY_LATER)

        f.model.onTextChange("first")
        f.model.submit()
        f.model.onTextChange("second")
        f.model.submit()

        assertEquals(2, f.model.state.value.pending)
    }

    @Test
    fun `a delivered capture leaves nothing pending`() = runTest {
        val f = fixture(Disposition.DELIVERED)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(0, f.model.state.value.pending)
    }

    @Test
    fun `an unsent capture asks for a background delivery`() = runTest {
        // Otherwise "will send when online" is a promise nothing in the app
        // is arranged to keep.
        val f = fixture(Disposition.RETRY_LATER)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(1, f.scheduler.asked)
    }

    @Test
    fun `a revoked token also asks, because reconnecting is what unblocks it`() = runTest {
        val f = fixture(Disposition.NEEDS_RECONNECT)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(1, f.scheduler.asked)
    }

    @Test
    fun `a delivered capture asks for nothing`() = runTest {
        // A wake-up scheduled over an empty queue is pure battery.
        val f = fixture(Disposition.DELIVERED)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(0, f.scheduler.asked)
    }

    @Test
    fun `a rejected capture asks for nothing either`() = runTest {
        // No amount of retrying makes a 400 acceptable; only editing does.
        val f = fixture(Disposition.REJECTED)
        f.model.onTextChange("buy milk")

        f.model.submit()

        assertEquals(0, f.scheduler.asked)
    }

    @Test
    fun `opening with something already queued asks for a delivery`() = runTest {
        // Covers the gap where the process died between queueing a capture
        // and scheduling its delivery -- the queue would otherwise sit there
        // with nothing arranged to drain it.
        val f = fixture(Disposition.RETRY_LATER)
        f.queue.add("from a previous life", "key-old", 1)

        f.model.refresh()

        assertEquals(1, f.scheduler.asked)
        assertEquals(1, f.model.state.value.pending)
    }

    @Test
    fun `opening with an empty queue asks for nothing`() = runTest {
        val f = fixture()

        f.model.refresh()

        assertEquals(0, f.scheduler.asked)
    }

    @Test
    fun `sending is false again however it ended`() = runTest {
        Disposition.entries.forEach { outcome ->
            val f = fixture(outcome)
            f.model.onTextChange("buy milk")

            f.model.submit()

            assertFalse("after $outcome", f.model.state.value.sending)
        }
    }

    @Test
    fun `typing again clears the previous confirmation`() = runTest {
        // A "Captured." still on screen while a new thought is being typed
        // reads as though this one has already been sent.
        val f = fixture()
        f.model.onTextChange("first")
        f.model.submit()
        assertNotNull(f.model.state.value.message)

        f.model.onTextChange("second")

        assertNull(f.model.state.value.message)
    }
}
