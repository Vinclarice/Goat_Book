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

    private class FakeApi(
        private val result: IdentifyResult,
        private val loginResult: LoginResult = InvalidCredentials("unused"),
    ) : ClariceApi {
        var calls = 0
        var lastToken: String? = null
        var loginCalls = 0
        var lastUsername: String? = null
        var lastPassword: String? = null
        var lastLabel: String? = null

        override suspend fun identify(token: String): IdentifyResult {
            calls++
            lastToken = token
            return result
        }

        override suspend fun login(username: String, password: String, label: String): LoginResult {
            loginCalls++
            lastUsername = username
            lastPassword = password
            lastLabel = label
            return loginResult
        }

        // Connecting never sends a capture; CaptureApiTest covers this.
        override suspend fun capture(
            token: String,
            text: String,
            idempotencyKey: String,
            tags: List<String>,
            capturedAt: Long?,
        ) =
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
    fun `a successful login saves the returned token, not anything typed`() = runTest {
        val store = FakeStore()
        val outcome = Connector(FakeApi(Unauthorised, LoggedIn("tok_fresh", alice)), store)
            .logIn("alice", "correct horse")

        assertEquals(Connected(alice), outcome)
        assertEquals("tok_fresh", store.read())
    }

    @Test
    fun `invalid credentials are never saved, and the server's own message is kept`() = runTest {
        val store = FakeStore()
        val outcome = Connector(
            FakeApi(Unauthorised, InvalidCredentials("3 attempts remaining before a temporary lock.")),
            store,
        ).logIn("alice", "wrong")

        assertEquals(Refused("3 attempts remaining before a temporary lock."), outcome)
        assertNull(store.read())
    }

    @Test
    fun `an unreachable server during login does not save and does not blame the password`() = runTest {
        val store = FakeStore()
        val outcome = Connector(FakeApi(Unauthorised, LoginUnreachable("offline")), store)
            .logIn("alice", "correct horse")

        assertTrue(outcome is Failed)
        assertNull(store.read())
    }

    @Test
    fun `the device label travels with the login request`() = runTest {
        val api = FakeApi(Unauthorised, LoggedIn("tok", alice))

        Connector(api, FakeStore()).logIn("alice", "correct horse", label = "Android (SM-S928U1)")

        assertEquals("Android (SM-S928U1)", api.lastLabel)
    }

    @Test
    fun `the label defaults to something reasonable when the caller doesn't say`() = runTest {
        val api = FakeApi(Unauthorised, LoggedIn("tok", alice))

        Connector(api, FakeStore()).logIn("alice", "correct horse")

        assertEquals("Android", api.lastLabel)
    }

    @Test
    fun `an empty username or password is refused without troubling the server`() = runTest {
        val api = FakeApi(Unauthorised, LoggedIn("tok", alice))

        val outcome = Connector(api, FakeStore()).logIn("", "correct horse")

        assertEquals(Blank, outcome)
        assertEquals(0, api.loginCalls)
    }

    @Test
    fun `logging in again replaces the stored token`() = runTest {
        val store = FakeStore().apply { save("tok_old") }

        Connector(FakeApi(Unauthorised, LoggedIn("tok_new", alice)), store)
            .logIn("alice", "correct horse")

        assertEquals("tok_new", store.read())
    }

    @Test
    fun `neither the password nor the returned token appear in the outcome`() = runTest {
        val outcomes = listOf(
            Connector(FakeApi(Unauthorised, LoggedIn("tok_secret", alice)), FakeStore())
                .logIn("alice", "password_secret"),
            Connector(FakeApi(Unauthorised, InvalidCredentials("unused")), FakeStore())
                .logIn("alice", "password_secret"),
        )

        outcomes.forEach { outcome ->
            assertFalse(outcome.toString().contains("tok_secret"))
            assertFalse(outcome.toString().contains("password_secret"))
        }
    }

    @Test
    fun `a stored token is reported as already connected`() = runTest {
        val store = FakeStore().apply { save("tok_good") }

        assertTrue(Connector(FakeApi(Identified(alice)), store).isConnected())
        assertFalse(Connector(FakeApi(Identified(alice)), FakeStore()).isConnected())
    }

    @Test
    fun `who the stored token belongs to is asked, not remembered`() = runTest {
        // Settings shows the account name, and the only honest source for it
        // is the server. Caching it locally would keep displaying an account
        // for a token that was revoked an hour ago.
        val api = FakeApi(Identified(alice))
        val store = FakeStore().apply { save("tok_good") }

        val outcome = Connector(api, store).whoAmI()

        assertEquals(Connected(alice), outcome)
        assertEquals("tok_good", api.lastToken)
    }

    @Test
    fun `with no stored token nobody is asked anything`() = runTest {
        val api = FakeApi(Identified(alice))

        val outcome = Connector(api, FakeStore()).whoAmI()

        assertEquals(Blank, outcome)
        assertEquals(0, api.calls)
    }

    @Test
    fun `a revoked token is reported without being thrown away`() = runTest {
        // Deliberate. Forgetting it here would drop somebody straight back to
        // the Connect screen the moment they opened Settings on a flaky
        // connection -- and worse, it would do so silently. Disconnecting is
        // an action someone takes, not something that happens to them.
        val store = FakeStore().apply { save("tok_revoked") }

        val outcome = Connector(FakeApi(Unauthorised), store).whoAmI()

        assertTrue(outcome is Refused)
        assertEquals("tok_revoked", store.read())
        assertEquals(0, store.clearedTimes)
    }

    @Test
    fun `an unreachable server leaves the stored token alone`() = runTest {
        val store = FakeStore().apply { save("tok_good") }

        val outcome = Connector(FakeApi(Unreachable("offline")), store).whoAmI()

        assertEquals(Failed("offline"), outcome)
        assertEquals("tok_good", store.read())
    }

    @Test
    fun `a refused token names the server that refused it`() = runTest {
        // On a split install this Connector is the *capture* one, so a
        // hard-coded "Clarice" here sends somebody to re-mint a token on the
        // server that never saw the request. Same defect as the one fixed in
        // OkHttpClariceApi, one layer up.
        val outcome = Connector(
            FakeApi(Unauthorised), FakeStore(), serverName = "Second Mind",
        ).connect("tok_bad") as Refused

        assertTrue(outcome.message, outcome.message.contains("Second Mind"))
        assertFalse(outcome.message, outcome.message.contains("Clarice"))
    }

    @Test
    fun `the server name defaults to Clarice`() = runTest {
        val outcome = Connector(FakeApi(Unauthorised), FakeStore()).connect("tok_bad") as Refused

        assertTrue(outcome.message, outcome.message.contains("Clarice"))
    }
}
