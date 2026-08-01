package com.vinclarice.capture

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * AES/GCM produces two things that both have to survive being written to
 * disk: the ciphertext and the IV that decrypts it. Storing them means
 * framing them into one string, and framing is where a silent corruption
 * lives -- a token that unpacks to the wrong bytes fails at the server with
 * a 401, which looks exactly like a revoked token and sends someone off to
 * mint a replacement that will not help.
 *
 * Split out from the Keystore code so it can be tested here at all: the
 * cipher itself needs a device, this does not.
 */
class TokenEnvelopeTest {

    @Test
    fun `an envelope round-trips its two parts`() {
        val iv = byteArrayOf(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
        val ciphertext = byteArrayOf(-128, 0, 127, 42)

        val unpacked = TokenEnvelope.unpack(TokenEnvelope.pack(iv, ciphertext))

        assertArrayEquals(iv, unpacked!!.iv)
        assertArrayEquals(ciphertext, unpacked.ciphertext)
    }

    @Test
    fun `bytes that are not valid text survive intact`() {
        // Ciphertext is arbitrary bytes, not a string. Anything that round
        // trips through a character encoding on the way to disk will mangle
        // it, so the encoding has to be binary-safe.
        val iv = ByteArray(12) { it.toByte() }
        val ciphertext = ByteArray(64) { (it * 7 - 128).toByte() }

        val unpacked = TokenEnvelope.unpack(TokenEnvelope.pack(iv, ciphertext))

        assertArrayEquals(ciphertext, unpacked!!.ciphertext)
    }

    @Test
    fun `a malformed envelope is refused rather than half-read`() {
        // Every one of these has been seen in the wild as a corrupted or
        // partially-written preference value. None may throw.
        listOf("", "   ", "no-separator", ":", "onlyleft:", ":onlyright", "a:b:c")
            .forEach { assertNull("input: '$it'", TokenEnvelope.unpack(it)) }
    }

    @Test
    fun `input that is not base64 is refused rather than throwing`() {
        assertNull(TokenEnvelope.unpack("not!base64:also!not"))
    }

    @Test
    fun `the packed form carries no raw token text`() {
        val packed = TokenEnvelope.pack(ByteArray(12), "tok_secret".toByteArray())

        // Trivially true here because the caller encrypts first -- asserted
        // so that a future "simplification" that stores the plaintext has to
        // delete a test that says not to.
        assertEquals(false, packed.contains("tok_secret"))
    }
}
