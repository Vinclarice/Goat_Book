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
 * DailyApi's network half, against a real HTTP server rather than a stub --
 * same convention ClariceApiTest already uses, and the same reason: "we
 * send the right header" should be a fact about bytes on a socket.
 */
class DailyApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpDailyApi(baseUrl = server.server.url("/").toString())

    private val fullDayBody = """
        {
          "date": "2026-08-10",
          "today": "2026-08-10",
          "intentions": "Ship the Daily slice",
          "gratitude": "Coffee",
          "happenings": "",
          "compass_purpose": "Build something that lasts",
          "compass_question": "What matters today?",
          "focus": [
            {"task_id": 7, "text": "Write the plan doc", "status": "active", "due_date": null, "selected_at": "2026-08-10T09:00:00Z"}
          ],
          "action_items": [
            {"id": 7, "text": "Write the plan doc", "status": "active", "created_at": "2026-08-01T00:00:00Z",
             "updated_at": "2026-08-01T00:00:00Z", "completed_at": null, "archived_at": null,
             "due_date": "2026-08-10", "position": 0, "tags": [], "recurrence": "none", "notes": "",
             "area_id": 3, "project_id": null, "url": "/app/tasks/7", "edit_url": "/app/tasks/7/edit",
             "age_in_days": 9}
          ],
          "areas": [{"id": 3, "title": "Clarice", "url": "/app/areas/3", "color_key": "sky"}],
          "projects": [],
          "shows_action_items": true,
          "routines": [
            {"routine_id": 1, "title": "Practice Spanish", "cadence": "daily", "period_start": "2026-08-10",
             "progress": 1, "target": 1, "unit": "", "outcome": "open", "is_met": true}
          ],
          "routines_are_loggable": true,
          "paused_routines": []
        }
    """.trimIndent()

    @Test
    fun `an action item with no area parses instead of blanking the day`() = runTest {
        // Same defect as AgendaApi's, same cause, same one-line-away idiom:
        // getInt("area_id") directly above optIntOrNull("project_id"). The
        // catch is at payload level, so one unfiled task emptied the Today
        // tab rather than its own row.
        val unfiledBody = fullDayBody.replace("\"area_id\": 3", "\"area_id\": null")
        server.server.enqueue(MockResponse(code = 200, body = unfiledBody))

        val result = api().getToday("tok_abc") as DayLoaded

        assertEquals(1, result.day.actionItems.size)
        assertEquals("Write the plan doc", result.day.actionItems[0].text)
        assertEquals(null, result.day.actionItems[0].areaId)
    }

    @Test
    fun `a successful response parses the whole day`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        val result = api().getToday("tok_abc") as DayLoaded

        assertEquals("2026-08-10", result.day.date)
        assertEquals("Ship the Daily slice", result.day.intentions)
        assertEquals("Build something that lasts", result.day.compassPurpose)
        assertTrue(result.day.isToday)
        assertEquals(1, result.day.focus.size)
        assertEquals(7, result.day.focus[0].taskId)
        assertEquals(1, result.day.actionItems.size)
        assertEquals(9, result.day.actionItems[0].ageInDays)
        assertEquals(3, result.day.actionItems[0].areaId)
        assertEquals(1, result.day.areas.size)
        assertEquals("Clarice", result.day.areas[0].title)
        assertTrue(result.day.showsActionItems)
        assertEquals(1, result.day.routines.size)
        assertTrue(result.day.routines[0].isMet)
        assertTrue(result.day.routinesAreLoggable)
        assertTrue(result.day.pausedRoutines.isEmpty())
    }

    @Test
    fun `the token travels as a bearer credential to day`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        api().getToday("tok_abc")

        val sent = server.server.takeRequest()
        assertEquals("Bearer tok_abc", sent.headers["Authorization"])
        assertEquals("GET", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/day"))
    }

    @Test
    fun `a rejected token is reported as unauthorised`() = runTest {
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(DayUnauthorised, api().getToday("tok_bad"))
    }

    @Test
    fun `a forbidden token is unauthorised too`() = runTest {
        server.server.enqueue(MockResponse(code = 403))

        assertEquals(DayUnauthorised, api().getToday("tok_bad"))
    }

    @Test
    fun `a server fault is a failure worth retrying`() = runTest {
        server.server.enqueue(MockResponse(code = 503))

        assertTrue(api().getToday("tok_abc") is DayUnreachable)
    }

    @Test
    fun `an unreachable host is a failure`() = runTest {
        val offline = OkHttpDailyApi(baseUrl = "http://127.0.0.1:1/")

        assertTrue(offline.getToday("tok_abc") is DayUnreachable)
    }

    @Test
    fun `a malformed body is a failure rather than a crash`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = "not json at all"))

        assertTrue(api().getToday("tok_abc") is DayUnreachable)
    }

    @Test
    fun `an empty focus and paused list parse to empty, not an error`() = runTest {
        server.server.enqueue(
            MockResponse(
                code = 200,
                body = """
                    {
                      "date": "2026-08-03", "today": "2026-08-10",
                      "intentions": "", "gratitude": "", "happenings": "",
                      "compass_purpose": "", "compass_question": "",
                      "focus": [], "action_items": [], "areas": [], "projects": [],
                      "shows_action_items": false,
                      "routines": [], "routines_are_loggable": false, "paused_routines": []
                    }
                """.trimIndent(),
            )
        )

        val result = api().getToday("tok_abc") as DayLoaded

        assertFalse(result.day.isToday)
        assertFalse(result.day.showsActionItems)
        assertTrue(result.day.focus.isEmpty())
        assertTrue(result.day.actionItems.isEmpty())
    }
}
