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
 * What happened when the Daily Page was asked for.
 *
 * Three outcomes, same split as [IdentifyResult] and for the same reason:
 * a revoked token needs "reconnect", a flaky network needs "try again", and
 * collapsing them would tell the wrong one of those to somebody who cannot
 * tell which is true from the screen alone.
 */
sealed interface DayResult

data class DayLoaded(val day: DayEntry) : DayResult

data object DayUnauthorised : DayResult

data class DayUnreachable(val reason: String) : DayResult

/**
 * What happened when a write against the Daily Page or a routine was
 * attempted -- focus pin/unpin, the day's own text, or any of the six
 * routine actions. None of these parse the server's response body (a
 * `DayOut` for the day writes, a different `StandingsOut` shape for the
 * routine ones) because [DailyViewModel] reloads the whole day on success
 * instead, the same "reload rather than hand-merge a shape change" rule
 * `AgendaViewModel`'s own write() uses.
 */
sealed interface DayWriteResult

data object DayWriteSucceeded : DayWriteResult

data object DayWriteUnauthorised : DayWriteResult

/** A 400/403/409 Ninja explained via its own `{"detail": "..."}` shape --
 *  different from lists.api's hand-rolled `{"errors": {...}}`, since every
 *  endpoint here is a Ninja operation, not a hand-rolled view. */
data class DayWriteRejected(val message: String) : DayWriteResult

data class DayWriteUnreachable(val reason: String) : DayWriteResult

interface DailyApi {
    /** The requesting account's own day, in its own time zone -- the
     *  server's `/api/v1/day` never takes a date from the client for this. */
    suspend fun getToday(token: String): DayResult

    suspend fun pinFocus(token: String, day: String, taskId: Int): DayWriteResult

    suspend fun unpinFocus(token: String, day: String, taskId: Int): DayWriteResult

    /** The web's own "Save the day" always sends all three sections
     *  together, so this does too -- the server's per-field-optional PATCH
     *  contract exists but nothing here exercises it. */
    suspend fun writeDayText(
        token: String,
        day: String,
        intentions: String,
        gratitude: String,
        happenings: String,
    ): DayWriteResult

    suspend fun createRoutine(
        token: String,
        title: String,
        cadence: String,
        targetQuantity: Int,
        unit: String,
    ): DayWriteResult

    /** [amount] is usually +1/-1 -- a negative amount corrects a mis-tap
     *  rather than being its own endpoint, per routines/api_v1.py's own
     *  reasoning. */
    suspend fun logRoutine(token: String, routineId: Int, amount: Int): DayWriteResult

    suspend fun skipRoutine(token: String, routineId: Int): DayWriteResult

    suspend fun callRoutineEnough(token: String, routineId: Int): DayWriteResult

    suspend fun pauseRoutine(token: String, routineId: Int): DayWriteResult

    suspend fun resumeRoutine(token: String, routineId: Int): DayWriteResult
}

/**
 * Talks to `GET /api/v1/day` (slice 1) and, now, every write the Daily
 * Page's own edit slice adds: focus pin/unpin, the day's own text, and the
 * six routine actions -- all Ninja operations on `daily/api_v1.py` and
 * `routines/api_v1.py`, so unlike Agenda's write half none of this needed
 * `token_or_session_required`'s CSRF-porting; see token-scopes-plan.md for
 * the day:write/routines:write scopes this adds.
 */
