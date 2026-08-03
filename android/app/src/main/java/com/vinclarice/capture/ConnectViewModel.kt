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
    val username: String = "",
    val password: String = "",
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

    fun onUsernameChange(value: String) {
        _state.value = _state.value.copy(username = value, error = null)
    }

    fun onPasswordChange(value: String) {
        _state.value = _state.value.copy(password = value, error = null)
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

    /**
     * Log in with a username and password instead of pasting a token.
     *
     * The password leaves the field the moment this returns, whichever way
     * it went -- there is no outcome where it is worth having on screen a
     * moment longer than the request that used it. The username stays on
     * failure, since retyping it buys nothing a wrong password didn't
     * already cost.
     */
    suspend fun logIn() {
        _state.value = _state.value.copy(checking = true, error = null)
        val username = _state.value.username
        val password = _state.value.password

        when (val outcome = connector.logIn(username, password)) {
            is Connected -> _state.value = ConnectUiState(
                checking = false,
                connectedAs = outcome.identity,
            )
            is Refused -> failLogin(username, outcome.message)
            is Failed -> failLogin(username, outcome.message)
            Blank -> failLogin(username, "Enter your username and password.")
        }
    }

    private fun failLogin(username: String, message: String) {
        _state.value = _state.value.copy(
            username = username,
            password = "",
            checking = false,
            error = message,
        )
    }

    fun disconnect() {
        connector.disconnect()
        _state.value = ConnectUiState()
    }

    private fun fail(message: String) {
        _state.value = _state.value.copy(checking = false, error = message)
    }
}
