package com.vinclarice.capture

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * The Agenda, read and acted on -- slice 2 of android-full-client-plan.md.
 * Same section order as the web's AgendaWorkspace: scope pills, search,
 * area/tag filters, quick-add, the bucketed list, then what's completed
 * today. Editing text/tags/notes/recurrence, deleting, and reordering stay
 * off this screen entirely -- they're not things AgendaWorkspace itself
 * does either; see the plan's §7 for the exact boundary.
 */
@Composable
fun AgendaScreen(
    model: AgendaViewModel,
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

        val agenda = state.agenda
        when {
            state.loading -> CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)

            agenda != null -> AgendaContent(state = state, agenda = agenda, model = model, scope = scope)

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

            else -> Text(
                "Connect an account in Settings to see your agenda.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private val BUCKET_LABELS = listOf(
    AgendaBucket.OVERDUE to "Overdue",
    AgendaBucket.TODAY to "Today",
    AgendaBucket.WEEK to "This week",
    AgendaBucket.LATER to "Later",
    AgendaBucket.SOMEDAY to "Someday",
)

@Composable
private fun AgendaContent(
    state: AgendaUiState,
    agenda: AgendaEntry,
    model: AgendaViewModel,
    scope: CoroutineScope,
) {
    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                "AGENDA",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
            Text(longDate(agenda.today), style = MaterialTheme.typography.headlineSmall)
        }

        // A failed write's message, shown without ever blanking the list
        // underneath it -- see AgendaViewModel.write()'s own reasoning.
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

        ScopePills(
            items = agenda.items,
            today = agenda.today,
            selected = state.scopeFilter,
            onSelect = model::setScopeFilter,
        )

        OutlinedTextField(
            value = state.query,
            onValueChange = model::setQuery,
            placeholder = { Text("Search") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            modifier = Modifier.fillMaxWidth(),
        )

        FilterChips(
            agenda = agenda,
            areaFilter = state.areaFilter,
            tagFilter = state.tagFilter,
            onAreaSelect = model::setAreaFilter,
            onTagSelect = model::setTagFilter,
        )

        if (agenda.areas.isNotEmpty()) {
            QuickAdd(
                areas = agenda.areas,
                targetAreaId = state.areaFilter,
                busy = state.busy,
                onAdd = { area, text -> scope.launch { model.quickAdd(area, text, null) } },
            )
        }

        val filtered = filterTasks(
            agenda.items,
            areaId = state.areaFilter,
            tag = state.tagFilter,
            query = state.query,
            scope = state.scopeFilter,
            today = agenda.today,
        )
        val areasById = agenda.areas.associateBy { it.id }
        val projectsById = agenda.projects.associateBy { it.id }

        if (filtered.isEmpty()) {
            EmptyHint("Nothing matches. Clear a filter, or add something new above.")
        } else {
            BUCKET_LABELS.forEach { (bucket, label) ->
                val inBucket = filtered.filter { bucketFor(it.dueDate, agenda.today) == bucket }
                if (inBucket.isNotEmpty()) {
                    Section(label) {
                        inBucket.forEach { task ->
                            TaskRow(
                                task = task,
                                today = agenda.today,
                                area = areasById[task.areaId],
                                project = task.projectId?.let { projectsById[it] },
                                busy = state.busy,
                                onComplete = { scope.launch { model.completeTask(task) } },
                                onReschedule = { date -> scope.launch { model.reschedule(task, date) } },
                            )
                        }
                    }
                }
            }
        }

        if (agenda.completedToday.isNotEmpty()) {
            Section("Completed today") {
                agenda.completedToday.forEach { task ->
                    CompletedRow(
                        task = task,
                        busy = state.busy,
                        onReopen = { scope.launch { model.reopenTask(task) } },
                    )
                }
            }
        }
    }
}

@Composable
private fun ScopePills(
    items: List<AgendaTaskEntry>,
    today: String,
    selected: AgendaScope?,
    onSelect: (AgendaScope) -> Unit,
) {
    val overdue = items.count { bucketFor(it.dueDate, today) == AgendaBucket.OVERDUE }
    val dueToday = items.count { bucketFor(it.dueDate, today) == AgendaBucket.TODAY }
    val dueWeek = items.count {
        val bucket = bucketFor(it.dueDate, today)
        bucket == AgendaBucket.OVERDUE || bucket == AgendaBucket.TODAY || bucket == AgendaBucket.WEEK
    }

    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Pill("Overdue ($overdue)", selected == AgendaScope.OVERDUE) { onSelect(AgendaScope.OVERDUE) }
        Pill("Today ($dueToday)", selected == AgendaScope.TODAY) { onSelect(AgendaScope.TODAY) }
        Pill("This week ($dueWeek)", selected == AgendaScope.WEEK) { onSelect(AgendaScope.WEEK) }
        Pill("Open (${items.size})", selected == null) { /* "Open" is the un-set state; nothing to toggle. */ }
    }
}

