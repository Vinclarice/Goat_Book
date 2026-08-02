package com.vinclarice.capture

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext

data class SettingsUiState(
    val loading: Boolean = true,
    val identity: Identity? = null,
    val message: String? = null,
    val isError: Boolean = false,
    // Whether a token is held, which is not the same as whether it works.
    // A revoked token leaves this true until someone disconnects.
    val connected: Boolean = true,
    /** Captures the app will keep trying to send on its own. */
    val waiting: Int = 0,
    /** Captures that have stopped trying and need a person. */
    val needsAttention: List<PendingCapture> = emptyList(),
    /** Whether the keyboard's Enter key sends a capture or breaks a line. */
    val enterSends: Boolean = true,
)

/**
 * The account behind the stored token, the queue behind the app, and the way
 * to stop using either.
 *
 * The screen's real job is answering "is this thing still working?", so it
 * asks the server every time it opens rather than showing something it
 * remembered. Two of the three answers -- revoked, and unreachable -- have to
 * stay distinct all the way to the text on screen, because one calls for a
 * new token and the other calls for patience.
 *
 * The queue is read regardless of any of that. Being offline is exactly when
 * somebody wants to know what is still unsent, so hiding it behind a
 * successful identity lookup would withhold it at the only moment it
 * matters.
 */
class SettingsViewModel(
    private val connector: Connector,
    private val queue: CaptureQueue,
    private val scheduler: DeliveryScheduler = DeliveryScheduler.None,
    private val preferences: CapturePreferences,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    suspend fun load() {
        readQueue()
        // Before the network call, and outside it. This is a keyboard
        // preference, not an account fact; withholding it because a request
        // failed would be absurd.
        _state.value = _state.value.copy(enterSends = preferences.enterSends())

        when (val outcome = connector.whoAmI()) {
            is Connected -> _state.value = _state.value.copy(
                loading = false,
                identity = outcome.identity,
                message = null,
            )
            // The token is kept. Settings is where someone comes to find out
            // their token stopped working; ejecting them to Connect before
            // they have read why is not an answer.
            is Refused -> report(outcome.message, isError = true)
            // Not an error in the sense that anything needs fixing, so it is
            // said plainly rather than in red.
            is Failed -> report(outcome.message, isError = false)
            Blank -> _state.value = _state.value.copy(loading = false, connected = false)
        }
    }

    /**
     * One more go at a capture that stopped trying.
     *
     * The queue keeps the original key through this, which is the entire
     * reason a stalled item is kept rather than dropped: a fresh key would
     * turn one thought into a second note the moment it finally landed.
     */
    suspend fun retry(key: String) {
        withContext(io) { queue.retry(key) }
        scheduler.schedule()
        readQueue()
    }

    /**
     * Whether Enter sends or breaks a line.
     *
     * Written through immediately rather than on leaving the screen: a
     * preference that only takes effect if you exit the right way is a
     * preference people stop trusting.
     */
    fun setEnterSends(sends: Boolean) {
        preferences.setEnterSends(sends)
        _state.value = _state.value.copy(enterSends = sends)
    }

    fun disconnect() {
        connector.disconnect()
        // The queue is deliberately untouched. It has its own Keystore alias
        // precisely so that disconnecting cannot destroy unsent thoughts.
        _state.value = _state.value.copy(
            loading = false,
            connected = false,
            identity = null,
            message = null,
        )
    }

    private suspend fun readQueue() = withContext(io) {
        val all = queue.all()
        _state.value = _state.value.copy(
            waiting = all.count { it.state == QueueState.WAITING },
            needsAttention = all.filter { it.state != QueueState.WAITING },
        )
    }

    private fun report(message: String, isError: Boolean) {
        _state.value = _state.value.copy(
            loading = false,
            identity = null,
            message = message,
            isError = isError,
        )
    }
}
