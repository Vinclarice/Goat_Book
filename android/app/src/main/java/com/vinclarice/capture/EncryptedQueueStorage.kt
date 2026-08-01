package com.vinclarice.capture

import android.content.Context
import android.content.SharedPreferences

/**
 * The pending queue, encrypted at rest.
 *
 * Capture text is somebody's unfiltered thinking -- often more sensitive
 * than the credential guarding it -- so it gets the same treatment as the
 * token, under its own key.
 *
 * Its own key specifically, and its own file. Disconnecting an account
 * deletes the token's key; sharing one would silently destroy every unsent
 * thought at the moment someone was told their token had stopped working,
 * which is the worst possible moment. Both halves of the identity are
 * parameterised for tests, because parameterising one and not the other has
 * already cost this project a live token off a real phone.
 */
class EncryptedQueueStorage(
    context: Context,
    alias: String = DEFAULT_ALIAS,
    prefsName: String = DEFAULT_PREFS,
) : QueueStorage {

    private val cipher = KeystoreCipher(alias)

    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences(prefsName, Context.MODE_PRIVATE)

    override fun load(): List<PendingCapture> {
        val stored = prefs.getString(KEY_QUEUE, null) ?: return emptyList()
        // Unreadable means the key is gone -- a restore onto a new device, a
        // firmware update. The thoughts inside are already unrecoverable;
        // ciphertext without its key is not coming back. Reporting an empty
        // queue is the only thing left that keeps the app working, and the
        // next save overwrites the dead blob under a fresh key.
        val plaintext = cipher.decrypt(stored) ?: return emptyList()
        return QueueDocument.decode(plaintext)
    }

    override fun save(items: List<PendingCapture>) {
        // commit, not apply. This is called on the way to and from network
        // work, including from a background worker the system may stop
        // immediately afterwards, and an asynchronous write that loses the
        // race loses a capture.
        prefs.edit()
            .putString(KEY_QUEUE, cipher.encrypt(QueueDocument.encode(items)))
            .commit()
    }

    private companion object {
        const val DEFAULT_ALIAS = "clarice_capture_queue"
        const val DEFAULT_PREFS = "clarice_capture_queue_store"
        const val KEY_QUEUE = "queue"
    }
}
