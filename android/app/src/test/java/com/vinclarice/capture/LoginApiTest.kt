package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * Trading a password for a token, against a real HTTP server.
 *
 * design/android-login-plan.md: how the app authenticates directly instead
 * of requiring someone to paste a token created on the web. The server side
 * is accounts.tests.test_login_api; these pin the client's side of the same
 * contract.
 */
class LoginApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpClariceApi(baseUrl = server.server.url("/").toString())

    private fun accepted() = MockResponse(
        code = 200,
        body = """{"token":"tok_fresh","username":"alice","email":"alice@example.com"}""",
    )

    @Test
    fun `valid credentials return the fresh token and the identity`() = runTest {
        server.server.enqueue(accepted())

        val result = api().login("alice", "correct horse") as LoggedIn

        assertEquals("tok_fresh", result.token)
        assertEquals(Identity("alice", "alice@example.com"), result.identity)
    }

    @Test
    fun `the request carries the username, password and a label`() = runTest {
        server.server.enqueue(accepted())

        api().login("alice", "correct horse", label = "Vince's phone")

        val sent = server.server.takeRequest()
        assertEquals("POST", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/login"))
        val body = JSONObject(sent.body!!.utf8())
        assertEquals("alice", body.getString("username"))
        assertEquals("correct horse", body.getString("password"))
        assertEquals("Vince's phone", body.getString("label"))
    }

    @Test
    fun `wrong credentials carry the server's own message, attempts remaining and all`() = runTest {
        server.server.enqueue(
            MockResponse(
                code = 401,
                body = """{"detail":"Incorrect username or password. 4 attempts remaining before a temporary lock."}""",
            )
        )

        val result = api().login("alice", "wrong") as InvalidCredentials

        assertEquals(
            "Incorrect username or password. 4 attempts remaining before a temporary lock.",
            result.message,
        )
    }

    @Test
    fun `a 401 with no readable body still reads as invalid credentials`() = runTest {
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(
            InvalidCredentials("Incorrect username or password."),
            api().login("alice", "wrong"),
        )
    }

    @Test
    fun `the request asks for JSON on a lockout rather than axes' HTML template`() = runTest {
        server.server.enqueue(accepted())

        api().login("alice", "correct horse")

        val sent = server.server.takeRequest()
        assertEquals("XMLHttpRequest", sent.headers["X-Requested-With"])
    }

    @Test
    fun `a lockout with no readable body still reads as invalid credentials`() = runTest {
        server.server.enqueue(MockResponse(code = 429))

        /* ~~"Too many attempts. Try again later."~~ — reworded September 9,
           2026 with the rest of the failure text, and **deliberately without a
           duration**. The first attempt at this said *wait a minute*, which is
           true of nginx's zones (all `r/m`) and false of the lockout this
           branch is actually for: axes' cooloff can be an hour. The branch
           below parses the real wait when the body is readable; this one fires
           when it is not, so it must not invent one. */
        assertEquals(
            InvalidCredentials("Too many attempts. Wait a while before trying again."),
            api().login("alice", "correct horse"),
        )
    }

    @Test
    fun `axes' own lockout JSON becomes a precise wait-time message`() = runTest {
        server.server.enqueue(
            MockResponse(
                code = 429,
                body = """{"failure_limit":5,"username":"alice","cooloff_time":"PT1H","cooloff_timedelta":"P0DT01H00M00S"}""",
            )
        )

        val result = api().login("alice", "correct horse") as InvalidCredentials

        assertEquals("Too many attempts. Try again in 1 hour.", result.message)
    }

    @Test
    fun `a shorter cooloff reads in minutes`() = runTest {
        server.server.enqueue(
            MockResponse(code = 429, body = """{"cooloff_time":"PT30M"}""")
        )

        val result = api().login("alice", "correct horse") as InvalidCredentials

        assertEquals("Too many attempts. Try again in 30 minutes.", result.message)
    }

    @Test
    fun `a server fault or a dead network is worth retrying, not blamed on the password`() = runTest {
        server.server.enqueue(MockResponse(code = 503))
        assertTrue(api().login("alice", "correct horse") is LoginUnreachable)

        val offline = OkHttpClariceApi(baseUrl = "http://127.0.0.1:1/")
        assertTrue(offline.login("alice", "correct horse") is LoginUnreachable)
    }

    @Test
    fun `a malformed body is a failure rather than a crash`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = "not json at all"))

        assertTrue(api().login("alice", "correct horse") is LoginUnreachable)
    }

    @Test
    fun `the password never appears in a failure message`() = runTest {
        server.server.enqueue(MockResponse(code = 503))

        val result = api().login("alice", "tok_secret_value") as LoginUnreachable

        assertFalse(result.reason.contains("tok_secret_value"))
    }

    /* The second factor -- android-overhaul-plan.md, Vince's *"I want to be
       able to enter my username/pw and it connect automatically."* */

    @Test
    fun `a code travels with the credentials when one is given`() = runTest {
        server.server.enqueue(accepted())

        api().login("vince", "hunter2", label = "phone", totp = "123456")

        val body = org.json.JSONObject(server.server.takeRequest().body!!.utf8())
        assertEquals("123456", body.getString("totp"))
    }

    @Test
    fun `no code sends an empty one rather than omitting the field`() = runTest {
        // The server defaults it to "" and treats empty as *not supplied*, so
        // either shape works -- sending it always is the one that keeps this
        // client's request identical in shape whether or not the account has a
        // factor, which is one fewer thing to be wrong about.
        server.server.enqueue(accepted())

        api().login("vince", "hunter2")

        val body = org.json.JSONObject(server.server.takeRequest().body!!.utf8())
        assertEquals("", body.getString("totp"))
    }

    @Test
    fun `a second factor refusal carries the servers own instruction`() = runTest {
        /* **This is the bug Vince hit.** A 403 fell through to `else` and
           became "Clarice answered 403." -- a number, where the server had
           sent a sentence saying exactly what to do. The endpoint answers 403
           for two distinct, actionable things (no code given, wrong code
           given) and both were being thrown away. */
        server.server.enqueue(
            MockResponse(
                code = 403,
                body = """{"detail": "This account has a second factor. Enter the code from your authenticator app, or one of your recovery codes."}""",
            )
        )

        val result = api().login("vince", "hunter2")

        assertTrue(result is InvalidCredentials)
        assertTrue((result as InvalidCredentials).message.contains("second factor"))
    }

    @Test
    fun `a wrong code is refused rather than reported as unreachable`() = runTest {
        server.server.enqueue(
            MockResponse(
                code = 403,
                body = """{"detail": "That code did not match. Codes expire after about thirty seconds, so try the current one."}""",
            )
        )

        val result = api().login("vince", "hunter2", totp = "000000")

        assertTrue((result as InvalidCredentials).message.contains("did not match"))
    }
}
