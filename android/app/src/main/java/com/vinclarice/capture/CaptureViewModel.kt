package com.vinclarice.capture

import java.util.UUID
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext

data class CaptureUiState(
    val text: String = "",
    /** Raw field contents, comma-separated -- same convention the web app
     *  already uses for a task's tags. Parsed only at submit time. */
    val tags: String = "",
    val sending: Boolean = false,
    val message: String? = null,
    val isError: Boolean = false,
    /** Captures written down but not yet accepted by Clarice. */
    val pending: Int = 0,
    /** Whether the keyboard's Enter key sends. Chosen in Settings. */
    val enterSends: Boolean = true,
)

/**
 * Capture: type a thought, send it, get out.
 *
 * One rule governs everything here -- a thought someone typed is never lost
 * -- but M3 changed how it is honoured. The field used to be the only place
 * an unsent capture existed, so a failed send had to leave the text on
 * screen and effectively hold the app hostage to it.
 *
 * Now every capture is written to the durable queue *before* the network is
 * touched, so there is no moment where the thought exists only in memory.
 * That is what lets the field clear on failure: the text is somewhere safer
 * than the screen. The single exception is a server rejection, which only a
 * person can resolve, and they cannot edit text they cannot see.
 */
class CaptureViewModel(
    private val api: ClariceApi,
    private val store: TokenStore,
    private val queue: CaptureQueue,
    // A seam rather than WorkManager itself, so these decisions stay
    // testable on the JVM. Everything this class knows about background
    // delivery is "ask for one".
    private val scheduler: DeliveryScheduler = DeliveryScheduler.None,
    private val preferences: CapturePreferences,
    // Queue work means decrypting, and Keystore calls are real IPC that has
    // no business on the main thread. Injected so tests can run it inline.
    private val io: CoroutineDispatcher = Dispatchers.IO,
    // Injected so a test can watch which keys were used. In production a
    // random UUID per capture, which is what the server's uniqueness
    // constraint is scoped to.
    private val newKey: () -> String = { UUID.randomUUID().toString() },
    private val now: () -> Long = { System.currentTimeMillis() },
    /** Which server captures go to, for the message when it refuses one. */
    private val serverName: String = "Clarice",
) {
    private val _state = MutableStateFlow(CaptureUiState())
    val state: StateFlow<CaptureUiState> = _state.asStateFlow()

    fun onTextChange(value: String) {
        // Dropping the previous message as soon as they start typing: a
        // "Captured." still on screen over a new thought reads as though
        // this one has already been sent.
        _state.value = _state.value.copy(text = value, message = null, isError = false)
    }

    fun onTagsChange(value: String) {
        _state.value = _state.value.copy(tags = value)
    }

    /** Recount what is waiting. Suspending because reading the queue means
     *  decrypting it, and Keystore calls are real IPC. */
    suspend fun refresh() = withContext(io) {
        val waiting = queue.waiting().size
        // Read on open rather than held, so a change made in Settings is in
        // force the moment somebody comes back here.
        _state.value = _state.value.copy(
            pending = waiting,
            enterSends = preferences.enterSends(),
        )
        // Covers the gap where the process died between queueing a capture
        // and scheduling its delivery. Asking twice is free -- the work is
        // enqueued under one name and a duplicate request is dropped -- and
        // not asking at all leaves a queue with nothing arranged to drain it.
        if (waiting > 0) scheduler.schedule()
    }

    /**
     * Keep the count honest while the screen is open.
     *
     * Suspends for as long as somebody is looking at Capture. Without it the
     * count is a snapshot taken when the screen opened, and a queue drained
     * by the worker leaves a number on screen that its owner cannot tell
     * apart from lost captures.
     */
    suspend fun watchDeliveries() {
        scheduler.completions().collect { refresh() }
    }

    suspend fun submit() = withContext(io) {
        val text = _state.value.text.trim()
        if (text.isEmpty()) return@withContext
        val tags = _state.value.tags.split(",").map { it.trim() }.filter { it.isNotEmpty() }

        // Durable first. If the process dies during the request, or the radio
        // never answers, the thought is already written down.
        val item = queue.add(text, newKey(), now(), tags)
        // Rebuilt rather than copied, to clear the field and any previous
        // message in one go -- so anything that is a *setting* rather than a
        // result has to be carried across explicitly. A keyboard that
        // changed behaviour halfway through a session would be maddening.
        _state.value = CaptureUiState(
            text = "",
            tags = "",
            sending = true,
            pending = queue.waiting().size,
            enterSends = _state.value.enterSends,
        )

        val token = store.read()
        if (token == null) {
            // Not a refusal any more. The queue can hold this until a token
            // exists, which is strictly better than making somebody reconnect
            // before they are allowed to think.
            scheduler.schedule()
            report(NEEDS_TOKEN, isError = false)
            return@withContext
        }

        // The queued item's own key, never a fresh one: a retry has to be
        // recognisably the same write, or it becomes a second note.
        when (api.capture(token, item.text, item.key, item.tags, item.createdAt)) {
            Disposition.DELIVERED -> {
                queue.delivered(item.key)
                report("Captured.", isError = false)
            }
            // Being offline is not an error, and saying so in red trains
            // people to distrust a queue that is working perfectly.
            Disposition.RETRY_LATER -> {
                queue.failed(item.key)
                scheduler.schedule()
                report("Saved — will send when online.", isError = false)
            }
            // No attempt charged. The ceiling bounds pointless repetition,
            // and this has a known cause and a known fix; spending attempts
            // here would strand the queue at the very moment reconnecting
            // was meant to drain it.
            Disposition.NEEDS_RECONNECT -> {
                scheduler.schedule()
                report(NEEDS_TOKEN, isError = false)
            }
            Disposition.REJECTED -> {
                queue.rejected(item.key)
                // The only path that returns the text. It is still queued --
                // "remove only after a successful response" has no exception
                // -- but the copy in the field is the one that can be edited.
                _state.value = _state.value.copy(
                    text = item.text,
                    tags = item.tags.joinToString(", "),
                    sending = false,
                    message = "$serverName would not accept that. Edit it and try again.",
                    isError = true,
                    pending = queue.waiting().size,
                )
            }
        }
    }

    private fun report(message: String, isError: Boolean) {
        _state.value = _state.value.copy(
            sending = false,
            message = message,
            isError = isError,
            pending = queue.waiting().size,
        )
    }

    private companion object {
        const val NEEDS_TOKEN = "Saved. Reconnect in Settings to send it."
    }
}
