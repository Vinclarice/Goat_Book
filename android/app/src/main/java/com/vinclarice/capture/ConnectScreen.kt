package com.vinclarice.capture

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/**
 * Connect: paste a personal access token, check it, keep it.
 *
 * All the decisions live in [ConnectViewModel]; this only draws them, which
 * is why there is no logic here worth a UI test on a device.
 */
@Composable
fun ConnectScreen(
    model: ConnectViewModel,
    onConnected: () -> Unit = {},
) {
    val state by model.state.collectAsState()
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Connect to Clarice", style = MaterialTheme.typography.headlineSmall)

        Text(
            "Open Clarice on the web, go to Access tokens, and create one " +
                "labelled for this phone. Paste it below. It is shown only " +
                "once, so copy it before leaving that page.",
            style = MaterialTheme.typography.bodyMedium,
        )

        OutlinedTextField(
            value = state.token,
            onValueChange = model::onTokenChange,
            label = { Text("Access token") },
            singleLine = true,
            enabled = !state.checking,
            isError = state.error != null,
            // Not a password field: this is pasted rather than typed, and
            // masking it would stop someone checking they pasted the right
            // thing while it is still theirs to check. It is cleared the
            // moment it is stored.
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.None,
                autoCorrectEnabled = false,
            ),
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentDescription = "Access token" },
        )

        state.error?.let { message ->
            Text(
                message,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
        }

        state.connectedAs?.let { identity ->
            Text(
                "Connected as ${identity.username}.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        Button(
            onClick = { scope.launch { model.connect(); if (model.state.value.connectedAs != null) onConnected() } },
            enabled = !state.checking,
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (state.checking) {
                CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp))
            }
            Text(if (state.checking) "Checking…" else "Connect")
        }
    }
}
