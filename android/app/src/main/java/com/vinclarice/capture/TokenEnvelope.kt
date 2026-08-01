package com.vinclarice.capture

import java.util.Base64

/**
 * Framing for an encrypted token on its way to and from disk.
 *
 * AES/GCM hands back a ciphertext and the IV needed to decrypt it, and both
 * have to be stored. Keeping the framing here, apart from the cipher, is
 * what lets it be tested without a device -- and framing is where a silent
 * corruption hides, since a token that unpacks to the wrong bytes fails at
 * the server as a 401, indistinguishable from a revoked one.
 *
 * java.util.Base64 rather than android.util.Base64 for two reasons: it is
 * available from API 26, which is this app's floor, and the Android one is
 * a stub in JVM unit tests whose every method throws.
 */
object TokenEnvelope {

    data class Parts(val iv: ByteArray, val ciphertext: ByteArray) {
        // Data classes compare arrays by identity, which would make any
        // equality check here quietly wrong. Tests compare contents
        // explicitly; these exist so nobody trusts == by accident.
        override fun equals(other: Any?): Boolean = this === other
        override fun hashCode(): Int = System.identityHashCode(this)
    }

    private const val SEPARATOR = ":"

    fun pack(iv: ByteArray, ciphertext: ByteArray): String {
        val encoder = Base64.getEncoder()
        return encoder.encodeToString(iv) + SEPARATOR + encoder.encodeToString(ciphertext)
    }

    /** Null for anything that is not a well-formed envelope. Never throws:
     *  a corrupted preference is an ordinary state to recover from, not an
     *  exceptional one to crash on. */
    fun unpack(stored: String): Parts? {
        val halves = stored.split(SEPARATOR)
        if (halves.size != 2) return null
        val (left, right) = halves
        if (left.isBlank() || right.isBlank()) return null
        return try {
            val decoder = Base64.getDecoder()
            Parts(decoder.decode(left), decoder.decode(right))
        } catch (malformed: IllegalArgumentException) {
            null
        }
    }
}
