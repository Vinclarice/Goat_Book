package com.vinclarice.capture

import java.io.IOException
import java.time.Instant
import java.time.format.DateTimeParseException
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
 * What the credential can do, as opposed to who it belongs to --
 * android-login-redesign-plan.md Half A.
 *
 * **A separate type from [Identity] because they answer different questions**,
 * and because only one of them arrives everywhere. `/api/v1/me` reports both;
 * `/api/v1/login` reports the identity and no scopes, so folding these fields
 * into [Identity] would have forced the login path to invent them.
 *
 * The phone was blind without this. A token missing `day:read` identified its
 * account perfectly while the Day screen refused, so a scope problem, an
 * expiry and a revocation all reached the person as one sentence -- *Reconnect
 * in Settings* -- which names a cure rather than a cause.
 */
data class TokenCapabilities(
    val scopes: Set<String>,
    /**
     * When this token stops working, or null for never -- which is what null
     * means on the server, and must keep meaning here. A client substituting a
     * far-future date would warn about an expiry that is not coming.
     */
    val expiresAt: Instant? = null,
) {
    /** Whether the connection can reach a surface at all, before it is asked
     *  to. This is the question the Day and Pool screens could not previously
     *  put to anything. */
    fun allows(scope: String) = scope in scopes
}

/**
 * Three outcomes, not two, because the caller has to say different things.
 *
 * Collapsing [Unauthorised] and [Unreachable] into one "failed" would tell
 * somebody on a train that the token they just pasted is invalid, and send
 * them off to mint a replacement that will fail in exactly the same way.
 */
sealed interface IdentifyResult

data class Identified(
    val identity: Identity,
    /**
     * Null means *this server did not say*, never *this token holds nothing*.
     * The two must not be confused: a screen that read absence as an empty
     * scope set would announce that a working connection can do nothing.
     *
     * Defaulted so a server that predates these fields still identifies an
     * account, which is the compatible half of `principles.md`'s rule about
     * evolving an API without stranding clients.
     */
    val capabilities: TokenCapabilities? = null,
) : IdentifyResult

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

/**
 * A pairing this phone has started and nobody has approved yet —
 * `android-login-redesign-plan.md` Half B.
 *
 * Two codes with opposite jobs. [userCode] is shown to a person and carried to
 * a laptop; it grants nothing on its own. [deviceCode] is the credential half,
 * kept here and never displayed — showing it would recreate exactly the thing
 * this flow exists to remove.
 */
data class PairingStarted(
    val userCode: String,
    val deviceCode: String,
    /** When the request stops being approvable, or null if the server did not
     *  say. Only drives a countdown, so an unreadable one costs nothing. */
    val expiresAt: Instant? = null,
    /**
     * Seconds between polls, as the *server* chose it.
     *
     * Read rather than hard-coded, because the nginx zone in front of the poll
     * endpoint is sized from this number — a client with its own idea of the
     * interval would be a second copy of a rate limit, and would rate-limit
     * itself out of its own pairing.
     */
    val intervalSeconds: Int = DEFAULT_POLL_SECONDS,
) {
    companion object {
        /** Only for a server that sent nothing usable. Never zero: a
         *  zero-delay poll loop is a self-inflicted flood. */
        const val DEFAULT_POLL_SECONDS = 5
    }
}

sealed interface PairingStartResult

data class PairingBegun(val started: PairingStarted) : PairingStartResult

/** Nothing is wrong with pairing, only with right now. */
data class PairingStartFailed(val reason: String) : PairingStartResult

sealed interface PairingPollResult

data class PairingGranted(val token: String) : PairingPollResult

/**
 * Nobody has approved it yet — **and this is the ordinary case, not an error.**
 *
 * The server answers waiting, expired and never-existed identically, on
 * purpose, so a client that treated an empty answer as a fault would report a
 * broken server for the entire normal duration of the flow.
 */
data object PairingPending : PairingPollResult

/** The poll itself failed. Distinct from [PairingPending] because one means
 *  *keep waiting* and the other means *something is wrong*. */
data class PairingPollFailed(val reason: String) : PairingPollResult

interface ClariceApi {
    suspend fun identify(token: String): IdentifyResult

    /**
     * Ask to be connected, with no credential of any kind.
     *
     * **Deliberately not defaulted on this interface**, so the five test fakes
     * implementing it had to acknowledge pairing rather than inherit a stub
     * that silently answers "unreachable". This codebase makes widenings
     * something somebody types on purpose -- `TOKEN_AUTHENTICATED`,
     * `EXPORT_KEYS`, `ELSEWHERE` -- and a second real client forgetting a
     * transition should be a compile error rather than a quiet failure.
     */
    suspend fun startPairing(label: String = "Android"): PairingStartResult

