package com.vinclarice.capture

/**
 * One server, and the credential slot that belongs to it.
 *
 * The slot travels with the URL rather than being chosen at the call site,
 * because the two are only ever correct together: a token minted by one
 * server is worthless to the other and must never be sent to it.
 */
data class Backend(
    val baseUrl: String,
    val tokenAlias: String,
    val tokenPrefs: String,
)

/**
 * Which server each concern talks to.
 *
 * This client faces two of them now. Capture belongs to Second Mind, where a
 * thought becomes a node; Today and Agenda stay with Clarice, which is the
 * only one that has tasks at all. See Second Mind's
 * docs/android-two-backends.md for why it is one client rather than two apps
 * -- briefly, a fork had already duplicated twenty-two files including both
 * known queue defects.
 *
 * Pure, and holding names rather than stores, so the decision is unit-testable
 * without a Context. Whoever wires up the activity turns a [Backend] into a
 * real [KeystoreTokenStore]; nothing here touches the Keystore.
 *
 * **Unconfigured means unsplit, not broken.** A build with no
 * `-PsecondMindBaseUrl` behaves exactly as every build before this one did:
 * one server, one token, one login. That is what makes this additive rather
 * than a migration, and it is why the empty string is a supported value
 * instead of a precondition failure -- `buildConfigField` has no way to say
 * "absent".
 */
class Backends(clariceBaseUrl: String, secondMindBaseUrl: String) {

    // Trimmed, because an unset gradle property arrives as "" and a mistyped
    // one arrives as whitespace. Both mean the same thing to a person and
    // should mean the same thing here.
    private val secondMind: String = secondMindBaseUrl.trim()

    /** Whether capture and the workspace face different servers. */
    val isSplit: Boolean = secondMind.isNotEmpty()

    /**
     * Today and Agenda. Always Clarice, and always the token slot every
     * existing install already holds -- this half must keep working through
     * the split without anyone being logged out.
     */
    val workspace: Backend = Backend(
        baseUrl = clariceBaseUrl,
        tokenAlias = KeystoreTokenStore.DEFAULT_ALIAS,
        tokenPrefs = KeystoreTokenStore.DEFAULT_PREFS,
    )

    /**
     * Capture, the queue, and the share target.
     *
     * Identical to [workspace] when unsplit -- the same object, so the two
     * cannot drift into asking one server for two separate logins.
     */
    val capture: Backend =
        if (isSplit) {
            Backend(
                baseUrl = secondMind,
                tokenAlias = SECOND_MIND_ALIAS,
                tokenPrefs = SECOND_MIND_PREFS,
            )
        } else {
            workspace
        }

    private companion object {
        const val SECOND_MIND_ALIAS = "second_mind_capture_token"
        const val SECOND_MIND_PREFS = "second_mind_capture_secret"
    }
}
