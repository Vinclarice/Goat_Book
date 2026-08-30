package com.vinclarice.capture

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONException
import org.json.JSONObject

sealed interface AgendaResult

data class AgendaLoaded(val agenda: AgendaEntry) : AgendaResult

data object AgendaUnauthorised : AgendaResult

data class AgendaUnreachable(val reason: String) : AgendaResult

/**
 * What happened when a task write was attempted -- complete/reopen,
 * reschedule, or quick-add, the three actions android-full-client-plan.md
 * §7 scopes this slice to.
 *
 * [TaskWriteUnauthorised] covers both a plain 401 (bad/expired/wrong-scope
 * token) and item_detail's own 403 field/method guard
 * (token-scopes-plan.md §7) -- Android has nothing more specific to say
 * about either, so it doesn't pretend to.
 */
sealed interface TaskWriteResult

data class TaskWriteSucceeded(val task: AgendaTaskEntry) : TaskWriteResult

data object TaskWriteUnauthorised : TaskWriteResult

/** A 400/404/409 the server explained -- an invalid date, a task that's
 *  gone, a conflicting transition. [message] is the server's own text. */
data class TaskWriteRejected(val message: String) : TaskWriteResult

data class TaskWriteUnreachable(val reason: String) : TaskWriteResult

interface AgendaApi {
    suspend fun getAgenda(token: String): AgendaResult

    /** [status] is the server's own vocabulary ("active"/"completed") --
     *  see Item.Status; there is no richer type here for the same reason
     *  DailyModels' own FocusEntry.status stays a plain string. */
    suspend fun setTaskStatus(token: String, taskId: Int, status: String): TaskWriteResult

    /** [dueDate] null clears the due date -- a real, distinct request from
     *  "don't change it", which is why this takes an explicit nullable
     *  rather than being skipped when absent. */
    suspend fun rescheduleTask(token: String, taskId: Int, dueDate: String?): TaskWriteResult

    suspend fun createTask(
        token: String,
        areaId: Int,
        text: String,
        dueDate: String?,
    ): TaskWriteResult
}

/**
 * Talks to `/api/v1/` and nothing else, since August 30, 2026.
 *
 * **It used to take urls out of the agenda payload and post to them** --
 * `url` on each task, `create_item_url` on each area -- which reached
 * `lists.api`'s hand-rolled views, on a different auth mechanism from the
 * agenda read beside them. coherence-audit-2026-08-30.md F2 moved every task
 * write onto the typed Ninja router, so this addresses `/api/v1/tasks/{id}`
 * and `/api/v1/areas/{id}/tasks` by id instead, and the two mechanisms became
 * one.
 *
 * **The build in Vince's pocket still uses the old urls**, which is why the
 * server keeps serving them and keeps sending both fields. This client is what
 * makes retiring them possible; what it waits on is
 * `android-release-signing-plan.md`'s keystore, without which no signed
 * release can carry it.
 */
