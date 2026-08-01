package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/**
 * The whole point of the app: open it, type, send, leave.
 *
 * The field takes focus on open so the keyboard is already up -- the plan
 * measures this app against opening a browser, and every tap saved is the
 * difference. All the decisions live in [CaptureViewModel]; this draws them.
 */
@Composable
fun CaptureScreen(
    model: CaptureViewModel,
    onOpenSettings: () -> Unit = {},
) {
    val state by model.state.collectAsState()
    val scope = rememberCoroutineScope()
    val focus = remember { FocusRequester() }

    LaunchedEffect(Unit) {
        focus.requestFocus()
        // What is already queued from a previous session, so a restart does
        // not look like an empty queue.
        model.refresh()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // A plain text button rather than an app bar: an app bar would take
        // a band of height off the field on every screen for one action.
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Visible rather than silent. A queue nobody can see is
            // indistinguishable from a capture that went missing.
            Text(
                if (state.pending > 0) "${state.pending} waiting to send" else "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TextButton(onClick = onOpenSettings) { Text("Settings") }
        }

        OutlinedTextField(
            value = state.text,
            onValueChange = model::onTextChange,
            placeholder = { Text("What's on your mind?") },
            enabled = !state.sending,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .focusRequester(focus)
                .semantics { contentDescription = "Capture text" },
        )

        state.message?.let { message ->
            Text(
                message,
                style = MaterialTheme.typography.bodyMedium,
                color = if (state.isError) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }

        Button(
            onClick = { scope.launch { model.submit() } },
            enabled = !state.sending && state.text.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (state.sending) "Sending…" else "Capture")
        }
    }
}
