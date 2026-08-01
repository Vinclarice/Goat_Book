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
 * The rule everything here serves: a thought someone typed is never lost.
 * Only a confirmed store clears the field; every other outcome keeps the
 * text where they can see it.
 */
class CaptureViewModelTest {

    private class FakeStore(token: String? = "tok_stored") : TokenStore {
        var saved: String? = token
        override fun save(token: String) { saved = token }
        override fun read(): String? = saved
        override fun clear() { saved = null }
    }

    private class FakeApi(var disposition: Disposition) : ClariceApi {
        val keys = mutableListOf<String>()
        val texts = mutableListOf<String>()
        var tokens = mutableListOf<String>()
        override suspend fun identify(token: String) = Identified(Identity("a", "a@b.c"))
        override suspend fun capture(token: String, text: String, idempotencyKey: String):
            Disposition {
            tokens += token
            texts += text
            keys += idempotencyKey
            return disposition
        }
    }

    private fun model(
        disposition: Disposition = Disposition.DELIVERED,
        store: TokenStore = FakeStore(),
        api: FakeApi = FakeApi(disposition),
    ) = api to CaptureViewModel(api, store)

    @Test
    fun `typing updates the field`() {
        val (_, model) = model()

        model.onTextChange("buy milk")

        assertEquals("buy milk", model.state.value.text)
    }

    @Test
    fun `a delivered capture clears the field and confirms`() = runTest {
        val (api, model) = model(Disposition.DELIVERED)
        model.onTextChange("buy milk")

        model.submit()

        assertEquals("", model.state.value.text)
        assertNotNull(model.state.value.message)
        assertFalse(model.state.value.isError)
        assertEquals(listOf("buy milk"), api.texts)
    }

    @Test
    fun `it sends the stored token`() = runTest {
        val (api, model) = model(store = FakeStore("tok_mine"))
        model.onTextChange("buy milk")

        model.submit()

        assertEquals(listOf("tok_mine"), api.tokens)
    }

    @Test
    fun `every capture gets its own key`() = runTest {
        // Two thoughts are two captures. Reusing a key across them would
        // make the server treat the second as a replay of the first and
        // silently drop it.
        val (api, model) = model()

        model.onTextChange("first")
        model.submit()
        model.onTextChange("second")
        model.submit()

        assertEquals(2, api.keys.size)
        assertNotEquals(api.keys[0], api.keys[1])
    }

    @Test
    fun `a key is a uuid the server will accept`() = runTest {
        // The server rejects a malformed Idempotency-Key with 400, so an
        // invented format here would fail every capture.
        val (api, model) = model()
        model.onTextChange("buy milk")

        model.submit()

        assertTrue(
            api.keys.single(),
            Regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
                .matches(api.keys.single()),
        )
    }

    @Test
    fun `a failure to send keeps the text on screen`() = runTest {
        // Until M3's durable queue exists, the only place an unsent capture
        // survives is the field itself. Clearing it here would lose the
        // thought outright.
        val (_, model) = model(Disposition.RETRY_LATER)
        model.onTextChange("buy milk")

        model.submit()

        assertEquals("buy milk", model.state.value.text)
        assertTrue(model.state.value.isError)
    }

    @Test
    fun `an expired token keeps the text and asks for reconnection`() = runTest {
        val (_, model) = model(Disposition.NEEDS_RECONNECT)
        model.onTextChange("buy milk")

        model.submit()

        assertEquals("buy milk", model.state.value.text)
        assertTrue(model.state.value.message!!.contains("reconnect", ignoreCase = true))
    }

    @Test
    fun `a rejected capture keeps the text and says it is fixable`() = runTest {
        val (_, model) = model(Disposition.REJECTED)
        model.onTextChange("buy milk")

        model.submit()

        assertEquals("buy milk", model.state.value.text)
        assertTrue(model.state.value.isError)
    }

    @Test
    fun `an empty field sends nothing`() = runTest {
        val (api, model) = model()
        model.onTextChange("   ")

        model.submit()

        assertTrue(api.texts.isEmpty())
    }

    @Test
    fun `with no stored token nothing is sent`() = runTest {
        // Signing out or a wiped keystore. Asking the network would only
        // produce a 401 that says less than we already know.
        val (api, model) = model(store = FakeStore(token = null))
        model.onTextChange("buy milk")

        model.submit()

        assertTrue(api.texts.isEmpty())
        assertEquals("buy milk", model.state.value.text)
    }

    @Test
    fun `sending is false again however it ended`() = runTest {
        Disposition.entries.forEach { outcome ->
            val (_, model) = model(outcome)
            model.onTextChange("buy milk")

            model.submit()

            assertFalse("after $outcome", model.state.value.sending)
        }
    }

    @Test
    fun `typing again clears the previous confirmation`() = runTest {
        // A "Captured." still on screen while a new thought is being typed
        // reads as though this one has already been sent.
        val (_, model) = model()
        model.onTextChange("first")
        model.submit()
        assertNotNull(model.state.value.message)

        model.onTextChange("second")

        assertNull(model.state.value.message)
    }
}
