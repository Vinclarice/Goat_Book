package com.vinclarice.capture

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.junit4.MockWebServerRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * The task verbs' network half.
 *
 * **Was `AgendaApiTest`**, and this is the half of it that survived
 * `android-overhaul-plan.md` increment 1: the agenda read went with its
 * screen, and completing and rescheduling stayed because the day still does
 * both. `createTask`'s test went too — it posted to
 * `/api/v1/areas/{id}/tasks`, and an Area is not somewhere a task gets made
 * on this client any more.
 *
 * Same conventions `DailyApiTest` uses: a real MockWebServer rather than a
 * stub, so "we send the right header/method/body" is a fact about bytes on a
 * socket rather than about a fake.
 */
class TaskApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpTaskApi(baseUrl = server.server.url("/").toString())

    /** A PATCH answers with TaskUpdateOut -- the task under "task", beside
     *  the successor a completion may have produced. */
    private val taskBody = """
        {"task": {"id": 7, "text": "Pay tmobile bill", "status": "completed",
         "due_date": "2026-07-31", "tags": ["bills"], "area_id": 3, "project_id": null},
         "spawned": null, "spawned_checklist_steps": []}
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
        val offline = OkHttpTaskApi(baseUrl = "http://127.0.0.1:1/")

        assertTrue(
            offline.setTaskStatus("tok_abc", 7, "completed") is TaskWriteUnreachable
        )
    }
}
