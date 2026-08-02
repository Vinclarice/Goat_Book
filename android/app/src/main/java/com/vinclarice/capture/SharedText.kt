package com.vinclarice.capture

/**
 * What another app handed us, if anything worth keeping.
 *
 * Kept as a pure function over the four things a share amounts to, so that
 * the awkward cases are decided somewhere testable rather than inside an
 * activity. There are more of them than the feature suggests: a browser
 * sends a title and a URL as separate extras, some apps send the same string
 * as both, and the launcher itself arrives through the same entry point with
 * no share at all.
 *
 * Shared links are stored as capture text and nothing more. Whether a
 * reference needs structured URLs, titles, previews or provenance belongs to
 * the later second-brain design; inventing that schema here would be
 * guessing at it in the one place hardest to change later.
 */
object SharedText {

    private const val ACTION_SEND = "android.intent.action.SEND"
    private const val PLAIN_TEXT = "text/plain"

    fun from(action: String?, type: String?, text: String?, subject: String?): String? {
        if (action != ACTION_SEND) return null
        // The manifest only offers text/plain, but an intent can still arrive
        // with something else, and inventing a caption for an image is not
        // capture.
        if (type != PLAIN_TEXT) return null

        val body = text?.trim().orEmpty()
        val title = subject?.trim().orEmpty()

        return when {
            body.isEmpty() -> title.ifEmpty { null }
            // Some apps send the same string as both. Two copies of a
            // headline is not extra information.
            title.isEmpty() || body.contains(title) -> body
            // A title and a link both survive. Taking only the URL would
            // discard the half a person is most likely to recognise in a
            // week's time.
            else -> "$title\n$body"
        }
    }
}
