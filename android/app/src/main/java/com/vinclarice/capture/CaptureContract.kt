package com.vinclarice.capture

/**
 * What the client does about a capture response.
 *
 * The server side of this contract lives in design/bittern-plan.md under
 * "Mobile handoff contract", and is deliberately small: both this client
 * and any future iOS one read the same table rather than each inferring
 * server behaviour from its own experiments.
 */
enum class Disposition {
    /** Stored. Drop it from the queue and stop retrying. */
    DELIVERED,

    /** The request itself is wrong. Keep the text, show a fixable error,
     *  and do not retry it unchanged -- the same request will fail again. */
    REJECTED,

    /** The token no longer works. Keep the text and ask the person to
     *  reconnect; a queue is never emptied because a credential expired. */
    NEEDS_RECONNECT,

    /** Nothing is wrong with the capture, only with right now. */
    RETRY_LATER,
}

/**
 * Maps an HTTP status to what the client should do with the capture.
 *
 * 200 and 201 are the same outcome on purpose. 201 means this request
 * stored it; 200 means an earlier request with the same Idempotency-Key
 * already did. Both mean the thought is safe, which is the entire point of
 * the key -- a client that treated 200 as failure would retry forever
 * against a server that keeps answering "already done".
 */
fun dispositionFor(statusCode: Int): Disposition = when (statusCode) {
    200, 201 -> Disposition.DELIVERED
    400 -> Disposition.REJECTED
    401, 403 -> Disposition.NEEDS_RECONNECT
    // Everything else, including statuses this client has never seen, is
    // treated as temporary. Retrying something permanently broken costs a
    // few backed-off background attempts; treating an unknown response as
    // rejection would discard a thought the person typed, and that is the
    // one failure this app exists to prevent.
    else -> Disposition.RETRY_LATER
}
