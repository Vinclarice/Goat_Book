package com.vinclarice.capture

/**
 * What to tell somebody when a request did not work.
 *
 * **One place, because there were twelve.** Every API client in this package
 * built its failure text the same way — `"$serverName answered ${code}."` —
 * so a three-digit number was the whole message. Vince met one on September 9,
 * 2026 and asked the only sensible question: *"Clarice answered 403?"*
 *
 * `principles.md` forbids exactly that: *state what happened in plain
 * language, give a sensible next action... generic error with no recovery path
 * is not an acceptable steady state.* A status code is neither half of it.
 *
 * **The code survives, demoted to brackets.** Deleting it would trade one
 * unusable message for another — the number is the only diagnostic when
 * something genuinely unexpected happens, and the person reading these is also
 * the person who reads this application's logs. So the sentence leads and the
 * number follows, which is the opposite of where they started.
 *
 * **The server is named by the caller, not assumed.** `Backends` allows a
 * split install where captures go to a different host, and three of the four
 * clients had "Clarice" written into them while the fourth passed a name.
 */

/**
 * A status this client did not expect, said as a sentence.
 *
 * Only for codes a call site has no better answer for. A 401 that means
 * *reconnect*, or a 409 the server explained in its own words, is worth more
 * than anything here — this is the fallback, not the first resort.
 */
fun whatWentWrong(serverName: String, code: Int): String {
    val sentence = when (code) {
        // **The most likely failure this app will ever show.** The deploy
        // playbook recreates the container mid-run, so a phone used during one
        // sees this — and "try again in a moment" is precisely right for it in
        // a way that a general server-fault message is not.
        502, 503 -> "$serverName is restarting. Try again in a moment."
        408, 504 -> "$serverName took too long to answer. Try again."
        // The one case where *try again* is the wrong advice, because retrying
        // is what caused it.
        //
        // **A minute is accurate here and would not be everywhere.** This is
        // nginx's 429 and every zone in `nginx-clarice.conf.j2` is an `r/m`
        // rate, so the window really is about a minute. Django's own lockout
        // also answers 429 and can be an hour — `ClariceApi` handles that one
        // separately and says no number when it cannot read the real wait.
        429 -> "Too many requests just now. Wait a minute, then try again."
        404 -> "$serverName could not find that. It may have been deleted or " +
            "changed somewhere else — reload and check."
        // Two surfaces disagreeing about one record: the website and the phone
        // acting on the same task. Reloading is the actual fix and nothing
        // else is.
        409 -> "That has already changed somewhere else. Reload and try again."
        in 500..599 -> "Something went wrong at $serverName's end. That is " +
            "usually brief — try again in a minute."
        in 400..499 -> "$serverName would not accept that. Try again, and if " +
            "it keeps happening the app and the server may disagree about " +
            "something."
        else -> "$serverName answered in a way this app did not expect. Try again."
    }
    return "$sentence ($code)"
}

/**
 * The request never arrived.
 *
 * Distinct from [couldNotUnderstand] on purpose: this one is the network, and
 * the next action is about the connection rather than about the request.
 */
fun couldNotReach(serverName: String): String =
    "Could not reach $serverName. Check your connection and try again."

/**
 * It arrived, came back, and could not be read.
 *
 * ~~"Unexpected response from that address."~~ — *that address* named nothing
 * a person could act on, and it read like a network failure while meaning the
 * opposite. This means the server answered and the answer did not parse, which
 * in practice is a client older than the server it is talking to.
 */
fun couldNotUnderstand(serverName: String): String =
    "$serverName sent something this app could not read. Try again, and " +
        "update the app if it keeps happening."
