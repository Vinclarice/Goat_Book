package com.vinclarice.capture

import android.content.Context

/**
 * How somebody wants the app to behave, as distinct from what it knows.
 *
 * A seam like [TokenStore] and [QueueStorage], for the same reason: it keeps
 * the decisions testable on the JVM. Unlike those two this is not encrypted,
 * because a keyboard preference is not a secret and pretending otherwise
 * would imply the encryption elsewhere is decoration rather than necessity.
 */
interface CapturePreferences {

    /**
     * Whether the keyboard's Enter key sends the capture.
     *
     * There is no answer that suits everyone. Sending costs the ability to
     * type a newline at all, since a multiline field's Enter key is either
     * one thing or the other; a newline costs a tap on every capture, on the
     * only action the app has. Short captures make sending the better
     * default, which is not the same as making it right for everybody.
     */
    fun enterSends(): Boolean

    fun setEnterSends(sends: Boolean)
}

class AndroidCapturePreferences(
    context: Context,
    prefsName: String = DEFAULT_PREFS,
) : CapturePreferences {

    // Its own file, away from the token and the queue. Those two are
    // encrypted and excluded from backup; this one should follow a phone to
    // a new device like any other preference.
    private val prefs = context.applicationContext
        .getSharedPreferences(prefsName, Context.MODE_PRIVATE)

    override fun enterSends(): Boolean = prefs.getBoolean(KEY_ENTER_SENDS, true)

    override fun setEnterSends(sends: Boolean) {
        prefs.edit().putBoolean(KEY_ENTER_SENDS, sends).apply()
    }

    private companion object {
        const val DEFAULT_PREFS = "clarice_capture_settings"
        const val KEY_ENTER_SENDS = "enter_sends"
    }
}