class OkHttpAgendaApi(
    private val baseUrl: String,
    private val client: OkHttpClient = OkHttpClariceApi.defaultClient(),
) : AgendaApi {

    override suspend fun getAgenda(token: String): AgendaResult =
        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/api/v1/agenda")
                .header("Authorization", "Bearer $token")
                .get()
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    when (response.code) {
                        200 -> parseAgenda(response.body.string())
                        401, 403 -> AgendaUnauthorised
                        else -> AgendaUnreachable("Clarice answered ${response.code}.")
                    }
                }
            } catch (failure: IOException) {
                AgendaUnreachable("Could not reach Clarice.")
            }
        }

    override suspend fun setTaskStatus(
        token: String,
        taskId: Int,
        status: String,
    ): TaskWriteResult =
        patchTask(token, taskId, JSONObject().put("status", status))

    override suspend fun rescheduleTask(
        token: String,
        taskId: Int,
        dueDate: String?,
    ): TaskWriteResult =
        patchTask(token, taskId, JSONObject().put("due_date", dueDate ?: JSONObject.NULL))

    override suspend fun createTask(
        token: String,
        areaId: Int,
        text: String,
        dueDate: String?,
    ): TaskWriteResult = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("text", text)
            .put("due_date", dueDate ?: JSONObject.NULL)
        val request = Request.Builder()
            .url(taskEndpoint("/api/v1/areas/" + areaId + "/tasks"))
            .header("Authorization", "Bearer $token")
            .post(body.toString().toRequestBody(JSON))
            .build()
        executeWrite(request)
    }

    private suspend fun patchTask(
        token: String,
        taskId: Int,
        body: JSONObject,
    ): TaskWriteResult = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(taskEndpoint("/api/v1/tasks/" + taskId))
            .header("Authorization", "Bearer $token")
            .patch(body.toString().toRequestBody(JSON))
            .build()
        executeWrite(request)
    }

    private fun executeWrite(request: Request): TaskWriteResult = try {
        client.newCall(request).execute().use { response ->
            when (response.code) {
                200, 201 -> parseTaskWrite(response.body.string())
                401, 403 -> TaskWriteUnauthorised
                // 422 joins them: the typed router validates enums at the
                // boundary, so an unknown status or an unparseable date is a
                // schema rejection now rather than a hand-written 400.
                400, 404, 409, 422 ->
                    TaskWriteRejected(errorMessageFrom(response.body.string()))
                else -> TaskWriteUnreachable("Clarice answered ${response.code}.")
            }
        }
    } catch (failure: IOException) {
        TaskWriteUnreachable("Could not reach Clarice.")
    }

    /** Absolute, because okhttp needs one and these paths are ours now.
     *
     * Was `absoluteUrl`, which accepted a whole url from the payload and only
     * prefixed a relative one. Nothing hands this client a url any more, so
     * the "already absolute" branch had no caller left.
     */
    private fun taskEndpoint(path: String) = baseUrl.trimEnd('/') + path

    private fun parseAgenda(body: String): AgendaResult = try {
        val json = JSONObject(body)
        AgendaLoaded(
            AgendaEntry(
                today = json.getString("today"),
                items = json.getJSONArray("items").map(::taskEntryFrom),
                completedToday = json.getJSONArray("completed_today").map(::taskEntryFrom),
                areas = json.getJSONArray("areas").map(::areaEntryFrom),
                projects = json.getJSONArray("projects").map(::projectEntryFrom),
            )
        )
    } catch (malformed: JSONException) {
        AgendaUnreachable("Unexpected response from that address.")
    }

    /** A created task comes back bare; an updated one comes back under
     *  "task", beside the successor a completion may have produced. The
     *  endpoint this replaces wrapped both in "data". */
    private fun parseTaskWrite(body: String): TaskWriteResult = try {
        val json = JSONObject(body)
        val task = if (json.has("task")) json.getJSONObject("task") else json
        TaskWriteSucceeded(taskEntryFrom(task))
    } catch (malformed: JSONException) {
        TaskWriteUnreachable("Unexpected response from that address.")
    }

    /** Ninja's `{"detail": "..."}`.
     *
     * **This comment used to say that shape did not apply here**, because
     * `lists.api` answered `{"errors": {"<field>": ["<message>"]}}`. It does
     * now. A 422 carries a list rather than a string, which only happens when
     * this client sends something its own contract forbids, so it falls
     * through to the generic line rather than rendering pydantic at a person.
     */
    private fun errorMessageFrom(body: String): String = try {
        JSONObject(body).getString("detail")
    } catch (malformed: JSONException) {
        "Clarice would not accept that."
    }

    private fun taskEntryFrom(json: JSONObject) = AgendaTaskEntry(
        id = json.getInt("id"),
        text = json.getString("text"),
        dueDate = json.optStringOrNull("due_date"),
        tags = json.getJSONArray("tags").let { tags -> (0 until tags.length()).map(tags::getString) },
        areaId = json.optIntOrNull("area_id"),
        projectId = json.optIntOrNull("project_id"),
        // `url` is still in the payload and deliberately unread -- the server
        // keeps sending it for the build that came before this one.
    )

    private fun areaEntryFrom(json: JSONObject) = AgendaAreaEntry(
        id = json.getInt("id"),
        title = json.getString("title"),
        colorKey = json.getString("color_key"),
        openCount = json.getInt("open_count"),
        overdueCount = json.getInt("overdue_count"),
        // `create_item_url` likewise: quick-add posts to
        // /api/v1/areas/{id}/tasks now, and the field survives for the
        // shipped build.
    )

    private fun projectEntryFrom(json: JSONObject) = AgendaProjectEntry(
        id = json.getInt("id"),
        title = json.getString("title"),
    )
}
