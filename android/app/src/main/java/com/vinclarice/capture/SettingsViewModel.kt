package com.vinclarice.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class SettingsUiState(
    val loading: Boolean = true,
    val identity: Identity? = null,
    val message: String? = null,
    val isError: Boolean = false,
    // Whether a token is held, which is not the same as whether it works.
    // A revoked token leaves this true until someone disconnects.
    val connected: Boolean = true,
)

/**
 * The account behind the stored token, and the way to stop using it.
 *
 * The screen's real job is answering "is this thing still working?", so it
 * asks the server every time it opens rather than showing something it
 * remembered. Two of the three answers -- revoked, and unreachable -- have to
 * stay distinct all the way to the text on screen, because one calls for a
 * new token and the other calls for patience.
 */
class SettingsViewModel(private val connector: Connector) {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    suspend fun load() {
        when (val outcome = connector.whoAmI()) {
            is Connected -> _state.value = SettingsUiState(
                loading = false,
                identity = outcome.identity,
            )
            // The token is kept. Settings is where someone comes to find out
            // their token stopped working; ejecting them to Connect before
            // they have read why is not an answer.
            is Refused -> report(outcome.message, isError = true)
            // Not an error in the sense that anything needs fixing, so it is
            // said plainly rather than in red.
            is Failed -> report(outcome.message, isError = false)
            Blank -> _state.value = SettingsUiState(loading = false, connected = false)
        }
    }

    fun disconnect() {
        connector.disconnect()
        _state.value = SettingsUiState(loading = false, connected = false)
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
