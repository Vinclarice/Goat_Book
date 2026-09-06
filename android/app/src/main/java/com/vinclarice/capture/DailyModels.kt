package com.vinclarice.capture

/**
 * The Daily Page's own shape, trimmed to what a read-only slice 1 renders.
 * Mirrors daily.api_v1.DayOut field-for-field -- see android-full-client-plan.md
 * §3 for exactly which of DayOut's writable affordances (focus pin/unpin,
 * routine logging, editing this text) are deliberately not built yet.
 *
 * Areas and projects are trimmed to id+title: DayOut also carries a
 * color_key and a url, but this slice draws no colored dots and links
 * nowhere yet -- both are display detail a later slice can add without
 * reshaping this model.
 */
data class DayEntry(
    val date: String,
    val today: String,
    val compassPurpose: String,
    val compassQuestion: String,
    /**
     * When the day's work began, or null while the list is still open.
     *
     * superlists-2.0-plan.md rules 3 and 11: the first act of execution draws
     * the line, and until something is executed there is no line to draw. Null
     * is the ordinary morning, not an error -- a client that treated it as one
     * would draw a line at nothing on every day before the first tick.
     */
    val listClosedAt: String?,
    val focus: List<FocusEntry>,
    /** Everything covering this date, cancelled ones included and struck --
     *  rule 6. Present on a past day, because an appointment is a dated record
     *  of something that was going to happen. */
    val appointments: List<AppointmentEntry>,
    /** What is ahead within the week, soonest first. Only ever today's. */
    val appointmentsComing: List<AppointmentEntry>,
    val actionItems: List<ActionItemEntry>,
    val areas: List<AreaSummaryEntry>,
    val projects: List<ProjectSummaryEntry>,
    val showsActionItems: Boolean,
    val routines: List<StandingEntry>,
    val routinesAreLoggable: Boolean,
    val pausedRoutines: List<PausedRoutineEntry>,
) {
    val isToday: Boolean get() = date == today
}

data class FocusEntry(
    val taskId: Int?,
    val text: String,
    val status: String?,
    val dueDate: String?,
    /**
     * Whether this was in the morning's set or joined after the work began.
     *
     * **Read, never computed.** `FocusOut.above_the_line` is derived on the
     * server from `selected_at` against the day's `list_closed_at`, and the
     * schema says why it is sent rather than left to a client: the comparison
     * is on timestamps in the owner's zone. That argument is stronger here
     * than on the web -- a phone can be in any zone at all, and one in the
     * wrong one would quietly file this morning's choices below the line.
     */
    val aboveTheLine: Boolean,
    // **`url` stood here until August 30, 2026** --
    // coherence-audit-2026-08-30.md F2. It was how the day acted on a task,
    // and `taskId` above says the same thing: both are null for a pin whose
    // task was deleted, and the client builds `/api/v1/tasks/{id}` itself now.
    // The server still sends the field, for the build that came before this.
)

data class ActionItemEntry(
    val id: Int,
    val text: String,
    val dueDate: String?,
    val ageInDays: Int,
    // Nullable like `projectId` beside it -- see TaskApi.TaskEntry.
    val areaId: Int?,
    val projectId: Int?,
)

data class AreaSummaryEntry(val id: Int, val title: String)

data class ProjectSummaryEntry(val id: Int, val title: String)

data class StandingEntry(
    val routineId: Int,
    val title: String,
    val cadence: String,
    val progress: Int,
    val target: Int,
    val unit: String,
    val outcome: String,
    val isMet: Boolean,
)

data class PausedRoutineEntry(
    val routineId: Int,
    val title: String,
    val cadence: String,
    val target: Int,
    val unit: String,
)

/**
 * One appointment -- something that happens whether or not you act.
 *
 * The model shipped on the website on September 4, 2026 and reaches this
 * client inside the day payload it already fetches, which is why
 * android-overhaul-plan.md increment 2 needs no server work: `appointments`
 * has no read endpoint of its own and does not need one.
 *
 * [cancelled] is a flag rather than an absence, on purpose -- rule 6 keeps a
 * called-off appointment visible and struck, and filtering it here would make
 * *it was cancelled* and *it never existed* the same thing on a phone.
 */
data class AppointmentEntry(
    val publicId: String,
    val text: String,
    val startsOn: String,
    val endsOn: String?,
    /** Null for something with no time of day -- an all-day thing, not midnight. */
    val startsAt: String?,
    val endsAt: String?,
    val location: String,
    val notes: String,
    val cancelled: Boolean,
)