@Composable
private fun FilterChips(
    agenda: AgendaEntry,
    areaFilter: Int?,
    tagFilter: String?,
    onAreaSelect: (Int) -> Unit,
    onTagSelect: (String) -> Unit,
) {
    val tags = remember(agenda.items) { agenda.items.flatMap { it.tags }.distinct().sorted() }
    if (agenda.areas.isEmpty() && tags.isEmpty()) return

    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        agenda.areas.forEach { area ->
            Pill(
                "${area.title} (${area.openCount})",
                selected = areaFilter == area.id,
            ) { onAreaSelect(area.id) }
        }
        tags.forEach { tag ->
            Pill(tag, selected = tagFilter == tag) { onTagSelect(tag) }
        }
    }
}

@Composable
private fun Pill(label: String, selected: Boolean, onClick: () -> Unit) {
    Text(
        label,
        style = MaterialTheme.typography.bodySmall,
        color = if (selected) {
            MaterialTheme.colorScheme.onPrimary
        } else {
            MaterialTheme.colorScheme.onSurfaceVariant
        },
        modifier = Modifier
            .border(
                BorderStroke(
                    1.dp,
                    if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline,
                ),
                MaterialTheme.shapes.extraLarge,
            )
            .let {
                if (selected) it.background(MaterialTheme.colorScheme.primary, MaterialTheme.shapes.extraLarge) else it
            }
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    )
}

@Composable
private fun QuickAdd(
    areas: List<AgendaAreaEntry>,
    targetAreaId: Int?,
    busy: Boolean,
    onAdd: (AgendaAreaEntry, String) -> Unit,
) {
    var text by remember { mutableStateOf("") }
    val target = areas.firstOrNull { it.id == targetAreaId } ?: areas.first()

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                placeholder = { Text("Add a task") },
                singleLine = true,
                enabled = !busy,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = {
                    if (text.isNotBlank()) { onAdd(target, text); text = "" }
                }),
                modifier = Modifier.weight(1f),
            )
            TextButton(
                enabled = !busy && text.isNotBlank(),
                onClick = { onAdd(target, text); text = "" },
            ) { Text("Add") }
        }
        Text(
            "Goes into ${target.title}.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
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

@Composable
private fun AgendaRow(content: @Composable RowScope.() -> Unit) {
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
private fun TaskRow(
    task: AgendaTaskEntry,
    today: String,
    area: AgendaAreaEntry?,
    project: AgendaProjectEntry?,
    busy: Boolean,
    onComplete: () -> Unit,
    onReschedule: (String?) -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }

    AgendaRow {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(task.text, style = MaterialTheme.typography.bodyMedium)
            if (area != null || project != null) {
                Text(
                    listOfNotNull(area?.title, project?.title).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(2.dp)) {
            task.dueDate?.let {
                Text(
                    dueLabel(it, today),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(0.dp), verticalAlignment = Alignment.CenterVertically) {
                Box {
                    TextButton(enabled = !busy, onClick = { menuOpen = true }) { Text("Reschedule") }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        DropdownMenuItem(
                            text = { Text("Tomorrow") },
                            onClick = { menuOpen = false; onReschedule(tomorrow(today)) },
                        )
                        DropdownMenuItem(
                            text = { Text("Next Monday") },
                            onClick = { menuOpen = false; onReschedule(nextMonday(today)) },
                        )
                        DropdownMenuItem(
                            text = { Text("Clear due date") },
                            onClick = { menuOpen = false; onReschedule(null) },
                        )
                    }
                }
                TextButton(enabled = !busy, onClick = onComplete) { Text("Done") }
            }
        }
    }
}

@Composable
private fun CompletedRow(task: AgendaTaskEntry, busy: Boolean, onReopen: () -> Unit) {
    AgendaRow {
        Text(
            task.text,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            textDecoration = TextDecoration.LineThrough,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        TextButton(enabled = !busy, onClick = onReopen) { Text("Reopen") }
    }
}
