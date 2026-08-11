package com.vinclarice.capture

import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
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

interface DailyApi {
    /** The requesting account's own day, in its own time zone -- the
     *  server's `/api/v1/day` never takes a date from the client for this. */
    suspend fun getToday(token: String): DayResult
}

/**
 * Talks to `GET /api/v1/day`, read-only -- slice 1 of
 * android-full-client-plan.md. No write methods yet: pinning, routine
 * logging and editing the day's own text are deliberately deferred, so
 * there is nothing here to call for them.
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
    )

    private fun actionItemEntryFrom(json: JSONObject) = ActionItemEntry(
        id = json.getInt("id"),
        text = json.getString("text"),
        dueDate = json.optStringOrNull("due_date"),
        ageInDays = json.getInt("age_in_days"),
        areaId = json.getInt("area_id"),
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

private fun <T> JSONArray.map(transform: (JSONObject) -> T): List<T> =
    (0 until length()).map { transform(getJSONObject(it)) }

/** A JSON integer or string that may be null -- org.json has no built-in
 *  for either. */
private fun JSONObject.optIntOrNull(name: String): Int? =
    if (isNull(name) || !has(name)) null else getInt(name)

private fun JSONObject.optStringOrNull(name: String): String? =
    if (isNull(name) || !has(name)) null else getString(name)
