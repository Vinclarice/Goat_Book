package com.vinclarice.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class PoolUiState(
    val loading: Boolean = true,
    val pool: PoolEntry? = null,
    /** Shown without ever blanking the list underneath it. */
    val message: String? = null,
    val isError: Boolean = false,
    /** True while a write is in flight -- disables the control it belongs to
     *  so a slow network cannot turn one tap into two requests. */
    val busy: Boolean = false,
)

/**
 * Every open line, and the one act worth doing from here.
 *
 * android-overhaul-plan.md increment 3. The pool replaced the Agenda on the
 * website on September 4, 2026, and its point is that there is nowhere to
 * file: one list, and you pick from it.
 *
 * **Picking goes through [DailyApi.pinFocus] rather than a pool verb of its
 * own.** Choosing something for today is the day's act wherever it is
 * performed; the endpoint was already reachable by a bearer, so this needed no
 * widening beyond the read; and a second way to pin would be a second
 * definition of what picking means. The same borrowing [DailyViewModel] does
 * for the task verbs, for the same reason.
 *
 * **Rule 8's *still wanted?* is deliberately absent.** `asks_to_be_kept`
 * arrives on every floating row and this screen shows it, because knowing the
 * pool is asking is worth something on its own -- but answering stays on the
 * website until there is a reason to widen a bearer to it. Letting go of a
 * task is a different decision from reading the list.
 */
class PoolViewModel(
    private val api: PoolApi,
    private val store: TokenStore,
    /** Borrowed, not rebuilt -- see the class doc. */
    private val days: DailyApi,
) {
    private val _state = MutableStateFlow(PoolUiState())
    val state: StateFlow<PoolUiState> = _state.asStateFlow()

    suspend fun load() {
        _state.value =
            _state.value.copy(loading = true, busy = false, message = null, isError = false)

        val token = store.read()
        if (token == null) {
            _state.value = _state.value.copy(loading = false, pool = null)
            return
        }

        _state.value = when (val result = api.getPool(token)) {
            is PoolLoaded -> _state.value.copy(
                loading = false,
                pool = result.pool,
                message = null,
                isError = false,
            )
            // Where to fix it, not what broke. A person holding a phone can
            // act on "reconnect in Settings"; they can do nothing at all with
            // "401".
            PoolUnauthorised -> _state.value.copy(
                loading = false,
                pool = null,
                message = "Reconnect in Settings to see the pool.",
                isError = true,
            )
            is PoolUnreachable -> _state.value.copy(
                loading = false,
                message = result.reason,
                isError = true,
            )
        }
    }

    /**
     * Choose a line for today.
     *
     * Against **the pool's own `today`**, which the server supplied, never the
     * device's clock -- the same rule the day screen's *tomorrow* follows, and
     * it matters more here because the account's zone decides what day it is
     * and a phone is not necessarily in it.
     */
    suspend fun pick(taskId: Int) {
        val pool = _state.value.pool ?: return
        val token = store.read() ?: return

        _state.value = _state.value.copy(busy = true, message = null, isError = false)

        when (val result = days.pinFocus(token, pool.today, taskId)) {
            DayWriteSucceeded -> {
                // Reloaded rather than patched here: `picked_for` is what stops
                // a Pick control looking like it did nothing, and only the
                // server knows it.
                load()
            }
            // **The list stays on screen.** A failed write must never blank a
            // page somebody is reading -- DailyViewModel's rule, inherited.
            DayWriteUnauthorised -> _state.value = _state.value.copy(
                busy = false,
                message = "Reconnect in Settings to choose from the pool.",
                isError = true,
            )
            is DayWriteRejected -> _state.value = _state.value.copy(
                busy = false,
                message = result.message,
                isError = true,
            )
            is DayWriteUnreachable -> _state.value = _state.value.copy(
                busy = false,
                message = result.reason,
                isError = true,
            )
        }
    }
}
