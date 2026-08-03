package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Settings: who am I connected as, and how do I stop being connected.
 *
 * Two of these describe the same situation the web has to handle -- a token
 * that has been revoked while the app still holds it -- which is the half of
 * B0.1 the phone can actually prove on its own.
 */
class SettingsViewModelTest {

    private class FakeStore : TokenStore {
        var saved: String? = null
        var clearedTimes = 0
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null; clearedTimes++ }
    }

    private class FakeApi(private val result: IdentifyResult) : ClariceApi {
        var calls = 0
        override suspend fun identify(token: String): IdentifyResult {
            calls++
            return result
        }

        override suspend fun login(username: String, password: String, label: String) =
            InvalidCredentials("unused")

        override suspend fun capture(token: String, text: String, idempotencyKey: String, tags: List<String>) =
            Disposition.DELIVERED
    }

    private val alice = Identity("alice", "alice@example.com")

    private class FakeStorage : QueueStorage {
        var items: List<PendingCapture> = emptyList()
        override fun load() = items
        override fun save(items: List<PendingCapture>) { this.items = items }
    }

    private class FakeScheduler : DeliveryScheduler {
        var asked = 0
        override fun schedule() { asked++ }
    }

    private fun queueOf(vararg items: PendingCapture): CaptureQueue {
        val storage = FakeStorage()
        storage.save(items.toList())
        return CaptureQueue(storage)
    }

    private class FakePreferences(
        private var sends: Boolean = true,
        private var unlock: Boolean = false,
    ) : CapturePreferences {
        override fun enterSends() = sends
        override fun setEnterSends(sends: Boolean) { this.sends = sends }
        override fun requireUnlock() = unlock
        override fun setRequireUnlock(require: Boolean) { unlock = require }
    }

    private fun viewModel(
        result: IdentifyResult,
        store: TokenStore = FakeStore().apply { save("tok_stored") },
        queue: CaptureQueue = queueOf(),
        scheduler: DeliveryScheduler = FakeScheduler(),
        preferences: CapturePreferences = FakePreferences(),
    ) = SettingsViewModel(Connector(FakeApi(result), store), queue, scheduler, preferences)

    @Test
    fun `it opens in a loading state rather than claiming to be disconnected`() {
        // The account name arrives over the network. Showing "not connected"
        // for the half second before it does would be a lie that provokes an
        // unnecessary reconnect.
        val state = viewModel(Identified(alice)).state.value

        assertTrue(state.loading)
        assertNull(state.identity)
        assertTrue(state.connected)
    }

    @Test
    fun `a working token names the account it belongs to`() = runTest {
        val model = viewModel(Identified(alice))

        model.load()

        assertEquals(alice, model.state.value.identity)
        assertFalse(model.state.value.loading)
        assertNull(model.state.value.message)
    }

    @Test
    fun `a revoked token says so and offers no account`() = runTest {
        // What B0.1's revocation step looks like from the phone: the token
        // is still on the device, the server no longer honours it.
        val model = viewModel(Unauthorised)

        model.load()

        assertNull(model.state.value.identity)
        assertTrue(model.state.value.isError)
        assertTrue(model.state.value.message!!.contains("did not accept"))
    }

    @Test
    fun `a revoked token is still not thrown away on its own`() = runTest {
        val store = FakeStore().apply { save("tok_revoked") }
        val model = viewModel(Unauthorised, store)

        model.load()

        assertEquals("tok_revoked", store.read())
        assertTrue(model.state.value.connected)
    }

    @Test
    fun `an unreachable server does not accuse the token`() = runTest {
        // Opening Settings on a train must not read as "your credentials are
        // broken". The token is almost certainly fine.
        val model = viewModel(Unreachable("Could not reach Clarice."))

        model.load()

        assertEquals("Could not reach Clarice.", model.state.value.message)
        assertTrue(model.state.value.connected)
        assertNull(model.state.value.identity)
    }

    @Test
    fun `with no stored token it reports being disconnected without asking`() = runTest {
        val store = FakeStore()
        val model = viewModel(Identified(alice), store)

        model.load()

        assertFalse(model.state.value.connected)
        assertFalse(model.state.value.loading)
    }

    @Test
    fun `loading ends however it went`() = runTest {
        listOf(Identified(alice), Unauthorised, Unreachable("x")).forEach { result ->
            val model = viewModel(result)

            model.load()

            assertFalse("after $result", model.state.value.loading)
        }
    }

    @Test
    fun `disconnecting forgets the token and says the account is gone`() = runTest {
        val store = FakeStore().apply { save("tok_stored") }
        val model = viewModel(Identified(alice), store)
        model.load()

        model.disconnect()

        assertNull(store.read())
        assertEquals(1, store.clearedTimes)
        assertFalse(model.state.value.connected)
        assertNull(model.state.value.identity)
    }

    @Test
    fun `it says how many captures are waiting to send`() = runTest {
        val model = viewModel(
            Identified(alice),
            queue = queueOf(
                PendingCapture("key-1", "one", 100),
                PendingCapture("key-2", "two", 200),
            ),
        )

        model.load()

        assertEquals(2, model.state.value.waiting)
        assertTrue(model.state.value.needsAttention.isEmpty())
    }

    @Test
    fun `a stalled capture is shown as needing attention, not as waiting`() = runTest {
        // Otherwise it is invisible. A stalled item stops counting as
        // pending, so without this the screen shows nothing at all and the
        // capture has, as far as its owner can tell, disappeared.
        val model = viewModel(
            Identified(alice),
            queue = queueOf(
                PendingCapture("key-1", "stuck", 100, attempts = 5, state = QueueState.STALLED),
            ),
        )

        model.load()

        assertEquals(0, model.state.value.waiting)
        assertEquals(listOf("stuck"), model.state.value.needsAttention.map { it.text })
    }

    @Test
    fun `a rejected capture is distinguishable from a stalled one`() = runTest {
        // They need different things from a person -- one an edit, the other
        // just another go -- so collapsing them into "problem" would be
        // telling somebody there is a problem without saying what to do.
        val model = viewModel(
            Identified(alice),
            queue = queueOf(
                PendingCapture("key-1", "stuck", 100, attempts = 5, state = QueueState.STALLED),
                PendingCapture("key-2", "refused", 200, state = QueueState.REJECTED),
            ),
        )

        model.load()

        assertEquals(
            listOf(QueueState.STALLED, QueueState.REJECTED),
            model.state.value.needsAttention.map { it.state },
        )
    }

    @Test
    fun `retrying a stalled capture puts it back among the waiting`() = runTest {
        val queue = queueOf(
            PendingCapture("key-1", "stuck", 100, attempts = 5, state = QueueState.STALLED),
        )
        val model = viewModel(Identified(alice), queue = queue)
        model.load()

        model.retry("key-1")

        assertEquals(1, model.state.value.waiting)
        assertTrue(model.state.value.needsAttention.isEmpty())
    }

    @Test
    fun `a retried capture keeps the key it was first queued with`() = runTest {
        // The whole reason a stalled item is kept rather than dropped. A
        // fresh key here would turn one thought into a second note the
        // moment it finally landed.
        val queue = queueOf(
            PendingCapture("key-1", "stuck", 100, attempts = 5, state = QueueState.STALLED),
        )
        val model = viewModel(Identified(alice), queue = queue)

        model.retry("key-1")

        assertEquals("key-1", queue.waiting().single().key)
    }

    @Test
    fun `retrying asks for a delivery rather than waiting for one`() = runTest {
        val scheduler = FakeScheduler()
        val queue = queueOf(
            PendingCapture("key-1", "stuck", 100, attempts = 5, state = QueueState.STALLED),
        )
        val model = viewModel(Identified(alice), queue = queue, scheduler = scheduler)

        model.retry("key-1")

        assertEquals(1, scheduler.asked)
    }

    @Test
    fun `the queue is shown even when the account cannot be reached`() = runTest {
        // Being offline is exactly when somebody checks what is still
        // unsent, so hiding the queue behind a successful identity lookup
        // would withhold it at the only moment it matters.
        val model = viewModel(
            Unreachable("Could not reach Clarice."),
            queue = queueOf(PendingCapture("key-1", "one", 100)),
        )

        model.load()

        assertEquals(1, model.state.value.waiting)
    }

    @Test
    fun `disconnecting does not empty the queue`() = runTest {
        // The reason the queue has its own Keystore alias. If it rode on the
        // token's key, every unsent thought would be destroyed at the exact
        // moment somebody disconnected -- silently, and unrecoverably.
        val queue = queueOf(PendingCapture("key-1", "unsent", 100))
        val model = viewModel(Identified(alice), queue = queue)
        model.load()

        model.disconnect()

        assertEquals(1, queue.waiting().size)
        assertEquals(1, model.state.value.waiting)
    }

    @Test
    fun `enter sends by default`() = runTest {
        // The common case wins the default: captures are short, and the
        // alternative costs a tap on every one of them.
        val model = viewModel(Identified(alice), preferences = FakePreferences())

        model.load()

        assertTrue(model.state.value.enterSends)
    }

    @Test
    fun `choosing a newline is remembered`() = runTest {
        // Remembered where it outlives the screen: the whole point of the
        // setting is that somebody should not have to make this choice twice.
        val preferences = FakePreferences()
        val model = viewModel(Identified(alice), preferences = preferences)
        model.load()

        model.setEnterSends(false)

        assertFalse(model.state.value.enterSends)
        assertFalse(preferences.enterSends())
    }

    @Test
    fun `a saved choice is what the screen opens with`() = runTest {
        val model = viewModel(Identified(alice), preferences = FakePreferences(sends = false))

        model.load()

        assertFalse(model.state.value.enterSends)
    }

    @Test
    fun `the choice survives being unable to reach Clarice`() = runTest {
        // It is a keyboard preference, not an account fact. Withholding it
        // because a network call failed would be absurd.
        val model = viewModel(
            Unreachable("Could not reach Clarice."),
            preferences = FakePreferences(sends = false),
        )

        model.load()

        assertFalse(model.state.value.enterSends)
    }

    @Test
    fun `unlock is not required by default`() = runTest {
        // The app's behaviour today, and what Vince wants for his own use --
        // this is opt-in hardening, not a new default everyone is pushed
        // into.
        val model = viewModel(Identified(alice), preferences = FakePreferences())

        model.load()

        assertFalse(model.state.value.requireUnlock)
    }

    @Test
    fun `turning on require-unlock is remembered`() = runTest {
        val preferences = FakePreferences()
        val model = viewModel(Identified(alice), preferences = preferences)
        model.load()

        model.setRequireUnlock(true)

        assertTrue(model.state.value.requireUnlock)
        assertTrue(preferences.requireUnlock())
    }

    @Test
    fun `a saved require-unlock choice is what the screen opens with`() = runTest {
        val model = viewModel(Identified(alice), preferences = FakePreferences(unlock = true))

        model.load()

        assertTrue(model.state.value.requireUnlock)
    }

    @Test
    fun `the require-unlock choice survives being unable to reach Clarice too`() = runTest {
        val model = viewModel(
            Unreachable("Could not reach Clarice."),
            preferences = FakePreferences(unlock = true),
        )

        model.load()

        assertTrue(model.state.value.requireUnlock)
    }

    @Test
    fun `nothing the screen can show has ever held the token`() = runTest {
        // "Never display it after saving" has to hold for the state object as
        // much as for the field it was typed into.
        val store = FakeStore().apply { save("tok_secret") }
        val model = viewModel(Identified(alice), store)

        model.load()

        assertFalse(model.state.value.toString().contains("tok_secret"))
    }
}
