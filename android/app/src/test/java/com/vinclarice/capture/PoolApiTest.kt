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
 * The pool's network half -- android-overhaul-plan.md increment 3.
 *
 * The pool is what replaced the Agenda: every open line in one list, rather
 * than a set of buckets somebody has to file into. This is the first increment
 * of the Android overhaul that needed the server to change at all, and the
 * change was one line -- `GET /api/v1/pool` now takes a bearer with
 * `agenda:read`, argued at the decorator and pinned in
 * `test_api_auth_surface.py`.
 *
 * Same conventions as `DailyApiTest`: a real MockWebServer, so the header, the
 * method and the query are facts about bytes on a socket.
 */
class PoolApiTest {

    @get:Rule
    val server = MockWebServerRule()

    private fun api() = OkHttpPoolApi(baseUrl = server.server.url("/").toString())

    private val poolBody = """
        {
          "today": "2026-09-06",
          "open_count": 12,
          "fixed": [
            {"kind": "bill", "due_date": "2026-09-10", "days_until": 1,
             "task": null, "appointment": null,
             "bill": {"id": 12, "payee": "T-Mobile", "due_date": "2026-09-10",
               "amount": "84.00", "currency": "USD", "direction": "out",
               "repeats": true},
             "picked_for": []},
            {"kind": "appointment", "due_date": "2026-09-06", "days_until": 0,
             "task": null, "bill": null,
             "appointment": {"public_id": "3f2a1b4c-0000-4000-8000-000000000001",
               "text": "Dentist", "starts_on": "2026-09-06", "ends_on": null,
               "starts_at": "09:30:00", "ends_at": null, "location": "High Street",
               "notes": "", "cancelled": false},
             "picked_for": []}
          ],
          "floating": [
            {"task": {"id": 7, "text": "Write the plan doc", "status": "active",
              "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z",
              "completed_at": null, "archived_at": null, "due_date": null, "position": 0,
              "tags": ["work"], "recurrence": "none", "priority": "none", "lead_days": 0,
              "notes": "", "area_id": 3, "project_id": null, "url": "/app/tasks/7"},
             "age_in_days": 36, "picked_for": ["today"], "unpicked_for_days": 22,
             "asks_to_be_kept": true}
          ]
        }
    """.trimIndent()

