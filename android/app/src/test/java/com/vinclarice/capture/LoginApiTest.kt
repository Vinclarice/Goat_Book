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

        assertEquals(InvalidCredentials("Too many attempts. Try again later."), api().login("alice", "correct horse"))
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
}
