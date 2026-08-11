package com.vinclarice.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class DailyUiState(
    val loading: Boolean = true,
    val day: DayEntry? = null,
    val message: String? = null,
    val isError: Boolean = false,
)

/**
 * The Daily Page, read-only -- slice 1 of android-full-client-plan.md.
 *
 * Asked fresh every time the screen opens, the same instinct
 * SettingsViewModel already has: what today looked like five minutes ago is
 * not what this screen is for. No stored token is answered quietly rather
 * than as an error -- it means "not connected", which Settings already
 * says, not "something is wrong with today".
 */
class DailyViewModel(
    private val api: DailyApi,
    private val store: TokenStore,
) {
    private val _state = MutableStateFlow(DailyUiState())
    val state: StateFlow<DailyUiState> = _state.asStateFlow()

    suspend fun load() {
        _state.value = DailyUiState(loading = true)

        val token = store.read()
        if (token == null) {
            _state.value = DailyUiState(loading = false)
            return
        }

        _state.value = when (val result = api.getToday(token)) {
            is DayLoaded -> DailyUiState(loading = false, day = result.day)
            DayUnauthorised -> DailyUiState(
                loading = false,
                message = "Reconnect in Settings to see today.",
                isError = true,
            )
            is DayUnreachable -> DailyUiState(
                loading = false,
                message = result.reason,
                isError = true,
            )
        }
    }
}
