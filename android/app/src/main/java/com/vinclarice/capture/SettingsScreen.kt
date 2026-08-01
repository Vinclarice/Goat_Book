package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * Settings: the account this phone is connected to, and the way out.
 *
 * Deliberately not a place to change anything except that. Bittern scopes
 * this client to capture, so preferences, triage and account editing all
 * stay on the web.
 *
 * The pending-queue state the plan asks for is not here yet, because there
 * is no queue until M3. Showing "nothing waiting" while the text field is
 * the only thing holding an unsent thought would be true and misleading at
 * the same time.
 */
@Composable
fun SettingsScreen(
    model: SettingsViewModel,
    onBack: () -> Unit = {},
    onDisconnected: () -> Unit = {},
) {
    val state by model.state.collectAsState()

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
