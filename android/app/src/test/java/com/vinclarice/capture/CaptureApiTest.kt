package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test

/**
 * Sending a capture, against a real HTTP server.
 *
 * The server half of this is M1: 201 for a genuine write, 200 for a replay
 * of an Idempotency-Key it has already seen, and the same body either way.
 * These pin the client's side of that -- most importantly that a retry
 * carries the *same* key, which is the entire mechanism protecting someone
 * from a duplicated thought.
 */
class CaptureApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpClariceApi(baseUrl = server.server.url("/").toString())

    private val key = "3f1c9a2e-0000-4000-8000-000000000001"

    private fun accepted(code: Int) = MockResponse(
        code = code,
        body = """{"id":42,"created_at":"2026-08-01T12:00:00+00:00"}""",
    )

    @Test
    fun `a stored capture is delivered`() = runTest {
        server.server.enqueue(accepted(201))

        assertEquals(Disposition.DELIVERED, api().capture("tok", "buy milk", key))
    }

    @Test
    fun `a replayed key is delivered rather than sent again`() = runTest {
        // 200 means an earlier request with this key already stored it. A
        // client treating that as failure would retry forever against a
        // server patiently answering "already done".
        server.server.enqueue(accepted(200))

        assertEquals(Disposition.DELIVERED, api().capture("tok", "buy milk", key))
    }

    @Test
    fun `the request carries the token, the key and the text`() = runTest {
        server.server.enqueue(accepted(201))

        api().capture("tok_abc", "buy milk", key)

        val sent = server.server.takeRequest()
        assertEquals("POST", sent.method)
        assertEquals("Bearer tok_abc", sent.headers["Authorization"])
        assertEquals(key, sent.headers["Idempotency-Key"])
        assertEquals("buy milk", JSONObject(sent.body!!.utf8()).getString("text"))
    }

    @Test
    fun `a retry reuses the key it was given`() = runTest {
        // Not a new UUID per attempt. The key identifies the thought, not
        // the attempt, and inventing a fresh one on retry is precisely how
        // a lost response becomes two captures.
        server.server.enqueue(MockResponse(code = 503))
        server.server.enqueue(accepted(200))

        api().capture("tok", "buy milk", key)
        api().capture("tok", "buy milk", key)

        assertEquals(key, server.server.takeRequest().headers["Idempotency-Key"])
        assertEquals(key, server.server.takeRequest().headers["Idempotency-Key"])
    }

    @Test
    fun `text with quotes and newlines survives the journey`() = runTest {
        // Captures are prose typed in a hurry. If the body were assembled
        // by string concatenation this is where it would break.
        val awkward = "she said \"later\"\nand a backslash \\ too"
        server.server.enqueue(accepted(201))

        api().capture("tok", awkward, key)

        val sent = server.server.takeRequest()
        assertEquals(awkward, JSONObject(sent.body!!.utf8()).getString("text"))
    }

    @Test
    fun `a rejected capture is not retried blindly`() = runTest {
        server.server.enqueue(MockResponse(code = 400))

        assertEquals(Disposition.REJECTED, api().capture("tok", "", key))
    }

    @Test
    fun `an expired token asks for reconnection and keeps the text`() = runTest {
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(Disposition.NEEDS_RECONNECT, api().capture("tok", "buy milk", key))
    }

    @Test
    fun `a server fault or a dead network is worth retrying`() = runTest {
        server.server.enqueue(MockResponse(code = 503))
        assertEquals(Disposition.RETRY_LATER, api().capture("tok", "buy milk", key))

        val offline = OkHttpClariceApi(baseUrl = "http://127.0.0.1:1/")
        assertEquals(Disposition.RETRY_LATER, offline.capture("tok", "buy milk", key))
    }

    @Test
    fun `tags are optional and absent from the body by default`() = runTest {
        server.server.enqueue(accepted(201))

        api().capture("tok", "buy milk", key)

        val body = JSONObject(server.server.takeRequest().body!!.utf8())
        assertEquals(0, body.getJSONArray("tags").length())
    }

    @Test
    fun `tags travel in the request body`() = runTest {
        server.server.enqueue(accepted(201))

        api().capture("tok", "design a boss fight", key, tags = listOf("game-dev"))

        val body = JSONObject(server.server.takeRequest().body!!.utf8())
        assertEquals("game-dev", body.getJSONArray("tags").getString(0))
    }

    @Test
    fun `the token never appears in what is sent as the body`() = runTest {
        server.server.enqueue(accepted(201))

        api().capture("tok_secret_value", "buy milk", key)

        val body = server.server.takeRequest().body!!.utf8()
        assertFalse(body.contains("tok_secret_value"))
    }
}
