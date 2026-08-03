package com.vinclarice.capture

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/** Who a token belongs to. Shown on Connect to confirm, and on Settings. */
data class Identity(val username: String, val email: String)

/**
 * Three outcomes, not two, because the caller has to say different things.
 *
 * Collapsing [Unauthorised] and [Unreachable] into one "failed" would tell
 * somebody on a train that the token they just pasted is invalid, and send
 * them off to mint a replacement that will fail in exactly the same way.
 */
sealed interface IdentifyResult

data class Identified(val identity: Identity) : IdentifyResult

/** The token is wrong, revoked, or its account is deactivated. */
data object Unauthorised : IdentifyResult

/** Nothing is wrong with the token, only with right now. */
data class Unreachable(val reason: String) : IdentifyResult

/**
 * What happened when someone tried to log in with a username and password.
 *
 * A separate sealed type from [IdentifyResult] rather than a reuse of it:
 * logging in mints a token that has to travel back out to the caller so it
 * can be stored, which identifying an already-stored one never needs to do.
 */
sealed interface LoginResult

data class LoggedIn(val token: String, val identity: Identity) : LoginResult

/**
 * Wrong username, wrong password, a deactivated account, or a lockout in
 * progress -- deliberately indistinguishable in *which* is true, the same
 * as the server. [message] is the server's own text, which for an ordinary
 * failure is how many attempts remain before a lock, and for a lockout
 * already in progress is how long it lasts -- neither is safe to hard-code
 * on the client since both depend on state only the server has.
 */
data class InvalidCredentials(val message: String) : LoginResult

/** Nothing is wrong with the credentials, only with right now. */
data class LoginUnreachable(val reason: String) : LoginResult

interface ClariceApi {
    suspend fun identify(token: String): IdentifyResult

    /** Trade a password for a token, once. Never called again after the
     *  token is stored -- the app never keeps the password itself. */
    suspend fun login(username: String, password: String, label: String = "Android"): LoginResult

    /**
     * Send one capture.
     *
     * [idempotencyKey] identifies the *thought*, not the attempt: every
     * retry of the same capture must pass the same key, which is what lets
     * the server answer "already stored" instead of storing it twice.
     * Generating a fresh key on retry is exactly how a lost response
     * becomes a duplicated note.
     */
    suspend fun capture(
        token: String,
        text: String,
        idempotencyKey: String,
        tags: List<String> = emptyList(),
    ): Disposition
}

/**
 * Talks to `GET /api/v1/me`, the only endpoint a token can call without
 * writing anything -- validating by posting a capture would leave a junk
 * row in the Inbox every time a token was mistyped.
 *
 * [baseUrl] is supplied rather than compiled in: the plan is explicit that
 * no endpoint or secret is hard-coded into this app.
 */
