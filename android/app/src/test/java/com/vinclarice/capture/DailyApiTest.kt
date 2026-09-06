package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
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
          "list_closed_at": "2026-08-10T14:30:00Z",
          "closing": {
            "chosen": 3, "finished": 1, "unfinished": 2, "released": 0,
            "joined": 1, "joined_finished": 1,
            "leftovers": [
              {"task_id": 7, "text": "Write the plan doc", "above_the_line": true,
               "moved_to_tomorrow": false},
              {"task_id": 9, "text": "Joined after the work started",
               "above_the_line": false, "moved_to_tomorrow": true}
            ]
          },
          "focus": [
            {"task_id": 7, "text": "Write the plan doc", "status": "active", "due_date": null,
             "selected_at": "2026-08-10T09:00:00Z", "above_the_line": true},
            {"task_id": 9, "text": "Joined after the work started", "status": "active", "due_date": null,
             "selected_at": "2026-08-10T16:00:00Z", "above_the_line": false}
          ],
          "appointments": [
            {"public_id": "3f2a1b4c-0000-4000-8000-000000000001", "text": "Dentist",
             "starts_on": "2026-08-10", "ends_on": null, "starts_at": "09:30:00", "ends_at": null,
             "location": "High Street", "notes": "", "cancelled": false}
          ],
          "appointments_coming": [
            {"public_id": "3f2a1b4c-0000-4000-8000-000000000002", "text": "Standup",
             "starts_on": "2026-08-12", "ends_on": null, "starts_at": null, "ends_at": null,
             "location": "", "notes": "", "cancelled": true}
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
        // The fixture above still carries `intentions`, `gratitude` and
        // `happenings`, deliberately: the server still sends all three, and a
        // parser that broke on a field it no longer reads would be a worse
        // client than one that ignores it. What went on September 6, 2026 is
        // the assertion, not the fixture.
        assertEquals("Build something that lasts", result.day.compassPurpose)
        assertTrue(result.day.isToday)
        // Two focus rows since September 6, 2026, not one: the fixture now
        // carries one pinned before the line and one after it, which is what
        // makes `above_the_line` testable at all.
        assertEquals(2, result.day.focus.size)
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
                      "list_closed_at": null,
                      "focus": [], "action_items": [], "areas": [], "projects": [],
                      "appointments": [], "appointments_coming": [],
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

    /* android-overhaul-plan.md increment 2: the day as it now is. Every field
       below already arrives in the payload this client has been fetching since
       August -- what was missing was a model that named them. */

    @Test
    fun `the line arrives as the day's own instant`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        val result = api().getToday("tok_abc") as DayLoaded

        assertEquals("2026-08-10T14:30:00Z", result.day.listClosedAt)
    }

    @Test
    fun `a day whose list is still open has no line`() = runTest {
        // superlists-2.0-plan.md rule 11 keeps `list_closed_at` null until
        // something is executed, so null is the ordinary morning rather than
        // an error, and a client that treated it as one would show a line at
        // nothing on every day before the first tick.
        server.server.enqueue(
            MockResponse(code = 200, body = fullDayBody.replace(
                """"list_closed_at": "2026-08-10T14:30:00Z",""",
                """"list_closed_at": null,""",
            ))
        )

        val result = api().getToday("tok_abc") as DayLoaded

        assertNull(result.day.listClosedAt)
    }

    @Test
    fun `each pinned task says which side of the line it is on`() = runTest {
        // **Read, never computed.** `FocusOut.above_the_line` is derived on the
        // server from selected_at against list_closed_at, and its own comment
        // says why it is sent rather than left to the client: the comparison is
        // on timestamps in the owner's zone. That argument is stronger on a
        // phone, which can be in any zone at all.
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        val result = api().getToday("tok_abc") as DayLoaded

        assertTrue(result.day.focus[0].aboveTheLine)
        assertFalse(result.day.focus[1].aboveTheLine)
    }

    @Test
    fun `the day carries what is happening and what is coming`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        val result = api().getToday("tok_abc") as DayLoaded

        assertEquals("Dentist", result.day.appointments[0].text)
        assertEquals("09:30:00", result.day.appointments[0].startsAt)
        assertEquals("High Street", result.day.appointments[0].location)
        assertEquals("Standup", result.day.appointmentsComing[0].text)
    }

    @Test
    fun `a cancelled appointment arrives rather than being filtered away`() = runTest {
        // Rule 6: a cancelled appointment stays visible and struck. Dropping it
        // here would make "it was cancelled" and "it never existed" the same
        // thing on a phone.
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        val result = api().getToday("tok_abc") as DayLoaded

        assertTrue(result.day.appointmentsComing[0].cancelled)
        assertFalse(result.day.appointments[0].cancelled)
    }

    /* android-overhaul-plan.md increment 4: the evening. */

    @Test
    fun `the day reads itself back with what it held`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        val closing = (api().getToday("tok_abc") as DayLoaded).day.closing

        assertEquals(3, closing?.chosen)
        assertEquals(1, closing?.finished)
        // Counted apart from `chosen` and never folded into it -- rule 4: a
        // day with three chosen and four unplanned done is a good day this can
        // say so about.
        assertEquals(1, closing?.joined)
        assertEquals(1, closing?.joinedFinished)
    }

    @Test
    fun `a released pin is reported apart from what is still open`() = runTest {
        // "I decided this wasn't for today" and "I never got to it" are
        // different facts, and one number over both would be one nobody should
        // act on.
        server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

        val closing = (api().getToday("tok_abc") as DayLoaded).day.closing

        assertEquals(0, closing?.released)
        assertEquals(2, closing?.unfinished)
    }

    @Test
    fun `each leftover says which side of the line it fell and whether it is decided`() =
        runTest {
            server.server.enqueue(MockResponse(code = 200, body = fullDayBody))

            val leftovers = (api().getToday("tok_abc") as DayLoaded).day.closing!!.leftovers

            assertEquals(2, leftovers.size)
            assertTrue(leftovers[0].aboveTheLine)
            assertFalse(leftovers[0].movedToTomorrow)
            assertTrue(leftovers[1].movedToTomorrow)
        }

    @Test
    fun `a day with nothing to read back yet has no closing at all`() = runTest {
        // `closing` is null before the evening and on any day but today --
        // `reads.closing_for` returns None rather than an empty summary, so a
        // client treating null as "nothing happened" would say something false
        // at two in the afternoon.
        server.server.enqueue(
            MockResponse(
                code = 200,
                body = """
                    {
                      "date": "2026-08-03", "today": "2026-08-10",
                      "intentions": "", "gratitude": "", "happenings": "",
                      "compass_purpose": "", "compass_question": "",
                      "list_closed_at": null, "closing": null,
                      "focus": [], "action_items": [], "areas": [], "projects": [],
                      "appointments": [], "appointments_coming": [],
                      "shows_action_items": false,
                      "routines": [], "routines_are_loggable": false, "paused_routines": []
                    }
                """.trimIndent(),
            )
        )

        val result = api().getToday("tok_abc") as DayLoaded

        assertNull(result.day.closing)
    }
}
