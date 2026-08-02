package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * What another app handed us, if anything.
 *
 * A pure function over the four things an Android share amounts to, so the
 * awkward parts -- a browser sending a title and a URL separately, a share
 * that contains nothing worth keeping -- are decided here rather than in an
 * activity that can only be tested by hand.
 */
class SharedTextTest {

    private fun shared(
        action: String? = "android.intent.action.SEND",
        type: String? = "text/plain",
        text: String? = null,
        subject: String? = null,
    ) = SharedText.from(action, type, text, subject)

    @Test
    fun `a plain text share is the text`() {
        assertEquals("a thought from elsewhere", shared(text = "a thought from elsewhere"))
    }

    @Test
    fun `a shared link is kept as text`() {
        // The plan is explicit: no source-link model yet. Whether a reference
        // needs structured URLs, titles and provenance belongs to the later
        // second-brain design, and guessing now would be a schema nobody
        // asked for.
        assertEquals("https://example.com/article", shared(text = "https://example.com/article"))
    }

    @Test
    fun `a title and a link both survive`() {
        // How browsers share: the page title as the subject, the URL as the
        // text. Taking only the text would throw away the half a person is
        // most likely to recognise later.
        assertEquals(
            "How to Build a Bittern\nhttps://example.com/article",
            shared(text = "https://example.com/article", subject = "How to Build a Bittern"),
        )
    }

    @Test
    fun `a subject already present in the text is not repeated`() {
        // Some apps send the same string twice. Two copies of a headline is
        // not extra information, it is a mess to tidy up later.
        assertEquals(
            "How to Build a Bittern",
            shared(text = "How to Build a Bittern", subject = "How to Build a Bittern"),
        )
    }

    @Test
    fun `a subject alone is still worth keeping`() {
        assertEquals("Just a headline", shared(subject = "Just a headline"))
    }

    @Test
    fun `surrounding whitespace is trimmed`() {
        assertEquals("a thought", shared(text = "  a thought\n\n"))
    }

    @Test
    fun `a share with nothing in it is nothing`() {
        assertNull(shared(text = null, subject = null))
        assertNull(shared(text = "   "))
        assertNull(shared(text = "", subject = ""))
    }

    @Test
    fun `an ordinary launch is not a share`() {
        // MainActivity asks this on every start, so the launcher icon has to
        // come back with nothing rather than an empty draft.
        assertNull(shared(action = "android.intent.action.MAIN", text = "ignored"))
        assertNull(shared(action = null, text = "ignored"))
    }

    @Test
    fun `a share this app cannot hold is refused`() {
        // The manifest only offers text/plain, but an intent can still
        // arrive with something else, and inventing a caption for an image
        // is not capture.
        assertNull(shared(type = "image/png", text = "ignored"))
        assertNull(shared(type = null, text = "ignored"))
    }
}