class OkHttpClariceApi(
    private val baseUrl: String,
    private val client: OkHttpClient = defaultClient(),
) : ClariceApi {

    override suspend fun identify(token: String): IdentifyResult =
        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/api/v1/me")
                .header("Authorization", "Bearer $token")
                .get()
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    when (response.code) {
                        200 -> parseIdentity(response.body.string())
                        401, 403 -> Unauthorised
                        else -> Unreachable("Clarice answered ${response.code}.")
                    }
                }
            } catch (failure: IOException) {
                // Deliberately not failure.message: it can carry the URL and
                // whatever the stack felt like saying, and this string is
                // shown on screen and written to logs. Nothing that has ever
                // touched the token goes in here.
                Unreachable("Could not reach Clarice.")
            }
        }

    override suspend fun login(
        username: String,
        password: String,
        label: String,
    ): LoginResult = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("username", username)
            .put("password", password)
            .put("label", label)
            .toString()
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/api/v1/login")
            // Asks axes to answer a lockout with its own JSON body instead
            // of the HTML template the web login gets -- see
            // design/android-login-plan.md and axes.helpers.get_lockout_response.
            .header("X-Requested-With", "XMLHttpRequest")
            .post(body.toRequestBody(JSON))
            .build()
        try {
            client.newCall(request).execute().use { response ->
                when (response.code) {
                    200 -> parseLogin(response.body.string())
                    // This endpoint's own 401 -- wrong username, wrong
                    // password, or deactivated, deliberately
                    // indistinguishable. The message is the server's,
                    // which is where the attempts-remaining count lives.
                    401 -> InvalidCredentials(
                        parseDetail(response.body.string())
                            ?: "Incorrect username or password."
                    )
                    // axes' own lockout, not this endpoint's -- distinct
                    // response shape, so parsed separately.
                    429 -> InvalidCredentials(
                        parseCooloffMessage(response.body.string())
                            ?: "Too many attempts. Try again later."
                    )
                    else -> LoginUnreachable("Clarice answered ${response.code}.")
                }
            }
        } catch (failure: IOException) {
            LoginUnreachable("Could not reach Clarice.")
        }
    }

    private fun parseLogin(body: String): LoginResult = try {
        val json = JSONObject(body)
        LoggedIn(
            token = json.getString("token"),
            identity = Identity(
                username = json.getString("username"),
                email = json.getString("email"),
            ),
        )
    } catch (malformed: JSONException) {
        LoginUnreachable("Unexpected response from that address.")
    }

    /** Ninja's HttpError body shape: `{"detail": "..."}`. */
    private fun parseDetail(body: String): String? = try {
        JSONObject(body).getString("detail")
    } catch (malformed: JSONException) {
        null
    }

    private fun parseCooloffMessage(body: String): String? = try {
        val cooloff = JSONObject(body).getString("cooloff_time")
        formatCooloff(cooloff)?.let { "Too many attempts. Try again in $it." }
    } catch (malformed: JSONException) {
        null
    }

    /**
     * A whole-hours-and-minutes reading of an ISO 8601 duration, e.g.
     * "PT1H" or "PT1H30M" -- axes' own format (axes.helpers.get_cool_off_iso8601),
     * not a general-purpose parser. `AXES_COOLOFF_TIME` is configured in
     * whole hours today, so seconds are deliberately not extracted.
     */
    private fun formatCooloff(iso: String): String? {
        val match = Regex("""PT(?:(\d+)H)?(?:(\d+)M)?""").matchEntire(iso) ?: return null
        val hours = match.groupValues[1].toIntOrNull() ?: 0
        val minutes = match.groupValues[2].toIntOrNull() ?: 0
        if (hours == 0 && minutes == 0) return null
        val parts = buildList {
            if (hours > 0) add("$hours hour" + if (hours == 1) "" else "s")
            if (minutes > 0) add("$minutes minute" + if (minutes == 1) "" else "s")
        }
        return parts.joinToString(" ")
    }

    override suspend fun capture(
        token: String,
        text: String,
        idempotencyKey: String,
        tags: List<String>,
    ): Disposition = withContext(Dispatchers.IO) {
        // Built with JSONObject rather than string concatenation: capture
        // text is prose typed in a hurry, and quotes, newlines and
        // backslashes are ordinary in it.
        val body = JSONObject()
            .put("text", text)
            .put("tags", JSONArray(tags))
            .toString()
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/api/v1/capture")
            .header("Authorization", "Bearer $token")
            .header("Idempotency-Key", idempotencyKey)
            .post(body.toRequestBody(JSON))
            .build()
        try {
            client.newCall(request).execute().use { response ->
                dispositionFor(response.code)
            }
        } catch (failure: IOException) {
            // Offline, timed out, DNS gone. Nothing is wrong with the
            // capture, so it is worth another attempt later.
            Disposition.RETRY_LATER
        }
    }

    private fun parseIdentity(body: String): IdentifyResult = try {
        val json = JSONObject(body)
        Identified(
            Identity(
                username = json.getString("username"),
                email = json.getString("email"),
            )
        )
    } catch (malformed: JSONException) {
        // A 200 we cannot read is not a valid token -- it usually means the
        // base URL points at something that is not Clarice, which is a
        // connection problem rather than a credential one.
        Unreachable("Unexpected response from that address.")
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            // Short on purpose. Connect is a foreground action with someone
            // watching it; a minute of spinner is worse than a clear failure
            // they can retry.
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
    }
}
