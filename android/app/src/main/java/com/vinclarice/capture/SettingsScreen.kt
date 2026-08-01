package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
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
) {
    val state by model.state.collectAsState()
    val scope = rememberCoroutineScope()
    val onRetry: (String) -> Unit = { key -> scope.launch { model.retry(key) } }

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
            state.loading -> CircularProgressIndicator()

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

        QueueSection(state = state, onRetry = onRetry)

        if (state.connected) {
            OutlinedButton(
                onClick = { model.disconnect(); onDisconnected() },
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
private fun QueueSection(state: SettingsUiState, onRetry: (String) -> Unit) {
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
                        "Clarice would not accept this. Retrying it unchanged will fail again."
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
