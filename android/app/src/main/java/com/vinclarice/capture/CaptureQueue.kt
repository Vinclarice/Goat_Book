package com.vinclarice.capture

/**
 * Why a queued capture is not being sent right now.
 *
 * [WAITING] is the ordinary state and the only one the background drain
 * touches. The other two are dead ends until a person intervenes, which is
 * the point: the app stops repeating a request that is not going to start
 * working, and says so, rather than deciding on somebody's behalf that the
 * thought is gone.
 */
enum class QueueState {
    /** Will be attempted again when there is a network. */
    WAITING,

    /** Attempts exhausted. Kept, with its key, for an explicit retry. */
    STALLED,

    /** The server refused the text itself. Repeating it changes nothing. */
    REJECTED,
}

/**
 * One captured thought that has not reached Clarice yet.
 *
 * [key] is generated once, when the text is first accepted, and never
 * changes -- including across a stall and a manual retry weeks later.
 * Regenerating it would turn one thought into two notes the moment the
 * network came back, which is the exact failure M1's idempotency exists to
 * make impossible.
 */
data class PendingCapture(
    val key: String,
    val text: String,
    val createdAt: Long,
    val attempts: Int = 0,
    val state: QueueState = QueueState.WAITING,
    /** Optional, same as at capture time. Carried through the queue so a
     *  capture typed with tags while offline does not lose them by the
     *  time it is finally sent. */
    val tags: List<String> = emptyList(),
)

/**
 * Where the queue survives process death.
 *
 * A seam, for the same reason [TokenStore] is one: the encryption underneath
 * is the part most likely to change, while what the queue needs of it -- keep
 * a list, hand it back -- will not.
 */
interface QueueStorage {
    fun load(): List<PendingCapture>
    fun save(items: List<PendingCapture>)
}

/**
 * The durable queue. Every capture enters here before any network call, so
 * there is no window in which a typed thought exists only in memory.
 *
 * Reads go through storage on every call rather than caching, because a
 * foreground submit and a background drain both mutate this and neither is
 * the owner of the truth.
 *
 * **Every operation holds [LOCK], and it is deliberately not per-instance.**
 * `add` and `delivered` each load, mutate and save; interleaved, the later
 * save silently discards the earlier one, so a thought typed while the worker
 * was finishing a delivery vanished and a delivered capture came back to be
 * sent again. Losing a capture is the one failure this app exists to prevent.
 *
 * The lock is on the companion rather than on `this` because [MainActivity]
 * and [CaptureWorker] each construct their own `CaptureQueue` over the same
 * storage. Two instances mean two monitors, so `@Synchronized` would look
 * like a fix, pass a test that shared one queue, and protect nothing in the
 * app. There is one store per process, so one process-wide monitor is the
 * matching scope.
 *
 * Contention is not a concern: two callers, both already off the main thread,
 * over a handful of rows.
 */
class CaptureQueue(
    private val storage: QueueStorage,
    private val ceiling: Int = DEFAULT_CEILING,
) {

    fun add(
        text: String,
        key: String,
        createdAt: Long,
        tags: List<String> = emptyList(),
    ): PendingCapture = synchronized(LOCK) {
        val item = PendingCapture(key = key, text = text, createdAt = createdAt, tags = tags)
        storage.save(all() + item)
        item
    }

    /** Everything still queued, oldest first, whatever its state. */
    fun all(): List<PendingCapture> = synchronized(LOCK) {
        storage.load().sortedBy { it.createdAt }
    }

    /** Only what the background drain should attempt. */
    fun waiting(): List<PendingCapture> = all().filter { it.state == QueueState.WAITING }

    fun find(key: String): PendingCapture? = all().firstOrNull { it.key == key }

    /** Gone for good, and only ever called after a parsed server response. */
    fun delivered(key: String) = synchronized(LOCK) {
        storage.save(all().filterNot { it.key == key })
    }

    /**
     * One attempt spent. Reaching [ceiling] stops the retrying, not the
     * keeping -- the text and the key stay exactly as they were.
     */
    fun failed(key: String) = update(key) { item ->
        val attempts = item.attempts + 1
        item.copy(
            attempts = attempts,
            state = if (attempts >= ceiling) QueueState.STALLED else item.state,
        )
    }

    /**
     * The server refused the text. No attempt is charged, because the
     * ceiling exists to bound *pointless repetition*, and this will not be
     * repeated at all.
     */
    fun rejected(key: String) = update(key) { it.copy(state = QueueState.REJECTED) }

    /**
     * A person asking for one more go. The allowance resets; the key does
     * not, so this is still the same write as the first attempt.
     */
    fun retry(key: String) = update(key) {
        it.copy(attempts = 0, state = QueueState.WAITING)
    }

    /**
     * Bookkeeping for an item that is no longer there is a no-op, never a
     * resurrection and never a throw: a foreground submit and a background
     * drain can deliver the same capture at the same moment, and the loser
     * of that race must be harmless.
     */
    private fun update(key: String, change: (PendingCapture) -> PendingCapture) =
        synchronized(LOCK) {
            storage.save(all().map { if (it.key == key) change(it) else it })
        }

    companion object {
        /**
         * Serialises every load-mutate-save in the process. Re-entrant, which
         * is what lets [add] and [update] call [all] while already holding it.
         */
        private val LOCK = Any()

        /**
         * Five, and the number is a judgement rather than a measurement.
         * Enough to ride out a flaky connection or a brief outage; few
         * enough that a permanently broken endpoint is surfaced to somebody
         * the same day instead of being retried into the battery.
         */
        const val DEFAULT_CEILING = 5
    }
}
