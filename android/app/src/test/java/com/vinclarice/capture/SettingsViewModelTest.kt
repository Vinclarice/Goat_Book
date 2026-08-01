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

        override suspend fun capture(token: String, text: String, idempotencyKey: String) =
            Disposition.DELIVERED
    }

    private val alice = Identity("alice", "alice@example.com")

    private fun viewModel(
        result: IdentifyResult,
        store: TokenStore = FakeStore().apply { save("tok_stored") },
    ) = SettingsViewModel(Connector(FakeApi(result), store))

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
    fun `nothing the screen can show has ever held the token`() = runTest {
        // "Never display it after saving" has to hold for the state object as
        // much as for the field it was typed into.
        val store = FakeStore().apply { save("tok_secret") }
        val model = viewModel(Identified(alice), store)

        model.load()

        assertFalse(model.state.value.toString().contains("tok_secret"))
    }
}
