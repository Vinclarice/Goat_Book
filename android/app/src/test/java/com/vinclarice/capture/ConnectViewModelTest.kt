package com.vinclarice.capture

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

    private class FakeApi(var result: IdentifyResult) : ClariceApi {
        override suspend fun identify(token: String) = result
    }

    private val alice = Identity("alice", "alice@example.com")

    private fun viewModel(result: IdentifyResult, store: TokenStore = FakeStore()) =
        ConnectViewModel(Connector(FakeApi(result), store))

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
    fun `an already stored token shows as connected on open`() {
        val store = FakeStore().apply { save("tok_existing") }

        assertTrue(ConnectViewModel(Connector(FakeApi(Identified(alice)), store)).isConnected)
    }
}

/** Runs [ConnectViewModel.connect] outside a coroutine, for the handful of
 *  assertions that only care about the state it leaves behind. */
private fun ConnectViewModel.connectBlocking() = kotlinx.coroutines.runBlocking { connect() }
