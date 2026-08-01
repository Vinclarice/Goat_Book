package com.vinclarice.capture

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
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
        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            // Short on purpose. Connect is a foreground action with someone
            // watching it; a minute of spinner is worse than a clear failure
            // they can retry.
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
    }
}
