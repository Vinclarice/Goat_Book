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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * The Daily Page, read and now acted on. Slice 1 was read-only; this
 * extends it to what DayRoute.tsx itself does -- choose today's focus,
 * log/skip/pause/resume/call-it-enough a routine and keep new ones, and
 * save the day's own Intentions/Grateful for/Happenings. The quick-capture
 * box stays off this screen: Capture is one tab away already, the same
 * reasoning DayRoute.tsx's own comment gives for not duplicating it.
 * Editing a past day and a date picker are still out of scope -- nothing
 * here reaches a day other than today.
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

            day != null -> DailyContent(state = state, day = day, model = model, scope = scope)

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
private fun DailyContent(state: DailyUiState, day: DayEntry, model: DailyViewModel, scope: CoroutineScope) {
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

        // A failed write's message, shown without ever blanking the page
        // underneath it -- see DailyViewModel.write()'s own reasoning.
        state.message?.let { message ->
            Text(
                message,
                style = MaterialTheme.typography.bodySmall,
                color = if (state.isError) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }

        val pinnedIds = remember(day.focus) { day.focus.mapNotNull { it.taskId }.toSet() }

        Section(title = "Focus") {
            if (day.focus.isEmpty()) {
                EmptyHint("Nothing pinned yet. Choose from your action items below to plan the day.")
            } else {
                day.focus.forEach { focus ->
                    FocusRow(
                        focus = focus,
                        today = day.today,
                        busy = state.busy,
                        onUnpin = { taskId -> scope.launch { model.unpinTask(taskId) } },
                    )
                }
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
                day.actionItems.forEach { item ->
                    ActionItemRow(
                        item = item,
                        today = day.today,
                        areasById = areasById,
                        projectsById = projectsById,
                        pinned = item.id in pinnedIds,
                        busy = state.busy,
                        onPin = { scope.launch { model.pinTask(item.id) } },
                        onUnpin = { scope.launch { model.unpinTask(item.id) } },
                    )
                }
            }
        }

        Section(title = "Routines") {
            if (day.routines.isEmpty()) {
                EmptyHint(
                    "No routines yet. A routine is practice you repeat — five lessons a " +
                        "day, three sessions a week — rather than a task you finish once.",
                )
            } else {
                day.routines.forEach { standing ->
                    RoutineRow(
                        standing = standing,
                        loggable = day.routinesAreLoggable,
                        busy = state.busy,
                        onLog = { amount -> scope.launch { model.logRoutine(standing.routineId, amount) } },
                        onSkip = { scope.launch { model.skipRoutine(standing.routineId) } },
                        onEnough = { scope.launch { model.callRoutineEnough(standing.routineId) } },
                        onPause = { scope.launch { model.pauseRoutine(standing.routineId) } },
                    )
                }
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
                day.pausedRoutines.forEach { routine ->
                    PausedRoutineRow(
                        routine = routine,
                        loggable = day.routinesAreLoggable,
                        busy = state.busy,
                        onResume = { scope.launch { model.resumeRoutine(routine.routineId) } },
                    )
                }
            }
            if (day.routinesAreLoggable) {
                AddRoutine(
                    busy = state.busy,
                    onCreate = { title, cadence, target, unit ->
                        scope.launch { model.createRoutine(title, cadence, target, unit) }
                    },
                )
            }
        }

        WrittenSection(
            state = state,
            onIntentionsChange = model::setDraftIntentions,
            onGratitudeChange = model::setDraftGratitude,
            onHappeningsChange = model::setDraftHappenings,
            onSave = { scope.launch { model.saveDayText() } },
        )
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

/** The border/shape/padding every card and row in this screen shares --
 *  same visual grammar DayRoute.tsx's own rows have, ported to Compose. */
@Composable
private fun cardModifier(): Modifier = Modifier
    .fillMaxWidth()
    .border(BorderStroke(1.dp, MaterialTheme.colorScheme.outline), MaterialTheme.shapes.medium)
    .padding(horizontal = 12.dp, vertical = 10.dp)

@Composable
private fun DailyRow(content: @Composable RowScope.() -> Unit) {
    Row(
        modifier = cardModifier(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) { content() }
}

@Composable
private fun FocusRow(focus: FocusEntry, today: String, busy: Boolean, onUnpin: (Int) -> Unit) {
    DailyRow {
        Text(
            focus.text,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            textDecoration = if (focus.status == "completed") TextDecoration.LineThrough else null,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
            focus.dueDate?.let {
                Text(
                    dueLabel(it, today),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            // A deleted task leaves the record but nothing to unpin.
            if (focus.taskId != null) {
                TextButton(enabled = !busy, onClick = { onUnpin(focus.taskId) }) { Text("Unpin") }
            }
        }
    }
}

@Composable
private fun ActionItemRow(
    item: ActionItemEntry,
    today: String,
    areasById: Map<Int, AreaSummaryEntry>,
    projectsById: Map<Int, ProjectSummaryEntry>,
    pinned: Boolean,
    busy: Boolean,
    onPin: () -> Unit,
    onUnpin: () -> Unit,
) {
    DailyRow {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Weighted and truncating rather than both Texts sizing to
                // their own content: an unweighted long title left "Pinned"
                // as little as a few px of a narrow row, wrapping it letter
                // by letter instead of ever shrinking the title beside it.
                Text(
                    item.text,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                // Stays in the list below rather than being carved out of it --
                // this row says which it is rather than leaving two
                // identical-looking entries between here and Focus.
                if (pinned) {
                    Text(
                        "  Pinned",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                        maxLines = 1,
                        softWrap = false,
                    )
                }
            }
            val area = item.areaId?.let { areasById[it] }
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
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
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
            TextButton(
                enabled = !busy,
                onClick = if (pinned) onUnpin else onPin,
            ) { Text(if (pinned) "Unpin" else "Pin to today") }
        }
    }
}

@Composable
private fun RoutineRow(
    standing: StandingEntry,
    loggable: Boolean,
    busy: Boolean,
    onLog: (Int) -> Unit,
    onSkip: () -> Unit,
    onEnough: () -> Unit,
    onPause: () -> Unit,
) {
    Column(modifier = cardModifier(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
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
        if (loggable) {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                // Minus first and only when there is something to take back,
                // so the common action is not the one you have to aim past.
                if (standing.progress > 0) {
                    TextButton(enabled = !busy, onClick = { onLog(-1) }) { Text("−1") }
                }
                TextButton(enabled = !busy, onClick = { onLog(1) }) { Text("+1") }
                if (standing.progress > 0 && !standing.isMet && standing.outcome != "partial") {
                    TextButton(enabled = !busy, onClick = onEnough) { Text("Enough") }
                }
                if (standing.outcome != "skipped") {
                    TextButton(enabled = !busy, onClick = onSkip) { Text("Skip") }
                }
                TextButton(enabled = !busy, onClick = onPause) { Text("Pause") }
            }
        }
    }
}

@Composable
private fun PausedRoutineRow(
    routine: PausedRoutineEntry,
    loggable: Boolean,
    busy: Boolean,
    onResume: () -> Unit,
) {
    DailyRow {
        Text(
            routine.title,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (loggable) {
            TextButton(enabled = !busy, onClick = onResume) { Text("Resume") }
        }
    }
}

/**
 * Keeping a new routine -- folded away by default, the same reasoning
 * DayRoute.tsx's own AddRoutine gives: keeping one is rare next to logging
 * one, and four fields permanently open would make the day look like a
 * form.
 */
@Composable
private fun AddRoutine(busy: Boolean, onCreate: (String, String, Int, String) -> Unit) {
    var open by remember { mutableStateOf(false) }

    if (!open) {
        TextButton(onClick = { open = true }) { Text("Keep a routine") }
        return
    }

    var title by remember { mutableStateOf("") }
    var cadence by remember { mutableStateOf("daily") }
    var target by remember { mutableStateOf("1") }
    var unit by remember { mutableStateOf("") }

    Column(modifier = cardModifier(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(
            value = title,
            onValueChange = { title = it },
            placeholder = { Text("Routine") },
            singleLine = true,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            CadenceChoice("Every day", selected = cadence == "daily") { cadence = "daily" }
            CadenceChoice("Every week", selected = cadence == "weekly") { cadence = "weekly" }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = target,
                onValueChange = { new -> target = new.filter { it.isDigit() } },
                placeholder = { Text("How many") },
                singleLine = true,
                enabled = !busy,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.weight(1f),
            )
            OutlinedTextField(
                value = unit,
                onValueChange = { unit = it },
                placeholder = { Text("Of what") },
                singleLine = true,
                enabled = !busy,
                modifier = Modifier.weight(1f),
            )
        }
        Text(
            "Leave \"Of what\" empty for a plain yes-or-no, like moving today.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(
                enabled = !busy && title.isNotBlank(),
                onClick = {
                    onCreate(title, cadence, target.toIntOrNull()?.coerceAtLeast(1) ?: 1, unit)
                    title = ""
                    unit = ""
                    target = "1"
                    open = false
                },
            ) { Text("Keep it") }
            TextButton(onClick = { open = false }) { Text("Cancel") }
        }
    }
}

@Composable
private fun CadenceChoice(label: String, selected: Boolean, onClick: () -> Unit) {
    TextButton(onClick = onClick) {
        Text(
            label,
            color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
        )
    }
}

@Composable
private fun WrittenSection(
    state: DailyUiState,
    onIntentionsChange: (String) -> Unit,
    onGratitudeChange: (String) -> Unit,
    onHappeningsChange: (String) -> Unit,
    onSave: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        HorizontalDivider()
        WrittenField(
            "Intentions",
            "Outcomes or ways of showing up. Not always tasks.",
            state.draftIntentions,
            onIntentionsChange,
            state.busy,
        )
        WrittenField(
            "Grateful for",
            "Short, and for you rather than for the record.",
            state.draftGratitude,
            onGratitudeChange,
            state.busy,
        )
        WrittenField(
            "Happenings",
            "What actually occurred. This is what a later review reads.",
            state.draftHappenings,
            onHappeningsChange,
            state.busy,
        )
        TextButton(enabled = !state.busy, onClick = onSave) { Text("Save the day") }
    }
}

@Composable
private fun WrittenField(
    label: String,
    hint: String,
    value: String,
    onChange: (String) -> Unit,
    busy: Boolean,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
        OutlinedTextField(
            value = value,
            onValueChange = onChange,
            enabled = !busy,
            minLines = 2,
            modifier = Modifier.fillMaxWidth(),
        )
        Text(hint, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