    /** Ask once whether somebody has approved yet. The loop belongs to the
     *  caller, which is what lets it be tested on a virtual clock. */
    suspend fun pollPairing(deviceCode: String): PairingPollResult

    /** Trade a password for a token, once. Never called again after the
     *  token is stored -- the app never keeps the password itself. */
    /**
     * Trade a password for a token.
     *
     * @param totp the second factor, when the account has one -- an
     *   authenticator code or a recovery code. Sent always, empty when there
     *   is none, so the request has one shape whether or not the account has a
     *   factor.
     */
    suspend fun login(
        username: String,
        password: String,
        label: String = "Android",
        totp: String = "",
    ): LoginResult

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
        /**
         * When the text was written, epoch millis, or null when unknown.
         *
         * Not the same as when it is sent, and the difference is the whole
         * point: a capture can sit in the queue for hours. The server falls
         * back to its own clock when this is absent, which is right for
         * anything captured while connected and wrong for everything else.
         */
        capturedAt: Long? = null,
    ): Disposition
}

/**
 * Talks to `GET /api/v1/me`, the only endpoint a token can call without
 * writing anything -- validating by posting a capture would leave a junk
 * row in the Inbox every time a token was mistyped.
 *
 * [baseUrl] is supplied rather than compiled in: the plan is explicit that
 * no endpoint or secret is hard-coded into this app.
 *
 * [serverName] travels with it, and is not cosmetic. This class serves both
 * backends on a split install, so a hard-coded "Clarice" in a failure
 * message names the wrong system exactly when somebody is trying to work out
 * which one is broken -- found on a device, where a capture that could not
 * reach Second Mind reported Clarice as unreachable. It defaults to Clarice,
 * which is what every unsplit call site means.
 */
