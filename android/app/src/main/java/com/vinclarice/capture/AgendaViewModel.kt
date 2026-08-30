package com.vinclarice.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class AgendaUiState(
    val loading: Boolean = true,
    val agenda: AgendaEntry? = null,
    val message: String? = null,
    val isError: Boolean = false,
    /** True while a write is in flight -- disables the row it belongs to
     *  so a slow network can't turn one tap into two requests. */
    val busy: Boolean = false,
    val scopeFilter: AgendaScope? = null,
    val areaFilter: Int? = null,
    val tagFilter: String? = null,
    val query: String = "",
)

/**
 * The Agenda, read and acted on -- slice 2 of android-full-client-plan.md.
 *
 * Filters (area, tag, search) live here rather than in the composable:
 * they're user-observable state the same way CaptureUiState's draft text
 * is, and keeping them off Compose's own remember{} means a rotation or a
 * trip to Settings and back doesn't reset them.
 */
class AgendaViewModel(
    private val api: AgendaApi,
    private val store: TokenStore,
) {
    private val _state = MutableStateFlow(AgendaUiState())
    val state: StateFlow<AgendaUiState> = _state.asStateFlow()

    suspend fun load() {
        _state.value = _state.value.copy(loading = true, busy = false, message = null, isError = false)

        val token = store.read()
        if (token == null) {
            _state.value = _state.value.copy(loading = false, agenda = null)
            return
        }

        _state.value = when (val result = api.getAgenda(token)) {
            is AgendaLoaded -> _state.value.copy(
                loading = false,
                agenda = result.agenda,
                message = null,
                isError = false,
            )
            AgendaUnauthorised -> _state.value.copy(
                loading = false,
                agenda = null,
                message = "Reconnect in Settings to see your agenda.",
                isError = true,
            )
            is AgendaUnreachable -> _state.value.copy(
                loading = false,
                agenda = null,
                message = result.reason,
                isError = true,
            )
        }
    }

    fun setScopeFilter(scope: AgendaScope?) {
        _state.value = _state.value.copy(
            scopeFilter = if (_state.value.scopeFilter == scope) null else scope,
        )
    }

    /** Toggling the same area off again is the only way to clear it from
     *  a plain tap -- there's no separate "all areas" control. */
    fun setAreaFilter(areaId: Int?) {
        _state.value = _state.value.copy(
            areaFilter = if (_state.value.areaFilter == areaId) null else areaId,
        )
    }

    fun setTagFilter(tag: String?) {
        _state.value = _state.value.copy(
            tagFilter = if (_state.value.tagFilter == tag) null else tag,
        )
    }

    fun setQuery(query: String) {
        _state.value = _state.value.copy(query = query)
    }

    suspend fun completeTask(task: AgendaTaskEntry) = write { token ->
        api.setTaskStatus(token, task.id, "completed")
    }

    suspend fun reopenTask(task: AgendaTaskEntry) = write { token ->
        api.setTaskStatus(token, task.id, "active")
    }

    suspend fun reschedule(task: AgendaTaskEntry, dueDate: String?) = write { token ->
        api.rescheduleTask(token, task.id, dueDate)
    }

    suspend fun quickAdd(area: AgendaAreaEntry, text: String, dueDate: String?) {
        if (text.isBlank()) return
        write { token -> api.createTask(token, area.id, text, dueDate) }
    }

    /**
     * Reloads the whole agenda on success rather than patching the one
     * row in place: completing a task moves it from `items` to
     * `completed_today`, a shape change a single-row merge can't express
     * honestly, and quick-add needs the new row's full server-assigned
     * fields anyway. A failed write never touches `agenda` -- an
     * already-visible list must not go blank because one action on it
     * failed, the same "failure is recoverable and visible" reasoning
     * every other screen here already follows.
     */
    private suspend fun write(perform: suspend (String) -> TaskWriteResult) {
        val token = store.read()
        if (token == null) {
            _state.value = _state.value.copy(
                message = "Connect an account in Settings first.",
                isError = true,
            )
            return
        }

        _state.value = _state.value.copy(busy = true, message = null, isError = false)

        when (val result = perform(token)) {
            is TaskWriteSucceeded -> load()
            TaskWriteUnauthorised -> _state.value = _state.value.copy(
                busy = false,
                message = "Reconnect in Settings to change tasks.",
                isError = true,
            )
            is TaskWriteRejected -> _state.value = _state.value.copy(
                busy = false,
                message = result.message,
                isError = true,
            )
            is TaskWriteUnreachable -> _state.value = _state.value.copy(
                busy = false,
                message = result.reason,
                isError = true,
            )
        }
    }
}
