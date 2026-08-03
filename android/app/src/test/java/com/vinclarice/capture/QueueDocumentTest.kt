package com.vinclarice.capture

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Turning the queue into a string and back.
 *
 * Separated from the encryption so it can be tested on the JVM, and because
 * the two failure modes are genuinely different: a cipher that will not open
 * is unrecoverable, whereas a document with one bad entry in it should cost
 * that entry and nothing else.
 */
class QueueDocumentTest {

    private val one = PendingCapture(
        key = "key-1",
        text = "a thought with \"quotes\" and\na newline",
        createdAt = 1_700_000_000_000,
        attempts = 2,
        state = QueueState.WAITING,
    )
    private val two = PendingCapture(
        key = "key-2",
        text = "another",
        createdAt = 1_700_000_001_000,
        attempts = 5,
        state = QueueState.STALLED,
    )

    @Test
    fun `a queue survives the round trip unchanged`() {
        // Quotes and newlines are ordinary in prose typed in a hurry, which
        // is why this is built with a JSON library rather than string
        // concatenation.
        val encoded = QueueDocument.encode(listOf(one, two))

        assertEquals(listOf(one, two), QueueDocument.decode(encoded))
    }

    @Test
    fun `an empty queue round trips`() {
        assertEquals(emptyList<PendingCapture>(), QueueDocument.decode(QueueDocument.encode(emptyList())))
    }

    @Test
    fun `every state survives`() {
        val all = QueueState.entries.mapIndexed { index, state ->
            PendingCapture("key-$index", "text", createdAt = index.toLong(), state = state)
        }

        assertEquals(all, QueueDocument.decode(QueueDocument.encode(all)))
    }

    @Test
    fun `one unreadable entry costs only that entry`() {
        // The alternative -- discarding the document because one record in it
        // is wrong -- would throw away every other thought in the queue.
        val damaged = """[{"key":"key-1","text":"kept","createdAt":1,"attempts":0,"state":"WAITING"},
                          {"key":"key-2"}]"""

        val recovered = QueueDocument.decode(damaged)

        assertEquals(listOf("kept"), recovered.map { it.text })
    }

    @Test
    fun `an unknown state is treated as waiting rather than dropped`() {
        // A state written by a future version of the app. Retrying it is
        // wrong at worst; dropping it loses somebody's note.
        val forward = """[{"key":"key-1","text":"kept","createdAt":1,"attempts":0,"state":"SOMETHING_NEW"}]"""

        val recovered = QueueDocument.decode(forward)

        assertEquals(QueueState.WAITING, recovered.single().state)
    }

    @Test
    fun `tags survive the round trip too`() {
        val tagged = PendingCapture(
            key = "key-1", text = "design a boss fight", createdAt = 1,
            tags = listOf("game-dev", "movies"),
        )

        val recovered = QueueDocument.decode(QueueDocument.encode(listOf(tagged)))

        assertEquals(tagged, recovered.single())
    }

    @Test
    fun `a record written before tags existed reads as having none`() {
        val fromAnOlderVersion =
            """[{"key":"key-1","text":"kept","createdAt":1,"attempts":0,"state":"WAITING"}]"""

        val recovered = QueueDocument.decode(fromAnOlderVersion)

        assertEquals(emptyList<String>(), recovered.single().tags)
    }

    @Test
    fun `an unreadable document reads as an empty queue rather than throwing`() {
        // Nothing can be salvaged here, but crashing on open would make the
        // app unusable rather than merely empty.
        assertTrue(QueueDocument.decode("not json at all").isEmpty())
        assertTrue(QueueDocument.decode("").isEmpty())
        assertTrue(QueueDocument.decode("{}").isEmpty())
    }
}
