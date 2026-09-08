package com.vinclarice.capture

import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the Connect screen shows, without a screen.
 *
 * The composable is a thin rendering of this state, so everything worth
 * asserting -- when the button is disabled, which message appears, whether
 * the token is still on screen afterwards -- is decided here, on the JVM,
 * rather than in a UI test that needs a device.
 */
class ConnectViewModelTest {

    private class FakeStore : TokenStore {
        var saved: String? = null
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null }
    }

    private class FakeApi(
        var result: IdentifyResult,
        var loginResult: LoginResult = InvalidCredentials("unused"),
        var startResult: PairingStartResult = PairingStartFailed("unused"),
        /**
         * Answered in order, one per poll, so a test can say *pending, pending,
         * then granted* -- which is the whole shape of this flow and cannot be
         * expressed by a single fixed answer. The last entry repeats once the
         * list runs out.
         */
        var pollResults: List<PairingPollResult> = listOf(PairingPending),
    ) : ClariceApi {
        var lastLoginUsername: String? = null
        var lastLoginPassword: String? = null
        var lastLoginLabel: String? = null
        var lastPairingLabel: String? = null
        var pollCalls = 0

        override suspend fun identify(token: String) = result

        override suspend fun startPairing(label: String): PairingStartResult {
            lastPairingLabel = label
            return startResult
        }

        override suspend fun pollPairing(deviceCode: String): PairingPollResult {
            val answer = pollResults[minOf(pollCalls, pollResults.lastIndex)]
            pollCalls++
            return answer
        }

        var lastLoginTotp: String? = null

        override suspend fun login(
            username: String, password: String, label: String, totp: String,
        ): LoginResult {
            lastLoginUsername = username
            lastLoginPassword = password
            lastLoginLabel = label
            lastLoginTotp = totp
            return loginResult
        }

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

    private fun viewModel(result: IdentifyResult, store: TokenStore = FakeStore()) =
        ConnectViewModel(Connector(FakeApi(result), store))

    private fun loginViewModel(
        loginResult: LoginResult,
        store: TokenStore = FakeStore(),
        deviceLabel: String = "Android",
    ): Pair<ConnectViewModel, FakeApi> {
        val api = FakeApi(Unreachable("unused"), loginResult)
        return ConnectViewModel(Connector(api, store), deviceLabel = deviceLabel) to api
    }

    @Test
    fun `starts empty and idle`() {
        val state = viewModel(Identified(alice)).state.value

        assertEquals("", state.token)
        assertFalse(state.checking)
        assertNull(state.error)
        assertNull(state.connectedAs)
    }

    @Test
    fun `typing updates the field`() {
        val model = viewModel(Identified(alice))

        model.onTokenChange("tok_abc")

        assertEquals("tok_abc", model.state.value.token)
    }

    @Test
    fun `typing clears a previous error`() {
        // Otherwise the old failure sits under the field while someone
        // corrects it, and it is unclear whether it refers to what they are
        // now typing.
        val model = viewModel(Unauthorised)
        model.onTokenChange("tok_bad")
        model.connectBlocking()
        assertNotNull(model.state.value.error)

        model.onTokenChange("tok_bad2")

        assertNull(model.state.value.error)
    }

    @Test
    fun `a working token reports the account it belongs to`() = runTest {
        val store = FakeStore()
        val model = viewModel(Identified(alice), store)
        model.onTokenChange("tok_good")

        model.connect()

        assertEquals(alice, model.state.value.connectedAs)
        assertEquals("tok_good", store.read())
    }

    @Test
    fun `the token leaves the screen once it is stored`() = runTest {
        // "Never display it after saving." Clearing the field is how that
        // is true of the screen as well as of storage.
        val model = viewModel(Identified(alice))
        model.onTokenChange("tok_good")

        model.connect()

        assertEquals("", model.state.value.token)
    }

    @Test
    fun `a refused token stays in the field with a fixable message`() = runTest {
        // Kept deliberately: someone who pasted a token with a character
        // missing should be able to fix it, not retype forty characters.
        val model = viewModel(Unauthorised)
        model.onTokenChange("tok_bad")

        model.connect()

        assertEquals("tok_bad", model.state.value.token)
        assertTrue(model.state.value.error!!.contains("did not accept"))
        assertNull(model.state.value.connectedAs)
    }

    @Test
    fun `a refused token points at logging in again, not just the web`() = runTest {
        // Written before login existed in the app at all -- "create a new
        // one on the web and paste it again" was the only path there was.
        // It is no longer the easiest one.
        val model = viewModel(Unauthorised)
        model.onTokenChange("tok_bad")

        model.connect()

        assertTrue(model.state.value.error!!.contains("Log in again"))
    }

    @Test
    fun `an unreachable server says so rather than blaming the token`() = runTest {
        val model = viewModel(Unreachable("Could not reach Clarice."))
        model.onTokenChange("tok_good")

        model.connect()

        assertEquals("Could not reach Clarice.", model.state.value.error)
        assertEquals("tok_good", model.state.value.token)
    }

    @Test
    fun `an empty field is refused without a request`() = runTest {
        val model = viewModel(Identified(alice))

        model.connect()

        assertNotNull(model.state.value.error)
        assertNull(model.state.value.connectedAs)
    }

    @Test
    fun `checking is false again however it ended`() = runTest {
        // A spinner that never stops is the classic way a failed request
        // becomes a stuck screen.
        listOf(Identified(alice), Unauthorised, Unreachable("x")).forEach { result ->
            val model = viewModel(result)
            model.onTokenChange("tok_abc")

            model.connect()

            assertFalse("after $result", model.state.value.checking)
        }
    }

    @Test
    fun `typing updates the username and password fields`() {
        val model = viewModel(Identified(alice))

        model.onUsernameChange("alice")
        model.onPasswordChange("hunter2")

        assertEquals("alice", model.state.value.username)
        assertEquals("hunter2", model.state.value.password)
    }

    @Test
    fun `a successful login reports the account and stores the returned token`() = runTest {
        val store = FakeStore()
        val (model, _) = loginViewModel(LoggedIn("tok_fresh", alice), store)
        model.onUsernameChange("alice")
        model.onPasswordChange("correct horse")

        model.logIn()

        assertEquals(alice, model.state.value.connectedAs)
        assertEquals("tok_fresh", store.read())
    }

    @Test
    fun `the password never remains on screen, win or lose`() = runTest {
        val (model, _) = loginViewModel(InvalidCredentials("Incorrect username or password."))
        model.onUsernameChange("alice")
        model.onPasswordChange("wrong")

        model.logIn()

        assertEquals("", model.state.value.password)
    }

    @Test
    fun `invalid credentials keep the username so it need not be retyped`() = runTest {
        val (model, _) = loginViewModel(InvalidCredentials("Incorrect username or password."))
        model.onUsernameChange("alice")
        model.onPasswordChange("wrong")

        model.logIn()

        assertEquals("alice", model.state.value.username)
        assertNotNull(model.state.value.error)
        assertNull(model.state.value.connectedAs)
    }

    @Test
    fun `an unreachable server says so rather than blaming the credentials`() = runTest {
        val (model, _) = loginViewModel(LoginUnreachable("Could not reach Clarice."))
        model.onUsernameChange("alice")
        model.onPasswordChange("correct horse")

        model.logIn()

        assertEquals("Could not reach Clarice.", model.state.value.error)
    }

    @Test
    fun `an empty username or password is refused without a request`() = runTest {
        val (model, api) = loginViewModel(LoggedIn("tok", alice))
        model.onPasswordChange("correct horse")
        // Username left blank.

        model.logIn()

        assertNotNull(model.state.value.error)
        assertNull(api.lastLoginUsername)
    }

    @Test
    fun `the injected device label is what the request carries, not something typed`() = runTest {
        val (model, api) = loginViewModel(
            LoggedIn("tok", alice), deviceLabel = "Android (SM-S928U1)",
        )
        model.onUsernameChange("alice")
        model.onPasswordChange("correct horse")

        model.logIn()

        assertEquals("Android (SM-S928U1)", api.lastLoginLabel)
    }

    @Test
    fun `an already stored token shows as connected on open`() {
        val store = FakeStore().apply { save("tok_existing") }

        assertTrue(ConnectViewModel(Connector(FakeApi(Identified(alice)), store)).isConnected)
    }

    @Test
    fun `disconnecting forgets the identity this screen was showing`() = runTest {
        // A regression guard, not new behaviour: this method already existed
        // and already did the right thing -- what was missing was anyone
        // calling it. Root wired "Disconnect this phone" to
        // SettingsViewModel.disconnect() only, which clears the stored
        // token through a *different* Connector-backed view model and never
        // touches this one, so returning to Connect kept showing "Connected
        // as alice." above a login form for someone trying to log in as
        // somebody else.
        val store = FakeStore()
        val model = ConnectViewModel(Connector(FakeApi(Identified(alice)), store))
        model.onTokenChange("tok_good")
        model.connect()
        assertEquals(alice, model.state.value.connectedAs)

        model.disconnect()

        assertNull(model.state.value.connectedAs)
        assertNull(store.read())
    }

    /* Pairing -- android-login-redesign-plan.md Half B, increment 4.

       The half that finally delivers the requirement: the phone asks, a person
       carries a short code the other way, and the token arrives here. Nothing
       secret is carried to the phone. */

    private fun pairingModel(api: FakeApi, store: TokenStore = FakeStore()) =
        ConnectViewModel(Connector(api, store), deviceLabel = "Pixel")

    private fun begun(interval: Int = 5) = PairingBegun(
        PairingStarted(
            userCode = "ABCD-EFGH",
            deviceCode = "dev_secret",
            expiresAt = null,
            intervalSeconds = interval,
        )
    )

    @Test
    fun `starting a pairing shows the code a person has to carry`() = runTest {
        /* Observed *while* waiting rather than after. `beginPairing` suspends
           for the whole flow, so calling it straight through and then reading
           the state asks what the screen looks like once the pairing has
           already given up -- at which point the code is correctly gone.
           Written that way first, and it failed for exactly that reason. */
        val api = FakeApi(Identified(alice), startResult = begun())
        val model = pairingModel(api)

        backgroundScope.launch { model.beginPairing() }
        runCurrent()

        assertEquals("ABCD-EFGH", model.state.value.pairing?.userCode)
    }

    @Test
    fun `the device code is never put on screen`() = runTest {
        /* **The credential half.** Showing it would recreate exactly the thing
           this flow exists to remove -- a secret displayed on one device for
           somebody to carry to another. */
        val api = FakeApi(Identified(alice), startResult = begun())
        val model = pairingModel(api)

        backgroundScope.launch { model.beginPairing() }
        runCurrent()

        assertEquals("ABCD-EFGH", model.state.value.pairing?.userCode)
        assertFalse(model.state.value.toString().contains("dev_secret"))
    }

    @Test
    fun `the phone names itself so the web can say which one`() = runTest {
        val api = FakeApi(Identified(alice), startResult = begun())

        pairingModel(api).beginPairing()

        assertEquals("Pixel", api.lastPairingLabel)
    }

    @Test
    fun `it keeps asking while nobody has approved`() = runTest {
        /* Pending is the ordinary answer for most of this flow, so a client
           that gave up on the first one would never pair at all. */
        val api = FakeApi(
            Identified(alice),
            startResult = begun(),
            pollResults = listOf(
                PairingPending, PairingPending, PairingGranted("tok_paired")
            ),
        )
        val model = pairingModel(api)

        model.beginPairing()

        assertEquals(3, api.pollCalls)
        assertEquals(alice, model.state.value.connectedAs)
    }

    @Test
    fun `an approved pairing stores the token by the ordinary path`() = runTest {
        val store = FakeStore()
        val api = FakeApi(
            Identified(alice),
            startResult = begun(),
            pollResults = listOf(PairingGranted("tok_paired")),
        )

        pairingModel(api, store).beginPairing()

        assertEquals("tok_paired", store.read())
    }

    @Test
    fun `a pairing that cannot even be started says so`() = runTest {
        val api = FakeApi(
            Identified(alice),
            startResult = PairingStartFailed("Could not reach Clarice."),
        )
        val model = pairingModel(api)

        model.beginPairing()

        assertEquals("Could not reach Clarice.", model.state.value.error)
        assertNull(model.state.value.pairing)
    }

    @Test
    fun `a blip while polling does not abandon the pairing`() = runTest {
        /* The code on screen is still good and somebody may be walking to a
           laptop with it. Giving up on one failed request would throw away a
           pairing that is about to work. */
        val api = FakeApi(
            Identified(alice),
            startResult = begun(),
            pollResults = listOf(
                PairingPollFailed("Could not reach Clarice."),
                PairingGranted("tok_paired"),
            ),
        )
        val model = pairingModel(api)

        model.beginPairing()

        assertEquals(alice, model.state.value.connectedAs)
    }

    @Test
    fun `it gives up rather than polling forever`() = runTest {
        /* A pairing nobody ever approves must end. Polling an endpoint with a
           rate limit until the process dies is how a phone flattens its own
           battery and earns a 429. */
        val api = FakeApi(
            Identified(alice), startResult = begun(), pollResults = listOf(PairingPending)
        )
        val model = pairingModel(api)

        model.beginPairing()

        assertNull(model.state.value.connectedAs)
        assertNotNull(model.state.value.error)
    }

    @Test
    fun `cancelling stops the asking`() = runTest {
        val api = FakeApi(
            Identified(alice), startResult = begun(), pollResults = listOf(PairingPending)
        )
        val model = pairingModel(api)
        model.beginPairing()
        val asked = api.pollCalls

        model.cancelPairing()

        assertNull(model.state.value.pairing)
        assertEquals(asked, api.pollCalls)
    }


    /* Where to approve, as a person would type it. */

    @Test
    fun `the pairing address comes from the real base url`() {
        /* **Written after reading the screen back and finding a bug.** The
           first version built this from the server's display *name* --
           "Clarice".lowercase() + ".com" -- which renders `clarice.com/pair`,
           a domain this project does not own. The name is for prose; the
           address has to come from the URL the app actually talks to. */
        assertEquals(
            "vinclarice.com/pair",
            pairingAddress("https://vinclarice.com/"),
        )
    }

    @Test
    fun `it survives a base url with no trailing slash`() {
        assertEquals("vinclarice.com/pair", pairingAddress("https://vinclarice.com"))
    }

    @Test
    fun `a local or staging server names itself honestly`() {
        // -PclariceBaseUrl points a debug build somewhere else, and telling
        // somebody to visit production while the app talks to staging is how
        // an approval never arrives.
        assertEquals("10.0.2.2:8000/pair", pairingAddress("http://10.0.2.2:8000/"))
    }

}

/** Runs [ConnectViewModel.connect] outside a coroutine, for the handful of
 *  assertions that only care about the state it leaves behind. */
private fun ConnectViewModel.connectBlocking() = kotlinx.coroutines.runBlocking { connect() }
