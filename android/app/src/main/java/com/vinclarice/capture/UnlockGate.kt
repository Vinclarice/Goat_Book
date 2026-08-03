package com.vinclarice.capture

import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

/** What came back from asking the phone to unlock itself. */
sealed interface UnlockResult

data object Unlocked : UnlockResult

/** Backed out of the prompt on purpose -- not a failure, so it is not
 *  shown as one. */
data object UnlockCancelled : UnlockResult

/** Locked out, no biometric enrolled and no device credential set, or
 *  something the platform itself refused. */
data class UnlockFailed(val message: String) : UnlockResult

/**
 * Asks whoever is holding the phone to prove it, once, using whatever the
 * phone's own lock screen already accepts.
 *
 * A seam for the same reason [TokenStore] is one: what backs it is a real
 * system service with no JVM implementation, so what it *means* to gate on
 * an unlock lives in [Root]'s wiring and this interface's callers, and the
 * mechanism itself is verified on a device rather than in a unit test.
 */
interface UnlockGate {
    fun requestUnlock(onResult: (UnlockResult) -> Unit)
}

/**
 * [BIOMETRIC_STRONG] or [DEVICE_CREDENTIAL], never just the first: gating
 * the app behind a fingerprint requirement would lock out anyone whose
 * phone is secured with a PIN or pattern instead, which is most of the
 * point of "whatever the phone already accepts".
 *
 * The two are mutually exclusive with a custom negative-button label in
 * this API -- when DEVICE_CREDENTIAL is allowed, the system supplies its
 * own way back to that fallback, so none is set here.
 */
class BiometricUnlockGate(private val activity: FragmentActivity) : UnlockGate {

    override fun requestUnlock(onResult: (UnlockResult) -> Unit) {
        val prompt = BiometricPrompt(
            activity,
            ContextCompat.getMainExecutor(activity),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(
                    result: BiometricPrompt.AuthenticationResult,
                ) {
                    onResult(Unlocked)
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    val cancelled = errorCode == BiometricPrompt.ERROR_USER_CANCELED ||
                        errorCode == BiometricPrompt.ERROR_NEGATIVE_BUTTON ||
                        errorCode == BiometricPrompt.ERROR_CANCELED
                    onResult(if (cancelled) UnlockCancelled else UnlockFailed(errString.toString()))
                }

                // A single wrong fingerprint, not a final answer -- the
                // prompt stays open for another attempt, so there is
                // nothing to report until onAuthenticationError or
                // onAuthenticationSucceeded actually ends it.
                override fun onAuthenticationFailed() = Unit
            },
        )

        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Unlock Clarice Capture")
            .setAllowedAuthenticators(BIOMETRIC_STRONG or DEVICE_CREDENTIAL)
            .build()
        prompt.authenticate(info)
    }
}