    @Test
    fun `the pool arrives as two lists and a count of the whole thing`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = poolBody))

        val result = api().getPool("tok_abc") as PoolLoaded

        // `open_count` is the whole pool before any search narrowed the two
        // arrays, which is what lets a header say how many there really are.
        assertEquals(12, result.pool.openCount)
        // Two since September 9, 2026: a bill joined the fixture when it
        // turned out the bill branch had never been exercised.
        assertEquals(2, result.pool.fixed.size)
        assertEquals(1, result.pool.floating.size)
    }

    @Test
    fun `a floating line carries its staleness and whether the pool is asking`() = runTest {
        // **The server decides `asks_to_be_kept`**, so the threshold stays in
        // one language. A client comparing `unpicked_for_days` against a
        // number of its own would be D8's mirrored constant arriving by the
        // back door -- and this client has no business holding that number.
        server.server.enqueue(MockResponse(code = 200, body = poolBody))

        val row = (api().getPool("tok_abc") as PoolLoaded).pool.floating[0]

        assertEquals(22, row.unpickedForDays)
        assertEquals(36, row.ageInDays)
        assertTrue(row.asksToBeKept)
        assertEquals(listOf("today"), row.pickedFor)
    }

    @Test
    fun `a fixed row says what kind of thing it is`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = poolBody))

        val row = (api().getPool("tok_abc") as PoolLoaded).pool.fixed
            .first { it.kind == "appointment" }

        assertEquals("appointment", row.kind)
        assertEquals(0, row.daysUntil)
        assertEquals("Dentist", row.appointment?.text)
        assertEquals(null, row.task)
    }

    @Test
    fun `the token travels as a bearer credential`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = poolBody))

        api().getPool("tok_abc")

        val sent = server.server.takeRequest()
        assertEquals("GET", sent.method)
        assertEquals("Bearer tok_abc", sent.headers["Authorization"])
        assertTrue(sent.target.contains("/api/v1/pool"))
    }

    @Test
    fun `asking for the head asks the server rather than slicing here`() = runTest {
        // `head=true` is the panel beside the day rather than the page -- the
        // same rows, narrowed to what fits in a column. Narrowing on the
        // client would make `open_count` a number about a different set from
        // the one on screen.
        server.server.enqueue(MockResponse(code = 200, body = poolBody))

        api().getPool("tok_abc", head = true)

        assertTrue(server.server.takeRequest().target.contains("head=true"))
    }

    @Test
    fun `a rejected token is unauthorised`() = runTest {
        server.server.enqueue(MockResponse(code = 401))

        assertEquals(PoolUnauthorised, api().getPool("tok_abc"))
    }

    @Test
    fun `a token without the scope is unauthorised too`() = runTest {
        // The widening is `agenda:read` only. A token issued before September
        // 6, 2026 without that scope answers 403 here, and the client has
        // nothing more useful to say about it than about a 401.
        server.server.enqueue(MockResponse(code = 403))

        assertEquals(PoolUnauthorised, api().getPool("tok_abc"))
    }

    @Test
    fun `a server fault is worth retrying`() = runTest {
        server.server.enqueue(MockResponse(code = 503))

        assertTrue(api().getPool("tok_abc") is PoolUnreachable)
    }

    @Test
    fun `a malformed body is a failure rather than a crash`() = runTest {
        server.server.enqueue(MockResponse(code = 200, body = "not json at all"))

        assertTrue(api().getPool("tok_abc") is PoolUnreachable)
    }

    @Test
    fun `an unreachable host is a failure`() = runTest {
        val offline = OkHttpPoolApi(baseUrl = "http://127.0.0.1:1/")

        assertTrue(offline.getPool("tok_abc") is PoolUnreachable)
    }

    @Test
    fun `an empty pool parses to empty rather than to an error`() = runTest {
        server.server.enqueue(
            MockResponse(
                code = 200,
                body = """{"today": "2026-09-06", "open_count": 0, "fixed": [], "floating": []}""",
            )
        )

        val result = api().getPool("tok_abc") as PoolLoaded

        assertEquals(0, result.pool.openCount)
        assertTrue(result.pool.floating.isEmpty())
        assertFalse(result.pool.today.isEmpty())
    }

    @Test
    fun `a bill row parses, which it did not until September 9 2026`() = runTest {
        /* **The bug this test exists for, and how it hid.**
           `PoolBillRef` read `text` off a bill. `AgendaBillOut` has no such
           field — a bill is a `payee`, an `amount` and a direction — so
           `getString("text")` threw, the whole payload failed to parse, and
           the pool section said it could not read the answer.

           It survived three days because the fixture above carried
           `"bill": null` in its only fixed row. The bill branch was written
           and never exercised, so the test proved the parser against a shape
           this server does not send. **A fixture invented rather than copied
           is a test of the imagination**, and the fix is the row now sitting
           at the top of `poolBody`, taken field for field from
           `money/api_v1.py`.

           Found on a real phone against real data, by the failure message
           shipped an hour earlier — which is the argument for that message
           making itself. */
        server.server.enqueue(MockResponse(code = 200, body = poolBody))

        val result = api().getPool("tok_abc") as PoolLoaded

        val bill = result.pool.fixed.first { it.kind == "bill" }
        assertEquals("T-Mobile", bill.bill?.payee)
        assertEquals("84.00", bill.bill?.amount)
        assertEquals("out", bill.bill?.direction)
    }

    @Test
    fun `every row the server can send parses in one payload`() = runTest {
        // The regression guard for the shape of the bug rather than the bug:
        // `fixed` is a tagged row and one unparseable kind takes the whole
        // pool down with it, so all three belong in one fixture.
        server.server.enqueue(MockResponse(code = 200, body = poolBody))

        val pool = (api().getPool("tok_abc") as PoolLoaded).pool

        assertEquals(setOf("bill", "appointment"), pool.fixed.map { it.kind }.toSet())
        assertEquals(1, pool.floating.size)
    }
}