class OkHttpDailyApi(
    private val baseUrl: String,
    private val client: OkHttpClient = OkHttpClariceApi.defaultClient(),
) : DailyApi {

    override suspend fun getToday(token: String): DayResult =
        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/api/v1/day")
                .header("Authorization", "Bearer $token")
                .get()
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    when (response.code) {
                        200 -> parseDay(response.body.string())
                        401, 403 -> DayUnauthorised
                        else -> DayUnreachable("Clarice answered ${response.code}.")
                    }
                }
            } catch (failure: IOException) {
                DayUnreachable("Could not reach Clarice.")
            }
        }

    override suspend fun pinFocus(token: String, day: String, taskId: Int): DayWriteResult =
        post(token, "/api/v1/day/$day/focus", JSONObject().put("task_id", taskId))

    override suspend fun unpinFocus(token: String, day: String, taskId: Int): DayWriteResult =
        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/api/v1/day/$day/focus/$taskId")
                .header("Authorization", "Bearer $token")
                .delete()
                .build()
            executeWrite(request)
        }

    override suspend fun writeDayText(
        token: String,
        day: String,
        intentions: String,
        gratitude: String,
        happenings: String,
    ): DayWriteResult = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("intentions", intentions)
            .put("gratitude", gratitude)
            .put("happenings", happenings)
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/api/v1/day/$day")
            .header("Authorization", "Bearer $token")
            .patch(body.toString().toRequestBody(JSON))
            .build()
        executeWrite(request)
    }

    override suspend fun createRoutine(
        token: String,
        title: String,
        cadence: String,
        targetQuantity: Int,
        unit: String,
    ): DayWriteResult = post(
        token,
        "/api/v1/routines",
        JSONObject()
            .put("title", title)
            .put("cadence", cadence)
            .put("target_quantity", targetQuantity)
            .put("unit", unit),
    )

    override suspend fun logRoutine(token: String, routineId: Int, amount: Int): DayWriteResult =
        post(token, "/api/v1/routines/$routineId/log", JSONObject().put("amount", amount))

    override suspend fun skipRoutine(token: String, routineId: Int): DayWriteResult =
        post(token, "/api/v1/routines/$routineId/skip", body = null)

    override suspend fun callRoutineEnough(token: String, routineId: Int): DayWriteResult =
        post(token, "/api/v1/routines/$routineId/enough", body = null)

    override suspend fun pauseRoutine(token: String, routineId: Int): DayWriteResult =
        post(token, "/api/v1/routines/$routineId/pause", body = null)

    override suspend fun resumeRoutine(token: String, routineId: Int): DayWriteResult =
        post(token, "/api/v1/routines/$routineId/resume", body = null)

    /** [body] null means a plain POST with no content -- skip/enough/pause/
     *  resume all take no payload, only the routine id in the path. */
    private suspend fun post(token: String, path: String, body: JSONObject?): DayWriteResult =
        withContext(Dispatchers.IO) {
            val requestBody = if (body != null) body.toString().toRequestBody(JSON) else "".toRequestBody()
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + path)
                .header("Authorization", "Bearer $token")
                .post(requestBody)
                .build()
            executeWrite(request)
        }

    private fun executeWrite(request: Request): DayWriteResult = try {
        client.newCall(request).execute().use { response ->
            when (response.code) {
                200, 201 -> DayWriteSucceeded
                401, 403 -> DayWriteUnauthorised
                400, 404, 409 -> DayWriteRejected(detailFrom(response.body.string()))
                else -> DayWriteUnreachable("Clarice answered ${response.code}.")
            }
        }
    } catch (failure: IOException) {
        DayWriteUnreachable("Could not reach Clarice.")
    }

    /** Ninja's HttpError shape: `{"detail": "..."}`. */
    private fun detailFrom(body: String): String = try {
        JSONObject(body).getString("detail")
    } catch (malformed: JSONException) {
        "Clarice would not accept that."
    }

    private fun parseDay(body: String): DayResult = try {
        DayLoaded(dayEntryFrom(JSONObject(body)))
    } catch (malformed: JSONException) {
        // A 200 that doesn't parse means the base URL points at something
        // that isn't Clarice, same reasoning as OkHttpClariceApi.identify.
        DayUnreachable("Unexpected response from that address.")
    }

    private fun dayEntryFrom(json: JSONObject) = DayEntry(
        date = json.getString("date"),
        today = json.getString("today"),
        intentions = json.getString("intentions"),
        gratitude = json.getString("gratitude"),
        happenings = json.getString("happenings"),
        compassPurpose = json.getString("compass_purpose"),
        compassQuestion = json.getString("compass_question"),
        focus = json.getJSONArray("focus").map(::focusEntryFrom),
        actionItems = json.getJSONArray("action_items").map(::actionItemEntryFrom),
        areas = json.getJSONArray("areas").map(::areaSummaryFrom),
        projects = json.getJSONArray("projects").map(::projectSummaryFrom),
        showsActionItems = json.getBoolean("shows_action_items"),
        routines = json.getJSONArray("routines").map(::standingEntryFrom),
        routinesAreLoggable = json.getBoolean("routines_are_loggable"),
        pausedRoutines = json.getJSONArray("paused_routines").map(::pausedRoutineFrom),
    )

    private fun focusEntryFrom(json: JSONObject) = FocusEntry(
        taskId = json.optIntOrNull("task_id"),
        text = json.getString("text"),
        status = json.optStringOrNull("status"),
        dueDate = json.optStringOrNull("due_date"),
        url = json.optStringOrNull("url"),
    )

    private fun actionItemEntryFrom(json: JSONObject) = ActionItemEntry(
        id = json.getInt("id"),
        text = json.getString("text"),
        dueDate = json.optStringOrNull("due_date"),
        ageInDays = json.getInt("age_in_days"),
        areaId = json.optIntOrNull("area_id"),
        projectId = json.optIntOrNull("project_id"),
    )

    private fun areaSummaryFrom(json: JSONObject) = AreaSummaryEntry(
        id = json.getInt("id"),
        title = json.getString("title"),
    )

    private fun projectSummaryFrom(json: JSONObject) = ProjectSummaryEntry(
        id = json.getInt("id"),
        title = json.getString("title"),
    )

    private fun standingEntryFrom(json: JSONObject) = StandingEntry(
        routineId = json.getInt("routine_id"),
        title = json.getString("title"),
        cadence = json.getString("cadence"),
        progress = json.getInt("progress"),
        target = json.getInt("target"),
        unit = json.getString("unit"),
        outcome = json.getString("outcome"),
        isMet = json.getBoolean("is_met"),
    )

    private fun pausedRoutineFrom(json: JSONObject) = PausedRoutineEntry(
        routineId = json.getInt("routine_id"),
        title = json.getString("title"),
        cadence = json.getString("cadence"),
        target = json.getInt("target"),
        unit = json.getString("unit"),
    )
}

