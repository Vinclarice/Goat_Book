package com.vinclarice.capture

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONException
import org.json.JSONObject

/**
 * The task verbs, and nothing about an agenda.
 *
 * **Was `AgendaApi`, split on September 6, 2026** —
 * `android-overhaul-plan.md` increment 1. That interface did two jobs: it read
 * `/api/v1/agenda` for a screen, and it carried the two task writes
 * [DailyViewModel] borrows. The Agenda was deleted from the website on
 * September 4 and its screen went with it here; the verbs stayed, because the
 * day still completes and reschedules things.
 *
 * Renamed rather than emptied in place. A file called `AgendaApi` with no
 * agenda in it is exactly the stale name this overhaul exists to find, and
 * `DailyViewModel` already documents borrowing these rather than growing a
 * second copy — *one rule, one authoritative definition*.
 *
 * **`createTask` did not survive the split.** It took an `areaId`, and Areas
 * left the navigation on September 4; its only caller was the Agenda screen.
 * How a task gets made on a phone is **A1** in the plan — the composer posts
 * to `/api/v1/capture`, which this client already reaches. The server keeps
 * `POST /api/v1/areas/{area_id}/tasks` regardless: the build in Vince's pocket
 * still calls it, and a shipped APK is what pins it.
 */

/**
 * What happened when a task write was attempted.
 *
 * [TaskWriteUnauthorised] covers both a plain 401 (bad/expired/wrong-scope
 * token) and item_detail's own 403 field/method guard
 * (token-scopes-plan.md §7) -- Android has nothing more specific to say
 * about either, so it doesn't pretend to.
 */
sealed interface TaskWriteResult

data class TaskWriteSucceeded(val task: TaskEntry) : TaskWriteResult

data object TaskWriteUnauthorised : TaskWriteResult

/** A 400/404/409 the server explained -- an invalid date, a task that's
 *  gone, a conflicting transition. [message] is the server's own text. */
data class TaskWriteRejected(val message: String) : TaskWriteResult

data class TaskWriteUnreachable(val reason: String) : TaskWriteResult

/**
 * One task, as a write answers with it.
 *
 * **Was `AgendaTaskEntry`**, and the only model to survive `AgendaModels.kt`:
 * `AgendaEntry`, `AgendaAreaEntry` and `AgendaProjectEntry` described a
 * screen that no longer exists on either client.
 *
 * `areaId` and `projectId` are kept although nothing renders them, because
 * they are what the server sends and dropping a field from a parser is a
 * different decision from dropping it from a screen — see the plan's A3,
 * which is about not answering a deferred question by accident.
 */
data class TaskEntry(
    val id: Int,
    val text: String,
    val dueDate: String?,
    val tags: List<String>,
    val areaId: Int?,
    val projectId: Int?,
)

interface TaskApi {
    /** [status] is the server's own vocabulary ("active"/"completed") --
     *  see Item.Status; there is no richer type here for the same reason
     *  DailyModels' own FocusEntry.status stays a plain string. */
    suspend fun setTaskStatus(token: String, taskId: Int, status: String): TaskWriteResult

    /** [dueDate] null clears the due date -- a real, distinct request from
     *  "don't change it", which is why this takes an explicit nullable
     *  rather than being skipped when absent. */
    suspend fun rescheduleTask(token: String, taskId: Int, dueDate: String?): TaskWriteResult
}

/**
 * Talks to `/api/v1/` and nothing else, since August 30, 2026.
 *
 * **It used to take urls out of the agenda payload and post to them** --
 * `url` on each task, `create_item_url` on each area -- which reached
 * `lists.api`'s hand-rolled views, on a different auth mechanism from the
 * agenda read beside them. coherence-audit-2026-08-30.md F2 moved every task
 * write onto the typed Ninja router, so this addresses `/api/v1/tasks/{id}`
 * by id instead, and the two mechanisms became one.
 *
 * **The build in Vince's pocket still uses the old urls**, which is why the
 * server keeps serving them and keeps sending both fields. This client is what
 * makes retiring them possible; what it waits on is
 * `android-release-signing-plan.md`'s keystore, without which no signed
 * release can carry it.
 */
class OkHttpTaskApi(
    private val baseUrl: String,
    private val client: OkHttpClient = OkHttpClariceApi.defaultClient(),
) : TaskApi {

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

    /** Absolute, because okhttp needs one and these paths are ours now. */
    private fun taskEndpoint(path: String) = baseUrl.trimEnd('/') + path

    /** The typed router answers with the task itself, or with it under
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
     * A 422 carries a list rather than a string, which only happens when
     * this client sends something its own contract forbids, so it falls
     * through to the generic line rather than rendering pydantic at a person.
     */
    private fun errorMessageFrom(body: String): String = try {
        JSONObject(body).getString("detail")
    } catch (malformed: JSONException) {
        "Clarice would not accept that."
    }

    private fun taskEntryFrom(json: JSONObject) = TaskEntry(
        id = json.getInt("id"),
        text = json.getString("text"),
        dueDate = json.optStringOrNull("due_date"),
        tags = json.getJSONArray("tags").let { tags -> (0 until tags.length()).map(tags::getString) },
        areaId = json.optIntOrNull("area_id"),
        projectId = json.optIntOrNull("project_id"),
        // `url` is still in the payload and deliberately unread -- the server
        // keeps sending it for the build that came before this one.
    )
}
