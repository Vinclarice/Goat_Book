package com.vinclarice.capture

import java.time.Instant
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * Asking to be let in, against a real HTTP server —
 * `android-login-redesign-plan.md` Half B, increment 4.
 *
 * **The inversion this client half completes.** A token used to be minted on a
 * laptop and carried here. Now the phone asks, shows a short code somebody
 * carries the *other* way, and the token arrives over this connection — to the
 * device that asked for it, never displayed.
 *
 * The server side is `accounts/tests/test_pairing.py`; these pin the client's
 * half of the same contract.
 */
class PairingApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpClariceApi(baseUrl = server.server.url("/").toString())

    private fun begun() = MockResponse(
        code = 200,
        body = """{"user_code":"ABCD-EFGH","device_code":"dev_secret",
            "expires_at":"2026-09-07T23:30:00Z","interval":5}""",
    )

    @Test
    fun `starting a pairing returns both codes and the poll interval`() = runTest {
        server.server.enqueue(begun())

        val result = api().startPairing(label = "Pixel") as PairingBegun

        assertEquals("ABCD-EFGH", result.started.userCode)
        assertEquals("dev_secret", result.started.deviceCode)
        assertEquals(5, result.started.intervalSeconds)
        assertEquals(Instant.parse("2026-09-07T23:30:00Z"), result.started.expiresAt)
    }

    @Test
    fun `starting one needs no credential at all`() = runTest {
        /* The whole reason this endpoint is unauthenticated: a phone with no
           token is exactly the phone that needs to pair. An Authorization
           header here would be asking for the thing being asked for. */
        server.server.enqueue(begun())

        api().startPairing()

        val sent = server.server.takeRequest()
        assertNull(sent.headers["Authorization"])
        assertEquals("POST", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/pair/start"))
    }

    @Test
    fun `the label travels so the web can say which phone`() = runTest {
        server.server.enqueue(begun())

        api().startPairing(label = "Pixel 9")

        val body = JSONObject(server.server.takeRequest().body!!.utf8())
        assertEquals("Pixel 9", body.getString("label"))
    }

    @Test
    fun `polling before anybody approves is pending rather than a failure`() = runTest {
        /* **Pending is the ordinary case, not an error.** The server answers
           200 with a null token for waiting, expired and never-existed alike,
           deliberately -- so a client that treated a null token as a fault
           would report a broken server for the entire normal duration of the
           flow. */
        server.server.enqueue(MockResponse(code = 200, body = """{"token":null}"""))

        assertEquals(PairingPending, api().pollPairing("dev_secret"))
    }

    @Test
    fun `polling after approval hands back the token`() = runTest {
        server.server.enqueue(
            MockResponse(code = 200, body = """{"token":"tok_paired"}""")
        )

        val result = api().pollPairing("dev_secret") as PairingGranted

        assertEquals("tok_paired", result.token)
    }

    @Test
    fun `the device code travels in the body rather than the query`() = runTest {
        /* It is the credential half of this flow. A query string is the one
           place a secret reliably ends up in a log -- which this project
           already fixed once, for `/mind/search/`. */
        server.server.enqueue(MockResponse(code = 200, body = """{"token":null}"""))

        api().pollPairing("dev_secret")

        val sent = server.server.takeRequest()
        assertTrue(sent.target.endsWith("/api/v1/pair/poll"))
        assertEquals("dev_secret", JSONObject(sent.body!!.utf8()).getString("device_code"))
    }

    @Test
    fun `a server that cannot be reached is a failure worth retrying`() = runTest {
        val offline = OkHttpClariceApi(baseUrl = "http://127.0.0.1:1/")

        assertTrue(offline.startPairing() is PairingStartFailed)
        assertTrue(offline.pollPairing("dev_secret") is PairingPollFailed)
    }

    @Test
    fun `a rate limited poll is a failure rather than a granted token`() = runTest {
        /* 429 is reachable here in a way it is not on most endpoints: this one
           is polled, and its nginx zone is sized from the poll interval. The
           thing that must never happen is a 429 being read as "no token yet"
           forever, or worse as success. */
        server.server.enqueue(MockResponse(code = 429, body = ""))

        assertTrue(api().pollPairing("dev_secret") is PairingPollFailed)
    }

    @Test
    fun `a malformed body is a failure rather than a crash`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = "not json"))

        assertTrue(api().startPairing() is PairingStartFailed)
        server.server.enqueue(MockResponse(code = 200, body = "not json"))
        assertTrue(api().pollPairing("dev_secret") is PairingPollFailed)
    }

    @Test
    fun `an unreadable expiry does not cost the pairing`() = runTest {
        /* The codes are what matter; the expiry only drives a countdown. A
           date this client cannot parse degrades to null rather than failing
           a pairing that would otherwise work. */
        server.server.enqueue(
            MockResponse(
                code = 200,
                body = """{"user_code":"ABCD-EFGH","device_code":"dev_secret",
                    "expires_at":"whenever","interval":5}""",
            )
        )

        val result = api().startPairing() as PairingBegun

        assertEquals("ABCD-EFGH", result.started.userCode)
        assertNull(result.started.expiresAt)
    }

    @Test
    fun `a missing interval falls back rather than polling as fast as it can`() = runTest {
        /* An absent or nonsense interval must not become zero. A zero-delay
           poll loop is a self-inflicted flood against an endpoint that has a
           rate limit, and the phone would rate-limit itself out of its own
           pairing. */
        server.server.enqueue(
            MockResponse(
                code = 200,
                body = """{"user_code":"ABCD-EFGH","device_code":"dev_secret"}""",
            )
        )

        val result = api().startPairing() as PairingBegun

        assertTrue(result.started.intervalSeconds >= 1)
    }
}
