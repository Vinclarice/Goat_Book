package com.vinclarice.capture

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/**
 * Same wording as frontend/src/agenda.ts's dueLabel/ageLabel -- ported by
 * hand rather than shared, since there is no build step between a Gradle
 * project and a Vite one to share one across. See
 * android-full-client-plan.md §2. Only the branches the Daily Page's own
 * rows actually need are ported; the web's fuller `bucketFor` (which also
 * answers "someday"/"later" for the Agenda's own filtering) has no
 * equivalent here yet because nothing on Android filters by it.
 */

private val SHORT_DATE = DateTimeFormatter.ofPattern("EEE d MMM", Locale.getDefault())
private val LONG_DATE = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.getDefault())

/** "Saturday 10 August" -- the label a person recognises their own day by,
 *  same wording DayRoute.tsx's own longDate produces. */
fun longDate(isoDate: String): String = LocalDate.parse(isoDate).format(LONG_DATE)

/** The short due-date label shown on a task row. [dueDate] and [today] are
 *  ISO 8601 (YYYY-MM-DD), the same shape the API sends. */
fun dueLabel(dueDate: String, today: String): String {
    val due = LocalDate.parse(dueDate)
    val now = LocalDate.parse(today)
    if (due.isBefore(now)) {
        val days = ChronoUnit.DAYS.between(due, now)
        return if (days == 1L) "Yesterday" else "$days days overdue"
    }
    if (due.isEqual(now)) return "Today"
    if (ChronoUnit.DAYS.between(now, due) == 1L) return "Tomorrow"
    return due.format(SHORT_DATE)
}

/** Below this, age is noise -- mirrors agenda.ts's AGE_WORTH_MENTIONING. */
const val AGE_WORTH_MENTIONING = 7

/** How long a task has been waiting, said plainly -- see agenda.ts's own
 *  doc comment for why this reports a fact and draws no conclusion. */
fun ageLabel(days: Int): String? {
    if (days < AGE_WORTH_MENTIONING) return null
    return "Added $days days ago"
}

/**
 * How far a routine has got, in words -- mirrors DayRoute.tsx's
 * standingLabel. A blank unit with a target of one means a plain yes/no for
 * the period rather than a count of anything.
 */
fun standingLabel(standing: StandingEntry): String {
    if (standing.outcome == "skipped") return "Skipped"
    if (standing.unit.isEmpty() && standing.target == 1) {
        return if (standing.progress >= 1) "Done" else "Not yet"
    }
    val unit = if (standing.unit.isNotEmpty()) " ${standing.unit}" else ""
    val count = "${standing.progress} of ${standing.target}$unit"
    return if (standing.outcome == "partial") "$count — enough" else count
}
