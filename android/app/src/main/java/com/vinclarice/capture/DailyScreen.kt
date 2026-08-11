package com.vinclarice.capture

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/**
 * The Daily Page, read-only -- slice 1 of android-full-client-plan.md.
 *
 * Same section order as the web's DayRoute.tsx: compass, focus, action
 * items, routines, paused routines, then what was written. No pin/unpin, no
 * routine logging, no editing the day's own text -- those are named as
 * deliberately deferred in the plan, and a row with nothing to do simply
 * shows what is true rather than a disabled or placeholder control.
 */
@Composable
fun DailyScreen(
    model: DailyViewModel,
    onOpenSettings: () -> Unit = {},
) {
    val state by model.state.collectAsState()
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { model.load() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = onOpenSettings) { Text("Settings") }
        }

        val day = state.day
        when {
            state.loading -> CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)

            day != null -> DailyContent(day)

            state.message != null -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    state.message!!,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (state.isError) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
                TextButton(onClick = { scope.launch { model.load() } }) { Text("Try again") }
            }

            // No token, no message -- Blank, not a failure. Settings already
            // says "Not connected."; repeating it here in red would make a
            // normal, expected state look like something broke.
            else -> Text(
                "Connect an account in Settings to see today.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun DailyContent(day: DayEntry) {
    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                (if (day.isToday) "Today" else "Your day").uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
            Text(longDate(day.date), style = MaterialTheme.typography.headlineSmall)
        }

        if (day.compassPurpose.isNotBlank() || day.compassQuestion.isNotBlank()) {
            CompassCard(day)
        }

        Section(title = "Focus") {
            if (day.focus.isEmpty()) {
                EmptyHint("Nothing pinned yet. Choose from your action items below to plan the day.")
            } else {
                day.focus.forEach { FocusRow(it, day.today) }
            }
        }

        Section(title = "Action items") {
            if (!day.showsActionItems) {
                EmptyHint("Only today shows action items. What you wrote on this day is below.")
            } else if (day.actionItems.isEmpty()) {
                EmptyHint("Nothing due today. Anything you add with today's date shows up here.")
            } else {
                val areasById = day.areas.associateBy { it.id }
                val projectsById = day.projects.associateBy { it.id }
                day.actionItems.forEach { ActionItemRow(it, day.today, areasById, projectsById) }
            }
        }

        Section(title = "Routines") {
            if (day.routines.isEmpty()) {
                EmptyHint(
                    "No routines yet. A routine is practice you repeat — five lessons a " +
                        "day, three sessions a week — rather than a task you finish once.",
                )
            } else {
                day.routines.forEach { RoutineRow(it) }
            }
            if (!day.routinesAreLoggable && day.routines.isNotEmpty()) {
                EmptyHint("What this day's routines came to. Logging happens on today.")
            }
            if (day.pausedRoutines.isNotEmpty()) {
                Text(
                    "Paused",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                day.pausedRoutines.forEach { PausedRoutineRow(it) }
            }
        }

        WrittenSection(day)
    }
}

@Composable
private fun CompassCard(day: DayEntry) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(BorderStroke(1.dp, MaterialTheme.colorScheme.outline), MaterialTheme.shapes.medium)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        if (day.compassPurpose.isNotBlank()) {
            Text(day.compassPurpose, style = MaterialTheme.typography.bodyMedium)
        }
        if (day.compassQuestion.isNotBlank()) {
            Text(
                day.compassQuestion,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun Section(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
        content()
    }
}

@Composable
private fun EmptyHint(text: String) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

/** The shared bordered-row shape every read-only line in this screen uses --
 *  same visual grammar DayRoute.tsx's own rows have, ported to Compose. */
@Composable
private fun DailyRow(content: @Composable RowScope.() -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(BorderStroke(1.dp, MaterialTheme.colorScheme.outline), MaterialTheme.shapes.medium)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) { content() }
}

@Composable
private fun FocusRow(focus: FocusEntry, today: String) {
    DailyRow {
        Text(
            focus.text,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            textDecoration = if (focus.status == "completed") TextDecoration.LineThrough else null,
        )
        focus.dueDate?.let {
            Text(
                dueLabel(it, today),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ActionItemRow(
    item: ActionItemEntry,
    today: String,
    areasById: Map<Int, AreaSummaryEntry>,
    projectsById: Map<Int, ProjectSummaryEntry>,
) {
    DailyRow {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(item.text, style = MaterialTheme.typography.bodyMedium)
            val area = areasById[item.areaId]
            val project = item.projectId?.let { projectsById[it] }
            if (area != null || project != null) {
                Text(
                    listOfNotNull(area?.title, project?.title).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            ageLabel(item.ageInDays)?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            item.dueDate?.let {
                Text(
                    dueLabel(it, today),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun RoutineRow(standing: StandingEntry) {
    DailyRow {
        Text(
            standing.title,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            textDecoration = if (standing.isMet) TextDecoration.LineThrough else null,
        )
        Text(
            standingLabel(standing),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PausedRoutineRow(routine: PausedRoutineEntry) {
    DailyRow {
        Text(
            routine.title,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun WrittenSection(day: DayEntry) {
    val sections = listOf(
        "Intentions" to day.intentions,
        "Grateful for" to day.gratitude,
        "Happenings" to day.happenings,
    ).filter { it.second.isNotBlank() }

    if (sections.isEmpty()) return

    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        HorizontalDivider()
        sections.forEach { (label, text) ->
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                Text(text, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}
