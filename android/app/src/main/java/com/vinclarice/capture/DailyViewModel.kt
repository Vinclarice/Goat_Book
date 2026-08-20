package com.vinclarice.capture

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class DailyUiState(
    val loading: Boolean = true,
    val day: DayEntry? = null,
    val message: String? = null,
    val isError: Boolean = false,
    /** True while a write is in flight -- disables the control it belongs
     *  to so a slow network can't turn one tap into two requests. */
    val busy: Boolean = false,
    /** The day's own text, editable before "Save the day" -- separate from
     *  `day.intentions` etc. so a background reload (after logging a
     *  routine, say) can't stomp on text mid-typing. Seeded once per
     *  calendar date, not once per load() -- see [DailyViewModel]'s own
     *  seededForDate. */
    val draftIntentions: String = "",
    val draftGratitude: String = "",
    val draftHappenings: String = "",
)

/**
 * The Daily Page, read and now acted on -- slice 1 read the page
 * (android-full-client-plan.md); this extends it to what DayRoute.tsx
 * itself does: choose today's focus, log/skip/pause/resume/call-it-enough
 * a routine and keep new ones, and save the day's own Intentions/Grateful
 * for/Happenings. The quick-capture box stays off this screen -- Capture
 * is one tab away already, the same reasoning DayRoute.tsx's own comment
 * gives for not duplicating it.
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
    /**
     * The task verbs the day needs, borrowed rather than rebuilt.
     *
     * Completing and rescheduling are `lists.api`'s hand-rolled
     * `item_detail`, and [AgendaApi] already speaks to it -- so this reaches
     * the one authority instead of growing a second copy inside [DailyApi].
     * Exactly the move `DayRoute.tsx` makes on the web for the same reason;
     * `principles.md`'s *one rule, one authoritative definition*.
     */
    private val tasks: AgendaApi,
) {
    private val _state = MutableStateFlow(DailyUiState())
    val state: StateFlow<DailyUiState> = _state.asStateFlow()

    // Which date the draft fields were last seeded for -- not part of
    // DailyUiState because it drives no UI itself, only whether the next
    // load() is allowed to overwrite what's being typed.
    private var seededForDate: String? = null

    suspend fun load() {
        _state.value = _state.value.copy(loading = true, busy = false, message = null, isError = false)

        val token = store.read()
        if (token == null) {
            _state.value = _state.value.copy(loading = false, day = null)
            return
        }

        _state.value = when (val result = api.getToday(token)) {
            is DayLoaded -> {
                val day = result.day
                val reseed = seededForDate != day.date
                if (reseed) seededForDate = day.date
                _state.value.copy(
                    loading = false,
                    day = day,
                    message = null,
                    isError = false,
                    draftIntentions = if (reseed) day.intentions else _state.value.draftIntentions,
                    draftGratitude = if (reseed) day.gratitude else _state.value.draftGratitude,
                    draftHappenings = if (reseed) day.happenings else _state.value.draftHappenings,
                )
            }
            DayUnauthorised -> _state.value.copy(
                loading = false,
                day = null,
                message = "Reconnect in Settings to see today.",
                isError = true,
            )
            is DayUnreachable -> _state.value.copy(
                loading = false,
                day = null,
                message = result.reason,
                isError = true,
            )
        }
    }

    fun setDraftIntentions(text: String) {
        _state.value = _state.value.copy(draftIntentions = text)
    }

    fun setDraftGratitude(text: String) {
        _state.value = _state.value.copy(draftGratitude = text)
    }

    fun setDraftHappenings(text: String) {
        _state.value = _state.value.copy(draftHappenings = text)
    }

    suspend fun saveDayText() {
        val day = _state.value.day ?: return
        val draft = _state.value
        write { token ->
            api.writeDayText(token, day.date, draft.draftIntentions, draft.draftGratitude, draft.draftHappenings)
        }
    }

    suspend fun pinTask(taskId: Int) {
        val day = _state.value.day ?: return
        write { token -> api.pinFocus(token, day.date, taskId) }
    }

    suspend fun unpinTask(taskId: Int) {
        val day = _state.value.day ?: return
        write { token -> api.unpinFocus(token, day.date, taskId) }
    }

    suspend fun completeTask(url: String) = writeTask { token ->
        tasks.setTaskStatus(token, url, "completed")
    }

    /**
     * "Moves one task to tomorrow" -- S2's second verb.
     *
     * **Not carry-forward.** `daily-operating-system-vision.md` forbids
     * rewriting a due date *automatically*; one person moving one item is the
     * shape that rule deliberately leaves open.
     *
     * Tomorrow is measured from *the day's* date, which the server supplied,
     * never the device's clock -- and it comes from [tomorrow], the rule the
     * Agenda screen already snoozes with, rather than a fourth hand-written
     * copy of it.
     */
    suspend fun deferTaskToTomorrow(url: String) {
        val day = _state.value.day ?: return
        writeTask { token -> tasks.rescheduleTask(token, url, tomorrow(day.date)) }
    }

    /**
     * The borrowed verbs answer with [TaskWriteResult]; everything else here
     * speaks [DayWriteResult]. Mapped one to one rather than duplicated, so
     * completing inherits [write]'s reload-on-success and its rule that a
     * failed write never blanks an already-visible page.
     */
    private suspend fun writeTask(perform: suspend (String) -> TaskWriteResult) =
        write { token ->
            when (val result = perform(token)) {
                is TaskWriteSucceeded -> DayWriteSucceeded
                TaskWriteUnauthorised -> DayWriteUnauthorised
                is TaskWriteRejected -> DayWriteRejected(result.message)
                is TaskWriteUnreachable -> DayWriteUnreachable(result.reason)
            }
        }

    suspend fun logRoutine(routineId: Int, amount: Int) = write { token ->
        api.logRoutine(token, routineId, amount)
    }

    suspend fun skipRoutine(routineId: Int) = write { token -> api.skipRoutine(token, routineId) }

    suspend fun callRoutineEnough(routineId: Int) = write { token -> api.callRoutineEnough(token, routineId) }

    suspend fun pauseRoutine(routineId: Int) = write { token -> api.pauseRoutine(token, routineId) }

    suspend fun resumeRoutine(routineId: Int) = write { token -> api.resumeRoutine(token, routineId) }

    suspend fun createRoutine(title: String, cadence: String, targetQuantity: Int, unit: String) {
        if (title.isBlank()) return
        write { token -> api.createRoutine(token, title, cadence, targetQuantity, unit) }
    }

    /**
     * Reloads the whole day on success rather than hand-merging the
     * response: a routine write answers with a different shape
     * (`StandingsOut`, not `DayOut`) than a focus/text write does, and a
     * reload is one honest way to handle both without two merge paths. A
     * failed write never touches `day` -- an already-visible page must not
     * go blank because one action on it failed, the same rule
     * AgendaViewModel's own write() follows.
     */
    private suspend fun write(perform: suspend (String) -> DayWriteResult) {
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
            DayWriteSucceeded -> load()
            DayWriteUnauthorised -> _state.value = _state.value.copy(
                busy = false,
                message = "Reconnect in Settings to change today.",
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
