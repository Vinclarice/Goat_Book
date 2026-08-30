package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * AgendaApi's network half -- android-full-client-plan.md slice 2. Same
 * conventions DailyApiTest already uses: a real MockWebServer rather than
 * a stub, so "we send the right header/method/body" is a fact about bytes
 * on a socket.
 */
class AgendaApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpAgendaApi(baseUrl = server.server.url("/").toString())

    private val agendaBody = """
        {
          "today": "2026-08-11",
          "items": [
            {"id": 7, "text": "Pay tmobile bill", "status": "active", "created_at": "2026-07-29T00:00:00Z",
             "updated_at": "2026-07-29T00:00:00Z", "completed_at": null, "archived_at": null,
             "due_date": "2026-07-31", "position": 0, "tags": ["bills"], "recurrence": "none", "notes": "",
             "area_id": 3, "project_id": null, "url": "/api/items/7/", "edit_url": "/app/tasks/7/edit"}
          ],
          "completed_today": [],
          "areas": [
            {"id": 3, "title": "House hold", "url": "/app/areas/3", "create_item_url": "/api/areas/3/items/",
             "open_count": 1, "overdue_count": 1, "color_key": "sky"}
          ],
          "projects": []
        }
    """.trimIndent()

    @Test
    fun `a successful response parses the whole agenda`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = agendaBody))

        val result = api().getAgenda("tok_abc") as AgendaLoaded

        assertEquals("2026-08-11", result.agenda.today)
        assertEquals(1, result.agenda.items.size)
        assertEquals("Pay tmobile bill", result.agenda.items[0].text)
        assertEquals(listOf("bills"), result.agenda.items[0].tags)
        assertTrue(result.agenda.completedToday.isEmpty())
        assertEquals(1, result.agenda.areas.size)
        assertEquals("House hold", result.agenda.areas[0].title)
        assertEquals(1, result.agenda.areas[0].overdueCount)
    }

    @Test
    fun `a task with no area parses instead of discarding the whole agenda`() = runTest {
        // `Item.list` went nullable on the server on August 14; this parser
        // kept reading area_id with getInt, which throws. The catch sits at
        // payload level, so one unfiled task did not lose its own row -- it
        // emptied the Agenda tab and reported a wrong server address. An
        // unfiled task is one tap away in the knowledge core.
        //
        // The idiom was already here: project_id on the very next line.
        val unfiledBody = agendaBody.replace("\"area_id\": 3", "\"area_id\": null")
        server.server.enqueue(MockResponse(code = 200, body = unfiledBody))

        val result = api().getAgenda("tok_abc") as AgendaLoaded

        assertEquals(1, result.agenda.items.size)
        assertEquals("Pay tmobile bill", result.agenda.items[0].text)
        assertEquals(null, result.agenda.items[0].areaId)
    }

    @Test
    fun `the token travels as a bearer credential to agenda`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = agendaBody))

        api().getAgenda("tok_abc")

        val sent = server.server.takeRequest()
        assertEquals("Bearer tok_abc", sent.headers["Authorization"])
        assertEquals("GET", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/agenda"))
    }

    @Test
    fun `a rejected agenda token is unauthorised`() = runTest {
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(AgendaUnauthorised, api().getAgenda("tok_bad"))
    }

    @Test
    fun `a server fault reading the agenda is a failure worth retrying`() = runTest {
        server.server.enqueue(MockResponse(code = 503))

        assertTrue(api().getAgenda("tok_abc") is AgendaUnreachable)
    }

    @Test
    fun `a malformed agenda body is a failure rather than a crash`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = "not json at all"))

        assertTrue(api().getAgenda("tok_abc") is AgendaUnreachable)
    }

    /** A PATCH answers with TaskUpdateOut -- the task under "task", beside
     *  the successor a completion may have produced. */
    private val taskBody = """
        {"task": {"id": 7, "text": "Pay tmobile bill", "status": "completed",
         "due_date": "2026-07-31", "tags": ["bills"], "area_id": 3, "project_id": null},
         "spawned": null, "spawned_checklist_steps": []}
    """.trimIndent()

    /** A create answers with the task itself, unwrapped. */
    private val createdBody = """
        {"id": 7, "text": "Pay tmobile bill", "status": "active",
         "due_date": "2026-07-31", "tags": ["bills"], "area_id": 3, "project_id": null}
    """.trimIndent()

    @Test
    fun `completing a task sends the status field as a PATCH`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = taskBody))

        val result = api().setTaskStatus("tok_abc", 7, "completed")

        val sent = server.server.takeRequest()
        assertEquals("PATCH", sent.method)
        assertEquals("Bearer tok_abc", sent.headers["Authorization"])
        assertTrue(sent.target.endsWith("/api/v1/tasks/7"))
        assertEquals("""{"status":"completed"}""", sent.body!!.utf8())
        assertEquals(7, (result as TaskWriteSucceeded).task.id)
    }

    @Test
    fun `rescheduling a task sends the due_date field`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = taskBody))

        api().rescheduleTask("tok_abc", 7, "2026-08-15")

        val sent = server.server.takeRequest()
        assertEquals("""{"due_date":"2026-08-15"}""", sent.body!!.utf8())
    }

    @Test
    fun `clearing a tasks due date sends a null`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = taskBody))

        api().rescheduleTask("tok_abc", 7, null)

        val sent = server.server.takeRequest()
        assertEquals("""{"due_date":null}""", sent.body!!.utf8())
    }

    @Test
    fun `creating a task posts to the areas own create_item_url`() = runTest {
        server.server.enqueue(MockResponse(code = 201, body = taskBody))

        val result = api().createTask("tok_abc", 3, "Call the vet", null)

        val sent = server.server.takeRequest()
        assertEquals("POST", sent.method)
        assertTrue(sent.target.endsWith("/api/v1/areas/3/tasks"))
        assertTrue(result is TaskWriteSucceeded)
    }

    @Test
    fun `a write refused for missing scope is unauthorised`() = runTest {
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(
            TaskWriteUnauthorised,
            api().setTaskStatus("tok_abc", 7, "completed"),
        )
    }

    @Test
    fun `a write a token cant reach at all -- like editing text -- is unauthorised too`() = runTest {
        // item_detail's own field guard answers 403, not 401 -- both mean
        // "this token cannot do that", and Android has nothing useful to
        // say differently about either.
        server.server.enqueue(MockResponse(code = 403))

        assertEquals(
            TaskWriteUnauthorised,
            api().setTaskStatus("tok_abc", 7, "completed"),
        )
    }

    @Test
    fun `a validation failure is rejected with the servers own message`() = runTest {
        server.server.enqueue(
            MockResponse(
                code = 400,
                body = """{"detail": "Use a valid date (YYYY-MM-DD)."}""",
            )
        )

        val result = api().rescheduleTask("tok_abc", 7, "not-a-date")

        assertEquals(
            "Use a valid date (YYYY-MM-DD).",
            (result as TaskWriteRejected).message,
        )
    }

    @Test
    fun `a task that no longer exists is rejected`() = runTest {
        server.server.enqueue(
            MockResponse(code = 404, body = """{"detail": "Task not found."}""")
        )

        assertTrue(
            api().setTaskStatus("tok_abc", 999, "completed") is TaskWriteRejected
        )
    }

    @Test
    fun `an unreachable host is a write failure`() = runTest {
        val offline = OkHttpAgendaApi(baseUrl = "http://127.0.0.1:1/")

        assertTrue(
            offline.setTaskStatus("tok_abc", 7, "completed") is TaskWriteUnreachable
        )
    }
}
