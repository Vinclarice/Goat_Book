package com.vinclarice.capture

import java.time.Instant
import java.time.temporal.ChronoUnit
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Saying what is wrong with a connection, in words somebody can act on --
 * android-login-redesign-plan.md Half A.
 *
 * **Pure, and here rather than in the Compose screen, on purpose.** This suite
 * has no UI tests, so anything decided inside a `@Composable` is verified by
 * compiling and nothing else. The judgement lives here where it can be
 * asserted; the screen only draws the string this returns.
 */
class ConnectionHealthTest {

    private val now: Instant = Instant.parse("2026-09-07T12:00:00Z")

    private fun caps(scopes: Set<String>, expiresAt: Instant? = null) =
        TokenCapabilities(scopes, expiresAt)

    private val everything = setOf(
        "capture:write", "identity:read", "day:read",
        "agenda:read", "agenda:write", "day:write", "routines:write",
    )

    @Test
    fun `a healthy connection has nothing to say`() {
        assertNull(connectionWarning(caps(everything), now))
    }

    @Test
    fun `an unknown capability set says nothing rather than guessing`() {
        // Null is "the server did not say", and inventing a complaint from
        // that would put a permanent warning on every older server.
        assertNull(connectionWarning(null, now))
    }

    @Test
    fun `a connection that cannot read the day names the day`() {
        /* **The defect that started the redesign.** This token identifies its
           account perfectly, so Settings said "connected" while the Day screen
           answered 401 and said "reconnect" -- neither naming the cause. */
        val warning = connectionWarning(caps(setOf("capture:write", "identity:read")), now)

        assertTrue(warning!!.contains("day", ignoreCase = true))
        assertTrue(warning.contains("Reconnect", ignoreCase = true))
    }

    @Test
    fun `a connection that cannot read the pool names the pool`() {
        val warning = connectionWarning(caps(everything - "agenda:read"), now)

        assertTrue(warning!!.contains("pool", ignoreCase = true))
    }

    @Test
    fun `one warning names every missing piece rather than only the first`() {
        // Two reconnect trips to fix one token is the failure this replaces.
        val warning = connectionWarning(
            caps(setOf("capture:write", "identity:read")), now
        )

        assertTrue(warning!!.contains("day", ignoreCase = true))
        assertTrue(warning.contains("pool", ignoreCase = true))
    }

    @Test
    fun `an expiry that is close is warned about before it happens`() {
        val warning = connectionWarning(
            caps(everything, now.plus(5, ChronoUnit.DAYS)), now
        )

        assertTrue(warning!!.contains("5 days"))
    }

    @Test
    fun `an expiry that is far away is not mentioned`() {
        // A ninety-day token would otherwise carry a standing warning from the
        // moment it was minted, which is how a warning becomes wallpaper.
        assertNull(connectionWarning(caps(everything, now.plus(60, ChronoUnit.DAYS)), now))
    }

    @Test
    fun `a token that never expires is not warned about`() {
        assertNull(connectionWarning(caps(everything, expiresAt = null), now))
    }

    @Test
    fun `an expiry already past is said in the past tense`() {
        val warning = connectionWarning(
            caps(everything, now.minus(1, ChronoUnit.DAYS)), now
        )

        assertTrue(warning!!.contains("expired", ignoreCase = true))
    }

    @Test
    fun `tomorrow is a day rather than zero days`() {
        // Integer division on hours reports 0 for anything under 24, so an
        // expiry twenty hours out would read "expires in 0 days".
        val warning = connectionWarning(
            caps(everything, now.plus(20, ChronoUnit.HOURS)), now
        )

        assertTrue(warning!!, !warning.contains("0 days"))
    }
}
