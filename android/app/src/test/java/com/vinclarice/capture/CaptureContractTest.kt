package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The client half of M1's handoff contract, from design/bittern-plan.md.
 *
 * The server's table says what each response means; this says what the
 * client does about it. Encoded as a pure function so the rule is testable
 * without a device, a network, or a queue -- M3's retry logic then branches
 * on this rather than re-deciding it.
 *
 * The rule that outranks the others: a capture the person typed is never
 * discarded because of a response we did not expect.
 */
class CaptureContractTest {

    @Test
    fun `a fresh capture that was stored is delivered`() {
        assertEquals(Disposition.DELIVERED, dispositionFor(201))
    }

    @Test
    fun `a replayed idempotency key is delivered, not duplicated`() {
        // The server answers 200 with the original capture when it has seen
        // the key before. To the client that is the same outcome as 201:
        // the thought is safely stored, stop retrying.
        assertEquals(Disposition.DELIVERED, dispositionFor(200))
    }

    @Test
    fun `a malformed key or capture is rejected without blind retry`() {
        assertEquals(Disposition.REJECTED, dispositionFor(400))
    }

    @Test
    fun `an unauthorised token asks for reconnection`() {
        assertEquals(Disposition.NEEDS_RECONNECT, dispositionFor(401))
    }

    @Test
    fun `a forbidden token asks for reconnection too`() {
        assertEquals(Disposition.NEEDS_RECONNECT, dispositionFor(403))
    }

    @Test
    fun `server faults are worth retrying later`() {
        listOf(500, 502, 503, 504).forEach { status ->
            assertEquals("status $status", Disposition.RETRY_LATER, dispositionFor(status))
        }
    }

    @Test
    fun `rate limiting is a retry, not a rejection`() {
        assertEquals(Disposition.RETRY_LATER, dispositionFor(429))
    }

    @Test
    fun `an unrecognised status keeps the text rather than dropping it`() {
        // Deliberately not REJECTED. Retrying something permanently broken
        // wastes a few background attempts; discarding a thought the person
        // typed loses it for good, and the queue applies backoff anyway.
        listOf(302, 404, 418).forEach { status ->
            assertEquals("status $status", Disposition.RETRY_LATER, dispositionFor(status))
        }
    }
}