class OkHttpClariceApi(
    private val baseUrl: String,
    private val client: OkHttpClient = defaultClient(),
    private val serverName: String = "Clarice",
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
                        else -> Unreachable(whatWentWrong(serverName, response.code))
                    }
                }
            } catch (failure: IOException) {
                // Deliberately not failure.message: it can carry the URL and
                // whatever the stack felt like saying, and this string is
                // shown on screen and written to logs. Nothing that has ever
                // touched the token goes in here.
                Unreachable(couldNotReach(serverName))
            }
        }

    override suspend fun login(
        username: String,
        password: String,
        label: String,
        totp: String,
    ): LoginResult = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("username", username)
            .put("password", password)
            .put("label", label)
            .put("totp", totp)
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
                            ?: "Too many attempts. Wait a while before trying again."
                    )
                    // The second factor: no code given, or the wrong one.
                    // **Refused, not unreachable** -- this fell through to the
                    // line below until September 6, 2026, so a person who had
                    // simply not typed their code was told "Clarice answered
                    // 403." The server sends a sentence saying what to do and
                    // it was being thrown away for a number.
                    403 -> InvalidCredentials(
                        parseDetail(response.body.string())
                            ?: "That account needs a second factor."
                    )
                    else -> LoginUnreachable(whatWentWrong(serverName, response.code))
                }
            }
        } catch (failure: IOException) {
            LoginUnreachable(couldNotReach(serverName))
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
        LoginUnreachable(couldNotUnderstand(serverName))
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
    /**
     * Epoch millis as ISO 8601 in UTC, which is what the server parses.
     *
     * Formatted here rather than sent as a number so the wire format says what
     * it means, and pinned to UTC so a phone that changes timezone between
     * capture and delivery cannot move the timestamp.
     */
    private fun isoUtc(epochMillis: Long): String =
        java.time.Instant.ofEpochMilli(epochMillis)
            .atOffset(java.time.ZoneOffset.UTC)
            .format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'"))

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
        capturedAt: Long?,
    ): Disposition = withContext(Dispatchers.IO) {
        // Built with JSONObject rather than string concatenation: capture
        // text is prose typed in a hurry, and quotes, newlines and
        // backslashes are ordinary in it.
        val body = JSONObject()
            .put("text", text)
            .put("tags", JSONArray(tags))
            // Omitted rather than guessed when unknown: the server falls back
            // to now, which is the honest answer for a capture that never
            // waited. Sending an invented time would be worse than sending
            // none, because a temporal detector cannot tell the two apart.
            .apply { capturedAt?.let { put("captured_at", isoUtc(it)) } }
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

    override suspend fun startPairing(label: String): PairingStartResult =
        withContext(Dispatchers.IO) {
            val body = JSONObject().put("label", label).toString()
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/api/v1/pair/start")
                // No Authorization header, and that is the point rather than an
                // omission: a phone with no token is exactly the phone that
                // needs to pair.
                .post(body.toRequestBody(JSON))
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    if (response.code != 200) {
                        return@use PairingStartFailed(
                            whatWentWrong(serverName, response.code)
                        )
                    }
                    parseStartedPairing(response.body.string())
                }
            } catch (failure: IOException) {
                PairingStartFailed(couldNotReach(serverName))
            }
        }

    override suspend fun pollPairing(deviceCode: String): PairingPollResult =
        withContext(Dispatchers.IO) {
            // In the body rather than the query string. It is the credential
            // half of this flow, and a query string is the one place a secret
            // reliably ends up in a log -- which this project already had to
            // fix once, for `/mind/search/`.
            val body = JSONObject().put("device_code", deviceCode).toString()
            val request = Request.Builder()
                .url(baseUrl.trimEnd('/') + "/api/v1/pair/poll")
                .post(body.toRequestBody(JSON))
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    // A 429 is genuinely reachable here, unlike on most
                    // endpoints, because this one is polled. It must never be
                    // read as "no token yet" -- that would poll forever
                    // against a closed door -- nor as success.
                    if (response.code != 200) {
                        return@use PairingPollFailed(
                            whatWentWrong(serverName, response.code)
                        )
                    }
                    parsePolledPairing(response.body.string())
                }
            } catch (failure: IOException) {
                PairingPollFailed(couldNotReach(serverName))
            }
        }

    private fun parseStartedPairing(body: String): PairingStartResult = try {
        val json = JSONObject(body)
        PairingBegun(
            PairingStarted(
                userCode = json.getString("user_code"),
                deviceCode = json.getString("device_code"),
                expiresAt = parseInstantOrNull(json, "expires_at"),
                // `optInt` returns 0 for absent, and zero here is a poll loop
                // with no delay -- a self-inflicted flood against an endpoint
                // that has a rate limit. Anything unusable falls back.
                intervalSeconds = json.optInt("interval", 0)
                    .takeIf { it >= 1 }
                    ?: PairingStarted.DEFAULT_POLL_SECONDS,
            )
        )
    } catch (malformed: JSONException) {
        PairingStartFailed(couldNotUnderstand(serverName))
    }

    private fun parsePolledPairing(body: String): PairingPollResult = try {
        val json = JSONObject(body)
        // Absent and null both mean "not yet". The server sends one answer for
        // waiting, expired and never-existed, so this client cannot tell them
        // apart and does not try.
        val token = if (json.isNull("token")) null else json.optString("token", "")
        if (token.isNullOrEmpty()) PairingPending else PairingGranted(token)
    } catch (malformed: JSONException) {
        PairingPollFailed(couldNotUnderstand(serverName))
    }

    /** A timestamp that only drives a countdown, so anything unreadable
     *  degrades to null rather than failing the call around it. */
    private fun parseInstantOrNull(json: JSONObject, key: String): Instant? =
        if (json.isNull(key)) {
            null
        } else {
            try {
                Instant.parse(json.getString(key))
            } catch (unreadable: DateTimeParseException) {
                null
            }
        }

    private fun parseIdentity(body: String): IdentifyResult = try {
        val json = JSONObject(body)
        Identified(
            Identity(
                username = json.getString("username"),
                email = json.getString("email"),
            ),
            parseCapabilities(json),
        )
    } catch (malformed: JSONException) {
        // A 200 we cannot read is not a valid token -- it usually means the
        // base URL points at something that is not Clarice, which is a
        // connection problem rather than a credential one.
        Unreachable(couldNotUnderstand(serverName))
    }

    /**
     * The scopes and expiry, or null when this server did not send them.
     *
     * **Nothing in here may cost the caller its identity.** The account name
     * is what Connect and Settings exist to show and it has already parsed by
     * the time this runs; a missing or unreadable capability is strictly less
     * valuable than that, so every failure here degrades to null rather than
     * escalating into [Unreachable]. That is why `optJSONArray` and a swallowed
     * `DateTimeParseException` are right here and would be wrong above.
     */
    private fun parseCapabilities(json: JSONObject): TokenCapabilities? {
        val scopes = json.optJSONArray("scopes") ?: return null
        return TokenCapabilities(
            scopes = (0 until scopes.length()).map(scopes::getString).toSet(),
            // `optString` returns "null" -- the four characters -- for a JSON
            // null, so the explicit isNull check is load-bearing rather than
            // defensive: without it every never-expiring token would carry an
            // unparseable date instead of no date.
            expiresAt = if (json.isNull("expires_at")) {
                null
            } else {
                try {
                    Instant.parse(json.getString("expires_at"))
                } catch (unreadable: DateTimeParseException) {
                    null
                }
            },
        )
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
