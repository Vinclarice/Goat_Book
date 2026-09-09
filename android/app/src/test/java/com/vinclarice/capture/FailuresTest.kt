package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What a person is told when a request does not work.
 *
 * **Vince, September 9, 2026**, after meeting one of these in the wild:
 * *"Clarice answered 403?"* — which is the whole complaint. Twelve call sites
 * across four API clients built their failure text the same way,
 * `"$serverName answered ${response.code}."`, so a status code was the entire
 * message and there was nothing in it to act on.
 *
 * `principles.md` already forbids this in as many words: *state what happened
 * in plain language, give a sensible next action... generic error with no
 * recovery path is not an acceptable steady state.* A three-digit number is
 * neither half.
 *
 * **The number survives, demoted.** It is the only diagnostic when something
 * genuinely unexpected happens, and this is an application whose user reads
 * its logs — so the sentence leads and the code follows in brackets, rather
 * than the code being the sentence.
 */
class FailuresTest {

    @Test
    fun `a restart says so, because that is what a deploy looks like`() {
        // 502 and 503 during a deploy are the most likely failure this app
        // will ever show, and "try again in a moment" is exactly right for it
        // in a way that a generic five-hundred message is not.
        val message = whatWentWrong("Clarice", 503)

        assertTrue(message.contains("restarting"))
        assertTrue(message.contains("moment"))
    }

    @Test
    fun `a server fault says whose end it is and that it will pass`() {
        val message = whatWentWrong("Clarice", 500)

        assertTrue(message.contains("Clarice"))
        assertTrue(message.lowercase().contains("try again"))
    }

    @Test
    fun `being rate limited says to wait rather than to retry now`() {
        // The one case where "try again" is the wrong advice: retrying
        // immediately is what caused it.
        val message = whatWentWrong("Clarice", 429)

        assertTrue(message.lowercase().contains("wait"))
        assertFalse(message.lowercase().contains("try again now"))
    }

    @Test
    fun `something missing suggests where it went`() {
        val message = whatWentWrong("Clarice", 404)

        assertTrue(message.lowercase().contains("could not find"))
    }

    @Test
    fun `a conflict says something else changed it`() {
        // 409 is two surfaces disagreeing -- the website and the phone acting
        // on the same task. "Reload" is the actual fix and nothing else is.
        val message = whatWentWrong("Clarice", 409)

        assertTrue(message.lowercase().contains("already changed"))
    }

    @Test
    fun `every message names a next action`() {
        // The half of `principles.md`'s rule that is easiest to skip. Checked
        // across the range rather than case by case, so a new branch added
        // without one fails here.
        val codes = listOf(400, 404, 409, 418, 422, 429, 500, 502, 503, 504, 599)

        for (code in codes) {
            val message = whatWentWrong("Clarice", code).lowercase()
            assertTrue(
                "no next action for $code: $message",
                listOf("try again", "wait", "reload", "check").any(message::contains),
            )
        }
    }

    @Test
    fun `no message is only a number`() {
        // The regression this whole file exists for.
        for (code in listOf(400, 403, 404, 418, 500, 503)) {
            val message = whatWentWrong("Clarice", code)
            assertFalse(
                "still just a status line: $message",
                message == "Clarice answered $code.",
            )
            assertTrue("too terse to act on: $message", message.length > 30)
        }
    }

    @Test
    fun `the code is still there for whoever has to diagnose it`() {
        // Demoted, not deleted. Vince reads this app's logs and is the person
        // who would be told "it said something went wrong" otherwise.
        assertTrue(whatWentWrong("Clarice", 418).contains("418"))
    }

    @Test
    fun `the server is named rather than assumed`() {
        // `Backends` allows a split install where captures go somewhere else,
        // and three of the four API clients had "Clarice" hardcoded while the
        // fourth passed a name. One helper, one name, given by the caller.
        assertTrue(whatWentWrong("Second Mind", 500).contains("Second Mind"))
    }

    @Test
    fun `an unreadable body is not the same as an unreachable server`() {
        // Two different failures that had nearly the same words. This one
        // means the request arrived and came back wrong, which is worth
        // saying differently from "the network is down".
        val garbled = couldNotUnderstand("Clarice")
        val offline = couldNotReach("Clarice")

        assertEquals(false, garbled == offline)
        assertTrue(offline.lowercase().contains("connection"))
        assertTrue(garbled.lowercase().contains("try again"))
    }
}
