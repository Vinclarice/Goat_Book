package com.vinclarice.capture

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
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
 * Every open line, in one list — android-overhaul-plan.md increment 3.
 *
 * This is what replaced the Agenda, and the difference is the point: the
 * Agenda was buckets you filed into, and the pool is everything still open
 * with nowhere to put it. The one act here is picking something for today.
 *
 * Two lists, mirroring the server and the website: **fixed** things have a
 * date and arrive in date order with bills and appointments among the tasks,
 * and **floating** things are the lines nothing was promised about.
 * Interleaving them here would mean this client deciding what a date means.
 */
@Composable
fun PoolSection(model: PoolViewModel) {
    val state by model.state.collectAsState()
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { model.load() }

    /* A section, not a screen -- see [CaptureSection].

       **The full-screen spinner went with the tab.** A section that took over
       the whole page while it loaded would blank the day above it, which is
       the rule every view model here already follows for writes: a slow
       network must not blank something somebody is reading. It says one line
       instead. */
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        val pool = state.pool

        Text("The pool", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)

        if (state.loading && pool == null) {
            Text(
                "Looking…",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (pool != null) {
            // `open_count` is the whole pool before any narrowing, which is
            // what lets this say how many there really are.
            Text(
                if (pool.openCount == 1) "1 open line" else "${pool.openCount} open lines",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        // A failed write's message, shown without ever blanking the list
        // underneath it -- PoolViewModel.pick()'s own reasoning.
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

        if (pool == null) return@Column

        if (pool.fixed.isEmpty() && pool.floating.isEmpty()) {
            Text(
                "Nothing open. Everything you have written is done or let go.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (pool.fixed.isNotEmpty()) {
            PoolGroup(title = "Dated") {
                pool.fixed.forEach { row ->
                    FixedRow(
                        row = row,
                        busy = state.busy,
                        onPick = { id -> scope.launch { model.pick(id) } },
                    )
                }
            }
        }

        if (pool.floating.isNotEmpty()) {
            PoolGroup(title = "Everything else") {
                pool.floating.forEach { row ->
                    FloatingRow(
                        row = row,
                        busy = state.busy,
                        onPick = { id -> scope.launch { model.pick(id) } },
                    )
                }
            }
        }
    }
}

@Composable
private fun PoolGroup(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
        content()
    }
}

@Composable
private fun FixedRow(row: PoolFixedRow, busy: Boolean, onPick: (Int) -> Unit) {
    Column(modifier = poolCardModifier(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            row.task?.text ?: row.bill?.text ?: row.appointment?.text.orEmpty(),
            style = MaterialTheme.typography.bodyMedium,
            // A cancelled appointment stays visible and struck -- rule 6.
            textDecoration =
                if (row.appointment?.cancelled == true) TextDecoration.LineThrough else null,
        )
        Text(
            "${row.kind.replaceFirstChar { it.uppercase() }} · ${whenLabel(row.daysUntil, row.dueDate)}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        // Only a task can be chosen for a day. A bill and an appointment
        // happen whether or not you pick them, which is what "fixed" means.
        row.task?.let { task -> PickControl(task.id, row.pickedFor, busy, onPick) }
    }
}

@Composable
private fun FloatingRow(row: PoolFloatingRow, busy: Boolean, onPick: (Int) -> Unit) {
    Column(modifier = poolCardModifier(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(row.task.text, style = MaterialTheme.typography.bodyMedium)
        Text(
            ageLabel(row.ageInDays) ?: "Written today",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (row.asksToBeKept) {
            /* Rule 8, and **the server decides**: this shows the question, it
               does not work out when to ask it. Answering stays on the website
               until there is a reason to widen a bearer to it -- letting go of
               a task is a different decision from reading the list. */
            Text(
                "Untouched for ${row.unpickedForDays} days. Still wanted?",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
        PickControl(row.task.id, row.pickedFor, busy, onPick)
    }
}

/**
 * Pick, or say it is already picked.
 *
 * `picked_for` is what stops this looking like it did nothing when the same
 * line is tapped twice — the server sends which days it is already chosen for,
 * and this reads that rather than tracking its own idea of what it has done.
 */
@Composable
private fun PickControl(
    taskId: Int,
    pickedFor: List<String>,
    busy: Boolean,
    onPick: (Int) -> Unit,
) {
    if ("today" in pickedFor) {
        Text(
            "Chosen for today",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.primary,
        )
    } else {
        TextButton(enabled = !busy, onClick = { onPick(taskId) }) { Text("Pick for today") }
    }
}

/** `days_until` is computed by the server, because the account's zone decides
 *  what day it is and this device is not necessarily in it. */
private fun whenLabel(daysUntil: Int, dueDate: String): String = when {
    daysUntil == 0 -> "Today"
    daysUntil == 1 -> "Tomorrow"
    daysUntil < 0 -> "${-daysUntil} days ago"
    else -> "In $daysUntil days · $dueDate"
}

@Composable
private fun poolCardModifier(): Modifier = Modifier
    .fillMaxWidth()
    .border(BorderStroke(1.dp, MaterialTheme.colorScheme.outline), MaterialTheme.shapes.medium)
    .padding(horizontal = 12.dp, vertical = 10.dp)
