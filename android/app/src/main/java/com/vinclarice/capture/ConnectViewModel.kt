package com.vinclarice.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Everything the Connect screen shows, so the composable can be a thin
 * rendering of it and the decisions stay testable without a device.
 */
data class ConnectUiState(
    val token: String = "",
    val checking: Boolean = false,
    val error: String? = null,
    val connectedAs: Identity? = null,
)

class ConnectViewModel(private val connector: Connector) {

    private val _state = MutableStateFlow(ConnectUiState())
    val state: StateFlow<ConnectUiState> = _state.asStateFlow()

    val isConnected: Boolean get() = connector.isConnected()

    fun onTokenChange(value: String) {
        // Clearing the error as soon as they start correcting it: leaving
        // it under the field makes it ambiguous whether it describes the
        // old attempt or what is being typed now.
        _state.value = _state.value.copy(token = value, error = null)
    }

    suspend fun connect() {
        _state.value = _state.value.copy(checking = true, error = null)

        when (val outcome = connector.connect(_state.value.token)) {
            is Connected -> _state.value = ConnectUiState(
                // Field emptied, not merely hidden. The token is stored now,
                // and "never display it after saving" has to be true of the
                // screen as well as of the log.
                token = "",
                checking = false,
                connectedAs = outcome.identity,
            )
            // Both failures keep what was typed. Someone who pasted a token
            // with one character missing should be able to fix it rather
            // than fetch all forty again.
            is Refused -> fail(outcome.message)
            is Failed -> fail(outcome.message)
            Blank -> fail("Paste the access token from the Clarice web app.")
        }
    }

    fun disconnect() {
        connector.disconnect()
        _state.value = ConnectUiState()
    }

    private fun fail(message: String) {
        _state.value = _state.value.copy(checking = false, error = message)
    }
}
