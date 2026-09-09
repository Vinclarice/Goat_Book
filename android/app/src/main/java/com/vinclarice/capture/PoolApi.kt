package com.vinclarice.capture

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONException
import org.json.JSONObject

/**
 * Every open line, in one list — android-overhaul-plan.md increment 3.
 *
 * The pool is what replaced the Agenda on September 4, 2026: not a set of
 * buckets somebody has to file into, but everything still open, with the
 * dated things in date order and everything else beside them.
 *
 * **This is the first increment of the overhaul that needed the server to
 * change**, and the change was one line: `GET /api/v1/pool` now accepts a
 * bearer with `agenda:read`. That widening is argued at the decorator and
 * pinned in `test_api_auth_surface.py`, and it is read-only — rule 8's *still
 * wanted?* stays session-only, because letting go of a task is a different
 * decision from reading the list.
 */

sealed interface PoolResult

data class PoolLoaded(val pool: PoolEntry) : PoolResult

data object PoolUnauthorised : PoolResult

data class PoolUnreachable(val reason: String) : PoolResult

data class PoolEntry(
    val today: String,
    /** Every open line, *before* any search narrowed the two lists below —
     *  which is what lets a header say how many there really are. */
    val openCount: Int,
    val fixed: List<PoolFixedRow>,
    val floating: List<PoolFloatingRow>,
)

/**
 * A line with a date on it, whichever kind of record it came from.
 *
 * **A tagged row rather than three lists**, mirroring the server: the pool's
 * fixed half is one sequence in date order with bills and appointments among
 * the tasks. Interleaving them here would mean this client deciding what a
 * date means, which is the server's job.
 */
data class PoolFixedRow(
    /** `task`, `bill` or `appointment` — exactly one of the three below is set. */
    val kind: String,
    val dueDate: String,
    /** Negative when it is already past. Computed on the server, because the
     *  account's zone decides what day it is and this device is not
     *  necessarily in it. */
    val daysUntil: Int,
    val task: TaskEntry?,
    val bill: PoolBillRef?,
    val appointment: AppointmentEntry?,
    val pickedFor: List<String>,
)

/** Only what a row needs to say which bill it is. The Money module is not on
 *  this client and nothing here opens one. */
data class PoolBillRef(val id: Int, val text: String)

data class PoolFloatingRow(
    val task: TaskEntry,
    /** How long ago it was written. Never resets. */
    val ageInDays: Int,
    /** Which of today and tomorrow this line is already chosen for, so a Pick
     *  control can say so rather than looking like it did nothing. */
    val pickedFor: List<String>,
    /** How long it has gone untouched — written, chosen or kept, whichever was
     *  latest. Not the same number as [ageInDays]. */
    val unpickedForDays: Int,
    /**
     * Whether the pool is asking about it — rule 8.
     *
     * **Read, never computed.** The server owns the threshold, so it stays in
     * one language; a client comparing [unpickedForDays] against a number of
     * its own would be the plan's mirrored constant arriving by the back door.
     */
    val asksToBeKept: Boolean,
)

interface PoolApi {
    /**
     * @param head the panel beside the day rather than the whole page — the
     *   same rows, narrowed by the server. Narrowing here instead would make
     *   [PoolEntry.openCount] a number about a different set from the one on
     *   screen.
     */
    suspend fun getPool(token: String, head: Boolean = false): PoolResult
}

class OkHttpPoolApi(
    private val baseUrl: String,
    private val client: OkHttpClient = OkHttpClariceApi.defaultClient(),
    /** What to call this server when telling somebody it refused or could
     *  not answer. Defaulted rather than threaded from `Backends` at every
     *  call site, because a split install renames the *capture* backend and
     *  these three only ever talk to the workspace one. */
    private val serverName: String = "Clarice",
) : PoolApi {

    override suspend fun getPool(token: String, head: Boolean): PoolResult =
        withContext(Dispatchers.IO) {
            val query = if (head) "?head=true" else ""
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/api/v1/pool" + query)
                .header("Authorization", "Bearer $token")
                .get()
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    when (response.code) {
                        200 -> parsePool(response.body.string())
                        // 403 joins 401: a token issued before the September 6
                        // widening has no `agenda:read`, and this client has
                        // nothing more useful to say about that than about an
                        // expired one.
                        401, 403 -> PoolUnauthorised
                        else -> PoolUnreachable(whatWentWrong(serverName, response.code))
                    }
                }
            } catch (failure: IOException) {
                PoolUnreachable(couldNotReach(serverName))
            }
        }

    private fun parsePool(body: String): PoolResult = try {
        val json = JSONObject(body)
        PoolLoaded(
            PoolEntry(
                today = json.getString("today"),
                openCount = json.getInt("open_count"),
                fixed = json.getJSONArray("fixed").map(::fixedRowFrom),
                floating = json.getJSONArray("floating").map(::floatingRowFrom),
            )
        )
    } catch (malformed: JSONException) {
        PoolUnreachable(couldNotUnderstand(serverName))
    }

    private fun fixedRowFrom(json: JSONObject) = PoolFixedRow(
        kind = json.getString("kind"),
        dueDate = json.getString("due_date"),
        daysUntil = json.getInt("days_until"),
        task = json.optJSONObject("task")?.let(::taskFrom),
        bill = json.optJSONObject("bill")?.let {
            PoolBillRef(id = it.getInt("id"), text = it.getString("text"))
        },
        appointment = json.optJSONObject("appointment")?.let(::appointmentFrom),
        pickedFor = json.getJSONArray("picked_for").strings(),
    )

    private fun floatingRowFrom(json: JSONObject) = PoolFloatingRow(
        task = taskFrom(json.getJSONObject("task")),
        ageInDays = json.getInt("age_in_days"),
        pickedFor = json.getJSONArray("picked_for").strings(),
        unpickedForDays = json.getInt("unpicked_for_days"),
        asksToBeKept = json.getBoolean("asks_to_be_kept"),
    )

    /** [TaskEntry] rather than a pool-shaped copy: a task is a task, and the
     *  two verbs `TaskApi` carries act on exactly this. */
    private fun taskFrom(json: JSONObject) = TaskEntry(
        id = json.getInt("id"),
        text = json.getString("text"),
        dueDate = json.optStringOrNull("due_date"),
        tags = json.getJSONArray("tags").strings(),
        areaId = json.optIntOrNull("area_id"),
        projectId = json.optIntOrNull("project_id"),
    )

    private fun appointmentFrom(json: JSONObject) = AppointmentEntry(
        publicId = json.getString("public_id"),
        text = json.getString("text"),
        startsOn = json.getString("starts_on"),
        endsOn = json.optStringOrNull("ends_on"),
        startsAt = json.optStringOrNull("starts_at"),
        endsAt = json.optStringOrNull("ends_at"),
        location = json.getString("location"),
        notes = json.getString("notes"),
        cancelled = json.getBoolean("cancelled"),
    )
}
