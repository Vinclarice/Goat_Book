package com.vinclarice.capture

/**
 * What one drain achieved.
 *
 * [finished] is the question the background worker actually asks: is there
 * anything left that another wake-up could fix? Stalled and rejected items
 * deliberately do not count -- they need a person, and reporting them as
 * outstanding would have the system retry forever over something no retry
 * can resolve.
 */
data class DrainReport(val delivered: Int, val waiting: Int) {
    val finished: Boolean get() = waiting == 0
}

/**
 * Empties the queue, one capture at a time, oldest first.
 *
 * Every interesting decision here is about when to *stop*. A drain that
 * keeps going after the network has plainly gone spends an attempt from
 * every item's budget on a single outage, and can stall a whole queue in one
 * pass over five minutes of no signal. So a failure that says something
 * about the connection ends the run, while a failure that says something
 * about one capture does not.
 */
class QueueDrainer(
    private val api: ClariceApi,
    private val store: TokenStore,
    private val queue: CaptureQueue,
) {

    suspend fun drain(): DrainReport {
        var delivered = 0

        // Read once. The token cannot change under a drain -- disconnecting
        // happens on the screen, and this runs when nobody is on it.
        val token = store.read() ?: return report(delivered)

        for (item in queue.waiting()) {
            when (api.capture(token, item.text, item.key)) {
                Disposition.DELIVERED -> {
                    queue.delivered(item.key)
                    delivered++
                }
                // The connection, not the capture. Charging the rest of the
                // queue for this would be charging them all for one outage.
                Disposition.RETRY_LATER -> {
                    queue.failed(item.key)
                    return report(delivered)
                }
                // Equally about the connection rather than any one item, and
                // no attempt is charged at all: a revoked token has a known
                // fix, and burning budget on it would strand the queue at
                // the moment reconnecting was meant to drain it.
                Disposition.NEEDS_RECONNECT -> return report(delivered)
                // This one *is* about the capture. Stopping here would let a
                // single unacceptable text block every good capture behind
                // it, indefinitely.
                Disposition.REJECTED -> queue.rejected(item.key)
            }
        }

        return report(delivered)
    }

    private fun report(delivered: Int) = DrainReport(delivered, queue.waiting().size)
}
