package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * The Connect screen's network half, tested against a real HTTP server
 * rather than a stubbed client -- so "we send the right header" is a fact
 * about bytes on a socket rather than an assumption about a mock.
 *
 * GET /api/v1/me is the only endpoint a freshly pasted token can call
 * without writing anything, which is why Connect validates against it.
 */
class ClariceApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpClariceApi(baseUrl = server.server.url("/").toString())

    @Test
    fun `a valid token identifies the account`() = runTest {
        server.server.enqueue(
            MockResponse(
                code = 200,
                body = """{"username":"alice","email":"alice@example.com"}""",
            )
        )

        val result = api().identify("tok_abc")

        assertEquals(Identity("alice", "alice@example.com"), (result as Identified).identity)
    }

    @Test
    fun `the token travels as a bearer credential`() = runTest {
        server.server.enqueue(
            MockResponse(code = 200, body = """{"username":"a","email":"a@b.c"}""")
        )

        api().identify("tok_abc")

        val sent = server.server.takeRequest()
        assertEquals("Bearer tok_abc", sent.headers["Authorization"])
        assertEquals("GET", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/me"))
    }

    @Test
    fun `a rejected token is reported as unauthorised, not as a failure`() = runTest {
        // The distinction matters to the caller: unauthorised means "this
        // token is wrong, ask for another"; a failure means "try again".
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(Unauthorised, api().identify("tok_bad"))
    }

    @Test
    fun `a forbidden token is unauthorised too`() = runTest {
        server.server.enqueue(MockResponse(code = 403))

        assertEquals(Unauthorised, api().identify("tok_bad"))
    }

    @Test
    fun `a server fault is a failure worth retrying`() = runTest {
        server.server.enqueue(MockResponse(code = 503))

        assertTrue(api().identify("tok_abc") is Unreachable)
    }

    @Test
    fun `an unreachable host is a failure, not a bad token`() = runTest {
        // Someone on a train should be told the network failed, not that
        // the token they just pasted is invalid.
        val offline = OkHttpClariceApi(baseUrl = "http://127.0.0.1:1/")

        assertTrue(offline.identify("tok_abc") is Unreachable)
    }

    @Test
    fun `an unreachable server is named, so the wrong one is not blamed`() = runTest {
        // Found on a real device, August 14, 2026. This class now serves both
        // backends on a split install, and every failure message said
        // "Clarice" -- so a capture that could not reach Second Mind reported
        // the *other* server as broken, sending somebody to debug the half
        // that was working. A message that names the wrong system is worse
        // than one that names none.
        val offline = OkHttpClariceApi(baseUrl = "http://127.0.0.1:1/", serverName = "Second Mind")

        val result = offline.identify("tok_abc") as Unreachable

        assertTrue(result.reason, result.reason.contains("Second Mind"))
        assertFalse(result.reason, result.reason.contains("Clarice"))
    }

    @Test
    fun `an unexpected status names the server that sent it`() = runTest {
        server.server.enqueue(MockResponse(code = 503))

        val result = OkHttpClariceApi(
            baseUrl = server.server.url("/").toString(),
            serverName = "Second Mind",
        ).identify("tok_abc") as Unreachable

        assertTrue(result.reason, result.reason.contains("Second Mind"))
        assertTrue(result.reason, result.reason.contains("503"))
    }

    @Test
    fun `the name defaults to Clarice, so every existing call site is unchanged`() = runTest {
        val offline = OkHttpClariceApi(baseUrl = "http://127.0.0.1:1/")

        val result = offline.identify("tok_abc") as Unreachable

        assertTrue(result.reason, result.reason.contains("Clarice"))
    }

    @Test
    fun `a malformed body is a failure rather than a crash`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = "not json at all"))

        assertTrue(api().identify("tok_abc") is Unreachable)
    }

    @Test
    fun `the token is never written into the failure message`() = runTest {
        // Failure text ends up in logs and on screen. A token that leaks
        // through an error string is a token you cannot un-leak.
        server.server.enqueue(MockResponse(code = 503))

        val result = api().identify("tok_secret_value") as Unreachable

        assertFalse(result.reason.contains("tok_secret_value"))
    }
}
