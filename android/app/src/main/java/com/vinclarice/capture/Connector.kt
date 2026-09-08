package com.vinclarice.capture

/**
 * Where the access token lives.
 *
 * An interface because the encryption underneath it is the part most likely
 * to change -- platform guidance on storing a secret has moved more than
 * once -- while what the app needs of it (keep one string, hand it back,
 * forget it) has not. Swapping the implementation should touch one class
 * and no tests but its own.
 */
interface TokenStore {
    fun save(token: String)
    fun read(): String?
    fun clear()
}

/**
 * What happened when someone tried to connect an account.
 *
 * None of these carries the token. Outcomes end up in logs, crash reports
 * and on screen, and the safest way to keep a secret out of all three is
 * never to hand it to them.
 */
sealed interface ConnectOutcome

data class Connected(
    val identity: Identity,
    /**
     * What this connection can actually do, or null when the server did not
     * say -- android-login-redesign-plan.md Half A. Carried through here
     * rather than re-fetched, because [whoAmI] has already asked the one
     * endpoint that answers it.
     */
    val capabilities: TokenCapabilities? = null,
) : ConnectOutcome

/** The server refused the token. A different token is needed. */
data class Refused(val message: String) : ConnectOutcome

/** The server could not be asked. The token may well be fine. */
data class Failed(val message: String) : ConnectOutcome

/** Nothing was entered. */
data object Blank : ConnectOutcome

/**
 * Validates a pasted token and keeps it only if it works.
 *
 * Validate-then-save rather than save-then-validate: a token the server has
 * already refused, sitting in storage, produces an app where every capture
 * fails and nothing explains why.
 */
class Connector(
    private val api: ClariceApi,
    private val store: TokenStore,
    /** Which server this one talks to, for the message when it says no. */
    private val serverName: String = "Clarice",
) {
    suspend fun connect(rawInput: String): ConnectOutcome {
        // Pasting from a browser or password manager routinely brings a
        // trailing newline along, and a token rejected for an invisible
        // reason is the worst kind of rejection.
        val token = rawInput.trim()
        if (token.isEmpty()) return Blank

        val outcome = ask(token)
        // Storage is written only on success, and untouched on both failure
        // paths. Re-pasting a token while offline must not cost someone the
        // working one they had.
        if (outcome is Connected) store.save(token)
        return outcome
    }

    /**
     * Trade a password for a token, and keep only the token.
     *
     * The password itself never reaches [store] -- it exists for the one
     * request this makes and nowhere else. What gets saved is whatever the
     * server minted, the same as a pasted token would be.
     */
    suspend fun logIn(
        username: String,
        password: String,
        label: String = "Android",
        /** The second factor, when the account has one. Blank is *not
         *  supplied*, which the server distinguishes from *wrong*. */
        totp: String = "",
    ): ConnectOutcome {
        if (username.isBlank() || password.isBlank()) return Blank

        return when (val result = api.login(username, password, label, totp)) {
            is LoggedIn -> {
                store.save(result.token)
                Connected(result.identity)
            }
            is InvalidCredentials -> Refused(result.message)
            is LoginUnreachable -> Failed(result.reason)
        }
    }

    /**
     * Who the stored token belongs to, according to the server.
     *
     * Asked rather than remembered. Caching the account name at connect time
     * would leave Settings cheerfully displaying an account for a token that
     * was revoked an hour ago -- and revocation is precisely what someone
     * opens that screen to check.
     *
     * [Blank] means there is no token to ask about. Nothing here writes to
     * storage: a [Refused] token stays exactly where it is, because
     * disconnecting is an action someone takes, not one that befalls them
     * because a request came back badly.
     */
    suspend fun whoAmI(): ConnectOutcome {
        val token = store.read() ?: return Blank
        return ask(token)
    }

    private suspend fun ask(token: String): ConnectOutcome =
        when (val result = api.identify(token)) {
            is Identified -> Connected(result.identity, result.capabilities)
            Unauthorised -> Refused(
                "$serverName did not accept that token. Log in again, or " +
                    "create a new one on the web and paste it."
            )
            is Unreachable -> Failed(result.reason)
        }

    fun isConnected(): Boolean = store.read() != null

    fun disconnect() = store.clear()

    /**
     * Ask the server to start a pairing — `android-login-redesign-plan.md`
     * Half B. Nothing is stored yet; this only mints a request that is inert
     * until somebody approves it on the web.
     */
    suspend fun beginPairing(label: String = "Android"): PairingStartResult =
        api.startPairing(label)

    /**
     * Ask once whether it has been approved. **Null means keep waiting**, which
     * is the ordinary answer for most of this flow.
     *
     * On success it goes through [connect], so a paired token is saved and
     * identified by exactly the code path a pasted one is. A second storage
     * route would be a second place the token could fail to be written.
     */
    suspend fun collectPairing(deviceCode: String): ConnectOutcome? =
        when (val polled = api.pollPairing(deviceCode)) {
            is PairingGranted -> connect(polled.token)
            PairingPending -> null
            is PairingPollFailed -> Failed(polled.reason)
        }

}
