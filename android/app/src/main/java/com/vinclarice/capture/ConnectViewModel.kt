package com.vinclarice.capture

import java.time.Duration
import java.time.Instant
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Everything the Connect screen shows, so the composable can be a thin
 * rendering of it and the decisions stay testable without a device.
 */
data class ConnectUiState(
    val token: String = "",
    val username: String = "",
    val password: String = "",
    /** The authenticator or recovery code, for an account with a second
     *  factor. Empty for everybody else, and the server ignores it there. */
    val totp: String = "",
    val checking: Boolean = false,
    val error: String? = null,
    val connectedAs: Identity? = null,
    /**
     * The pairing in progress, or null when there is none —
     * `android-login-redesign-plan.md` Half B.
     *
     * **Holds the user code and never the device code.** The device code is
     * the credential half of the flow, and anything on this state object can
     * end up in a log, a crash report or on a screen.
     */
    val pairing: PairingUiState? = null,
)

/** A pairing waiting for somebody to approve it, as the screen needs it. */
data class PairingUiState(
    /** The short code to read off this phone and type into the web. */
    val userCode: String,
    /** When it stops being approvable, or null if the server did not say. */
    val expiresAt: Instant? = null,
)


/**
 * Where to approve a pairing, as a person would type it into a browser.
 *
 * **Derived from the base URL the app actually talks to, never from the
 * server's display name.** The first version of the Connect screen built this
 * from `serverName.lowercase() + ".com"`, which renders `clarice.com/pair` --
 * a domain this project does not own, printed in large type as an instruction.
 * A name is for prose; an address has to come from the URL.
 *
 * The scheme is dropped because nobody types it, and because the thing on
 * screen is being read aloud into another device rather than clicked.
 */
fun pairingAddress(baseUrl: String): String =
    baseUrl.trim()
        .removePrefix("https://")
        .removePrefix("http://")
        .trimEnd('/') + "/pair"

