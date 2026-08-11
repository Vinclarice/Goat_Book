package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * DailyApi's write half -- pinning/unpinning focus, saving the day's own
 * text, and the six routine actions. android-full-client-plan.md's
 * Daily-edit slice. Every write here answers with a whole DayOut or
 * StandingsOut, neither of which this client parses -- DailyViewModel
 * reloads the day on success instead (same reasoning AgendaViewModel's own
 * write() gives), so these tests only need to prove the right
 * method/url/body went out and the right outcome came back.
 */
class DailyWriteApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpDailyApi(baseUrl = server.server.url("/").toString())

    private val dayOutBody = """{"date": "2026-08-11", "today": "2026-08-11", "intentions": "", "gratitude": "",
        "happenings": "", "compass_purpose": "", "compass_question": "", "focus": [], "action_items": [],
        "areas": [], "projects": [], "shows_action_items": true, "routines": [], "routines_are_loggable": true,
        "paused_routines": []}"""

    private val standingsOutBody = """{"today": "2026-08-11", "standings": [], "paused": []}"""

    @Test
    fun `pinning a task posts the task id with no csrf concern`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = dayOutBody))

        val result = api().pinFocus("tok_abc", "2026-08-11", taskId = 7)

        val sent = server.server.takeRequest()
        assertEquals("POST", sent.method)
        assertEquals("Bearer tok_abc", sent.headers["Authorization"])
        assertTrue(sent.target.endsWith("/api/v1/day/2026-08-11/focus"))
        assertEquals("""{"task_id":7}""", sent.body!!.utf8())
        assertEquals(DayWriteSucceeded, result)
    }

    @Test
    fun `unpinning a task sends DELETE to the task-specific focus url`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = dayOutBody))

        api().unpinFocus("tok_abc", "2026-08-11", taskId = 7)

        val sent = server.server.takeRequest()
        assertEquals("DELETE", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/day/2026-08-11/focus/7"))
    }

    @Test
    fun `writing the days text sends all three sections together`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = dayOutBody))

        api().writeDayText("tok_abc", "2026-08-11", "Ship it", "Coffee", "")

        val sent = server.server.takeRequest()
        assertEquals("PATCH", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/day/2026-08-11"))
        // org.json doesn't preserve key insertion order, so this checks
        // fields rather than the exact serialized string.
        val body = org.json.JSONObject(sent.body!!.utf8())
        assertEquals("Ship it", body.getString("intentions"))
        assertEquals("Coffee", body.getString("gratitude"))
        assertEquals("", body.getString("happenings"))
    }

    @Test
    fun `logging a routine sends the amount`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = standingsOutBody))

        api().logRoutine("tok_abc", routineId = 3, amount = 1)

        val sent = server.server.takeRequest()
        assertEquals("POST", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/routines/3/log"))
        assertEquals("""{"amount":1}""", sent.body!!.utf8())
    }

    @Test
    fun `a negative amount corrects a mis-tap`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = standingsOutBody))

        api().logRoutine("tok_abc", routineId = 3, amount = -1)

        assertEquals("""{"amount":-1}""", server.server.takeRequest().body!!.utf8())
    }

    @Test
    fun `skipping a routine is a plain POST with no body`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = standingsOutBody))

        api().skipRoutine("tok_abc", routineId = 3)

        val sent = server.server.takeRequest()
        assertTrue(sent.target.endsWith("/api/v1/routines/3/skip"))
        assertTrue(sent.body!!.size == 0)
    }

    @Test
    fun `calling a routine enough hits its own url`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = standingsOutBody))

        api().callRoutineEnough("tok_abc", routineId = 3)

        assertTrue(server.server.takeRequest().target.endsWith("/api/v1/routines/3/enough"))
    }

    @Test
    fun `pausing a routine hits its own url`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = standingsOutBody))

        api().pauseRoutine("tok_abc", routineId = 3)

        assertTrue(server.server.takeRequest().target.endsWith("/api/v1/routines/3/pause"))
    }

    @Test
    fun `resuming a routine hits its own url`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = standingsOutBody))

        api().resumeRoutine("tok_abc", routineId = 3)

        assertTrue(server.server.takeRequest().target.endsWith("/api/v1/routines/3/resume"))
    }

    @Test
    fun `keeping a new routine posts its fields`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = standingsOutBody))

        api().createRoutine("tok_abc", "Practice Spanish", "daily", 5, "lessons")

        val sent = server.server.takeRequest()
        assertTrue(sent.target.endsWith("/api/v1/routines"))
        val body = org.json.JSONObject(sent.body!!.utf8())
        assertEquals("Practice Spanish", body.getString("title"))
        assertEquals("daily", body.getString("cadence"))
        assertEquals(5, body.getInt("target_quantity"))
        assertEquals("lessons", body.getString("unit"))
    }

    @Test
    fun `a missing scope is unauthorised`() = runTest {
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(DayWriteUnauthorised, api().pinFocus("tok_abc", "2026-08-11", 7))
    }

    @Test
    fun `a refused write reports Ninja's own detail message`() = runTest {
        server.server.enqueue(
            MockResponse(code = 409, body = """{"detail": "That routine is paused."}""")
        )

        val result = api().logRoutine("tok_abc", routineId = 3, amount = 1)

        assertEquals("That routine is paused.", (result as DayWriteRejected).message)
    }

    @Test
    fun `an unreachable host is a write failure`() = runTest {
        val offline = OkHttpDailyApi(baseUrl = "http://127.0.0.1:1/")

        assertTrue(offline.skipRoutine("tok_abc", 3) is DayWriteUnreachable)
    }
}
