package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Connecting an account: validate a pasted token, and only keep it if it
 * actually works.
 *
 * Deliberately free of Android types so it runs as a plain JVM test. What
 * backs the token store is an implementation detail behind [TokenStore] --
 * these say what connecting *means*, and stay true whichever way the
 * secret is eventually encrypted.
 */
class ConnectorTest {

    private class FakeStore : TokenStore {
        var saved: String? = null
        var clearedTimes = 0
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null; clearedTimes++ }
    }

    private class FakeApi(private val result: IdentifyResult) : ClariceApi {
        var calls = 0
        var lastToken: String? = null
        override suspend fun identify(token: String): IdentifyResult {
            calls++
            lastToken = token
            return result
        }

        // Connecting never sends a capture; CaptureApiTest covers this.
        override suspend fun capture(token: String, text: String, idempotencyKey: String) =
            Disposition.DELIVERED
    }

    private val alice = Identity("alice", "alice@example.com")

    @Test
    fun `a working token is saved and the account named`() = runTest {
        val store = FakeStore()
        val outcome = Connector(FakeApi(Identified(alice)), store).connect("tok_good")

        assertEquals(Connected(alice), outcome)
        assertEquals("tok_good", store.read())
    }

    @Test
    fun `a rejected token is never written to storage`() = runTest {
        // The point of validating before saving. Persisting a token the
        // server just refused would leave the app in a state where every
        // capture fails and nothing says why.
        val store = FakeStore()
        val outcome = Connector(FakeApi(Unauthorised), store).connect("tok_bad")

        assertTrue(outcome is Refused)
        assertNull(store.read())
    }

    @Test
    fun `an unreachable server does not save and does not blame the token`() = runTest {
        val store = FakeStore()
        val outcome = Connector(FakeApi(Unreachable("offline")), store).connect("tok_good")

        assertTrue(outcome is Failed)
        assertNull(store.read())
    }

    @Test
    fun `whitespace around a pasted token is ignored`() = runTest {
        // Pasting from a browser or a password manager routinely brings a
        // trailing newline, and a token that fails for an invisible reason
        // is the worst kind of failure.
        val api = FakeApi(Identified(alice))
        val store = FakeStore()

        Connector(api, store).connect("  tok_good\n")

        assertEquals("tok_good", api.lastToken)
        assertEquals("tok_good", store.read())
    }

    @Test
    fun `an empty entry is refused without troubling the server`() = runTest {
        val api = FakeApi(Identified(alice))
        val outcome = Connector(api, FakeStore()).connect("   ")

        assertEquals(Blank, outcome)
        assertEquals(0, api.calls)
    }

    @Test
    fun `connecting again replaces the stored token`() = runTest {
        val store = FakeStore().apply { save("tok_old") }

        Connector(FakeApi(Identified(alice)), store).connect("tok_new")

        assertEquals("tok_new", store.read())
    }

    @Test
    fun `a failed reconnection leaves the existing token alone`() = runTest {
        // Someone re-pasting a token while offline must not lose the working
        // one they already had.
        val store = FakeStore().apply { save("tok_working") }

        Connector(FakeApi(Unreachable("offline")), store).connect("tok_new")

        assertEquals("tok_working", store.read())
    }

    @Test
    fun `disconnecting forgets the token`() = runTest {
        val store = FakeStore().apply { save("tok_good") }

        Connector(FakeApi(Identified(alice)), store).disconnect()

        assertNull(store.read())
        assertEquals(1, store.clearedTimes)
    }

    @Test
    fun `the outcome never carries the token back out`() = runTest {
        // Nothing downstream -- a log line, a crash report, a screen -- can
        // leak what it was never handed.
        val outcomes = listOf(
            Connector(FakeApi(Identified(alice)), FakeStore()).connect("tok_secret"),
            Connector(FakeApi(Unauthorised), FakeStore()).connect("tok_secret"),
            Connector(FakeApi(Unreachable("x")), FakeStore()).connect("tok_secret"),
        )

        outcomes.forEach { outcome ->
            assertFalse(outcome.toString().contains("tok_secret"))
        }
    }

    @Test
    fun `a stored token is reported as already connected`() = runTest {
        val store = FakeStore().apply { save("tok_good") }

        assertTrue(Connector(FakeApi(Identified(alice)), store).isConnected())
        assertFalse(Connector(FakeApi(Identified(alice)), FakeStore()).isConnected())
    }
}
