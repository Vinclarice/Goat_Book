package com.vinclarice.capture

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/**
 * The queue as a string, and back.
 *
 * Its whole design principle is that reading is more forgiving than writing.
 * Every path that cannot understand something prefers keeping too much to
 * dropping anything: a malformed record costs that record, an unrecognised
 * state is treated as ordinary, and only a document that yields nothing at
 * all yields nothing at all.
 *
 * That asymmetry is deliberate. The cost of keeping a bad entry is one
 * wasted request; the cost of dropping a good one is a thought somebody
 * typed and will never see again.
 */
object QueueDocument {

    fun encode(items: List<PendingCapture>): String {
        val array = JSONArray()
        items.forEach { item ->
            array.put(
                JSONObject()
                    .put(KEY, item.key)
                    .put(TEXT, item.text)
                    .put(CREATED_AT, item.createdAt)
                    .put(ATTEMPTS, item.attempts)
                    .put(STATE, item.state.name)
            )
        }
        return array.toString()
    }

    fun decode(raw: String): List<PendingCapture> {
        val array = try {
            JSONArray(raw)
        } catch (malformed: JSONException) {
            // Not an array at all -- truncated, empty, or written by
            // something else entirely. Nothing here is salvageable.
            return emptyList()
        }

        return (0 until array.length()).mapNotNull { index ->
            try {
                val json = array.getJSONObject(index)
                PendingCapture(
                    // getString, not optString: a record without a key cannot
                    // be delivered idempotently, and sending it under a new
                    // key is how one thought becomes two notes. Better to
                    // lose the record than to duplicate it.
                    key = json.getString(KEY),
                    text = json.getString(TEXT),
                    createdAt = json.getLong(CREATED_AT),
                    attempts = json.optInt(ATTEMPTS, 0),
                    state = stateOf(json.optString(STATE)),
                )
            } catch (unreadable: JSONException) {
                null
            }
        }
    }

    /** An unfamiliar state -- from a newer version, or a corrupted write --
     *  is treated as waiting. Retrying something that should have stopped is
     *  a wasted request; dropping it is a lost note. */
    private fun stateOf(name: String): QueueState =
        QueueState.entries.firstOrNull { it.name == name } ?: QueueState.WAITING

    private const val KEY = "key"
    private const val TEXT = "text"
    private const val CREATED_AT = "createdAt"
    private const val ATTEMPTS = "attempts"
    private const val STATE = "state"
}
