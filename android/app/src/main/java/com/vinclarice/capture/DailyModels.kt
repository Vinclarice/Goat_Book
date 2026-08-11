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
    val intentions: String,
    val gratitude: String,
    val happenings: String,
    val compassPurpose: String,
    val compassQuestion: String,
    val focus: List<FocusEntry>,
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
)

data class ActionItemEntry(
    val id: Int,
    val text: String,
    val dueDate: String?,
    val ageInDays: Int,
    val areaId: Int,
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
