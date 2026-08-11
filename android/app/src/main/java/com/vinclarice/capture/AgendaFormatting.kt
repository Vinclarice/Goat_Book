package com.vinclarice.capture

import java.time.DayOfWeek
import java.time.LocalDate

/**
 * Same rule as frontend/src/agenda.ts's bucketFor -- mirrors lists.agenda's
 * own bucket_for, which is the actual server-side authority; this is a
 * client-side re-derivation for filtering/counting over an already-fetched
 * agenda, the same reasoning agenda.ts's own SCOPES comment gives.
 */
enum class AgendaBucket { OVERDUE, TODAY, WEEK, LATER, SOMEDAY }

/** Mirrors lists.agenda.WEEK_HORIZON_DAYS. */
const val WEEK_HORIZON_DAYS = 7L

fun bucketFor(dueDate: String?, today: String): AgendaBucket {
    if (dueDate == null) return AgendaBucket.SOMEDAY
    val due = LocalDate.parse(dueDate)
    val now = LocalDate.parse(today)
    if (due.isBefore(now)) return AgendaBucket.OVERDUE
    if (due.isEqual(now)) return AgendaBucket.TODAY
    if (!due.isAfter(now.plusDays(WEEK_HORIZON_DAYS))) return AgendaBucket.WEEK
    return AgendaBucket.LATER
}

/** The Agenda's search box: case-insensitive substring match against a
 *  task's own text, same as agenda.ts's applyFilters. An empty (or
 *  whitespace-only) query matches everything, the same default an
 *  unfilled search field already has. */
fun matchesQuery(text: String, query: String): Boolean {
    val trimmed = query.trim()
    if (trimmed.isEmpty()) return true
    return text.contains(trimmed, ignoreCase = true)
}

/** The header's Overdue/Today/This week pills -- mirrors agenda.ts's
 *  SCOPES. "Open" (everything) is simply `scope == null`, not a fourth
 *  member, the same way the web's own scope filter has no explicit
 *  "all" value either. */
enum class AgendaScope { OVERDUE, TODAY, WEEK }

/**
 * Area, tag, search and scope combined with AND, mirroring agenda.ts's
 * applyFilters -- a null area/tag/scope means that dimension is inactive.
 *
 * [today] is only read when [scope] is non-null; the default is never
 * dereferenced otherwise, so a caller filtering without a scope never has
 * to supply a real date.
 */
fun filterTasks(
    tasks: List<AgendaTaskEntry>,
    areaId: Int?,
    tag: String?,
    query: String,
    scope: AgendaScope? = null,
    today: String = "",
): List<AgendaTaskEntry> = tasks.filter { task ->
    (areaId == null || task.areaId == areaId) &&
        (tag == null || task.tags.contains(tag)) &&
        matchesQuery(task.text, query) &&
        (scope == null || matchesScope(task.dueDate, today, scope))
}

/** The day after [today] -- the plainest of agenda.ts's snoozePresets. */
fun tomorrow(today: String): String = LocalDate.parse(today).plusDays(1).toString()

/**
 * The Monday after [today], never today itself -- the other snooze preset
 * this slice offers, trimmed from agenda.ts's fuller snoozePresets ("this
 * weekend" is left for a later pass).
 */
fun nextMonday(today: String): String {
    val date = LocalDate.parse(today)
    val daysUntilMonday = (DayOfWeek.MONDAY.value - date.dayOfWeek.value + 7) % 7
    val ahead = if (daysUntilMonday == 0) 7L else daysUntilMonday.toLong()
    return date.plusDays(ahead).toString()
}

private fun matchesScope(dueDate: String?, today: String, scope: AgendaScope): Boolean {
    val bucket = bucketFor(dueDate, today)
    // WEEK is cumulative -- overdue and today are inside "this week" too,
    // the same reason agenda.ts's own summaryCounts comment gives.
    return when (scope) {
        AgendaScope.OVERDUE -> bucket == AgendaBucket.OVERDUE
        AgendaScope.TODAY -> bucket == AgendaBucket.TODAY
        AgendaScope.WEEK -> bucket == AgendaBucket.OVERDUE ||
            bucket == AgendaBucket.TODAY ||
            bucket == AgendaBucket.WEEK
    }
}
