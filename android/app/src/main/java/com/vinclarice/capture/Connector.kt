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

data class Connected(val identity: Identity) : ConnectOutcome

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
) {
    suspend fun connect(rawInput: String): ConnectOutcome {
        // Pasting from a browser or password manager routinely brings a
        // trailing newline along, and a token rejected for an invisible
        // reason is the worst kind of rejection.
        val token = rawInput.trim()
        if (token.isEmpty()) return Blank

        return when (val result = api.identify(token)) {
            is Identified -> {
                store.save(token)
                Connected(result.identity)
            }
            // Storage is untouched on both failure paths. Re-pasting a token
            // while offline must not cost someone the working one they had.
            Unauthorised -> Refused(
                "Clarice did not accept that token. Create a new one on the " +
                    "web and paste it again."
            )
            is Unreachable -> Failed(result.reason)
        }
    }

    fun isConnected(): Boolean = store.read() != null

    fun disconnect() = store.clear()
}
