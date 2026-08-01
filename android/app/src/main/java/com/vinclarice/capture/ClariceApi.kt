package com.vinclarice.capture

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
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

interface ClariceApi {
    suspend fun identify(token: String): IdentifyResult

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

    override suspend fun capture(
        token: String,
        text: String,
        idempotencyKey: String,
    ): Disposition = withContext(Dispatchers.IO) {
        // Built with JSONObject rather than string concatenation: capture
        // text is prose typed in a hurry, and quotes, newlines and
        // backslashes are ordinary in it.
        val body = JSONObject().put("text", text).toString()
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
