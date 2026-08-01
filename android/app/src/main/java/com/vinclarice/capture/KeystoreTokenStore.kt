package com.vinclarice.capture

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.GeneralSecurityException
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * The access token, encrypted with a key that never leaves the device.
 *
 * Written against the Android Keystore directly, with no library. The
 * obvious candidate -- `androidx.security:security-crypto` and its
 * `EncryptedSharedPreferences` -- is deprecated: its 1.1.0 "stable" release
 * shipped with every API already marked deprecated and no further releases
 * planned, and Google's replacement guidance is exactly this. It is an easy
 * trap, because a library reaching stable normally means the opposite.
 *
 * The key lives in the Keystore and is not exportable, so a device backup
 * can only ever carry ciphertext that nothing elsewhere can read. The
 * preference file is still excluded from backup (see xml/backup_rules) --
 * not for secrecy but for correctness, since a restore would otherwise hand
 * a new device ciphertext with no key to open it.
 *
 * Keystore calls do real IPC and can be slow. Call this off the main
 * thread; [Connector] already runs inside a coroutine.
 */
class KeystoreTokenStore(
    context: Context,
    private val alias: String = DEFAULT_ALIAS,
) : TokenStore {

    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    override fun save(token: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val ciphertext = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString(KEY_TOKEN, TokenEnvelope.pack(cipher.iv, ciphertext))
            .apply()
    }

    override fun read(): String? {
        val stored = prefs.getString(KEY_TOKEN, null) ?: return null
        val parts = TokenEnvelope.unpack(stored) ?: return forget()

        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                existingKey() ?: return forget(),
                GCMParameterSpec(TAG_LENGTH_BITS, parts.iv),
            )
            String(cipher.doFinal(parts.ciphertext), Charsets.UTF_8)
        } catch (unreadable: GeneralSecurityException) {
            // Not exceptional, and never a crash. A key can genuinely go
            // away underneath a stored value: a restore onto a new device,
            // an OEM firmware update, keystore corruption. Mishandling this
            // is a large part of why the library above was abandoned.
            //
            // Treat it as "there is no token": drop the unreadable blob and
            // the dead key so the app asks to be connected again, rather
            // than failing every capture with a decryption error nobody can
            // act on.
            forget()
        }
    }

    override fun clear() {
        forget()
    }

    /** Always null, so callers can `return forget()` where a token was
     *  expected and the intent stays readable. */
    private fun forget(): String? {
        prefs.edit().remove(KEY_TOKEN).apply()
        runCatching { keyStore().deleteEntry(alias) }
        return null
    }

    private fun keyStore(): KeyStore =
        KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }

    private fun existingKey(): SecretKey? =
        keyStore().getKey(alias, null) as? SecretKey

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
                // False, deliberately. A key that requires user
                // authentication is permanently invalidated when the secure
                // lock screen is removed or biometrics are re-enrolled --
                // after which every capture would throw. Capture has to keep
                // working from a background job on a device whose owner just
                // changed their PIN.
                .setUserAuthenticationRequired(false)
                .build()
        )
        return generator.generateKey()
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val DEFAULT_ALIAS = "clarice_capture_token"
        const val PREFS_NAME = "clarice_capture_secret"
        const val KEY_TOKEN = "token"
        const val KEY_SIZE_BITS = 256
        const val TAG_LENGTH_BITS = 128
    }
}
