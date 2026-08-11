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
    suspend fun setTaskStatus(token: String, taskUrl: String, status: String): TaskWriteResult

    /** [dueDate] null clears the due date -- a real, distinct request from
     *  "don't change it", which is why this takes an explicit nullable
     *  rather than being skipped when absent. */
    suspend fun rescheduleTask(token: String, taskUrl: String, dueDate: String?): TaskWriteResult

    suspend fun createTask(
        token: String,
        createItemUrl: String,
        text: String,
        dueDate: String?,
    ): TaskWriteResult
}

/**
 * Talks to `GET /api/v1/agenda` (a Ninja route, `TokenAuth`-scoped like
 * `/day`) and `lists.api`'s hand-rolled `create_item`/`item_detail`
 * (`token_or_session_required`, see token-scopes-plan.md §7) -- two
 * different auth mechanisms on the Django side, one client interface here,
 * because from Android's own view they're the same thing: a Bearer token
 * and a URL.
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
        taskUrl: String,
        status: String,
    ): TaskWriteResult =
        patchTask(token, taskUrl, JSONObject().put("status", status))

    override suspend fun rescheduleTask(
        token: String,
        taskUrl: String,
        dueDate: String?,
    ): TaskWriteResult =
        patchTask(token, taskUrl, JSONObject().put("due_date", dueDate ?: JSONObject.NULL))

    override suspend fun createTask(
        token: String,
        createItemUrl: String,
        text: String,
        dueDate: String?,
    ): TaskWriteResult = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("text", text)
            .put("due_date", dueDate ?: JSONObject.NULL)
        val request = Request.Builder()
            .url(absoluteUrl(createItemUrl))
            .header("Authorization", "Bearer $token")
            .post(body.toString().toRequestBody(JSON))
            .build()
        executeWrite(request)
    }

    private suspend fun patchTask(
        token: String,
        taskUrl: String,
        body: JSONObject,
    ): TaskWriteResult = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(absoluteUrl(taskUrl))
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
                400, 404, 409 -> TaskWriteRejected(errorMessageFrom(response.body.string()))
                else -> TaskWriteUnreachable("Clarice answered ${response.code}.")
            }
        }
    } catch (failure: IOException) {
        TaskWriteUnreachable("Could not reach Clarice.")
    }

    private fun absoluteUrl(path: String) =
        if (path.startsWith("http")) path else baseUrl.trimEnd('/') + path

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

    private fun parseTaskWrite(body: String): TaskWriteResult = try {
        TaskWriteSucceeded(taskEntryFrom(JSONObject(body).getJSONObject("data")))
    } catch (malformed: JSONException) {
        TaskWriteUnreachable("Unexpected response from that address.")
    }

    /** Ninja's `{"detail": "..."}` shape doesn't apply here -- lists.api's
     *  hand-rolled views answer `{"errors": {"<field>": ["<message>"]}}`. */
    private fun errorMessageFrom(body: String): String = try {
        val errors = JSONObject(body).getJSONObject("errors")
        val field = errors.keys().next()
        errors.getJSONArray(field).getString(0)
    } catch (malformed: JSONException) {
        "Clarice would not accept that."
    }

    private fun taskEntryFrom(json: JSONObject) = AgendaTaskEntry(
        id = json.getInt("id"),
        text = json.getString("text"),
        dueDate = json.optStringOrNull("due_date"),
        tags = json.getJSONArray("tags").let { tags -> (0 until tags.length()).map(tags::getString) },
        areaId = json.getInt("area_id"),
        projectId = json.optIntOrNull("project_id"),
        url = json.getString("url"),
    )

    private fun areaEntryFrom(json: JSONObject) = AgendaAreaEntry(
        id = json.getInt("id"),
        title = json.getString("title"),
        colorKey = json.getString("color_key"),
        openCount = json.getInt("open_count"),
        overdueCount = json.getInt("overdue_count"),
        createItemUrl = json.getString("create_item_url"),
    )

    private fun projectEntryFrom(json: JSONObject) = AgendaProjectEntry(
        id = json.getInt("id"),
        title = json.getString("title"),
    )
}
