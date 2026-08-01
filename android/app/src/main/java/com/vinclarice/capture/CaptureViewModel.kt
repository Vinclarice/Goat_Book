package com.vinclarice.capture

import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class CaptureUiState(
    val text: String = "",
    val sending: Boolean = false,
    val message: String? = null,
    val isError: Boolean = false,
)

/**
 * Capture: type a thought, send it, get out.
 *
 * One rule governs everything here -- a thought someone typed is never
 * lost. Only a confirmed store clears the field; every other outcome leaves
 * the text exactly where they can see it. Until M3's durable queue exists,
 * the field *is* the queue, so clearing it optimistically would discard the
 * thing this app exists to keep.
 */
class CaptureViewModel(
    private val api: ClariceApi,
    private val store: TokenStore,
    // Injected so a test can watch which keys were used. In production it
    // is a random UUID per capture, which is what the server's uniqueness
    // constraint is scoped to.
    private val newKey: () -> String = { UUID.randomUUID().toString() },
) {
    private val _state = MutableStateFlow(CaptureUiState())
    val state: StateFlow<CaptureUiState> = _state.asStateFlow()

    fun onTextChange(value: String) {
        // Dropping the previous message as soon as they start typing: a
        // "Captured." still on screen over a new thought reads as though
        // this one has already been sent.
        _state.value = _state.value.copy(text = value, message = null, isError = false)
    }

    suspend fun submit() {
        val text = _state.value.text.trim()
        if (text.isEmpty()) return

        val token = store.read()
        if (token == null) {
            // Asking the network would only earn a 401 that tells us less
            // than we already know, and would cost the person their text
            // for longer.
            report("Not connected. Add your access token in Settings.", isError = true)
            return
        }

        _state.value = _state.value.copy(sending = true, message = null, isError = false)

        // One key per capture, generated before the first attempt, so that
        // any retry of *this* thought is recognisably the same write.
        when (api.capture(token, text, newKey())) {
            Disposition.DELIVERED -> _state.value = CaptureUiState(
                text = "",
                sending = false,
                message = "Captured.",
            )
            Disposition.NEEDS_RECONNECT ->
                report("Your access token no longer works. Reconnect in Settings.")
            Disposition.REJECTED ->
                report("Clarice would not accept that. Edit it and try again.")
            Disposition.RETRY_LATER ->
                report("Couldn't reach Clarice. Your text is still here — try again.")
        }
    }

    private fun report(message: String, isError: Boolean = true) {
        _state.value = _state.value.copy(sending = false, message = message, isError = isError)
    }
}