class ConnectViewModel(
    private val connector: Connector,
    // Injected rather than read from android.os.Build in here, so this
    // stays a plain JVM test subject. MainActivity supplies the real
    // model string; every test gets the same default a device would
    // fall back to reading a blank one.
    private val deviceLabel: String = "Android",
    /** Named on screen, so a split install says which server to connect to. */
    val serverName: String = "Clarice",
    /**
     * The URL this client talks to, used only to tell somebody where to go and
     * approve. Read from `BuildConfig` at the call site, so a debug build
     * pointed at staging says *staging* rather than sending somebody to
     * production to approve a pairing that is waiting somewhere else.
     */
    private val baseUrl: String = "",
    /**
     * Read once per pairing, to turn the server's expiry into a poll budget.
     *
     * Injected rather than called inside, per `principles.md`: it makes the
     * whole wait assertable at any instant a test likes, and turns the phone's
     * clock from an assumption into a visible choice at the call site.
     */
    private val now: () -> Instant = Instant::now,
) {

    /** Where to approve, for the screen. */
    val pairAddress: String get() = pairingAddress(baseUrl)

    private val _state = MutableStateFlow(ConnectUiState())
    val state: StateFlow<ConnectUiState> = _state.asStateFlow()

    val isConnected: Boolean get() = connector.isConnected()

    fun onTokenChange(value: String) {
        // Clearing the error as soon as they start correcting it: leaving
        // it under the field makes it ambiguous whether it describes the
        // old attempt or what is being typed now.
        _state.value = _state.value.copy(token = value, error = null)
    }

    fun onUsernameChange(value: String) {
        _state.value = _state.value.copy(username = value, error = null)
    }

    fun onPasswordChange(value: String) {
        _state.value = _state.value.copy(password = value, error = null)
    }

    fun setTotp(value: String) {
        _state.value = _state.value.copy(totp = value, error = null)
    }

    suspend fun connect() {
        _state.value = _state.value.copy(checking = true, error = null)

        when (val outcome = connector.connect(_state.value.token)) {
            is Connected -> _state.value = ConnectUiState(
                // Field emptied, not merely hidden. The token is stored now,
                // and "never display it after saving" has to be true of the
                // screen as well as of the log.
                token = "",
                checking = false,
                connectedAs = outcome.identity,
            )
            // Both failures keep what was typed. Someone who pasted a token
            // with one character missing should be able to fix it rather
            // than fetch all forty again.
            is Refused -> fail(outcome.message)
            is Failed -> fail(outcome.message)
            Blank -> fail("Paste the access token from the $serverName web app.")
        }
    }

    /**
     * Log in with a username and password instead of pasting a token.
     *
     * The password leaves the field the moment this returns, whichever way
     * it went -- there is no outcome where it is worth having on screen a
     * moment longer than the request that used it. The username stays on
     * failure, since retyping it buys nothing a wrong password didn't
     * already cost.
     */
    suspend fun logIn() {
        _state.value = _state.value.copy(checking = true, error = null)
        val username = _state.value.username
        val password = _state.value.password
        val totp = _state.value.totp.trim()

        when (val outcome = connector.logIn(username, password, deviceLabel, totp)) {
            is Connected -> _state.value = ConnectUiState(
                checking = false,
                connectedAs = outcome.identity,
            )
            is Refused -> failLogin(username, outcome.message)
            is Failed -> failLogin(username, outcome.message)
            Blank -> failLogin(username, "Enter your username and password.")
        }
    }

    private fun failLogin(username: String, message: String) {
        _state.value = _state.value.copy(
            username = username,
            password = "",
            // Cleared with the password, and for the same reason: a code is
            // single-use and a stale one in the box is worse than an empty
            // one, because it looks like it might still work.
            totp = "",
            checking = false,
            error = message,
        )
    }

    fun disconnect() {
        connector.disconnect()
        _state.value = ConnectUiState()
    }

    private fun fail(message: String) {
        _state.value = _state.value.copy(checking = false, error = message)
    }

    /**
     * Ask to be connected, and wait for somebody to say yes —
     * `android-login-redesign-plan.md` Half B, increment 4.
     *
     * **This is the half that delivers the requirement.** Nothing secret is
     * carried to this phone: it asks, shows a code a person carries the *other*
     * way, and the token arrives over this connection.
     *
     * Suspends for the whole flow rather than launching, so the caller owns the
     * lifetime -- the screen cancels it by cancelling its scope, and a test
     * runs the entire wait on a virtual clock.
     */
    suspend fun beginPairing() {
        _state.value = _state.value.copy(checking = true, error = null, pairing = null)

        val started = when (val begun = connector.beginPairing(deviceLabel)) {
            is PairingStartFailed -> {
                _state.value = _state.value.copy(checking = false, error = begun.reason)
                return
            }
            is PairingBegun -> begun.started
        }

        _state.value = _state.value.copy(
            checking = false,
            pairing = PairingUiState(started.userCode, started.expiresAt),
        )

        // **Bounded, and bounded by the server's own expiry** rather than by a
        // lifetime copied from it. A constant here would be D8's mirrored
        // number arriving by the back door -- two places deciding how long a
        // pairing lives, drifting the first time one changes.
        //
        // The clock is read once, here, rather than each time round the loop:
        // `principles.md`'s injected clock, and it keeps the whole wait
        // testable on virtual time.
        val budget = started.expiresAt
            ?.let { Duration.between(now(), it).seconds / started.intervalSeconds }
            ?.coerceIn(1, MAX_POLLS.toLong())
            ?.toInt()
            ?: DEFAULT_POLLS

        repeat(budget) {
            delay(started.intervalSeconds * 1000L)
            // Null is "not yet", which is the ordinary answer for most of this.
            when (val outcome = connector.collectPairing(started.deviceCode)) {
                null -> Unit
                is Connected -> {
                    _state.value = ConnectUiState(connectedAs = outcome.identity)
                    return
                }
                // A blip does not end it. The code on screen is still good and
                // somebody may be walking to a laptop with it, so throwing the
                // pairing away over one failed request would discard something
                // about to work. The budget above is what stops this forever.
                is Failed -> Unit
                is Refused -> {
                    _state.value = _state.value.copy(
                        pairing = null, error = outcome.message
                    )
                    return
                }
                Blank -> Unit
            }
        }

        _state.value = _state.value.copy(
            pairing = null,
            error = "Nobody approved that code in time. Try again.",
        )
    }

    /** Stop waiting. The request expires on its own, so there is nothing to
     *  tell the server -- this only stops asking and clears the screen. */
    fun cancelPairing() {
        _state.value = _state.value.copy(pairing = null, checking = false)
    }

    private companion object {
        /** When the server named no expiry. Ten minutes at the default
         *  interval, which is what the server's own lifetime happens to be --
         *  a fallback rather than a second copy of it. */
        const val DEFAULT_POLLS = 120

        /** A ceiling whatever the server says, so a nonsense expiry cannot
         *  turn this into an unbounded poll loop against a rate-limited
         *  endpoint. */
        const val MAX_POLLS = 240
    }

}
