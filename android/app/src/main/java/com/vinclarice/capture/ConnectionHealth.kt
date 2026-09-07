package com.vinclarice.capture

import java.time.Duration
import java.time.Instant

/**
 * What is wrong with this connection, in a sentence, or null when nothing is
 * -- android-login-redesign-plan.md Half A.
 *
 * **The whole point is to name a cause where the app used to name a cure.**
 * Every failure a token could have reached the person as *Reconnect in
 * Settings*: a missing scope, an expiry and a revocation were one sentence,
 * and it took a day to find out which. `/api/v1/me` now reports the scopes and
 * the expiry, so the phone can say which.
 *
 * **Pure, and outside the Compose screen deliberately.** This module has no UI
 * tests, so a decision made inside a `@Composable` is checked by compiling and
 * nothing more. The screen renders what this returns.
 *
 * **Null means silence, and silence is the common case.** A warning that shows
 * on a healthy connection is wallpaper within a week, so a ninety-day token
 * says nothing for its first eighty-three days.
 */
fun connectionWarning(capabilities: TokenCapabilities?, now: Instant): String? {
    // Not known is not the same as holds nothing. A server that never sent the
    // fields must not produce a permanent complaint on every screen.
    if (capabilities == null) return null

    val missing = SURFACES.filterNot { capabilities.allows(it.scope) }.map { it.name }
    if (missing.isNotEmpty()) {
        // One sentence naming all of them: two reconnect trips to fix one
        // token is exactly the friction this replaces.
        return "This connection cannot see your ${missing.joinToString(" or ")}. " +
            "Reconnect in Settings to fix it."
    }

    val expiresAt = capabilities.expiresAt ?: return null
    if (!expiresAt.isAfter(now)) {
        return "This connection has expired. Reconnect in Settings."
    }

    val left = Duration.between(now, expiresAt)
    if (left > WARN_WITHIN) return null
    // Rounded up, never down. `toDays()` truncates, so an expiry twenty hours
    // away would announce itself as "0 days" -- which reads as a bug and, on
    // the last day, as no time at all.
    val days = Math.ceil(left.toMinutes() / MINUTES_PER_DAY).toInt()
    val unit = if (days == 1) "day" else "days"
    return "This connection expires in $days $unit. Reconnect in Settings before then."
}

private const val MINUTES_PER_DAY = 60.0 * 24

/** How close an expiry has to be before it is worth saying. */
private val WARN_WITHIN: Duration = Duration.ofDays(7)

/**
 * The scopes a surface needs, in the words the screens use rather than the
 * words the API does. Somebody reading this has no idea what `agenda:read` is,
 * and does know what the pool is because they are looking at it.
 *
 * Only the two reads are here. A missing *write* scope is not something to
 * warn about on sight -- it is worth saying at the moment somebody tries the
 * write, not as a standing complaint about a connection that mostly works.
 */
private val SURFACES = listOf(
    Surface("day", "day:read"),
    Surface("pool", "agenda:read"),
)

private data class Surface(val name: String, val scope: String)
