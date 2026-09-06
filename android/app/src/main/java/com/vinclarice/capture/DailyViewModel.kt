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
)

/**
 * The Daily Page, read and now acted on -- slice 1 read the page
 * (android-full-client-plan.md); this extends it to what DayRoute.tsx
 * itself does: choose today's focus, and log/skip/pause/resume/call-it-enough
 * a routine and keep new ones. ~~and save the day's own Intentions/Grateful
 * for/Happenings~~ -- **that editor was removed on September 6, 2026**; see
 * the note in [DailyScreen]. The quick-capture box stays off this screen -- Capture
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
     * `item_detail`, and [TaskApi] already speaks to it -- so this reaches
     * the one authority instead of growing a second copy inside [DailyApi].
     * Exactly the move `DayRoute.tsx` makes on the web for the same reason;
     * `principles.md`'s *one rule, one authoritative definition*.
     */
    private val tasks: TaskApi,
) {
    private val _state = MutableStateFlow(DailyUiState())
    val state: StateFlow<DailyUiState> = _state.asStateFlow()


    suspend fun load() {
        _state.value = _state.value.copy(loading = true, busy = false, message = null, isError = false)

        val token = store.read()
        if (token == null) {
            _state.value = _state.value.copy(loading = false, day = null)
            return
        }

        _state.value = when (val result = api.getToday(token)) {
            is DayLoaded -> {
                _state.value.copy(
                    loading = false,
                    day = result.day,
                    message = null,
                    isError = false,
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

    suspend fun pinTask(taskId: Int) {
        val day = _state.value.day ?: return
        write { token -> api.pinFocus(token, day.date, taskId) }
    }

    suspend fun unpinTask(taskId: Int) {
        val day = _state.value.day ?: return
        write { token -> api.unpinFocus(token, day.date, taskId) }
    }

    suspend fun completeTask(taskId: Int) = writeTask { token ->
        tasks.setTaskStatus(token, taskId, "completed")
    }

    /**
     * Choose it for tomorrow -- rule 7's first move.
     *
     * ~~"Moves one task to tomorrow" -- S2's second verb, `rescheduleTask`
     * against [tomorrow].~~ **Corrected September 6, 2026**,
     * android-overhaul-plan.md increment 4, and it is the same defect the
     * website fixed on September 3: this re-promised a due date while the
     * evening's *Tomorrow* chose a day, so **one word did two opposite things
     * on one screen**.
     *
     * A due date is a promise to somebody. Choosing to work on something
     * tomorrow is not the same act as re-promising it, and rule 7 says *never
     * a date move* in as many words. So this goes through `leftovers`, which
     * pins tomorrow and leaves today's record untouched -- you chose it, you
     * did not do it, and you are choosing it again.
     *
     * Against *the day's* date, which the server supplied, never the device's
     * clock.
     */
    suspend fun deferTaskToTomorrow(taskId: Int) = decideAboutLeftover(taskId, "tomorrow")

    /** Unchoose it, and leave it open -- rule 7's second move. The task is
     *  already in the pool; what ends is the *choice*. */
    suspend fun putTaskBackInThePool(taskId: Int) = decideAboutLeftover(taskId, "pool")

    /**
     * Stop carrying it -- rule 7's third move.
     *
     * Archived rather than deleted, which is what makes it reversible: the
     * archive is a place somebody browses and restoring is one click. The
     * thought stays either way; only the commitment ends.
     */
    suspend fun letTaskGo(taskId: Int) = decideAboutLeftover(taskId, "let_go")

    private suspend fun decideAboutLeftover(taskId: Int, decision: String) {
        val day = _state.value.day ?: return
        write { token -> api.decideAboutLeftover(token, day.date, taskId, decision) }
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
