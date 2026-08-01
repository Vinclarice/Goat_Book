package com.vinclarice.capture

import android.content.Context
import android.content.SharedPreferences

/**
 * The access token, encrypted with a key that never leaves the device.
 *
 * The cipher itself now lives in [KeystoreCipher], which the pending-capture
 * queue shares. What remains here is the policy: where the ciphertext is
 * kept, and what "there is no token" means.
 *
 * Written against the Android Keystore directly, with no library. The
 * obvious candidate -- `androidx.security:security-crypto` and its
 * `EncryptedSharedPreferences` -- is deprecated: its 1.1.0 "stable" release
 * shipped with every API already marked deprecated and no further releases
 * planned, and Google's replacement guidance is exactly this. It is an easy
 * trap, because a library reaching stable normally means the opposite.
 *
 * The preference file is excluded from backup (see xml/backup_rules) -- not
 * for secrecy but for correctness, since a restore would otherwise hand a
 * new device ciphertext with no key to open it.
 *
 * Keystore calls do real IPC and can be slow. Call this off the main
 * thread; [Connector] already runs inside a coroutine.
 */
class KeystoreTokenStore(
    context: Context,
    alias: String = DEFAULT_ALIAS,
    // Parameterised alongside the alias, and for the same reason. When only
    // the alias was overridable, the instrumentation tests wrote to the real
    // app's preference file with a key the real app could not decrypt --
    // deleting a live token from a phone and sending its owner back to the
    // Connect screen. Isolating one half of the storage is isolating
    // neither.
    prefsName: String = DEFAULT_PREFS,
) : TokenStore {

    private val cipher = KeystoreCipher(alias)

    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences(prefsName, Context.MODE_PRIVATE)

    override fun save(token: String) {
        prefs.edit().putString(KEY_TOKEN, cipher.encrypt(token)).apply()
    }

    override fun read(): String? {
        val stored = prefs.getString(KEY_TOKEN, null) ?: return null
        // An unreadable value is not exceptional and never a crash. Treat it
        // as "there is no token": drop the dead blob and its key so the app
        // asks to be connected again, rather than failing every capture with
        // a decryption error nobody can act on. Mishandling this is a large
        // part of why the library above was abandoned.
        return cipher.decrypt(stored) ?: forget()
    }

    override fun clear() {
        forget()
    }

    /** Always null, so callers can `return forget()` where a token was
     *  expected and the intent stays readable. */
    private fun forget(): String? {
        prefs.edit().remove(KEY_TOKEN).apply()
        cipher.forget()
        return null
    }

    private companion object {
        const val DEFAULT_ALIAS = "clarice_capture_token"
        const val DEFAULT_PREFS = "clarice_capture_secret"
        const val KEY_TOKEN = "token"
    }
}
