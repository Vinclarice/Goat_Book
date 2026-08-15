package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
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
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/**
 * Settings: the account this phone is connected to, and the way out.
 *
 * Deliberately not a place to change anything except that. Bittern scopes
 * this client to capture, so preferences, triage and account editing all
 * stay on the web.
 *
 * It is also the only place a stalled capture is visible. A stalled item
 * stops counting as pending, so without this screen it would vanish from
 * the Capture count and, as far as its owner could tell, from existence.
 */
@Composable
fun SettingsScreen(
    model: SettingsViewModel,
    onBack: () -> Unit = {},
    onDisconnected: () -> Unit = {},
    /** Open a login for Clarice. Only reachable on a split install. */
    onReconnectWorkspace: () -> Unit = {},
) {
    val state by model.state.collectAsState()
    val scope = rememberCoroutineScope()
    val onRetry: (String) -> Unit = { key -> scope.launch { model.retry(key) } }
    val onEnterSendsChange: (Boolean) -> Unit = model::setEnterSends
    var confirmingDisconnect by remember { mutableStateOf(false) }

    // Asked on open, every open. The question this screen answers is whether
    // the connection still works, and only the server knows that.
    LaunchedEffect(Unit) { model.load() }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Settings", style = MaterialTheme.typography.headlineSmall)

        val identity = state.identity
        when {
            state.loading -> CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)

            identity != null -> {
                Text(
                    "Connected as ${identity.username}",
                    style = MaterialTheme.typography.bodyLarge,
                )
                Text(
                    identity.email,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            !state.connected -> Text(
                "Not connected.",
                style = MaterialTheme.typography.bodyLarge,
            )
        }

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

        // Only on a split install, where captures and tasks live on different
        // servers. Null means there is one connection and the block above is
        // all of it -- drawing a second heading over the same account would
        // invite someone to disconnect what they took for a spare.
        state.workspace?.let { workspace ->
            HorizontalDivider()
            Text("Tasks and today", style = MaterialTheme.typography.titleMedium)
            Text(
                "Captures go to your second mind. Today and Agenda read Clarice, " +
                    "which is the only one that has tasks.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            val workspaceIdentity = workspace.identity
            when {
                workspace.loading ->
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)

                workspaceIdentity != null -> Text(
                    "Connected as ${workspaceIdentity.username}",
                    style = MaterialTheme.typography.bodyLarge,
                )

                !workspace.connected -> Text(
                    "Not connected. Today and Agenda will not load.",
                    style = MaterialTheme.typography.bodyLarge,
                )
            }

            workspace.message?.let { message ->
                Text(
                    message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (workspace.isError) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
            }

            if (workspace.connected) {
                TextButton(onClick = { model.disconnectWorkspace() }) {
                    Text("Disconnect from tasks")
                }
            } else {
                // Deliberately not a confirmation dialog, unlike the capture
                // disconnect below: nothing is lost here. The queue is not
                // involved, and reconnecting is a login away.
                TextButton(onClick = onReconnectWorkspace) {
                    Text("Connect to tasks")
                }
            }
        }

        HorizontalDivider()

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Enter key sends", style = MaterialTheme.typography.bodyLarge)
                Text(
                    // Says what is given up, not just what is gained. A
                    // switch whose cost is invisible is a switch people flip
                    // and then wonder what broke.
                    if (state.enterSends) {
                        "One tap to capture. The keyboard has no newline key."
                    } else {
                        "Enter starts a new line. Capture with the button."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(
                checked = state.enterSends,
                onCheckedChange = onEnterSendsChange,
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Require unlock to open", style = MaterialTheme.typography.bodyLarge)
                Text(
                    // The stored token itself never expires either way --
                    // this is only about what it costs to see what is
                    // behind it. design/android-unlock-plan.md.
                    if (state.requireUnlock) {
                        "Opening the app asks for your phone's own unlock first."
                    } else {
                        "Opening the app goes straight to Capture."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(
                checked = state.requireUnlock,
                onCheckedChange = model::setRequireUnlock,
            )
        }

        QueueSection(state = state, onRetry = onRetry, serverName = model.serverName)

        if (state.connected) {
            OutlinedButton(
                onClick = { confirmingDisconnect = true },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Disconnect this phone")
            }
            Text(
                "Forgets the token on this device. Revoke it on the web too " +
                    "if the phone itself is what you have lost.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (confirmingDisconnect) {
                AlertDialog(
                    onDismissRequest = { confirmingDisconnect = false },
                    title = { Text("Disconnect this phone?") },
                    text = {
                        Text(
                            "You'll need to log in again to capture from here. " +
                                "Anything already waiting to send stays queued.",
                        )
                    },
                    confirmButton = {
                        TextButton(onClick = { model.disconnect(); onDisconnected() }) {
                            Text("Disconnect")
                        }
                    },
                    dismissButton = {
                        TextButton(onClick = { confirmingDisconnect = false }) {
                            Text("Cancel")
                        }
                    },
                )
            }
        }

        TextButton(onClick = onBack) { Text("Back to capture") }
    }
}

/**
 * What is unsent, and what has stopped trying.
 *
 * The two are drawn differently on purpose. A capture waiting for a network
 * needs nothing from anybody and says so in one quiet line; a capture that
 * has given up needs a decision, so it shows its own text and a button.
 * Collapsing them into one "problem" count would tell somebody there is a
 * problem without telling them what to do about it.
 */
@Composable
private fun QueueSection(
    state: SettingsUiState,
    onRetry: (String) -> Unit,
    /** Named rather than assumed: on a split install the queue faces
     *  Second Mind, and a rejection is that server's judgement. */
    serverName: String,
) {
    if (state.waiting == 0 && state.needsAttention.isEmpty()) return

    HorizontalDivider()

    if (state.waiting > 0) {
        Text(
            if (state.waiting == 1) {
                "1 capture waiting to send."
            } else {
                "${state.waiting} captures waiting to send."
            },
            style = MaterialTheme.typography.bodyMedium,
        )
    }

    state.needsAttention.forEach { item ->
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                // The text itself, because "a capture" is not enough to
                // decide anything about. Truncated rather than wrapped so
                // one long thought cannot push the button off screen.
                item.text.lineSequence().first().take(80),
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                when (item.state) {
                    QueueState.REJECTED ->
                        "$serverName would not accept this. Retrying it unchanged will fail again."
                    // Says what happened rather than naming a state. "Stalled"
                    // means nothing to somebody who did not write the queue.
                    else -> "Stopped after ${item.attempts} attempts."
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
            TextButton(onClick = { onRetry(item.key) }) { Text("Try again") }
        }
    }
}
