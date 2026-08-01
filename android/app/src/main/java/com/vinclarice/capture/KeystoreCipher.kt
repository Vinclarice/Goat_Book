package com.vinclarice.capture

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.GeneralSecurityException
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * AES-256/GCM against a key that never leaves the device.
 *
 * Extracted from [KeystoreTokenStore] when the pending-capture queue needed
 * the same treatment. Two copies of a cipher is two places to get GCM
 * wrong, and the mistakes here are the silent kind.
 *
 * Each [alias] is an independent key. The token and the queue use different
 * ones deliberately: disconnecting an account destroys the token's key, and
 * a shared key would take the unsent thoughts with it.
 *
 * Keystore calls do real IPC and can be slow. Call this off the main thread.
 */
class KeystoreCipher(private val alias: String) {

    fun encrypt(plaintext: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        return TokenEnvelope.pack(cipher.iv, cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8)))
    }

    /**
     * Null when the value cannot be opened, never an exception.
     *
     * A key can genuinely go away underneath a stored value: a restore onto
     * a new device, an OEM firmware update, keystore corruption. Callers
     * recover by treating it as absent, which is the only recovery available
     * -- ciphertext without its key is gone, and pretending otherwise would
     * just move the failure somewhere less convenient.
     */
    fun decrypt(packed: String): String? {
        val parts = TokenEnvelope.unpack(packed) ?: return null
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                existingKey() ?: return null,
                GCMParameterSpec(TAG_LENGTH_BITS, parts.iv),
            )
            String(cipher.doFinal(parts.ciphertext), Charsets.UTF_8)
        } catch (unreadable: GeneralSecurityException) {
            null
        }
    }

    /** Drops the key. Anything still encrypted under it is unreadable after
     *  this, which is the point when the intent is to forget a secret --
     *  and why the caller has to mean it. */
    fun forget() {
        runCatching { keyStore().deleteEntry(alias) }
    }

    private fun keyStore(): KeyStore =
        KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }

    private fun existingKey(): SecretKey? = runCatching {
        keyStore().getKey(alias, null) as? SecretKey
    }.getOrNull()

    private fun secretKey(): SecretKey = existingKey() ?: generateKey()

    private fun generateKey(): SecretKey {
        val generator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            ANDROID_KEYSTORE,
        )
        generator.init(
            KeyGenParameterSpec.Builder(
                alias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(KEY_SIZE_BITS)
                // False, deliberately. A key requiring user authentication is
                // permanently invalidated when the secure lock screen is
                // removed or biometrics are re-enrolled -- after which every
                // capture would throw. Capture has to keep working from a
                // background job on a device whose owner just changed their
                // PIN.
                .setUserAuthenticationRequired(false)
                .build()
        )
        return generator.generateKey()
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val KEY_SIZE_BITS = 256
        const val TAG_LENGTH_BITS = 128
    }
}
